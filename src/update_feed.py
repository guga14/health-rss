#!/usr/bin/env python3

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse
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

    Os parâmetros são enviados por GET.
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

    start = today - timedelta(days=LOOKBACK_DAYS)

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

    result = json.loads(data.decode("utf-8"))

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

    for i in range(0, len(pmids), BATCH_SIZE):

        batch = pmids[i:i + BATCH_SIZE]

        print(
            f"   A obter artigos "
            f"{i + 1}-"
            f"{min(i + BATCH_SIZE, len(pmids))} "
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

        for article in root.findall(".//PubmedArticle"):

            medline = article.find("MedlineCitation")

            if medline is None:
                continue

            pmid_element = medline.find("PMID")

            if pmid_element is None:
                continue

            pmid = pmid_element.text or ""

            if not pmid:
                continue

            article_node = medline.find("Article")

            if article_node is None:
                continue

            # ------------------------------------------------
            # TÍTULO
            # ------------------------------------------------

            title_node = article_node.find("ArticleTitle")

            title = ""

            if title_node is not None:
                title = "".join(
                    title_node.itertext()
                ).strip()

            # ------------------------------------------------
            # REVISTA
            # ------------------------------------------------

            journal = ""

            journal_node = article_node.find("Journal")

            if journal_node is not None:

                journal_title = journal_node.find("Title")

                if journal_title is not None:
                    journal = journal_title.text or ""

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

                    label = abstract_text.get("Label")

                    if label:
                        text = label + ": " + text

                    abstract_parts.append(text)

            abstract = " ".join(abstract_parts)

            # ------------------------------------------------
            # DOI
            # ------------------------------------------------

            doi = None

            for aid in article.findall(".//ArticleId"):

                if aid.attrib.get("IdType") == "doi":

                    doi = (aid.text or "").strip()
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

            publication_date = extract_publication_date(
                article_node
            )

            # ------------------------------------------------
            # PMC
            # ------------------------------------------------

            pmc_id = None

            for article_id in article.findall(
                ".//PubmedData/ArticleIdList/ArticleId"
            ):

                if article_id.attrib.get("IdType") == "pmc":

                    pmc_id = (article_id.text or "").strip()
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
                    publication_types.append(pub_type.text)

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

    journal = article_node.find("Journal")

    if journal is None:
        return ""

    pub_date = journal.find("JournalIssue/PubDate")

    if pub_date is None:
        return ""

    year = pub_date.findtext("Year")

    if year:

        month = pub_date.findtext("Month")
        month_number = month_to_number(month)

        day = pub_date.findtext("Day")

        if day and day.isdigit():
            day_number = int(day)
        else:
            day_number = 1

        return (
            f"{year}-"
            f"{month_number:02d}-"
            f"{day_number:02d}"
        )

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
# FILTROS DE TÍTULO
# ============================================================

def load_excluded_title_words():
    """
    Lê data/excluded_titles.txt.

    Formato normal:

        editorial
        correction
        retraction

    Para uma regra CASE-SENSITIVE:

        CASE:US
        CASE:USA
        CASE:United States
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

        if line.startswith("CASE:"):

            value = line[5:].strip()

            if value:
                rules.append(
                    {
                        "text": value,
                        "case_sensitive": True,
                    }
                )

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
    """

    if not title:
        return False, None

    for rule in excluded_rules:

        excluded = rule["text"]
        case_sensitive = rule["case_sensitive"]

        if case_sensitive:

            title_to_search = title
            excluded_to_search = excluded

        else:

            title_to_search = title.lower()
            excluded_to_search = excluded.lower()

        if " " in excluded_to_search:

            if excluded_to_search in title_to_search:
                return True, excluded

        else:

            pattern = (
                r"\b"
                + re.escape(excluded_to_search)
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

    journal_normalized = journal.strip().lower()

    for configured_journal, months in JOURNALS.items():

        if (
            journal_normalized
            == configured_journal.lower()
        ):
            return months

    return None


def embargo_elapsed(article):
    """
    Verifica se já passou o período de acesso gratuito.
    """

    months = get_embargo_months(article["journal"])

    if months is None:
        return False

    if months == 0:
        return True

    date_string = article["publication_date"]

    try:

        publication_date = datetime.strptime(
            date_string,
            "%Y-%m-%d",
        ).date()

    except (
        ValueError,
        TypeError,
    ):

        return False

    today = datetime.now(timezone.utc).date()

    elapsed_days = (
        today - publication_date
    ).days

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
# RSS / XML
# ============================================================

def xml_escape(text):
    """
    Escapa texto para utilização segura em XML/HTML.
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


def cdata_safe(text):
    """
    Coloca conteúdo dentro de CDATA de forma segura.

    A sequência ]]> não pode aparecer dentro de uma
    secção CDATA. Se aparecer, dividimos a secção.
    """

    if text is None:
        return ""

    return str(text).replace(
        "]]>",
        "]]]]><![CDATA[>"
    )


def valid_url(url):
    """
    Verifica se uma URL é absoluta e usa HTTP/HTTPS.
    """

    if not url:
        return False

    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def article_description(article):
    """
    Cria o conteúdo HTML da descrição do artigo.

    Este HTML será posteriormente colocado dentro de
    uma secção CDATA do RSS.
    """

    parts = []

    # --------------------------------------------------------
    # REVISTA
    # --------------------------------------------------------

    journal = article.get("journal", "")

    parts.append(
        "<strong>"
        + xml_escape(journal)
        + "</strong>"
    )

    # --------------------------------------------------------
    # DATA DE PUBLICAÇÃO
    # --------------------------------------------------------

    publication_date = article.get(
        "publication_date",
        "",
    )

    if publication_date:

        parts.append(
            "Publicado: "
            + xml_escape(publication_date)
        )

    # --------------------------------------------------------
    # PMC
    # --------------------------------------------------------

    pmc_url = article.get("pmc_url")

    if pmc_url and valid_url(pmc_url):

        parts.append(
            'Texto completo no PMC: '
            f'<a href="{xml_escape(pmc_url)}">'
            'abrir artigo'
            '</a>'
        )

    # --------------------------------------------------------
    # PUBMED
    # --------------------------------------------------------

    pubmed_url = article.get(
        "pubmed_url",
        "",
    )

    if pubmed_url and valid_url(pubmed_url):

        parts.append(
            'PubMed: '
            f'<a href="{xml_escape(pubmed_url)}">'
            'ver no PubMed'
            '</a>'
        )

    # --------------------------------------------------------
    # DOI
    # --------------------------------------------------------

    doi = article.get("doi")

    if doi:

        doi_url = (
            "https://doi.org/"
            + str(doi).strip()
        )

        if valid_url(doi_url):

            parts.append(
                'DOI: '
                f'<a href="{xml_escape(doi_url)}">'
                + xml_escape(doi_url)
                + "</a>"
            )

    # --------------------------------------------------------
    # ABSTRACT
    # --------------------------------------------------------

    abstract = article.get(
        "abstract",
        "",
    )

    if abstract:

        abstract = str(abstract)[:4000]

        parts.append(
            "<p>"
            + xml_escape(abstract)
            + "</p>"
        )

    return "<br/>".join(parts)


def make_feed_item(
    article,
    detected_free_at=None,
):

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
        "pubmed_url": article["pubmed_url"],
        "pmc_url": article["pmc_url"],
        "publication_date": article["publication_date"],
        "detected_free_at": detected_free_at,
    }


def validate_rss(rss):
    """
    Valida o XML e a estrutura básica de RSS 2.0.

    ElementTree garante que o documento é XML bem-formado.
    As verificações seguintes garantem que estamos realmente
    a publicar um RSS com a estrutura esperada.
    """

    try:

        root = ET.fromstring(rss)

    except ET.ParseError as error:

        raise ValueError(
            f"RSS inválido como XML: {error}"
        ) from error

    # --------------------------------------------------------
    # ROOT
    # --------------------------------------------------------

    if root.tag != "rss":

        raise ValueError(
            f"Elemento raiz inesperado: {root.tag}"
        )

    if root.get("version") != "2.0":

        raise ValueError(
            "O RSS não declara version=\"2.0\"."
        )

    # --------------------------------------------------------
    # CHANNEL
    # --------------------------------------------------------

    channels = root.findall("channel")

    if len(channels) != 1:

        raise ValueError(
            "O RSS deve conter exatamente um <channel>."
        )

    channel = channels[0]

    for required in (
        "title",
        "link",
        "description",
    ):

        element = channel.find(required)

        if element is None:

            raise ValueError(
                f"O <channel> não contém <{required}>."
            )

        if not (element.text or "").strip():

            raise ValueError(
                f"O <channel>/<${required}> está vazio."
            )

    # --------------------------------------------------------
    # CHANNEL LINK
    # --------------------------------------------------------

    channel_link = channel.findtext(
        "link",
        "",
    ).strip()

    if not valid_url(channel_link):

        raise ValueError(
            f"URL inválida no <channel>/<link>: "
            f"{channel_link}"
        )

    # --------------------------------------------------------
    # ITEMS
    # --------------------------------------------------------

    for index, item in enumerate(
        channel.findall("item"),
        start=1,
    ):

        title = item.findtext(
            "title",
            "",
        ).strip()

        description = item.find(
            "description"
        )

        if not title and (
            description is None
            or not (description.text or "").strip()
        ):

            raise ValueError(
                f"Item #{index} não tem "
                "title nem description."
            )

        link = item.findtext(
            "link",
            "",
        ).strip()

        if link and not valid_url(link):

            raise ValueError(
                f"URL inválida no item #{index}: "
                f"{link}"
            )

        guid = item.find(
            "guid"
        )

        if guid is not None:

            guid_text = (
                guid.text or ""
            ).strip()

            if (
                guid.get("isPermaLink") == "true"
                and guid_text
                and not valid_url(guid_text)
            ):

                raise ValueError(
                    f"GUID inválido no item #{index}: "
                    f"{guid_text}"
                )

    print(
        f"   RSS validado: "
        f"{len(channels[0].findall('item'))} itens."
    )


def build_feed(feed_items):
    """
    Constrói o ficheiro RSS.

    O XML e a estrutura básica RSS são validados antes
    de o ficheiro ser gravado.
    """

    now = datetime.now(timezone.utc)

    # --------------------------------------------------------
    # MAIS RECENTES PRIMEIRO
    # --------------------------------------------------------

    feed_items.sort(
        key=lambda item: item.get(
            "detected_free_at",
            "",
        ),
        reverse=True,
    )

    # --------------------------------------------------------
    # MANTÉM SOMENTE OS 200 MAIS RECENTES
    # --------------------------------------------------------

    feed_items = feed_items[:MAX_FEED_ITEMS]

    rss_items = []

    for item in feed_items:

        try:

            detected_at = datetime.fromisoformat(
                item["detected_free_at"].replace(
                    "Z",
                    "+00:00",
                )
            )

        except Exception:

            detected_at = now

        description = article_description(item)

        # ----------------------------------------------------
        # RSS:
        #
        # A description é CHARACTER DATA.
        #
        # O HTML é colocado dentro de CDATA para que
        # <strong>, <br>, <a>, <p>, etc. não sejam
        # interpretados como elementos XML do RSS.
        # ----------------------------------------------------

        description_cdata = cdata_safe(
            description
        )

        rss_items.append(
            f"""
        <item>
            <title>{xml_escape(item.get("title", ""))}</title>

            <link>{xml_escape(item.get("pubmed_url", ""))}</link>

            <guid isPermaLink="true">{xml_escape(item.get("pubmed_url", ""))}</guid>

            <pubDate>{format_datetime(detected_at)}</pubDate>

            <description><![CDATA[{description_cdata}]]></description>

            <category>{xml_escape(item.get("journal", ""))}</category>
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
    # VALIDAR ANTES DE PUBLICAR
    # --------------------------------------------------------

    print(
        "\n   A validar RSS..."
    )

    validate_rss(rss)

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
    # HISTÓRICO
    # --------------------------------------------------------

    seen = load_seen()

    # --------------------------------------------------------
    # FILTROS DE TÍTULO
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
    # PUBMED
    # --------------------------------------------------------

    print(
        "\n1. Pesquisando PubMed..."
    )

    pmids = search_pubmed()

    print(
        f"   {len(pmids)} artigos encontrados."
    )

    # --------------------------------------------------------
    # METADADOS
    # --------------------------------------------------------

    print(
        "\n2. Obtendo metadados..."
    )

    articles = fetch_pubmed(pmids)

    print(
        f"   {len(articles)} artigos recuperados."
    )

    # --------------------------------------------------------
    # ARTIGOS QUE JÁ ESTÃO NO FEED
    # --------------------------------------------------------

    feed_items = []

    for pmid, record in seen.items():

        feed_item = record.get("feed_item")

        if feed_item:

            feed_items.append(feed_item)

    # --------------------------------------------------------
    # DETECTAR ARTIGOS NOVOS
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
        # VERIFICAR EMBARGO
        # ----------------------------------------------------

        if not embargo_elapsed(article):
            continue

        # ----------------------------------------------------
        # VERIFICAR SE JÁ FOI DETECTADO
        # ----------------------------------------------------

        if pmid in seen:
            continue

        # ----------------------------------------------------
        # É NOVO PARA O NOSSO FEED
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

        newly_free.append(feed_item)

        # ----------------------------------------------------
        # GUARDAR NO HISTÓRICO
        # ----------------------------------------------------

        seen[pmid] = {
            "first_seen_free": now,
            "title": article["title"],
            "journal": article["journal"],
            "publication_date": article[
                "publication_date"
            ],
            "feed_item": feed_item,
        }

    # --------------------------------------------------------
    # ADICIONAR NOVOS ARTIGOS AO FEED
    # --------------------------------------------------------

    feed_items.extend(newly_free)

    # --------------------------------------------------------
    # REMOVER DUPLICADOS POR PMID
    # --------------------------------------------------------

    unique_items = {}

    for item in feed_items:
        unique_items[item["pmid"]] = item

    feed_items = list(
        unique_items.values()
    )

    # --------------------------------------------------------
    # ATUALIZAR RSS
    # --------------------------------------------------------

    print(
        "\n3. Atualizando RSS..."
    )

    build_feed(feed_items)

    # --------------------------------------------------------
    # GUARDAR HISTÓRICO
    # --------------------------------------------------------

    save_seen(seen)

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

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


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":
    main()
