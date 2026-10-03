from collections import Counter

from tools.analytics import dashboard


def test_kpis_match_ground_truth(dataset, raw_rows):
    kpis = dashboard(dataset)["kpis"]
    counts = Counter(r["availability_status"] for r in raw_rows)
    assert kpis["listings"] == 936 and kpis["stores"] == 40 and kpis["products"] == 27 and kpis["cities"] == 12
    assert (kpis["in_stock"], kpis["low_stock"], kpis["out_of_stock"]) == (counts["In Stock"], counts["Low Stock"], counts["Out of Stock"])
    assert round(100 * counts["In Stock"] / 936, 1) == kpis["in_stock_pct"]


def test_status_split_adds_up(dataset):
    split = dashboard(dataset)["status_split"]
    assert sum(s["count"] for s in split) == 936
    assert [s["status"] for s in split] == ["In Stock", "Low Stock", "Out of Stock"]


def test_by_city_matches_ground_truth(dataset, raw_rows):
    rows = {r["city"]: r for r in dashboard(dataset)["by_city"]}
    assert set(rows) == {r["city"] for r in raw_rows}
    for city, row in rows.items():
        mine = [r for r in raw_rows if r["city"] == city]
        assert row["total"] == len(mine)
        assert row["out_of_stock"] == sum(r["availability_status"] == "Out of Stock" for r in mine)
    assert dashboard(dataset)["by_city"][0]["city"] == "Amman"


def test_at_risk_products_sorted_and_correct(dataset, raw_rows):
    rows = dashboard(dataset)["at_risk_products"]
    assert len(rows) == 10
    assert [r["at_risk"] for r in rows] == sorted((r["at_risk"] for r in rows), reverse=True)
    top = rows[0]
    mine = [r for r in raw_rows if r["product_name"] == top["product_name"] and r["availability_status"] != "In Stock"]
    assert top["at_risk"] == len(mine)


def test_filters_narrow_everything(dataset, raw_rows):
    result = dashboard(dataset, city="amman", category="Cooking Oil", status="low stock")
    expected = [r for r in raw_rows if r["city"] == "Amman" and r["category"] == "Cooking Oil" and r["availability_status"] == "Low Stock"]
    assert result["kpis"]["listings"] == len(expected)
    assert result["filters"] == {"city": "amman", "category": "Cooking Oil", "status": "Low Stock"}
    assert result["options"]["cities"] and len(result["options"]["cities"]) == 12


def test_unknown_filter_yields_empty_not_everything(dataset):
    assert dashboard(dataset, city="Atlantis")["kpis"]["listings"] == 0


def test_freshness_covers_all_dates(dataset):
    fresh = dashboard(dataset)["freshness"]
    assert len(fresh) == 14 and sum(f["count"] for f in fresh) == 936
    assert fresh[0]["date"] == "2026-08-12" and fresh[-1]["date"] == "2026-08-25"
