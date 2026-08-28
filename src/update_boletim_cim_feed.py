```python
#!/usr/bin/env python3

import hashlib
import html
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import requests


# ============================================================
# CONFIGURAÇÃO
# ============================================================

SOURCE_URL = "https://ordemfarmaceuticos.pt/pt/CIM/INDICE-DE-PUBLICACOES/"
FEED_TITLE = "Boletim do CIM — Ordem dos Farmacêuticos"
FEED_LINK = SOURCE_URL
FEED_DESCRIPTION = (
    "Novas publicações do Boletim do CIM da Ordem dos Farmacêuticos."
)
FEED_LANGUAGE = "pt-PT"
FEED_TTL = "1440"

OUTPUT_FILE = "boletim_cim.xml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; health-rss/1.0; "
        "+https://github.com/guga14/health-rss)"
    )
}

REQUEST_TIMEOUT = 30


# ============================================================
# PERÍODOS
# ============================================================

PERIOD_ORDER = {
    "Jan-Fev": 1,
    "Jan-Mar": 1,
    "Mar-Abr": 2,
    "Mai-Ago": 3,
    "Abr-Jun": 2,
    "Set-Out": 3,
    "Jul-Set": 3,
    "Out-Dez": 4,
    "Nov-Dez": 4,
}

# Datas representativas para pubDate.
# Não pretendemos afirmar que esta foi a data exata de publicação;
# servem para manter a ordenação cronológica do arquivo.
PERIOD_END_MONTH = {
    "Jan-Fev": (2, 28),
    "Jan-Mar": (3, 31),
    "Mar-Abr": (4, 30),
    "Mai-Ago": (8, 31),
    "Abr-Jun": (6, 30),
    "Set-Out": (10, 31),
    "Jul-Set": (9, 30),
    "Out-Dez": (12, 31),
    "Nov-Dez": (12, 31),
}


# ============================================================
# PARSER DA PÁGINA
# ============================================================

class CIMParser(HTMLParser):
    """
    Extrai:

        ano
        período
        título
        URL

    da secção BOLETIM DO CIM.

    A página da Ordem tem HTML bastante irregular e, por isso,
    não dependemos da profundidade dos <div>s nem de classes
    específicas.
    """

    YEAR_RE = re.compile(r"^\s*(20\d{2})\s*$")
    PERIOD_RE = re.compile(
        r"^\s*(Jan-Mar|Jan-Fev|Mar-Abr|Abr-Jun|Mai-Ago|"
        r"Jul-Set|Set-Out|Out-Dez|Nov-Dez)\s*\|?"
    )

    def __init__(self, source_url):
        super().__init__(convert_charrefs=True)

        self.source_url = source_url

        self.current_year = None
        self.current_period = None

        self.in_anchor = False
        self.anchor_href = None
        self.anchor_text = []

        self.items = []

        self.text_buffer = []

        # Mantemos uma pequena pilha/contexto para conseguirmos
        # identificar anos mesmo quando estão dentro de <table>.
        self.tag_stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self.tag_stack.append(tag)

        if tag == "a":
            attrs_dict = dict(attrs)

            self.in_anchor = True
            self.anchor_href = attrs_dict.get("href")
            self.anchor_text = []

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == "a" and self.in_anchor:
            self.finish_anchor()

        if self.tag_stack:
            # HTML irregular pode provocar situações pouco comuns;
            # retiramos apenas o último elemento correspondente.
            if self.tag_stack[-1] == tag:
                self.tag_stack.pop()
            elif tag in self.tag_stack:
                index = len(self.tag_stack) - 1 - self.tag_stack[::-1].index(tag)
                del self.tag_stack[index]

    def handle_data(self, data):
        if not data:
            return

        clean = html.unescape(data).replace("\xa0", " ")
        clean = re.sub(r"\s+", " ", clean).strip()

        if not clean:
            return

        if self.in_anchor:
            self.anchor_text.append(clean)
            return

        # Procuramos anos em qualquer texto fora de links.
        year_match = self.YEAR_RE.match(clean)

        if year_match:
            year = int(year_match.group(1))

            # A página contém anos de 2011 em diante.
            if 2000 <= year <= 2100:
                self.current_year = year
                self.current_period = None
                return

        # Também procuramos períodos em texto fora do <a>.
        period_match = self.PERIOD_RE.match(clean)

        if period_match:
            self.current_period = period_match.group(1)

    def finish_anchor(self):
        title = " ".join(self.anchor_text)
        title = html.unescape(title)
        title = title.replace("\xa0", " ")
        title = re.sub(r"\s+", " ", title).strip()

        href = self.anchor_href

        self.in_anchor = False
        self.anchor_href = None
        self.anchor_text = []

        if not href or not title:
            return

        # Ignorar links internos que não sejam publicações.
        if href.startswith("#"):
            return

        # Ignorar extensões Chrome que aparecem ocasionalmente
        # quando a página foi copiada/alterada por uma extensão.
        if href.startswith("chrome-extension://"):
            return

        # URLs absolutas ou relativas.
        absolute_url = urljoin(self.source_url, href)

        # Guardamos apenas links que estão associados a um ano.
        if self.current_year is None:
            return

        # Determinar período.
        #
        # Normalmente "Jan-Mar |" aparece imediatamente antes
        # do <a>. O parser guarda esse estado.
        #
        # Se por alguma razão o período não tiver sido capturado,
        # tentamos recuperá-lo do contexto textual imediatamente
        # anterior através do método de fallback abaixo.
        period = self.current_period

        # A página atual da Ordem tem uma característica importante:
        # depois de um período, podem existir vários <a> consecutivos.
        # O período continua válido para todos esses links.
        if period is None:
            return

        # Guardar.
        self.items.append(
            {
                "year": self.current_year,
                "period": period,
                "title": title,
                "url": absolute_url,
            }
        )


# ============================================================
# PARSER MAIS ROBUSTO PARA OS PERÍODOS
# ============================================================

def parse_cim_page(content):
    """
    Faz o parsing da página.

    Primeiro usa CIMParser. Depois executa uma segunda passagem
    textual para corrigir uma particularidade do HTML da Ordem:

        "Abr-Jun | <a>...</a><br> Abr-Jun | <a>...</a>"

    e casos em que o período aparece imediatamente antes do link.
    """

    parser = CIMParser(SOURCE_URL)
    parser.feed(content)

    items = parser.items

    # Em páginas HTML muito irregulares, alguns períodos podem não
    # ficar corretamente associados aos anchors. Por isso fazemos
    # uma segunda extração baseada na sequência textual.
    if not items:
        return parse_cim_page_fallback(content)

    # Verificação de qualidade.
    #
    # Se encontrarmos poucos itens apesar de existirem muitos anchors
    # de publicação, utilizamos o fallback.
    publication_like_links = re.findall(
        r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        content,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if len(items) < max(5, len(publication_like_links) // 3):
        fallback_items = parse_cim_page_fallback(content)

        if len(fallback_items) > len(items):
            return fallback_items

    return items


def parse_cim_page_fallback(content):
    """
    Fallback especialmente tolerante.

    Remove tags mantendo separadores e percorre os anchors pela
    ordem em que aparecem no HTML.

    A associação ano/período é feita olhando para o texto que
    precede cada anchor.
    """

    # Primeiro encontramos todos os anos e anchors em sequência.
    token_re = re.compile(
        r"(?P<year>\b20(?:1[0-9]|2[0-9])\b)"
        r"|(?P<period>\b(?:Jan-Mar|Jan-Fev|Mar-Abr|Abr-Jun|Mai-Ago|"
        r"Jul-Set|Set-Out|Out-Dez|Nov-Dez)\b)"
        r"|(?P<a><a\b[^>]*href=[\"'](?P<href>[^\"']+)[\"'][^>]*>"
        r"(?P<title>.*?)</a>)",
        flags=re.IGNORECASE | re.DOTALL,
    )

    current_year = None
    current_period = None

    items = []

    for match in token_re.finditer(content):
        if match.group("year"):
            current_year = int(match.group("year"))
            current_period = None
            continue

        if match.group("period"):
            current_period = match.group("period")
            continue

        href = match.group("href")
        title_html = match.group("title")

        if not href or not title_html:
            continue

        # Remover HTML do título.
        title = re.sub(r"<[^>]+>", " ", title_html)
        title = html.unescape(title)
        title = title.replace("\xa0", " ")
        title = re.sub(r"\s+", " ", title).strip()

        if not title or current_year is None or current_period is None:
            continue

        if href.startswith("#") or href.startswith("chrome-extension://"):
            continue

        absolute_url = urljoin(SOURCE_URL, href)

        items.append(
            {
                "year": current_year,
                "period": current_period,
                "title": title,
                "url": absolute_url,
            }
        )

    return items


# ============================================================
# LIMPEZA / NORMALIZAÇÃO
# ============================================================

def normalize_title(title):
    title = html.unescape(title)
    title = title.replace("\xa0", " ")
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def normalize_url(url):
    url = html.unescape(url).strip()

    # Corrigir alguns URLs antigos que aparecem com www.
    if url.startswith("http://www.ordemfarmaceuticos.pt"):
        url = "http://ordemfarmaceuticos.pt" + url[
            len("http://www.ordemfarmaceuticos.pt") :
        ]

    if url.startswith("https://www.ordemfarmaceuticos.pt"):
        url = "https://ordemfarmaceuticos.pt" + url[
            len("https://www.ordemfarmaceuticos.pt") :
        ]

    return url


def clean_items(items):
    """
    Limpa e deduplica.

    IMPORTANTE:
    Não deduplicamos apenas pelo URL.

    Isto é deliberado porque a página contém situações como:

        PDF X -> Título A
        PDF X -> Título B

    e ambos são publicações diferentes no contexto do Boletim.
    """

    cleaned = []
    seen = set()

    for item in items:
        title = normalize_title(item["title"])
        url = normalize_url(item["url"])

        year = item.get("year")
        period = item.get("period")

        if not title or not url or not year or not period:
            continue

        key = (
            year,
            period,
            title.casefold(),
            url,
        )

        if key in seen:
            continue

        seen.add(key)

        cleaned.append(
            {
                "year": year,
                "period": period,
                "title": title,
                "url": url,
            }
        )

    return cleaned


# ============================================================
# ORDENAÇÃO CRONOLÓGICA
# ============================================================

def item_sort_key(item):
    year = int(item["year"])
    period_number = PERIOD_ORDER.get(item["period"], 0)

    return (
        year,
        period_number,
    )


def sort_items(items):
    # Mais recente primeiro.
    return sorted(
        items,
        key=item_sort_key,
        reverse=True,
    )


# ============================================================
# DATAS
# ============================================================

def make_pubdate(item):
    """
    Cria uma data RFC 822 representativa do período.

    Exemplo:
        2026 + Abr-Jun -> 30 Jun 2026

    Isto serve para o RSS conseguir ordenar cronologicamente
    os itens. A data não pretende ser a data oficial exata
    de publicação.
    """

    year = int(item["year"])
    period = item["period"]

    month_day = PERIOD_END_MONTH.get(period)

    if month_day is None:
        # Fallback seguro.
        month, day = 12, 31
    else:
        month, day = month_day

    # Ajuste para Fevereiro em anos bissextos/não bissextos.
    if month == 2:
        if day > 29:
            day = 29 if year % 4 == 0 else 28

    dt = datetime(
        year,
        month,
        day,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )

    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


# ============================================================
# GUID
# ============================================================

def make_guid(item):
    """
    ID estável para cada publicação.

    Incluímos ano, período, título e URL para garantir que
    dois artigos que apontem para o mesmo PDF continuam a
    ter GUIDs diferentes.
    """

    raw = "|".join(
        [
            str(item["year"]),
            item["period"],
            item["title"],
            item["url"],
        ]
    )

    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return f"cim-{digest}"


# ============================================================
# DESCRIÇÃO
# ============================================================

def make_description(item):
    title = html.escape(item["title"])
    period = html.escape(item["period"])
    year = html.escape(str(item["year"]))
    url = html.escape(item["url"], quote=True)

    return (
        f"<p><strong>{title}</strong></p>"
        f"<p>Boletim do CIM — {period} {year}.</p>"
        f'<p><a href="{url}">Abrir publicação</a></p>'
    )


# ============================================================
# RSS
# ============================================================

def build_rss(items):
    rss = ET.Element(
        "rss",
        {
            "version": "2.0",
        },
    )

    channel = ET.SubElement(rss, "channel")

    title = ET.SubElement(channel, "title")
    title.text = FEED_TITLE

    link = ET.SubElement(channel, "link")
    link.text = FEED_LINK

    description = ET.SubElement(channel, "description")
    description.text = FEED_DESCRIPTION

    language = ET.SubElement(channel, "language")
    language.text = FEED_LANGUAGE

    last_build = ET.SubElement(channel, "lastBuildDate")
    last_build.text = datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    ttl = ET.SubElement(channel, "ttl")
    ttl.text = FEED_TTL

    for item in items:
        rss_item = ET.SubElement(channel, "item")

        item_title = ET.SubElement(rss_item, "title")
        item_title.text = item["title"]

        item_link = ET.SubElement(rss_item, "link")
        item_link.text = item["url"]

        guid = ET.SubElement(
            rss_item,
            "guid",
            {"isPermaLink": "false"},
        )
        guid.text = make_guid(item)

        pub_date = ET.SubElement(rss_item, "pubDate")
        pub_date.text = make_pubdate(item)

        item_description = ET.SubElement(
            rss_item,
            "description",
        )

        item_description.text = make_description(item)

        category = ET.SubElement(rss_item, "category")
        category.text = "Boletim do CIM"

    return rss


# ============================================================
# ESCRITA DO XML
# ============================================================

def write_xml(root, filename):
    tree = ET.ElementTree(root)

    # Python 3.9+
    ET.indent(tree, space="  ")

    tree.write(
        filename,
        encoding="utf-8",
        xml_declaration=True,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print(f"A obter página: {SOURCE_URL}")

    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    # A Ordem usa UTF-8. O requests normalmente deteta corretamente,
    # mas forçamos UTF-8 para evitar problemas com acentos.
    response.encoding = "utf-8"

    content = response.text

    print(f"Página obtida: {len(content):,} caracteres")

    items = parse_cim_page(content)

    print(f"Itens encontrados inicialmente: {len(items)}")

    items = clean_items(items)

    print(f"Itens após limpeza: {len(items)}")

    items = sort_items(items)

    if not items:
        raise RuntimeError(
            "Não foram encontradas publicações do Boletim do CIM. "
            "O feed NÃO será substituído."
        )

    # Verificação de segurança.
    #
    # Se a página mudar radicalmente e o parser passar a encontrar
    # muito poucos itens, não queremos destruir o histórico.
    #
    # A página fornecida atualmente contém dezenas de publicações.
    if len(items) < 20:
        raise RuntimeError(
            f"Foram encontrados apenas {len(items)} itens. "
            "Por segurança, o feed NÃO será substituído. "
            "Verifica se a estrutura da página da Ordem mudou."
        )

    rss = build_rss(items)

    write_xml(rss, OUTPUT_FILE)

    print()
    print("=" * 60)
    print("FEED CIM ATUALIZADO COM SUCESSO")
    print("=" * 60)
    print(f"Publicações: {len(items)}")
    print(f"Ficheiro:    {OUTPUT_FILE}")
    print()

    print("Primeiras publicações:")
    for item in items[:10]:
        print(
            f"  {item['year']} {item['period']} | "
            f"{item['title']}"
        )

    print()
    print("Últimas publicações:")
    for item in items[-5:]:
        print(
            f"  {item['year']} {item['period']} | "
            f"{item['title']}"
        )


if __name__ == "__main__":
    main()
```
