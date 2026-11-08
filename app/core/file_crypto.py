"""Plaintext file access for the vendored document blocks.

Documents this platform writes are not encrypted at rest, so ``open_plaintext``
yields the original path. It is a context manager so a future encrypted
implementation can decrypt to a temporary file without touching the blocks.

Scope READS: the caller's file path (existence checked by the block).
Scope WRITES: nothing.
Scope NEVER: no network, no copy left behind.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def open_plaintext(path: str) -> Iterator[str]:
    yield str(Path(path))
