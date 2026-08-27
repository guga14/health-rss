#!/usr/bin/env python3

import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ============================================================
# CONFIGURAÇÃO
# ============================================================

NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "")
NCBI_TOOL = "jama-free-rss"

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

PUBLIC_DIR = Path("public")
DATA_DIR = Path("data")

FEED_FILE = PUBLIC_DIR / "jama-free.xml"
SEEN_FILE = DATA_DIR / "seen.json"


# Revistas JAMA Network indexadas no PubMed.
JOURNALS = {
    "JAMA": 6,

    "JAMA Netw Open": 0,
    "JAMA Health Forum": 0,

    "JAMA Cardiol": 12,
    "JAMA Dermatol": 12,
    "JAMA Intern Med": 12,
    "JAMA Neurol": 12,
    "JAMA Oncol": 12,
    "JAMA Ophthalmol": 12,
    "JAMA Otolaryngol Head Neck Surg": 12,
    "JAMA Pediatr": 12,
    "JAMA Psychiatry": 12,
    "JAMA Surg": 12,
}


# Quantos dias para trás devemos consultar.
# 420 dias cobre o embargo de 12 meses com folga.
LOOKBACK_DAYS = 450


# Máximo de artigos recuperados em cada consulta.
RETMAX = 1000


# ============================================================
# HTTP / NCBI
# ============================================================

def ncbi_get(endpoint, params):
    params = dict(params)

    params["tool"] = NCBI_TOOL

    if NCBI_EMAIL:
        params["email"] = NCBI_EMAIL

    query = urlencode(params)

    url = f"{EUTILS}/{endpoint}?{query}"

    request = Request(
        url,
        headers={
            "User-Agent": f"{NCBI_TOOL}/1.0 ({NCBI_EMAIL})"
        }
    )

    with urlopen(request, timeout=60) as response:
        return response.read()


# ============================================================
# PUBMED SEARCH
# ============================================================

def journal_query():
    parts = []

    for journal in JOURNALS:
        parts.append(f'"{journal}"[jour]')

    return "(" + " OR ".join(parts) + ")"


def search_pubmed():
    """
    Busca artigos das revistas JAMA publicados nos últimos
    ~15 meses que atualmente possuem texto completo gratuito.
    """

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=LOOKBACK_DAYS)

    term = (
        f"{journal_query()} "
        f'AND "{start.isoformat()}"[pdat] : "{today.isoformat()}"[pdat] '
        f"AND free full text[sb]"
    )

    data = ncbi_get(
        "esearch.fcgi",
        {
            "db": "pubmed",
            "term": term,
            "retmode": "json",
            "retmax": RETMAX,
            "sort": "pub date",
        },
    )

    result = json.loads(data.decode("utf-8"))

    return result["esearchresult"]["idlist"]


# ============================================================
# PUBMED FETCH
# ============================================================

def fetch_pubmed(pmids):
    if not pmids:
        return []

    data = ncbi_get(
        "efetch.fcgi",
        {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        },
    )

    root = ET.fromstring(data)

    articles = []

    for article in root.findall(".//PubmedArticle"):

        medline = article.find("MedlineCitation")

        if medline is None:
            continue

        pmid_element = medline.find("PMID")

        if pmid_element is None:
            continue

        pmid = pmid_element.text

        article_node = medline.find("Article")

        if article_node is None:
            continue

        title_node = article_node.find("ArticleTitle")

        title = ""

        if title_node is not None:
            title = "".join(title_node.itertext()).strip()

        journal_node = article_node.find("Journal")

        journal = ""

        if journal_node is not None:
            journal_title = journal_node.find("Title")

            if journal_title is not None:
                journal = journal_title.text or ""

        abstract_parts = []

        for abstract_text in article_node.findall(
            ".//Abstract/AbstractText"
        ):
            abstract_parts.append(
                "".join(abstract_text.itertext()).strip()
            )

        abstract = " ".join(abstract_parts)

        # DOI
        doi = None

        for aid in article.findall(".//ArticleId"):
            if aid.attrib.get("IdType") == "doi":
                doi = aid.text
                break

        # PubMed URL
        pubmed_url = (
            f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        )

        # Data de publicação
        pub_date = extract_publication_date(article_node)

        # Link para PMC, quando disponível
        pmc_id = None

        for article_id in article.findall(
            ".//PubmedData/ArticleIdList/ArticleId"
        ):
            if article_id.attrib.get("IdType") == "pmc":
                pmc_id = article_id.text
                break

        pmc_url = None

        if pmc_id:
            pmc_url = (
                f"https://pmc.ncbi.nlm.nih.gov/articles/"
                f"{pmc_id}/"
            )

        articles.append(
            {
                "pmid": pmid,
                "title": title,
                "journal": journal,
                "abstract": abstract,
                "doi": doi,
                "pubmed_url": pubmed_url,
                "pmc_id": pmc_id,
                "pmc_url": pmc_url,
                "publication_date": pub_date,
            }
        )

    return articles


