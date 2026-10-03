"""query_availability: filters, normalisation, ambiguity, no-match behaviour, freshness."""

import pytest

from tools.availability import canonical_pack, norm, normalize_status, query_availability


def truth(raw_rows, **conds):
    """Independent filter over raw csv rows (case-insensitive equality on given columns)."""
    return [r for r in raw_rows if all(r[k].lower() == v.lower() for k, v in conds.items())]


def stores_of(result):
    return {r["store_name"] for r in result["records"]}


# ---------------------------------------------------------------- exact filters vs ground truth


@pytest.mark.parametrize(
    "kwargs, cond",
    [
        ({"product_name": "Olive Oil Extra Virgin"}, {"product_name": "Olive Oil Extra Virgin"}),
        ({"product_name": "Basmati Rice", "city": "Amman"}, {"product_name": "Basmati Rice", "city": "Amman"}),
        ({"product_name": "Instant Coffee", "area": "Abdoun"}, {"product_name": "Instant Coffee", "area": "Abdoun"}),
        ({"product_name": "Basmati Rice", "store_name": "Sameh Mall Abdoun"}, {"product_name": "Basmati Rice", "store_name": "Sameh Mall Abdoun"}),
        ({"product_name": "Sunflower Cooking Oil", "pack_size": "3 L"}, {"product_name": "Sunflower Cooking Oil", "pack_size": "3 L"}),
        ({"product_name": "Sunflower Cooking Oil", "availability_status": "In Stock"}, {"product_name": "Sunflower Cooking Oil", "availability_status": "In Stock"}),
        ({"product_name": "Olive Oil Extra Virgin", "availability_status": "Low Stock"}, {"product_name": "Olive Oil Extra Virgin", "availability_status": "Low Stock"}),
        ({"city": "Irbid", "availability_status": "Out of Stock"}, {"city": "Irbid", "availability_status": "Out of Stock"}),
    ],
)
def test_total_matches_equal_ground_truth(dataset, raw_rows, kwargs, cond):
    result = query_availability(dataset, **kwargs, max_records=1000)
    expected = truth(raw_rows, **cond)
    assert result["total_matches"] == len(expected) > 0
    assert len(result["records"]) == len(expected)
    assert sum(result["status_counts"].values()) == len(expected)


def test_status_counts_are_distinct_states(dataset, raw_rows):
    result = query_availability(dataset, product_name="Olive Oil Extra Virgin")
    expected = truth(raw_rows, product_name="Olive Oil Extra Virgin")
    for status in ("In Stock", "Low Stock", "Out of Stock"):
        assert result["status_counts"][status] == sum(1 for r in expected if r["availability_status"] == status)


def test_filters_are_case_and_whitespace_insensitive(dataset):
    a = query_availability(dataset, product_name="  basmati RICE ", city="amman")
    b = query_availability(dataset, product_name="Basmati Rice", city="Amman")
    assert a["total_matches"] == b["total_matches"] > 0


def test_unknown_columns_never_leak(dataset):
    result = query_availability(dataset, product_name="Tahini")
    assert all("sales_rep" not in r and "sku" not in r for r in result["records"])


# ---------------------------------------------------------------- pack sizes


@pytest.mark.parametrize("raw, canon", [("3 L", "3000 ml"), ("3L", "3000 ml"), ("3 litre", "3000 ml"), ("3000 ml", "3000 ml"),
                                       ("1.5 L", "1500 ml"), ("750ml", "750 ml"), ("1 kg", "1000 g"), ("1000g", "1000 g"),
                                       ("1.8 kg", "1800 g"), ("100 bags", "100 bags"), ("100 bag", "100 bags"), ("odd pack", "odd pack")])
def test_canonical_pack(raw, canon):
    assert canonical_pack(raw) == canon


@pytest.mark.parametrize("variant", ["3 L", "3L", "3 litre", "3000ml"])
def test_pack_size_variants_find_the_same_rows(dataset, variant):
    result = query_availability(dataset, product_name="Sunflower Cooking Oil", pack_size=variant)
    assert result["pack_sizes_in_results"] == ["3 L"]


