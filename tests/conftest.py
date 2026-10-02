import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.customers.store import CustomerStore  # noqa: E402


@pytest.fixture
def customers_dir(tmp_path):
    dst = tmp_path / "customers"
    shutil.copytree(ROOT / "samples" / "customers", dst)
    return dst


@pytest.fixture
def store(customers_dir):
    return CustomerStore(customers_dir, ROOT / "templates" / "incident-ticket.md")


@pytest.fixture
def contoso(store):
    return store.load("contoso")


@pytest.fixture
def fabrikam(store):
    return store.load("fabrikam")


def example(cid, name):
    return (ROOT / "samples" / "customers" / cid / "examples" / name).read_text()
