from tools.analytics import RECORDS_LIMIT, records_view


def test_filters_are_exact_and_case_insensitive(dataset, raw_rows):
    out = records_view(dataset, city="amman", product="TAHINI")
    expected = [r for r in raw_rows if r["city"] == "Amman" and r["product_name"] == "Tahini"]
    assert out["total"] == len(expected) == len(out["records"]) and out["filters"] == {"city": "amman", "product_name": "TAHINI"}
    assert all(r["city"] == "Amman" for r in out["records"]) and all("sales_rep" not in r for r in out["records"])


def test_store_status_and_category(dataset, raw_rows):
    out = records_view(dataset, store="Sameh Mall Abdoun", status="Low Stock")
    assert {r["store_name"] for r in out["records"]} == {"Sameh Mall Abdoun"} or not out["records"]
    assert out["total"] == sum(1 for r in raw_rows if r["store_name"] == "Sameh Mall Abdoun" and r["availability_status"] == "Low Stock")
    assert records_view(dataset, category="Dairy")["total"] == sum(1 for r in raw_rows if r["category"] == "Dairy")


def test_unknown_values_match_nothing_and_results_are_sorted_by_state(dataset):
    assert records_view(dataset, city="Atlantis")["records"] == []
    assert records_view(dataset, status="bogus")["total"] == 0
    states = [r["availability_status"] for r in records_view(dataset, city="Amman")["records"]]
    assert states == sorted(states, key=["In Stock", "Low Stock", "Out of Stock"].index)


def test_limit_flags_truncation(dataset):
    out = records_view(dataset, limit=10)
    assert len(out["records"]) == 10 and out["truncated"] and out["total"] == 936 and RECORDS_LIMIT >= 200


def test_service_routes_records_action(dataset):
    from agent.service import AvailabilityService
    from config import Settings
    from tools.availability import DataStore, local_loader

    svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: None)
    assert svc.handle({"action": "records", "filters": {"city": "Irbid"}})["total"] == 114
    assert svc.handle({"action": "records", "filters": "bad"})["error"]["code"] == "invalid_request"
