#!/usr/bin/env python3

import json
import os
import re
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
EXCLUDED_TITLES_FILE = DATA_DIR / "excluded_titles.txt"

MAX_FEED_ITEMS = 200
LOOKBACK_DAYS = 450
RETMAX = 1000


# ============================================================
# REVISTAS JAMA E PERÍODO DE ACESSO
# ============================================================

JOURNALS = {
    "JAMA": 6,

    "JAMA Network Open": 0,
    "JAMA Health Forum": 0,

    "JAMA Cardiology": 12,
    "JAMA Dermatology": 12,
    "JAMA Internal Medicine": 12,
    "JAMA Neurology": 12,
    "JAMA Oncology": 12,
    "JAMA Ophthalmology": 12,
    "JAMA Pediatrics": 12,
    "JAMA Psychiatry": 12,
}


# ============================================================
# HTTP / NCBI
# ============================================================

def ncbi_get(endpoint, params):
    """
    Faz uma chamada às NCBI E-utilities.
    """

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
        },
    )

    with urlopen(request, timeout=60) as response:
        return response.read()


# ============================================================
# PUBMED
# ============================================================

def journal_query():
    """
    Cria a expressão PubMed correspondente às revistas JAMA.
    """

    parts = []

    for journal in JOURNALS:
        parts.append(f'"{journal}"[jour]')

    return "(" + " OR ".join(parts) + ")"


def search_pubmed():
    """
    Procura no PubMed artigos das revistas JAMA que:
    - foram publicados recentemente;
    - têm texto completo gratuito.
    """

    today = datetime.now(timezone.utc).date()

    start = today - timedelta(
        days=LOOKBACK_DAYS
    )

    term = (
        f"{journal_query()} "
        f'AND "{start.isoformat()}"[pdat] : '
        f'"{today.isoformat()}"[pdat] '
        f"AND free full text[sb]"
    )

    print("Pesquisa PubMed:")
    print(term)

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

    result = json.loads(
        data.decode("utf-8")
    )

    return result["esearchresult"]["idlist"]


def fetch_pubmed(pmids):
    """
    Obtém os metadados completos dos artigos.

    Os PMIDs são processados em pequenos lotes para evitar
    URLs demasiado longas nas chamadas às NCBI E-utilities.
    """

    if not pmids:
        return []

    articles = []

    BATCH_SIZE = 100

    for i in range(
        0,
        len(pmids),
        BATCH_SIZE,
    ):

        batch = pmids[
            i:i + BATCH_SIZE
        ]

        print(
            f"   A obter artigos "
            f"{i + 1}-{min(i + BATCH_SIZE, len(pmids))} "
            f"de {len(pmids)}..."
        )

        data = ncbi_get(
            "efetch.fcgi",
            {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
            },
        )

        root = ET.fromstring(data)

        for article in root.findall(
            ".//PubmedArticle"
        ):

            medline = article.find(
                "MedlineCitation"
            )

            if medline is None:
                continue

            pmid_element = medline.find(
                "PMID"
            )

            if pmid_element is None:
                continue

            pmid = pmid_element.text

            article_node = medline.find(
                "Article"
            )

            if article_node is None:
                continue

            # ------------------------------------------------
            # TÍTULO
            # ------------------------------------------------

            title_node = article_node.find(
                "ArticleTitle"
            )

            title = ""

            if title_node is not None:
                title = "".join(
                    title_node.itertext()
                ).strip()

            # ------------------------------------------------
            # REVISTA
            # ------------------------------------------------

            journal = ""

            journal_node = article_node.find(
                "Journal"
            )

            if journal_node is not None:

                journal_title = journal_node.find(
                    "Title"
                )

                if journal_title is not None:
                    journal = (
                        journal_title.text or ""
                    )

            # ------------------------------------------------
            # ABSTRACT
            # ------------------------------------------------

            abstract_parts = []

            for abstract_text in article_node.findall(
                ".//Abstract/AbstractText"
            ):

                text = "".join(
                    abstract_text.itertext()
                ).strip()

                if text:
                    abstract_parts.append(
                        text
                    )

            abstract = " ".join(
                abstract_parts
            )

            # ------------------------------------------------
            # DOI
            # ------------------------------------------------

            doi = None

            for aid in article.findall(
                ".//ArticleId"
            ):

                if aid.attrib.get(
                    "IdType"
                ) == "doi":

                    doi = aid.text

                    break

            # ------------------------------------------------
            # URL PUBMED
            # ------------------------------------------------

            pubmed_url = (
                "https://pubmed.ncbi.nlm.nih.gov/"
                f"{pmid}/"
            )

            # ------------------------------------------------
            # DATA DE PUBLICAÇÃO
            # ------------------------------------------------

            publication_date = (
                extract_publication_date(
                    article_node
                )
            )

            # ------------------------------------------------
            # PMC
            # ------------------------------------------------

            pmc_id = None

            for article_id in article.findall(
                ".//PubmedData/ArticleIdList/ArticleId"
            ):

                if article_id.attrib.get(
                    "IdType"
                ) == "pmc":

                    pmc_id = article_id.text

                    break

            pmc_url = None

            if pmc_id:

                pmc_url = (
                    "https://pmc.ncbi.nlm.nih.gov/"
                    "articles/"
                    f"{pmc_id}/"
                )

            # ------------------------------------------------
            # TIPOS DE PUBLICAÇÃO
            # ------------------------------------------------

            publication_types = []

            for pub_type in article_node.findall(
                ".//PublicationTypeList/PublicationType"
            ):

                if pub_type.text:
                    publication_types.append(
                        pub_type.text
                    )

            # ------------------------------------------------
            # ARTIGO
            # ------------------------------------------------

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
                    "publication_date": publication_date,
                    "publication_types": publication_types,
                }
            )

    return articles


