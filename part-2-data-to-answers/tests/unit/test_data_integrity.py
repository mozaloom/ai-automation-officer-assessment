"""The supplied CSV must match what the design draft states about it."""

import pytest

from tools.availability import DatasetError, PosDataset, STATUSES


def test_draft_statistics(raw_rows):
    assert len(raw_rows) == 936
    assert len({r["store_id"] for r in raw_rows}) == 40
    assert len({r["product_name"] for r in raw_rows}) == 27
    assert len({r["city"] for r in raw_rows}) == 12
    assert len({r["category"] for r in raw_rows}) == 8
    assert {r["availability_status"] for r in raw_rows} == set(STATUSES)


def test_no_missing_values(raw_rows):
    assert all(value.strip() for row in raw_rows for value in row.values())


def test_quantity_matches_status(raw_rows):
    for row in raw_rows:
        qty, status = int(row["quantity_on_shelf"]), row["availability_status"]
        assert (qty == 0) == (status == "Out of Stock")
        assert (1 <= qty <= 5) == (status == "Low Stock")


def test_store_and_sku_pairs_are_unique(raw_rows):
    pairs = [(r["store_id"], r["sku"]) for r in raw_rows]
    assert len(pairs) == len(set(pairs))


def test_dataset_parses_everything(dataset, raw_rows):
    assert len(dataset.records) == len(raw_rows)
    assert dataset.as_of.isoformat() == "2026-08-25"
    assert dataset.oldest.isoformat() == "2026-08-12"


def test_public_record_hides_internal_fields(dataset):
    public = dataset.records[0].to_public()
    assert "sales_rep" not in public and "sku" not in public and "store_id" not in public
    assert public["last_updated"].count("-") == 2


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda t: t.replace("store_id,", "store_identifier,", 1), "missing columns"),
        (lambda t: t.replace("In Stock", "Plenty", 1), "availability_status"),
        (lambda t: t.replace("19/08/2026", "2026-08-19", 1), "line"),
    ],
)
def test_bad_csv_is_rejected(csv_text, mutate, message):
    with pytest.raises(DatasetError, match=message):
        PosDataset.from_csv_text(mutate(csv_text))


def test_empty_csv_is_rejected():
    header = "store_id,store_name,store_type,area,city,region,sku,product_name,category,pack_size,quantity_on_shelf,availability_status,shelf_price_jod,last_updated,sales_rep\n"
    with pytest.raises(DatasetError, match="empty"):
        PosDataset.from_csv_text(header)
