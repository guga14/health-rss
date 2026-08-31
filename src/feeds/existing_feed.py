from pathlib import Path
import xml.etree.ElementTree as ET

from ..models.article import Article


class ExistingFeedReader:

    def read(self, path: Path) -> list[Article]:
        if not path.exists():
            return []

        tree = ET.parse(path)
        root = tree.getroot()

        articles = []

        for item in root.findall(".//item"):
            ...
            articles.append(
                Article(...)
            )

        return articles