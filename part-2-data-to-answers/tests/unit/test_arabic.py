"""Arabic support: normalisation, glossary resolution, search by Arabic terms, grounding of Arabic answers."""

import pytest

from agent.service import FALLBACK, FALLBACK_AR, AvailabilityService
from config import Settings
from tools.availability import DataStore, local_loader, query_availability
from tools.glossary import get_glossary, has_arabic, norm_ar
from tools.grounding import find_ungrounded
from tools.strands_tool import LANGUAGE_KEY

from test_service import FakeAgent

FIELDS = ("city", "area", "store_name", "product_name", "category", "store_type", "region")


# ---------------------------------------------------------------------- normalisation


@pytest.mark.parametrize(
    "text, expected",
    [
        ("الطحينة", "طحينه"),  # article and ta marbuta
        ("أرز", "ارز"),  # hamza
        ("إربد", "اربد"),
        ("عمّان", "عمان"),  # tashkeel/shadda
        ("٣ لتر", "3 لتر"),  # Arabic-Indic digits
        ("١٫٥ كغم", "1.5 كغم"),
        ("سامح مول - عبدون", "سامح مول عبدون"),
    ],
)
def test_norm_ar(text, expected):
    assert norm_ar(text) == expected


def test_has_arabic():
    assert has_arabic("where is طحينة") and not has_arabic("tahini 3 L")


# ---------------------------------------------------------------------- glossary completeness


@pytest.mark.parametrize("field", FIELDS)
def test_every_dataset_value_has_an_arabic_name(dataset, field):
    glossary = get_glossary()
    missing = [v for v in dataset.values(field) if not glossary.label(field, v)]
    assert not missing, f"{field}: no Arabic name for {missing}"


def test_statuses_units_and_packs_are_covered(dataset):
    glossary = get_glossary()
    assert [glossary.label("status", s) for s in ("In Stock", "Low Stock", "Out of Stock")] == ["متوفر", "كمية قليلة", "نفدت الكمية"]
    assert all(glossary.pack_label(p) for p in dataset.values("pack_size"))


@pytest.mark.parametrize("field", FIELDS)
def test_arabic_names_resolve_back_to_themselves(dataset, field):
    glossary = get_glossary()
    for value in dataset.values(field):
        found, exact = glossary.candidates(field, glossary.label(field, value))
        assert found == {value} and exact, f"{field}: {value!r} -> {found}"


# ---------------------------------------------------------------------- search in Arabic


def arabic(dataset, **filters):
    return query_availability(dataset, **filters)


@pytest.mark.parametrize("spelling", ["طحينة", "الطحينه", "طحينية", "تحينة", "الطحينة"])
def test_spelling_and_dialect_variants_give_the_same_records(dataset, spelling):
    expected = query_availability(dataset, product_name="Tahini", city="Amman")
    got = arabic(dataset, product_name=spelling, city="عمّان")
    assert got["records"] == expected["records"] and got["filters_applied"] == {"product_name": "Tahini", "city": "Amman"}
    assert got["interpreted_from_arabic"]["product_name"] == spelling


def test_attached_preposition_on_a_place(dataset):
    assert arabic(dataset, product_name="طحينة", city="بعمان")["filters_applied"]["city"] == "Amman"
    assert arabic(dataset, product_name="طحينة", city="في إربد")["filters_applied"]["city"] == "Irbid"


def test_arabic_status_pack_area_and_store(dataset):
    out = arabic(dataset, product_name="زيت دوار الشمس", pack_size="٣ لتر", area="الصويفية", availability_status="متوفر")
    assert out["filters_applied"] == {"product_name": "Sunflower Cooking Oil", "pack_size": "3 L", "area": "Swaifieh", "availability_status": "In Stock"}
    assert all(r["area"] == "Swaifieh" and r["pack_size"] == "3 L" for r in out["records"])
    store = arabic(dataset, product_name="زيت زيتون", store_name="سامح مول عبدون")
    assert {r["store_name"] for r in store["records"]} == {"Sameh Mall Abdoun"}


def test_out_of_stock_is_not_read_as_in_stock(dataset):
    glossary = get_glossary()
    assert glossary.status("غير متوفر") == "Out of Stock" and glossary.status("مش موجود") == "Out of Stock"
    assert glossary.status("متوفرة") == "In Stock" and glossary.status("كمية قليلة") == "Low Stock"
    out = arabic(dataset, product_name="Tahini", availability_status="نفدت الكمية")
    assert out["records"] and {r["availability_status"] for r in out["records"]} == {"Out of Stock"}


@pytest.mark.parametrize(
    "term, candidates",
    [
        ("شاي", {"Black Tea Bags", "Black Tea Loose", "Green Tea Bags"}),
        ("رز", {"Basmati Rice", "White Rice Egyptian"}),
        ("قهوة", {"Instant Coffee", "Turkish Coffee Ground"}),
        ("حليب بودرة", {"Full Cream Milk Powder", "Skimmed Milk Powder"}),
    ],
)
def test_generic_arabic_terms_are_ambiguous(dataset, term, candidates):
    out = arabic(dataset, product_name=term)
    assert set(out["ambiguous"]["candidates"]) == candidates and out["records"] == []