def test_multi_pack_product_lists_all_pack_sizes(dataset):
    result = query_availability(dataset, product_name="Sunflower Cooking Oil")
    assert result["pack_sizes_in_results"] == ["1.5 L", "3 L"]


def test_missing_pack_size_for_product_offers_real_options(dataset):
    result = query_availability(dataset, product_name="Olive Oil Extra Virgin", pack_size="3 L")
    assert result["total_matches"] == 0
    hint = result["no_match"]["hints"]["pack_size"]
    assert hint["available_for_product"] == ["750 ml"]


# ---------------------------------------------------------------- ambiguity (agent must ask)


@pytest.mark.parametrize(
    "term, expected",
    [
        ("tea", {"Black Tea Bags", "Black Tea Loose", "Green Tea Bags"}),
        ("coffee", {"Instant Coffee", "Turkish Coffee Ground"}),
        ("rice", {"Basmati Rice", "White Rice Egyptian"}),
        ("milk", {"Evaporated Milk", "Full Cream Milk Powder", "Skimmed Milk Powder"}),
        ("corn", {"Corn Cooking Oil", "Sweet Corn Canned"}),
        ("pasta", {"Spaghetti Pasta", "Vermicelli Pasta"}),
    ],
)
def test_generic_terms_are_ambiguous(dataset, term, expected):
    result = query_availability(dataset, product_name=term, city="Amman")
    assert result["total_matches"] == 0 and result["records"] == []
    assert set(result["ambiguous"]["candidates"]) == expected
    assert result["next_step"].startswith("ASK_CLARIFICATION")


def test_pack_size_can_resolve_an_ambiguous_term(dataset):
    result = query_availability(dataset, product_name="tea", pack_size="100 bags")
    assert "ambiguous" not in result
    assert {r["product_name"] for r in result["records"]} == {"Black Tea Bags"}


@pytest.mark.parametrize("term", ["olive oil", "extra virgin olive oil", "Olive Oil Extra Virgin", "sunflower oil", "tuna", "basmati"])
def test_specific_terms_are_not_ambiguous(dataset, term):
    result = query_availability(dataset, product_name=term)
    assert "ambiguous" not in result and result["total_matches"] > 0


def test_exact_name_wins_over_partial_matches(dataset):
    result = query_availability(dataset, product_name="Black Tea Bags")
    assert {r["product_name"] for r in result["records"]} == {"Black Tea Bags"}


# ---------------------------------------------------------------- no-match handling (never invent, never broaden)


def test_unknown_store_is_reported_not_invented(dataset):
    result = query_availability(dataset, product_name="Basmati Rice", store_name="Carrefour Paris")
    assert result["total_matches"] == 0 and result["records"] == []
    assert result["no_match"]["unmatched_filters"] == ["store_name"]
    assert result["next_step"].startswith("REPORT_NO_MATCH")


def test_typo_in_product_gets_suggestions(dataset):
    result = query_availability(dataset, product_name="Olive Oil Extra Virgen")
    assert "Olive Oil Extra Virgin" in result["no_match"]["hints"]["product_name"]["suggestions"]


def test_value_in_wrong_field_is_pointed_out(dataset):
    result = query_availability(dataset, product_name="Basmati Rice", city="Abdoun")
    hits = result["no_match"]["hints"]["city"]["matches_other_field"]
    assert {"field": "area", "values": ["Abdoun"]} in hits


def test_valid_filters_with_no_combination_do_not_broaden(dataset, raw_rows):
    # Instant Coffee exists and Aqaba exists, but pick a pair that has no row.
    for product in {r["product_name"] for r in raw_rows}:
        for city in {r["city"] for r in raw_rows}:
            if not truth(raw_rows, product_name=product, city=city):
                result = query_availability(dataset, product_name=product, city=city)
                assert result["records"] == [] and result["total_matches"] == 0
                assert result["no_match"]["reason"] == "no_records_for_combination"
                assert result["no_match"]["broader_options"], "must offer broader options without applying them"
                return
    pytest.skip("every product is listed in every city")