# ============================================================
# DATA
# ============================================================

def extract_publication_date(article_node):
    """
    Extrai a data de publicação do PubMed.
    """

    journal = article_node.find(
        "Journal"
    )

    if journal is None:
        return ""

    pub_date = journal.find(
        "JournalIssue/PubDate"
    )

    if pub_date is None:
        return ""

    year = pub_date.findtext("Year")

    if year:

        month = pub_date.findtext(
            "Month"
        )

        month_number = month_to_number(
            month
        )

        day = pub_date.findtext(
            "Day"
        )

        if day and day.isdigit():
            day_number = int(day)
        else:
            day_number = 1

        return (
            f"{year}-"
            f"{month_number:02d}-"
            f"{day_number:02d}"
        )

    medline_date = pub_date.findtext(
        "MedlineDate"
    )

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

    return months.get(
        month[:3],
        1,
    )


# ============================================================
# FILTROS DE TÍTULO
# ============================================================

def load_excluded_title_words():
    """
    Lê data/excluded_titles.txt.

    Formato normal:

        editorial
        correction
        retraction

    As regras normais são CASE-INSENSITIVE.

    Para uma regra CASE-SENSITIVE, usar:

        CASE:US
        CASE:USA
        CASE:United States

    Linhas vazias e linhas começadas por # são ignoradas.
    """

    if not EXCLUDED_TITLES_FILE.exists():

        print(
            "   Aviso: "
            "data/excluded_titles.txt não existe."
        )

        return []

    rules = []

    for line in EXCLUDED_TITLES_FILE.read_text(
        encoding="utf-8"
    ).splitlines():

        line = line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        # ----------------------------------------------------
        # Regra CASE-SENSITIVE
        # ----------------------------------------------------

        if line.startswith("CASE:"):

            value = line[5:].strip()

            if value:

                rules.append(
                    {
                        "text": value,
                        "case_sensitive": True,
                    }
                )

        # ----------------------------------------------------
        # Regra normal CASE-INSENSITIVE
        # ----------------------------------------------------

        else:

            rules.append(
                {
                    "text": line.lower(),
                    "case_sensitive": False,
                }
            )

    return rules


