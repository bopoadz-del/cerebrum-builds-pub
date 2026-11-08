"""Per-request document artefacts the document blocks read.

A handler may hand a vendored block a real file, but it must not leave that
file behind: every artefact lives in one temporary directory the handler
removes in a finally block.

Scope READS: the record the caller supplied.
Scope WRITES: a temporary file only.
Scope NEVER: no network, no file under the mounted storage root.
"""

from __future__ import annotations

import csv
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Sequence


class Workspace:
    """One temporary directory, removed by ``close()``."""

    def __init__(self, prefix: str = "harbourline-") -> None:
        self.path = Path(tempfile.mkdtemp(prefix=prefix))

    def close(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def __enter__(self) -> "Workspace":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    def write_text(self, name: str, content: str) -> str:
        target = self.path / name
        target.write_text(str(content), encoding="utf-8")
        return str(target)

    def csv(self, name: str, rows: Iterable[Sequence[Any]]) -> str:
        target = self.path / name
        with target.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for row in rows:
                writer.writerow(row)
        return str(target)

    def xlsx(self, name: str, rows: Iterable[Sequence[Any]]) -> str:
        from openpyxl import Workbook

        target = self.path / name
        book = Workbook()
        sheet = book.active
        sheet.title = "BOQ"
        for row in rows:
            sheet.append(list(row))
        book.save(str(target))
        return str(target)

    def docx(self, name: str, text: str) -> str:
        import docx as python_docx

        target = self.path / name
        document = python_docx.Document()
        for line in str(text).splitlines():
            document.add_paragraph(line)
        document.save(str(target))
        return str(target)