def test_no_records_never_silently_widen_status(dataset, raw_rows):
    result = query_availability(dataset, product_name="Basmati Rice", area="Abdoun", availability_status="Low Stock")
    expected = truth(raw_rows, product_name="Basmati Rice", area="Abdoun", availability_status="Low Stock")
    assert result["total_matches"] == len(expected)


# ---------------------------------------------------------------- status handling


@pytest.mark.parametrize("raw, canon", [("in stock", "In Stock"), ("In-Stock", "In Stock"), ("low", "Low Stock"), ("LOW STOCK", "Low Stock"),
                                       ("out", "Out of Stock"), ("out of stock", "Out of Stock"), ("available", None), ("", None)])
def test_normalize_status(raw, canon):
    assert normalize_status(raw) == canon


def test_unknown_status_is_an_error_with_allowed_values(dataset):
    result = query_availability(dataset, product_name="Tahini", availability_status="plenty")
    assert "error" in result and result["allowed_statuses"] == ["In Stock", "Low Stock", "Out of Stock"]


# ---------------------------------------------------------------- freshness, ordering, limits


def test_freshness_comes_from_matched_records(dataset, raw_rows):
    result = query_availability(dataset, product_name="Tahini", city="Amman", max_records=1000)
    dates = sorted(
        __import__("datetime").datetime.strptime(r["last_updated"], "%d/%m/%Y").date().isoformat()
        for r in truth(raw_rows, product_name="Tahini", city="Amman")
    )
    assert result["data_as_of"] == dates[-1] and result["oldest_update"] == dates[0]
    assert result["dataset_as_of"] == "2026-08-25"


def test_results_are_capped_but_counts_are_complete(dataset):
    result = query_availability(dataset, city="Amman", max_records=10)
    assert result["returned"] == 10 and result["truncated"] is True
    assert result["total_matches"] == 440 and sum(result["status_counts"].values()) == 440


def test_results_are_deterministic_and_in_stock_first(dataset):
    a = query_availability(dataset, product_name="Tahini")
    b = query_availability(dataset, product_name="Tahini")
    assert a == b
    ranks = [{"In Stock": 0, "Low Stock": 1, "Out of Stock": 2}[r["availability_status"]] for r in a["records"]]
    assert ranks == sorted(ranks)


def test_no_filters_returns_everything_counted(dataset):
    result = query_availability(dataset, max_records=5)
    assert result["total_matches"] == 936 and result["returned"] == 5


def test_blank_filters_are_ignored(dataset):
    assert query_availability(dataset, product_name="  ", city="")["total_matches"] == 936


def test_norm_strips_accents_and_punctuation():
    assert norm("  Café  Olive-Oil! ") == "cafe olive oil"


# ---------------------------------------------------------------- size glued to the product name (common model slip)


@pytest.mark.parametrize("text, name, pack", [
    ("3 L Sunflower Cooking Oil", "Sunflower Cooking Oil", "3 L"),
    ("Sunflower Cooking Oil 3L", "Sunflower Cooking Oil", "3 L"),
    ("Basmati Rice 1 kg", "Basmati Rice", "1 kg"),
    ("Black Tea Bags 100 bags", "Black Tea Bags", "100 bags"),
    ("Tahini", "Tahini", None),
    ("Olive Oil Extra Virgin", "Olive Oil Extra Virgin", None),
])
def test_split_embedded_pack(text, name, pack):
    from tools.availability import split_embedded_pack

    assert split_embedded_pack(text) == (name, pack)


def test_embedded_pack_in_product_name_is_understood(dataset):
    glued = query_availability(dataset, product_name="3 L Sunflower Cooking Oil", pack_size="3 L")
    clean = query_availability(dataset, product_name="Sunflower Cooking Oil", pack_size="3 L")
    assert glued["total_matches"] == clean["total_matches"] > 0
    assert glued["filters_applied"] == {"product_name": "Sunflower Cooking Oil", "pack_size": "3 L"}
    only_glued = query_availability(dataset, product_name="Sunflower Cooking Oil 3L")
    assert only_glued["pack_sizes_in_results"] == ["3 L"]