def title_matches_exclusion(
    title,
    excluded_rules,
):
    """
    Verifica se o título contém alguma regra definida
    em excluded_titles.txt.

    Regras normais:
        case-insensitive

    Regras CASE:
        case-sensitive

    Palavras simples são procuradas como palavras inteiras.

    Expressões com várias palavras são procuradas como
    expressões completas.
    """

    if not title:
        return False, None

    for rule in excluded_rules:

        excluded = rule["text"]

        case_sensitive = rule[
            "case_sensitive"
        ]

        # ----------------------------------------------------
        # Preparar texto para comparação
        # ----------------------------------------------------

        if case_sensitive:

            title_to_search = title

            excluded_to_search = excluded

        else:

            title_to_search = title.lower()

            excluded_to_search = excluded.lower()

        # ----------------------------------------------------
        # Expressão com várias palavras
        # ----------------------------------------------------

        if " " in excluded_to_search:

            if (
                excluded_to_search
                in title_to_search
            ):

                return True, excluded

        # ----------------------------------------------------
        # Palavra isolada
        # ----------------------------------------------------

        else:

            pattern = (
                r"\b"
                + re.escape(
                    excluded_to_search
                )
                + r"\b"
            )

            if re.search(
                pattern,
                title_to_search,
            ):

                return True, excluded

    return False, None


# ============================================================
# EMBARGO
# ============================================================

def get_embargo_months(journal):
    """
    Retorna o período de embargo configurado.
    """

    journal_normalized = (
        journal.strip().lower()
    )

    for configured_journal, months in JOURNALS.items():

        if (
            journal_normalized
            == configured_journal.lower()
        ):

            return months

    return None


def embargo_elapsed(article):
    """
    Verifica se já passou o período de acesso
    gratuito previsto para a revista.
    """

    months = get_embargo_months(
        article["journal"]
    )

    if months is None:
        return False

    # Open access imediato.
    if months == 0:
        return True

    date_string = article[
        "publication_date"
    ]

    try:

        publication_date = (
            datetime.strptime(
                date_string,
                "%Y-%m-%d",
            ).date()
        )

    except ValueError:

        return False

    today = datetime.now(
        timezone.utc
    ).date()

    elapsed_days = (
        today - publication_date
    ).days

    # Margem de segurança de 7 dias.
    required_days = (
        months * 30 + 7
    )

    return (
        elapsed_days >= required_days
    )


# ============================================================
# HISTÓRICO
# ============================================================

