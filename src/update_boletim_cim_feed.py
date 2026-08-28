#!/usr/bin/env python3

import hashlib
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURAÇÃO
# ============================================================

SOURCE_URL = (
    "https://ordemfarmaceuticos.pt/"
    "pt/CIM/INDICE-DE-PUBLICACOES/"
)

SITE_ROOT = "https://ordemfarmaceuticos.pt/"

PUBLIC_DIR = Path("public")
DATA_DIR = Path("data")

FEED_FILE = PUBLIC_DIR / "boletim_cim.xml"
SEEN_FILE = DATA_DIR / "boletim_cim_seen.json"

FEED_TITLE = "Boletim do CIM — Ordem dos Farmacêuticos"

MAX_FEED_ITEMS = 100


# ============================================================
# HTTP
# ============================================================

def fetch_page(url):
    """
    Obtém o HTML da página da Ordem dos Farmacêuticos.

    É usado um User-Agent identificando o projeto.
    """

    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; HealthRSS/1.0; "
                "+https://github.com/)"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,"
                "application/xml;q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
        },
    )

    with urlopen(
        request,
        timeout=60,
    ) as response:

        content = response.read()

        charset = (
            response.headers.get_content_charset()
            or "utf-8"
        )

        return content.decode(
            charset,
            errors="replace",
        )


# ============================================================
# PARSER HTML
# ============================================================

class LinkParser(HTMLParser):
    """
    Extrai todos os links <a href="..."> da página,
    preservando a ordem em que aparecem no HTML.
    """

    def __init__(self):
        super().__init__(
            convert_charrefs=True
        )

        self.links = []

        self.current_href = None
        self.current_text = []

    def handle_starttag(
        self,
        tag,
        attrs,
    ):

        if tag.lower() != "a":
            return

        attributes = dict(attrs)

        href = attributes.get(
            "href"
        )

        if not href:
            return

        self.current_href = href
        self.current_text = []

    def handle_data(self, data):

        if self.current_href is not None:

            self.current_text.append(
                data
            )

    def handle_endtag(self, tag):

        if (
            tag.lower() == "a"
            and self.current_href is not None
        ):

            text = " ".join(
                self.current_text
            )

            text = re.sub(
                r"\s+",
                " ",
                text,
            ).strip()

            self.links.append(
                {
                    "href": self.current_href,
                    "text": text,
                }
            )

            self.current_href = None
            self.current_text = []


# ============================================================
# NORMALIZAÇÃO
# ============================================================

def normalize_url(
    href,
    base_url,
):
    """
    Converte URLs relativas em URLs absolutas.
    """

    href = html.unescape(
        href.strip()
    )

    if not href:
        return None

    if href.startswith(
        ("javascript:", "mailto:", "#")
    ):
        return None

    return urljoin(
        base_url,
        href,
    )


