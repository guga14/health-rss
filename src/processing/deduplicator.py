#Deve tratar apenas da deduplicação da recolha atual (a mesma notícia aparece duas vezes nos resultados da fonte). O estado histórico ficará num componente próprio. Isto também deixa aberta a possibilidade de, no futuro, querermos manter um artigo no histórico mas permitir que ele volte a ser publicado, sem alterar a lógica de deduplicação.
from models.article import Article


class ArticleDeduplicator:
    """Remove duplicate articles from a collection."""

    def deduplicate(self, articles: list[Article]) -> list[Article]:
        """Return articles with duplicate IDs removed."""
        unique_articles: list[Article] = []
        seen_ids: set[str] = set()

        for article in articles:
            if article.id in seen_ids:
                continue

            seen_ids.add(article.id)
            unique_articles.append(article)

        return unique_articles