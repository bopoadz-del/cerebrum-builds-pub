import os as _os
import sqlite3 as _sqlite3
from pathlib import Path as _HalPath


class _OfflineHal:
    """In-process HAL so Store DatabaseBlock can cursor() without a live store.

    Passing None made the tasting-room suite fail with
    ``'NoneType' object has no attribute 'cursor'`` after construct succeeded.
    """

    def __init__(self, db_path):
        self._db_path = db_path
        self._conn = None
        self.config = {}

    def _connect(self):
        if self._conn is None:
            parent = _HalPath(self._db_path).parent
            parent.mkdir(parents=True, exist_ok=True)
            self._conn = _sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = _sqlite3.Row
        return self._conn

    @property
    def connection(self):
        return self._connect()

    def get_connection(self):
        return self._connect()

    def cursor(self):
        return self._connect().cursor()

    def execute(self, *args, **kwargs):
        return self._connect().execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        return self._connect().executemany(*args, **kwargs)

    def commit(self):
        self._connect().commit()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None


def _offline_hal():
    root = _HalPath(_os.environ.get("STORAGE_PATH") or ".").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return _OfflineHal(str(root / "store_blocks.sqlite"))


def _ensure_store_block_ready(instance):
    """DatabaseBlock only opens SQLite in _legacy_initialize.

    Construct-with-HAL is not enough: process() uses self._connection,
    which stays None until initialize runs. LotDesk pilot then died on
    Insert failed: 'NoneType' object has no attribute 'cursor'.
    """
    conn = getattr(instance, "_connection", None)
    init = getattr(instance, "_legacy_initialize", None)
    if conn is None and callable(init):
        import asyncio
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(init())
            return instance
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, init()).result()
    return instance


def _instantiate_store_block(block_cls):
    """Store classes take (hal_block, config); kit shims called block_cls()."""
    hal = _offline_hal()
    attempts = []
    for call in (
        lambda: block_cls(hal, {}),
        lambda: block_cls(hal_block=hal, config={}),
        lambda: block_cls(hal=hal, config={}),
        lambda: block_cls(),
    ):
        try:
            return _ensure_store_block_ready(call())
        except TypeError as exc:
            attempts.append(exc)
    raise attempts[-1]


def _create_block_instance(block_or_name, *args, **kwargs):
    """Store host DI. Generated platforms have no app.dependencies host.

    Live sess_f1fe691 (VetCare Hub): workflow step_0 (database) raised
    DatabaseBlock.__init__() missing 2 required positional arguments:
    'hal_block' and 'config' after the Store-host import failed and the
    fallback constructed DatabaseBlock() with no HAL.
    """
    target = block_or_name
    if isinstance(target, str):
        try:
            from vendor.cerebrum.blocks import get_block as _gb
        except ImportError:
            from app.blocks import get_block as _gb
        target = _gb(target)
    if isinstance(target, type):
        return _instantiate_store_block(target)
    return _ensure_store_block_ready(target)

#!/usr/bin/env python3
"""
Auto-generated adapter for Cerebrum block: database
Wraps vendor.cerebrum.blocks.database into a synchronous run() function.
"""

import asyncio
from vendor.cerebrum.blocks import get_block


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        return pool.submit(asyncio.run, coro).result()


def run(**kwargs):
    """
    Execute the database block.
    Accepts keyword args matching the block's inputs/params.
    Returns the standardized block result payload.
    """
    block_cls = get_block("database")
    instance = _instantiate_store_block(block_cls)

    input_data = kwargs.get("input", kwargs)
    params = {k: v for k, v in kwargs.items() if k != "input"}

    envelope = _run_async(instance.execute(input_data, params))
    if envelope.get("status") == "error":
        inner = envelope.get("result", {})
        message = inner.get("error") if isinstance(inner, dict) else str(inner)
        raise RuntimeError(message or "database block failed")

    return envelope.get("result", envelope)