def load_seen():

    if not SEEN_FILE.exists():
        return {}

    try:

        return json.loads(
            SEEN_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        print(
            "Não foi possível ler seen.json. "
            "Começando novamente."
        )

        return {}


def save_seen(seen):

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

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
    """
    Escapa texto para utilização em XML.
    """

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
    """
    Cria o conteúdo HTML da descrição do artigo.

    IMPORTANTE:
    Esta função NÃO cria CDATA.

    O CDATA é criado apenas uma vez, em build_feed().
    Isto evita XML inválido devido a CDATA aninhado.
    """

    parts = []

    # --------------------------------------------------------
    # Revista
    # --------------------------------------------------------

    parts.append(
        "<strong>"
        + xml_escape(
            article["journal"]
        )
        + "</strong>"
    )

    # --------------------------------------------------------
    # Data de publicação
    # --------------------------------------------------------

    if article.get(
        "publication_date"
    ):

        parts.append(
            "Publicado: "
            + xml_escape(
                article[
                    "publication_date"
                ]
            )
        )

    # --------------------------------------------------------
    # PMC
    # --------------------------------------------------------

    if article.get(
        "pmc_url"
    ):

        parts.append(
            '<a href="'
            + xml_escape(
                article["pmc_url"]
            )
            + '">'
            "Texto completo no PMC"
            "</a>"
        )

    # --------------------------------------------------------
    # PubMed
    # --------------------------------------------------------

    parts.append(
        '<a href="'
        + xml_escape(
            article["pubmed_url"]
        )
        + '">'
        "PubMed"
        "</a>"
    )

    # --------------------------------------------------------
    # DOI
    # --------------------------------------------------------

    if article.get(
        "doi"
    ):

        doi_url = (
            "https://doi.org/"
            + article["doi"]
        )

        parts.append(
            '<a href="'
            + xml_escape(
                doi_url
            )
            + '">'
            "DOI"
            "</a>"
        )

    # --------------------------------------------------------
    # ABSTRACT
    # --------------------------------------------------------

    if article.get(
        "abstract"
    ):

        abstract = (
            article["abstract"][:4000]
        )

        # Escapamos o abstract como XML.
        #
        # Isto é deliberado: o conteúdo da descrição
        # será colocado dentro de um único CDATA em
        # build_feed().
        #
        # Também garante que uma eventual sequência
        # "]]>" no abstract não possa terminar
        # prematuramente o CDATA exterior.

        abstract = xml_escape(
            abstract
        )

        parts.append(
            "<p>"
            + abstract
            + "</p>"
        )

    return "<br/>".join(parts)


def make_feed_item(
    article,
    detected_free_at=None,
):
    """
    Converte um artigo PubMed num item persistente
    do nosso RSS.
    """

    if detected_free_at is None:

        detected_free_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

    return {
        "pmid": article["pmid"],
        "title": article["title"],
        "journal": article["journal"],
        "abstract": article["abstract"],
        "doi": article["doi"],
        "pubmed_url": article[
            "pubmed_url"
        ],
        "pmc_url": article[
            "pmc_url"
        ],
        "publication_date": article[
            "publication_date"
        ],
        "detected_free_at": detected_free_at,
    }


def build_feed(feed_items):

    now = datetime.now(
        timezone.utc
    )

    # --------------------------------------------------------
    # Mais recentes primeiro
    # --------------------------------------------------------

    feed_items.sort(
        key=lambda item: item.get(
            "detected_free_at",
            "",
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # Mantém somente os 200 mais recentes
    # --------------------------------------------------------

    feed_items = feed_items[
        :MAX_FEED_ITEMS
    ]

    rss_items = []

    for item in feed_items:

        try:

            detected_at = (
                datetime.fromisoformat(
                    item[
                        "detected_free_at"
                    ].replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

        except Exception:

            detected_at = now

        description = (
            article_description(
                item
            )
        )

        # ----------------------------------------------------
        # IMPORTANTE
        #
        # Há apenas UM CDATA:
        #
        # <description><![CDATA[ ... ]]></description>
        #
        # Não existe CDATA dentro de description.
        # ----------------------------------------------------

        rss_items.append(
            f"""
            <item>
                <title>{xml_escape(item["title"])}</title>

                <link>{xml_escape(item["pubmed_url"])}</link>

                <guid isPermaLink="true">{xml_escape(item["pubmed_url"])}</guid>

                <pubDate>{format_datetime(detected_at)}</pubDate>

                <description><![CDATA[{description}]]></description>

                <category>{xml_escape(item["journal"])}</category>
            </item>
            """
        )

    # --------------------------------------------------------
    # CHANNEL
    # --------------------------------------------------------

    channel = f"""
    <channel>

        <title>JAMA — Free Access</title>

        <link>https://jamanetwork.com/</link>

        <description>
            Novos artigos das revistas JAMA Network
            que passaram a ter acesso gratuito ou que
            são open access.
        </description>

        <language>pt-PT</language>

        <lastBuildDate>
            {format_datetime(now)}
        </lastBuildDate>

        {''.join(rss_items)}

    </channel>
    """

    # --------------------------------------------------------
    # RSS COMPLETO
    # --------------------------------------------------------

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>

<rss version="2.0">

{channel}

</rss>
"""

    # --------------------------------------------------------
    # VALIDAÇÃO
    #
    # Antes de escrever o ficheiro, verificamos se o XML
    # é realmente válido.
    #
    # Se houver algum problema, o workflow falha aqui,
    # em vez de publicar um RSS corrompido.
    # --------------------------------------------------------

    try:

        ET.fromstring(
            rss
        )

    except ET.ParseError as error:

        print(
            "\nERRO: o RSS gerado não é XML válido."
        )

        print(
            f"Detalhes: {error}"
        )

        raise

    # --------------------------------------------------------
    # ESCREVER FICHEIRO
    # --------------------------------------------------------

    PUBLIC_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    FEED_FILE.write_text(
        rss,
        encoding="utf-8",
    )

    print(
        f"   RSS válido gerado: {FEED_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "======================================"
    )

    print(
        "JAMA Free Access RSS"
    )

    print(
        "======================================"
    )

    # --------------------------------------------------------
    # Histórico
    # --------------------------------------------------------

    seen = load_seen()

    # --------------------------------------------------------
    # Filtros de título
    # --------------------------------------------------------

    excluded_title_rules = (
        load_excluded_title_words()
    )

    print(
        f"\nFiltros de título carregados: "
        f"{len(excluded_title_rules)}"
    )

    for rule in excluded_title_rules:

        if rule["case_sensitive"]:

            print(
                f"   - CASE:{rule['text']}"
            )

        else:

            print(
                f"   - {rule['text']}"
            )

    # --------------------------------------------------------
    # PubMed
    # --------------------------------------------------------

    print(
        "\n1. Pesquisando PubMed..."
    )

    pmids = search_pubmed()

    print(
        f"   {len(pmids)} artigos encontrados."
    )

    # --------------------------------------------------------
    # Metadados
    # --------------------------------------------------------

    print(
        "\n2. Obtendo metadados..."
    )

    articles = fetch_pubmed(
        pmids
    )

    print(
        f"   {len(articles)} artigos recuperados."
    )

    # --------------------------------------------------------
    # Artigos que já estão no feed
    # --------------------------------------------------------

    feed_items = []

    for pmid, record in seen.items():

        feed_item = (
            record.get(
                "feed_item"
            )
        )

        if feed_item:

            feed_items.append(
                feed_item
            )

    # --------------------------------------------------------
    # Detectar artigos novos
    # --------------------------------------------------------

    newly_free = []

    now = datetime.now(
        timezone.utc
    ).isoformat()

    for article in articles:

        pmid = article["pmid"]

        # ----------------------------------------------------
        # FILTRO DE TÍTULO
        # ----------------------------------------------------

        matches, matched_word = (
            title_matches_exclusion(
                article["title"],
                excluded_title_rules,
            )
        )

        if matches:

            print(
                "\nEXCLUÍDO pelo filtro de título:"
            )

            print(
                f"  Filtro: {matched_word}"
            )

            print(
                f"  Título: {article['title']}"
            )

            continue

        # ----------------------------------------------------
        # Verificar embargo
        # ----------------------------------------------------

        if not embargo_elapsed(
            article
        ):

            continue

        # ----------------------------------------------------
        # Verificar se já foi detectado
        # ----------------------------------------------------

        if pmid in seen:

            continue

        # ----------------------------------------------------
        # É novo para o nosso feed
        # ----------------------------------------------------

        print(
            "\nNOVO:"
        )

        print(
            f"  {article['journal']}"
        )

        print(
            f"  {article['title']}"
        )

        print(
            f"  PMID: {pmid}"
        )

        feed_item = make_feed_item(
            article,
            detected_free_at=now,
        )

        newly_free.append(
            feed_item
        )

        # ----------------------------------------------------
        # Guardar no histórico
        # ----------------------------------------------------

        seen[pmid] = {
            "first_seen_free": now,
            "title": article[
                "title"
            ],
            "journal": article[
                "journal"
            ],
            "publication_date": article[
                "publication_date"
            ],
            "feed_item": feed_item,
        }

    # --------------------------------------------------------
    # Adicionar novos artigos ao feed
    # --------------------------------------------------------

    feed_items.extend(
        newly_free
    )

    # --------------------------------------------------------
    # Remover duplicados por PMID
    # --------------------------------------------------------

    unique_items = {}

    for item in feed_items:

        unique_items[
            item["pmid"]
        ] = item

    feed_items = list(
        unique_items.values()
    )

    # --------------------------------------------------------
    # Atualizar RSS
    # --------------------------------------------------------

    print(
        "\n3. Atualizando RSS..."
    )

    build_feed(
        feed_items
    )

    # --------------------------------------------------------
    # Guardar histórico
    # --------------------------------------------------------

    save_seen(
        seen
    )

    print(
        "\n======================================"
    )

    print(
        f"Novos artigos: {len(newly_free)}"
    )

    print(
        f"Artigos mantidos no RSS: "
        f"{min(len(feed_items), MAX_FEED_ITEMS)}"
    )

    print(
        "======================================"
    )


if __name__ == "__main__":
    main()