def extract_publication_date(article_node):
    """
    Extrai uma data de publicação razoavelmente consistente
    dos metadados PubMed.
    """

    journal = article_node.find("Journal")

    if journal is not None:

        pub_date = journal.find("JournalIssue/PubDate")

        if pub_date is not None:

            year = pub_date.findtext("Year")

            if year:
                month = pub_date.findtext("Month")

                if month and month.isdigit():
                    month_number = int(month)
                else:
                    month_number = month_to_number(month)

                day = pub_date.findtext("Day")

                if day and day.isdigit():
                    day_number = int(day)
                else:
                    day_number = 1

                return f"{year}-{month_number:02d}-{day_number:02d}"

            medline_date = pub_date.findtext("MedlineDate")

            if medline_date:
                return medline_date

    return ""


def month_to_number(month):
    if not month:
        return 1

    months = {
        "Jan": 1,
        "Feb": 2,
        "Mar": 3,
        "Apr": 4,
        "May": 5,
        "Jun": 6,
        "Jul": 7,
        "Aug": 8,
        "Sep": 9,
        "Oct": 10,
        "Nov": 11,
        "Dec": 12,
    }

    return months.get(month[:3], 1)


# ============================================================
# FILTRO DE EMBARGO
# ============================================================

def embargo_elapsed(article):
    journal = article["journal"]

    months = None

    for configured_journal, embargo in JOURNALS.items():
        if journal.lower() == configured_journal.lower():
            months = embargo
            break

    if months is None:
        return False

    # Open-access imediato
    if months == 0:
        return True

    date_string = article["publication_date"]

    try:
        publication_date = datetime.strptime(
            date_string,
            "%Y-%m-%d"
        ).date()
    except ValueError:
        return False

    today = datetime.now(timezone.utc).date()

    elapsed_days = (today - publication_date).days

    # Pequena margem para diferenças entre data de publicação
    # online e data de indexação.
    required_days = months * 30 + 7

    return elapsed_days >= required_days


# ============================================================
# HISTÓRICO
# ============================================================

def load_seen():
    if not SEEN_FILE.exists():
        return {}

    try:
        return json.loads(
            SEEN_FILE.read_text(encoding="utf-8")
        )
    except Exception:
        return {}


def save_seen(seen):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    SEEN_FILE.write_text(
        json.dumps(
            seen,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


# ============================================================
# RSS
# ============================================================

def xml_escape(text):
    if text is None:
        return ""

    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def article_description(article):
    parts = []

    parts.append(
        f"<strong>{xml_escape(article['journal'])}</strong>"
    )

    if article["publication_date"]:
        parts.append(
            f"Publicado: {xml_escape(article['publication_date'])}"
        )

    if article["pmc_url"]:
        parts.append(
            f'<a href="{xml_escape(article["pmc_url"])}">'
            "Texto completo no PMC"
            "</a>"
        )

    parts.append(
        f'<a href="{xml_escape(article["pubmed_url"])}">'
        "PubMed"
        "</a>"
    )

    if article["abstract"]:
        abstract = article["abstract"][:4000]

        parts.append(
            "<p>"
            + xml_escape(abstract)
            + "</p>"
        )

    return "<br/>".join(parts)


def build_feed(articles):
    now = datetime.now(timezone.utc)

    items = []

    for article in articles:

        pub_date = now

        guid = (
            f"https://pubmed.ncbi.nlm.nih.gov/"
            f"{article['pmid']}/"
        )

        description = article_description(article)

        item = f"""
        <item>
            <title>{xml_escape(article['title'])}</title>
            <link>{xml_escape(guid)}</link>
            <guid isPermaLink="true">{xml_escape(guid)}</guid>
            <pubDate>{format_datetime(pub_date)}</pubDate>
            <description><![CDATA[{description}]]></description>
            <category>{xml_escape(article['journal'])}</category>
        </item>
        """

        items.append(item)

    channel = f"""
    <channel>
        <title>JAMA — Free Access</title>

        <link>https://jamanetwork.com/</link>

        <description>
            Artigos das revistas JAMA Network que passaram a
            ter acesso gratuito ou são open access.
        </description>

        <language>pt-PT</language>

        <lastBuildDate>{format_datetime(now)}</lastBuildDate>

        {''.join(items)}
    </channel>
    """

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
{channel}
</rss>
"""

    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)

    FEED_FILE.write_text(
        rss,
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print("Buscando artigos JAMA no PubMed...")

    pmids = search_pubmed()

    print(f"Encontrados {len(pmids)} PMIDs.")

    articles = fetch_pubmed(pmids)

    print(f"Recuperados {len(articles)} artigos.")

    seen = load_seen()

    newly_free = []

    for article in articles:

        pmid = article["pmid"]

        if not embargo_elapsed(article):
            continue

        if pmid not in seen:

            newly_free.append(article)

            seen[pmid] = {
                "first_seen_free": (
                    datetime.now(timezone.utc)
                    .isoformat()
                ),
                "title": article["title"],
                "journal": article["journal"],
                "publication_date": (
                    article["publication_date"]
                ),
            }

    # Mais recentes primeiro
    newly_free.sort(
        key=lambda x: x["publication_date"],
        reverse=True,
    )

    print(
        f"{len(newly_free)} artigos novos detectados."
    )

    # Guardamos apenas os últimos 200 itens no feed.
    current_feed = newly_free[:200]

    build_feed(current_feed)

    save_seen(seen)

    print(f"Feed escrito em {FEED_FILE}")


if __name__ == "__main__":
    main()