def clean_text(text):

    text = html.unescape(
        text or ""
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# DETEÇÃO DO BOLETIM
# ============================================================

def is_pdf(url):

    path = urlparse(
        url
    ).path.lower()

    return path.endswith(
        ".pdf"
    )


def score_link(
    link,
):
    """
    Atribui uma pontuação a um link.

    Quanto maior a pontuação, maior a probabilidade
    de ser uma edição do Boletim do CIM.

    O algoritmo usa simultaneamente:
      - texto do link;
      - URL;
      - PDF;
      - palavras-chave;
      - exclusão de links claramente irrelevantes.
    """

    text = clean_text(
        link["text"]
    )

    url = link["url"]

    combined = (
        f"{text} {url}"
    ).lower()

    score = 0

    # --------------------------------------------------------
    # Sinais muito fortes
    # --------------------------------------------------------

    if "boletim do cim" in combined:
        score += 100

    if "boletim-cim" in combined:
        score += 100

    if "boletim_cim" in combined:
        score += 100

    # --------------------------------------------------------
    # PDF
    # --------------------------------------------------------

    if is_pdf(url):
        score += 30

    # --------------------------------------------------------
    # CIM
    # --------------------------------------------------------

    if "cim" in combined:
        score += 10

    # --------------------------------------------------------
    # Palavras associadas a uma publicação/edição
    # --------------------------------------------------------

    for word in (
        "boletim",
        "edição",
        "edicao",
        "n.º",
        "nº",
        "numero",
        "número",
        "vol.",
        "volume",
    ):

        if word in combined:
            score += 10

    # --------------------------------------------------------
    # Sinais de que provavelmente NÃO é uma edição
    # --------------------------------------------------------

    negative_words = (
        "contacto",
        "contactos",
        "login",
        "registo",
        "pesquisa",
        "home",
        "início",
        "inicio",
        "sobre nós",
        "sobre nos",
        "cim à tarde",
        "cim a tarde",
        "recursos de informação",
        "recursos de informacao",
        "breves questões terapêuticas",
        "breves questoes terapeuticas",
        "e-publicação",
        "e-publicacao",
    )

    for word in negative_words:

        if word in combined:
            score -= 100

    return score


def find_bulletins(
    html_content,
):
    """
    Encontra candidatos a edições do Boletim do CIM.

    Mantém a ordem original da página.
    """

    parser = LinkParser()

    parser.feed(
        html_content
    )

    candidates = []

    for position, raw_link in enumerate(
        parser.links
    ):

        href = raw_link[
            "href"
        ]

        text = clean_text(
            raw_link["text"]
        )

        url = normalize_url(
            href,
            SOURCE_URL,
        )

        if not url:
            continue

        # Apenas links do domínio da Ordem.
        hostname = (
            urlparse(url)
            .hostname
            or ""
        ).lower()

        if not (
            hostname.endswith(
                "ordemfarmaceuticos.pt"
            )
        ):

            continue

        link = {
            "url": url,
            "text": text,
            "position": position,
        }

        score = score_link(
            link
        )

        # Só aceitamos candidatos que tenham sinais
        # suficientes de serem Boletim do CIM.
        if score >= 40:

            link["score"] = score

            candidates.append(
                link
            )

    return candidates


# ============================================================
# IDENTIFICAÇÃO DA EDIÇÃO
# ============================================================

def extract_issue_title(
    candidate,
):
    """
    Determina o título que será apresentado no RSS.
    """

    text = clean_text(
        candidate.get(
            "text",
            "",
        )
    )

    url = candidate[
        "url"
    ]

    # Se o texto do link é suficientemente informativo,
    # usamos o texto.
    if text:

        if len(text) >= 8:
            return text

    # Caso contrário usamos o nome do ficheiro.
    path = urlparse(
        url
    ).path

    filename = (
        Path(path).name
    )

    filename = (
        filename
        .replace(
            "-",
            " ",
        )
        .replace(
            "_",
            " ",
        )
        .replace(
            ".pdf",
            "",
        )
    )

    filename = re.sub(
        r"\s+",
        " ",
        filename,
    ).strip()

    if filename:

        return (
            "Boletim do CIM — "
            + filename
        )

    return "Novo Boletim do CIM"


def make_identifier(
    candidate,
):
    """
    Cria um identificador estável para a publicação.

    Normalmente o próprio URL é suficiente.
    O hash evita problemas com URLs muito grandes.
    """

    url = candidate[
        "url"
    ]

    return hashlib.sha256(
        url.encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# HISTÓRICO
# ============================================================

def load_seen():

    if not SEEN_FILE.exists():
        return {}

    try:

        with open(
            SEEN_FILE,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except Exception as exc:

        print(
            "Aviso: não foi possível ler "
            f"{SEEN_FILE}: {exc}"
        )

        return {}


def save_seen(
    seen,
):

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        SEEN_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            seen,
            file,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )


# ============================================================
# RSS
# ============================================================

def xml_escape(
    value,
):

    if value is None:
        return ""

    return (
        str(value)
        .replace(
            "&",
            "&amp;",
        )
        .replace(
            "<",
            "&lt;",
        )
        .replace(
            ">",
            "&gt;",
        )
        .replace(
            '"',
            "&quot;",
        )
        .replace(
            "'",
            "&apos;",
        )
    )


def create_description(
    title,
    url,
    detected_at,
):

    return (
        "<![CDATA["
        "<p>"
        "<strong>"
        + html.escape(
            title
        )
        + "</strong>"
        "</p>"
        "<p>"
        "Nova publicação detetada na página "
        "do Centro de Informação do Medicamento "
        "(CIM) da Ordem dos Farmacêuticos."
        "</p>"
        "<p>"
        "Detetada em: "
        + html.escape(
            detected_at
        )
        + "</p>"
        "<p>"
        '<a href="'
        + html.escape(
            url,
            quote=True,
        )
        + '">'
        "Abrir publicação"
        "</a>"
        "</p>"
        "]]>"
    )


def build_feed(
    items,
):

    now = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # Ordenação
    # --------------------------------------------------------

    items = sorted(
        items,
        key=lambda item: item.get(
            "detected_at",
            "",
        ),
        reverse=True,
    )

    items = items[
        :MAX_FEED_ITEMS
    ]

    rss_items = []

    for item in items:

        try:

            detected_at = (
                datetime.fromisoformat(
                    item[
                        "detected_at"
                    ].replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

        except Exception:

            detected_at = now

        description = (
            create_description(
                item["title"],
                item["url"],
                item["detected_at"],
            )
        )

        rss_items.append(
            """
    <item>
      <title>{title}</title>
      <link>{url}</link>
      <guid isPermaLink="false">
        cim-{identifier}
      </guid>
      <pubDate>{pubdate}</pubDate>
      <description>{description}</description>
      <category>Boletim do CIM</category>
    </item>
            """.format(
                title=xml_escape(
                    item["title"]
                ),
                url=xml_escape(
                    item["url"]
                ),
                identifier=xml_escape(
                    item["id"]
                ),
                pubdate=format_datetime(
                    detected_at
                ),
                description=description,
            )
        )

    rss = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>

    <title>{title}</title>

    <link>{source}</link>

    <description>
      Novas edições do Boletim do CIM da
      Ordem dos Farmacêuticos.
    </description>

    <language>pt-PT</language>

    <lastBuildDate>{last_build}</lastBuildDate>

    <ttl>1440</ttl>

{items}

  </channel>
</rss>
""".format(
        title=xml_escape(
            FEED_TITLE
        ),
        source=xml_escape(
            SOURCE_URL
        ),
        last_build=format_datetime(
            now
        ),
        items="".join(
            rss_items
        ),
    )

    # Verificação básica de XML antes de escrever.
    ET.fromstring(
        rss
    )

    PUBLIC_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    FEED_FILE.write_text(
        rss,
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "======================================"
    )

    print(
        "Boletim do CIM — RSS"
    )

    print(
        "======================================"
    )

    print(
        "\n1. A obter página do CIM..."
    )

    print(
        SOURCE_URL
    )

    html_content = fetch_page(
        SOURCE_URL
    )

    print(
        f"   HTML recebido: "
        f"{len(html_content):,} caracteres."
    )

    # --------------------------------------------------------
    # Encontrar candidatos
    # --------------------------------------------------------

    print(
        "\n2. A procurar links do Boletim do CIM..."
    )

    candidates = find_bulletins(
        html_content
    )

    print(
        f"   {len(candidates)} candidatos encontrados."
    )

    if not candidates:

        raise RuntimeError(
            "Não foi encontrado nenhum link "
            "que pareça corresponder ao Boletim "
            "do CIM. O site pode ter alterado "
            "a sua estrutura."
        )

    # --------------------------------------------------------
    # Mostrar candidatos no log
    # --------------------------------------------------------

    print(
        "\nCandidatos:"
    )

    for candidate in candidates[:20]:

        print(
            f"   score={candidate['score']:3d} "
            f"| {candidate['text'][:80]} "
            f"| {candidate['url']}"
        )

    # --------------------------------------------------------
    # Escolher o melhor candidato
    # --------------------------------------------------------

    # A página é mantida pela Ordem com a edição mais recente
    # acima das anteriores. Por isso, entre candidatos com
    # pontuação equivalente, damos prioridade à posição mais
    # alta na página.
    best_score = max(
        candidate["score"]
        for candidate in candidates
    )

    best_candidates = [
        candidate
        for candidate in candidates
        if candidate["score"] == best_score
    ]

    latest = min(
        best_candidates,
        key=lambda candidate: candidate[
            "position"
        ],
    )

    title = extract_issue_title(
        latest
    )

    identifier = make_identifier(
        latest
    )

    print(
        "\n3. Publicação mais recente detetada:"
    )

    print(
        f"   Título: {title}"
    )

    print(
        f"   URL: {latest['url']}"
    )

    print(
        f"   Score: {latest['score']}"
    )

    # --------------------------------------------------------
    # Histórico
    # --------------------------------------------------------

    seen = load_seen()

    feed_items = []

    # Recuperar itens anteriores.
    for identifier_key, item in seen.items():

        if "url" not in item:
            continue

        feed_items.append(
            item
        )

    # --------------------------------------------------------
    # Verificar se é uma nova publicação
    # --------------------------------------------------------

    if identifier in seen:

        print(
            "\n4. A publicação já é conhecida."
        )

        print(
            "   Nenhuma nova publicação."
        )

    else:

        detected_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        new_item = {
            "id": identifier,
            "title": title,
            "url": latest["url"],
            "detected_at": detected_at,
        }

        seen[
            identifier
        ] = new_item

        feed_items.append(
            new_item
        )

        print(
            "\n4. NOVA PUBLICAÇÃO!"
        )

        print(
            f"   {title}"
        )

    # --------------------------------------------------------
    # Remover duplicados
    # --------------------------------------------------------

    unique = {}

    for item in feed_items:

        unique[
            item["id"]
        ] = item

    feed_items = list(
        unique.values()
    )

    # --------------------------------------------------------
    # RSS
    # --------------------------------------------------------

    print(
        "\n5. A gerar RSS..."
    )

    build_feed(
        feed_items
    )

    save_seen(
        seen
    )

    print(
        f"   Feed: {FEED_FILE}"
    )

    print(
        f"   Itens no feed: "
        f"{min(len(feed_items), MAX_FEED_ITEMS)}"
    )

    print(
        "\n======================================"
    )

    print(
        "Concluído."
    )

    print(
        "======================================"
    )


if __name__ == "__main__":
    main()

