#Receber o XML de um feed e escrevê-lo de forma atómica no destino. O FileOutput não deve saber que está a escrever um RSS, nem conhecer Feed, Article ou PublishedState.
from __future__ import annotations

import os
from pathlib import Path
from tempfile import NamedTemporaryFile


class FileOutput:
    """Write generated content to files atomically."""

    def write(
        self,
        path: str | Path,
        content: str,
    ) -> None:
        """
        Atomically write content to a file.

        The target file is replaced only after the complete content has
        been written and flushed to disk.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        file_descriptor, temporary_path = NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        )

        try:
            with os.fdopen(
                file_descriptor,
                "w",
                encoding="utf-8",
            ) as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, path)

        except Exception:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass

            raise