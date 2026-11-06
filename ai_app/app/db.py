"""
The SQLite connections this app uses: a small pool of read-only connections, so a dashboard build, a report and a chat
question run side by side instead of queueing behind one another. Three independent protections, none trusted alone:

  1. Every connection opens the file with `mode=ro` in its URI and `PRAGMA query_only = ON`: SQLite refuses every write.
  2. For model-written SQL (restricted=True) an authorizer runs while each statement is compiled, so it holds however
     the SQL is phrased (aliases, sub-queries, CTEs): only SELECT / READ / FUNCTION actions are allowed and every table
     read must be a mart_* table (the raw dim_* / fact_* tables, including the person-level fact_hr_staff, can never be
     read). File / extension functions are denied.
  3. A wall-clock timeout interrupts the statement, and a row cap bounds the result.

`version` (size + modification time of the file) changes when the warehouse is rebuilt; caches key on it.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import queue
import sqlite3
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

ALLOWED_TABLE_PREFIX = "mart_"
_ALLOWED_VIRTUAL_TABLES = frozenset({"json_each", "json_tree"})
_DENIED_FUNCTIONS = frozenset({"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer", "randomblob",
                               "zeroblob", "sqlite_offset"})
_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}

# (base table, column, view) triples that genuine mart_* views read, recorded when the database is opened. The mart
# is physical tables now, so this is normally empty; it keeps the authorizer correct if a mart view is ever added.
_VIEW_READS: frozenset = frozenset()


def _record_view_reads(conn: sqlite3.Connection) -> frozenset:
    seen: set = set()

    def rec(action, arg1, arg2, _db, tv):
        if action == sqlite3.SQLITE_READ and tv is not None:
            seen.add(((arg1 or "").lower(), (arg2 or "").lower(), tv.lower()))
        return sqlite3.SQLITE_OK
    views = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'view' AND name LIKE 'mart\\_%' ESCAPE '\\'")]
    conn.set_authorizer(rec)
    try:
        for v in views:
            conn.execute(f"SELECT * FROM {v} LIMIT 0").fetchall()
    finally:
        conn.set_authorizer(None)
    return frozenset(seen)


def _restricted_authorizer(action, arg1, arg2, _db_name, trigger_or_view):
    if action not in _ALLOWED_ACTIONS:
        return sqlite3.SQLITE_DENY  # writes, PRAGMA, ATTACH, recursive CTEs, transactions ...
    if action == sqlite3.SQLITE_READ and arg2 != "":
        # arg2 == "" is SQLite's column-less read that COUNT(*) triggers: it can only yield a row count, never a value.
        table = (arg1 or "").lower()
        if not (table.startswith(ALLOWED_TABLE_PREFIX) or table in _ALLOWED_VIRTUAL_TABLES):
            if trigger_or_view is None or (table, (arg2 or "").lower(), trigger_or_view.lower()) not in _VIEW_READS:
                return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _DENIED_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


class RestrictedQueryError(Exception):
    """Model-written SQL tried to read or do something the authorizer forbids."""


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    truncated: bool
    elapsed_seconds: float


class ReadOnlyDB:
    def __init__(self, db_path: Path, pool_size: int | None = None):
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found at {db_path}. This app only reads it; build it with "
                                    "python warehouse/build_warehouse.py.")
        self.path = db_path
        st = db_path.stat()
        self.version = f"{st.st_size}-{int(st.st_mtime)}"
        n = pool_size or settings.rdpr_db_connections
        uri = f"file:{urllib.parse.quote(db_path.as_posix())}?mode=ro"
        self._conns: list[sqlite3.Connection] = []
        for _ in range(n):
            c = sqlite3.connect(uri, uri=True, check_same_thread=False)
            c.execute("PRAGMA query_only = ON")
            c.execute("PRAGMA cache_size = -64000")      # 64 MB page cache per connection
            c.execute("PRAGMA mmap_size = 1073741824")   # map the file: repeated reads come from the OS cache
            self._conns.append(c)
        global _VIEW_READS
        _VIEW_READS = _record_view_reads(self._conns[0])
        self._free: queue.Queue[sqlite3.Connection] = queue.Queue()
        for c in self._conns:
            self._free.put(c)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=n, thread_name_prefix="rdpr-sqlite")

    @property
    def _conn(self) -> sqlite3.Connection:          # kept for callers that need any one connection
        return self._conns[0]

    def close(self) -> None:
        # stop any statement still running (e.g. the start-up cache warm-up) and let its thread finish before the
        # connections go away: closing a connection under a running query can crash the process
        for c in self._conns:
            c.interrupt()
        self._executor.shutdown(wait=True, cancel_futures=True)
        for c in self._conns:
            c.close()

    def run_sync(self, sql: str, max_rows: int, restricted: bool = False, params: tuple = (),
                 holder: list | None = None) -> QueryResult:
        start = time.monotonic()
        conn = self._free.get()
        if holder is not None:
            holder.append(conn)
        try:
            if restricted:
                conn.set_authorizer(_restricted_authorizer)
            try:
                cur = conn.execute(sql, params)
                columns = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchmany(max_rows + 1)
            except sqlite3.DatabaseError as exc:
                msg = str(exc).lower()
                if restricted and ("not authorized" in msg or "prohibited" in msg):
                    raise RestrictedQueryError(str(exc)) from exc
                raise
            finally:
                if restricted:
                    conn.set_authorizer(None)
        finally:
            self._free.put(conn)
        truncated = len(rows) > max_rows
        return QueryResult(columns, rows[:max_rows], truncated, time.monotonic() - start)

    async def run(self, sql: str, max_rows: int, timeout_seconds: float, restricted: bool = False,
                  params: tuple = ()) -> QueryResult:
        """restricted=True for all model-written SQL: the authorizer then applies."""
        holder: list = []
        future = self._executor.submit(self.run_sync, sql, max_rows, restricted, params, holder)
        try:
            return await asyncio.wait_for(asyncio.wrap_future(future), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            if holder:
                holder[0].interrupt()
            raise TimeoutError(f"Query exceeded the {timeout_seconds}s timeout and was interrupted.")


_db: ReadOnlyDB | None = None


def get_db() -> ReadOnlyDB:
    if _db is None:
        raise RuntimeError("DB not initialised -- did FastAPI's lifespan run?")
    return _db


def init_db() -> ReadOnlyDB:
    global _db
    _db = ReadOnlyDB(settings.db_path)
    return _db


def shutdown_db() -> None:
    global _db
    if _db is not None:
        _db.close()
        _db = None
