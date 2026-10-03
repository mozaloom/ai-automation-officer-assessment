import pytest

from agent.service import CORRECTION, FALLBACK, AvailabilityService
from config import Settings
from tools.availability import DataStore, local_loader, query_availability
from tools.grounding import find_ungrounded
from tools.strands_tool import STATE_KEY

from test_service import FakeAgent


@pytest.fixture()
def calls(dataset):
    return [query_availability(dataset, product_name="Tahini", city="Amman")]


def test_grounded_answer_passes(dataset, calls):
    r = calls[0]["records"][0]
    answer = f"{r['store_name']} has Tahini: {r['quantity_on_shelf']} units at JOD {r['shelf_price_jod']}."
    assert find_ungrounded(answer, dataset, calls) == []


@pytest.mark.parametrize(
    "answer, fragment",
    [
        ("Try Wadi Musa Market, it has Tahini.", "Wadi Musa Market"),
        ("It costs JOD 99.99.", "99.99"),
        ("There are 777 units on the shelf.", "777"),
        ("Ask Omar Haddad, the sales rep.", "sales representative"),
    ],
)
def test_ungrounded_values_are_caught(dataset, calls, answer, fragment):
    assert any(fragment in p for p in find_ungrounded(answer, dataset, calls))


def test_suggested_stores_are_allowed_in_no_match_answers(dataset):
    calls = [query_availability(dataset, product_name="Basmati Rice", store_name="Carrefour Paris")]
    assert find_ungrounded("Did you mean Carrefour Galleria?", dataset, calls) == []


class Flaky(FakeAgent):
    """First answer invents a price, second (after the correction) is clean."""

    def __init__(self, dataset, always_bad=False):
        super().__init__(dataset, plan=[{"product_name": "Tahini", "city": "Amman"}])
        self.always_bad, self.calls = always_bad, 0

    def __call__(self, prompt):
        self.calls += 1
        if self.calls == 1:
            self.state[STATE_KEY] = [query_availability(self.dataset, product_name="Tahini", city="Amman")]
        return "Tahini costs JOD 999.00" if (self.always_bad or self.calls == 1) else "Tahini is available."


def make(dataset, agent):
    return AvailabilityService(Settings(), DataStore(local_loader(Settings().data_path)), lambda: agent)


def test_one_corrective_retry_fixes_an_ungrounded_answer(dataset):
    agent = Flaky(dataset)
    out = make(dataset, agent).handle({"prompt": "tahini?"}, "s")
    assert out["grounded"] is True and out["answer"] == "Tahini is available." and agent.calls == 2


def test_still_ungrounded_after_retry_falls_back_to_records_only(dataset):
    agent = Flaky(dataset, always_bad=True)
    out = make(dataset, agent).handle({"prompt": "tahini?"}, "s")
    assert out["grounded"] is False and out["answer"] == FALLBACK and out["records"]
    assert agent.calls == 2


def test_clean_answers_are_not_retried(dataset):
    agent = FakeAgent(dataset, plan=[{"product_name": "Tahini"}])
    out = make(dataset, agent).handle({"prompt": "q"}, "s")
    assert out["grounded"] is True and len(agent.prompts) == 1
    assert "Correction" in CORRECTION
