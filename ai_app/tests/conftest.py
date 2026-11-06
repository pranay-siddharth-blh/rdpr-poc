import asyncio
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("RDPR_RATE_LIMIT_PER_MINUTE", "100000")

from app.config import settings  # noqa: E402
from app.db import ReadOnlyDB  # noqa: E402


@pytest.fixture(scope="session")
def db():
    d = ReadOnlyDB(settings.db_path)
    yield d
    d.close()


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def ask(db):
    from app.pipeline import answer_question

    def _ask(q):
        return run(answer_question(q, db, 200, 60))
    return _ask