def test_unknown_arabic_values_report_no_match_with_suggestions(dataset):
    out = arabic(dataset, product_name="طحينة", city="غزة")
    assert out["no_match"]["unmatched_filters"] == ["city"] and out["records"] == []
    assert arabic(dataset, product_name="كافيار")["no_match"]["unmatched_filters"] == ["product_name"]
    typo = arabic(dataset, product_name="طحينة", city="عمانن")
    assert "Amman" in typo["no_match"]["hints"]["city"]["suggestions"] or typo["records"]


def test_labels_are_added_only_on_request(dataset):
    plain = query_availability(dataset, product_name="Tahini", city="Amman")
    labelled = query_availability(dataset, product_name="Tahini", city="Amman", with_labels=True)
    assert "labels_ar" not in plain
    labels = labelled["labels_ar"]
    assert labels["Tahini"] == "طحينة" and labels["Amman"] == "عمّان" and labels["In Stock"] == "متوفر" and labels["400 g"] == "400 غم"
    assert all(r["store_name"] in labels for r in labelled["records"])


# ---------------------------------------------------------------------- grounding in Arabic


@pytest.fixture()
def calls(dataset):
    return [query_availability(dataset, product_name="Tahini", city="Amman", with_labels=True)]


def test_grounded_arabic_answer_passes(dataset, calls):
    r = calls[0]["records"][0]
    store = get_glossary().label("store_name", r["store_name"])
    answer = f"في {store} تتوفر الطحينة: {r['quantity_on_shelf']} وحدة بسعر {r['shelf_price_jod']:.2f} دينار."
    assert find_ungrounded(answer, dataset, calls) == []


def test_arabic_indic_digits_are_normalised(dataset, calls):
    r = calls[0]["records"][0]
    digits = str(r["quantity_on_shelf"]).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
    assert find_ungrounded(f"الكمية {digits} وحدة", dataset, calls) == []
    assert find_ungrounded("الكمية ٧٧٧٧ وحدة", dataset, calls)


@pytest.mark.parametrize(
    "answer, fragment",
    [
        ("جرّب سوق وادي موسى، فيه طحينة.", "Wadi Musa Market"),
        ("السعر 99.99 دينار.", "99.99"),
        ("السعر دينار 99.99", "99.99"),
        ("يوجد 777 وحدة على الرف.", "777"),
        ("Try وادي موسى سوق", None),
    ],
)
def test_ungrounded_arabic_answers_are_flagged(dataset, calls, answer, fragment):
    problems = find_ungrounded(answer, dataset, calls)
    assert bool(problems) == (fragment is not None)
    if fragment:
        assert any(fragment in p for p in problems)


# ---------------------------------------------------------------------- service locale handling


@pytest.fixture()
def svc(dataset):
    agents = []

    def factory():
        agents.append(FakeAgent(dataset, plan=[{"product_name": "Tahini"}]))
        return agents[-1]

    service = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), factory)
    service.agents = agents
    return service


def test_reply_language_follows_the_question_and_hints_only_wordless_ones(svc):
    svc.handle({"action": "ask", "prompt": "وين الطحينة؟", "locale": "en"}, "a")
    svc.handle({"action": "ask", "prompt": "where is tahini", "locale": "ar"}, "b")
    svc.handle({"action": "ask", "prompt": "12345", "locale": "ar"}, "c")
    arabic, english, numbers = svc.agents
    assert (arabic.state[LANGUAGE_KEY], english.state[LANGUAGE_KEY], numbers.state[LANGUAGE_KEY]) == ("ar", "en", "ar")
    assert arabic.prompts[0] == "وين الطحينة؟" and english.prompts[0] == "where is tahini"
    assert numbers.prompts[0].endswith("[interface_language: ar]")


def test_unknown_or_missing_locale_adds_nothing(svc):
    svc.handle({"action": "ask", "prompt": "hello", "locale": "fr"}, "a")
    svc.handle({"action": "ask", "prompt": "hello"}, "b")
    assert [a.prompts[0] for a in svc.agents] == ["hello", "hello"]


def test_fallback_language_follows_the_question(dataset):
    class Stubborn(FakeAgent):
        def reply(self, prompt):
            return "There are 99999 units"

        def __call__(self, prompt):
            self.prompts.append(prompt)
            super().__call__(prompt)
            return "There are 99999 units"

    def answer(prompt, locale):
        svc = AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: Stubborn(dataset, plan=[{"product_name": "Tahini"}]))
        return svc.handle({"action": "ask", "prompt": prompt, "locale": locale}, "s")["answer"]

    assert answer("وين الطحينة؟", "en") == FALLBACK_AR
    assert answer("where is tahini", "ar") == FALLBACK
    assert answer("12345", "ar") == FALLBACK_AR
