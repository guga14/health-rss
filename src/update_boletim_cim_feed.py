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

# O GitHub Pages publica a pasta public/.

OUTPUT_FILE = "public/boletim_cim.xml"

HEADERS = {
"User-Agent": (
"Mozilla/5.0 (compatible; health-rss/1.0; "
"+https://github.com/guga14/health-rss)"
)
}

REQUEST_TIMEOUT = 30

# Número mínimo de publicações aceites.

# Evita substituir um feed válido caso a página da Ordem

# mude radicalmente ou o scraper deixe de encontrar conteúdo.

MIN_ITEMS = 20

# ============================================================

# PERÍODOS

# ============================================================

PERIOD_ORDER = {
"Jan-Fev": 1,
"Jan-Mar": 1,
"Mar-Abr": 2,
"Abr-Jun": 2,
"Mai-Ago": 3,
"Jul-Set": 3,
"Set-Out": 3,
"Out-Dez": 4,
"Nov-Dez": 4,
}

PERIOD_END_MONTH = {
"Jan-Fev": (2, 28),
"Jan-Mar": (3, 31),
"Mar-Abr": (4, 30),
"Mai-Ago": (8, 31),
"Abr-Jun": (6, 30),
"Jul-Set": (9, 30),
"Set-Out": (10, 31),
"Out-Dez": (12, 31),
"Nov-Dez": (12, 31),
}

# ============================================================

# PARSER DA PÁGINA

# ============================================================

class CIMParser(HTMLParser):
"""
Extrai ano, período, título e URL da secção
BOLETIM DO CIM.

```
O HTML da página da Ordem pode ser irregular, por isso
não dependemos de classes ou da profundidade dos divs.
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
        if self.tag_stack[-1] == tag:
            self.tag_stack.pop()
        elif tag in self.tag_stack:
            index = (
                len(self.tag_stack)
                - 1
                - self.tag_stack[::-1].index(tag)
            )
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

    year_match = self.YEAR_RE.match(clean)

    if year_match:
        year = int(year_match.group(1))

        if 2000 <= year <= 2100:
            self.current_year = year
            self.current_period = None
            return

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

    if href.startswith("#"):
        return

    if href.startswith("chrome-extension://"):
        return

    absolute_url = urljoin(self.source_url, href)

    if self.current_year is None:
        return

    period = self.current_period

    if period is None:
        return

    self.items.append(
        {
            "year": self.current_year,
            "period": period,
            "title": title,
            "url": absolute_url,
        }
    )
```

# ============================================================

# PARSING

# ============================================================

def parse_cim_page(content):
"""
Faz o parsing normal e, se necessário, recorre a um
parser alternativo mais tolerante.
"""

```
parser = CIMParser(SOURCE_URL)
parser.feed(content)

items = parser.items

if not items:
    return parse_cim_page_fallback(content)

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
```

def parse_cim_page_fallback(content):
"""
Fallback tolerante para HTML irregular.

```
A associação entre ano/período e publicação é feita pela
ordem dos elementos encontrados no HTML.
"""

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

    title = re.sub(r"<[^>]+>", " ", title_html)
    title = html.unescape(title)
    title = title.replace("\xa0", " ")
    title = re.sub(r"\s+", " ", title).strip()

    if not title or current_year is None or current_period is None:
        continue

    if href.startswith("#"):
        continue

    if href.startswith("chrome-extension://"):
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
```

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

```
if url.startswith("http://www.ordemfarmaceuticos.pt"):
    url = "http://ordemfarmaceuticos.pt" + url[
        len("http://www.ordemfarmaceuticos.pt") :
    ]

if url.startswith("https://www.ordemfarmaceuticos.pt"):
    url = "https://ordemfarmaceuticos.pt" + url[
        len("https://www.ordemfarmaceuticos.pt") :
    ]

return url
```

def clean_items(items):
"""
Limpa e deduplica.

```
O URL sozinho não é usado como chave de deduplicação,
porque publicações diferentes podem apontar para o
mesmo PDF.
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
```

# ============================================================

# ORDENAÇÃO

# ============================================================

def item_sort_key(item):
year = int(item["year"])
period_number = PERIOD_ORDER.get(item["period"], 0)

```
return (
    year,
    period_number,
)
```

def sort_items(items):
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
Cria uma data representativa do final do período.

```
A data não pretende ser a data oficial exata de publicação.
"""

year = int(item["year"])
period = item["period"]

month_day = PERIOD_END_MONTH.get(period)

if month_day is None:
    month, day = 12, 31
else:
    month, day = month_day

if month == 2 and day > 28:
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
```

# ============================================================

# GUID

# ============================================================

def make_guid(item):
"""
Cria um GUID estável para cada publicação.
"""

```
raw = "|".join(
    [
        str(item["year"]),
        item["period"],
        item["title"],
        item["url"],
    ]
)

digest = hashlib.sha256(
    raw.encode("utf-8")
).hexdigest()

return f"cim-{digest}"
```

# ============================================================

# DESCRIÇÃO

# ============================================================

def make_description(item):
title = html.escape(item["title"])
period = html.escape(item["period"])
year = html.escape(str(item["year"]))
url = html.escape(item["url"], quote=True)

```
return (
    f"<p><strong>{title}</strong></p>"
    f"<p>Boletim do CIM — {period} {year}.</p>"
    f'<p><a href="{url}">Abrir publicação</a></p>'
)
```

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

```
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
last_build.text = datetime.now(
    timezone.utc
).strftime("%a, %d %b %Y %H:%M:%S +0000")

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
```

# ============================================================

# ESCRITA DO XML

# ============================================================

def write_xml(root, filename):
tree = ET.ElementTree(root)

```
ET.indent(tree, space="  ")

tree.write(
    filename,
    encoding="utf-8",
    xml_declaration=True,
)
```

# ============================================================

# MAIN

# ============================================================

def main():
print(f"A obter página: {SOURCE_URL}")

```
response = requests.get(
    SOURCE_URL,
    headers=HEADERS,
    timeout=REQUEST_TIMEOUT,
)

response.raise_for_status()

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

if len(items) < MIN_ITEMS:
    raise RuntimeError(
        f"Foram encontrados apenas {len(items)} itens. "
        f"O mínimo esperado é {MIN_ITEMS}. "
        "Por segurança, o feed NÃO será substituído. "
        "Verifica se a estrutura da página da Ordem mudou."
    )

# Garantir que a pasta public existe.
import os

os.makedirs(
    os.path.dirname(OUTPUT_FILE),
    exist_ok=True,
)

rss = build_rss(items)

write_xml(
    rss,
    OUTPUT_FILE,
)

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
```

if **name** == "**main**":
main()
