import csv
from pathlib import Path

import pytest

from tools.availability import PosDataset

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "pos_availability.csv"


@pytest.fixture(scope="session")
def csv_text() -> str:
    return CSV_PATH.read_text(encoding="utf-8-sig")


@pytest.fixture(scope="session")
def raw_rows() -> list[dict]:
    """Rows straight from the csv module: the independent ground truth for assertions."""
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="session")
def dataset(csv_text) -> PosDataset:
    return PosDataset.from_csv_text(csv_text)
