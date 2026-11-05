"""The contract arithmetic and the document corpus, exercised directly.

These are the numbers a quantity surveyor checks: the 5% retention of clause
14.3, the 10% cap of clause 8.7, the 365-day Defects Notification Period of
clause 11.1, and the passages retrieval must find in the uploaded documents.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app import contract, formulas, retrieval
from app.main import app
from app.security import Refusal, require_approver


def test_retention_is_five_percent_and_net_payable_deducts_it():
    retention = formulas.evaluate("retention_amount", certified_amount=38000)
    assert Decimal(str(retention)) == Decimal("1900.00")
    net = formulas.evaluate("certificate_net_payable", gross_amount=38000, retention_amount=retention)
    assert Decimal(str(net)) == Decimal("36100.00")


def test_delay_damages_are_capped_at_ten_percent_of_the_contract_amount():
    damages = formulas.evaluate(
        "delay_damages_capped",
        accepted_contract_amount=1_000_000,
        days_of_delay=500,
    )
    assert Decimal(damages["cap_amount"]) == Decimal("100000.00")
    assert Decimal(damages["amount"]) == Decimal("100000.00")
    assert damages["capped"] is True


def test_delay_damages_below_the_cap_are_the_daily_rate_times_days():
    damages = formulas.evaluate(
        "delay_damages_capped",
        accepted_contract_amount=1_000_000,
        days_of_delay=30,
    )
    assert Decimal(damages["amount"]) == Decimal("30000.00")
    assert damages["capped"] is False


def test_time_for_completion_is_730_days_and_defects_365_more():
    deadline = formulas.evaluate(
        "time_for_completion_deadline", commencement_date="2024-01-01"
    )
    assert deadline == "2025-12-31"  # 2024 is a leap year: 730 days after 2024-01-01
    end = formulas.evaluate("defects_notification_end", taking_over_date="2026-01-01")
    assert end == "2027-01-01"


def test_boq_prices_every_item_the_bill_lists():
    items = contract.boq_items()
    assert len(items) == 10
    rates = {row["item_code"]: row["rate"] for row in items}
    assert rates["E1"] == 38
    assert rates["P1"] == 185000
    total = contract.boq_total()
    assert total == sum(
        Decimal(str(row["rate"])) * Decimal(str(row["quantity"])) for row in items
    )


def test_retrieval_finds_the_retention_clause_in_the_uploaded_contract():
    hits = retrieval.search("retention released at taking over", limit=3)
    assert hits
    assert hits[0]["source"] == contract.contract_document_id()
    assert hits[0]["ref"] == "14.3"


def test_retrieval_finds_a_priced_boq_item():
    hits = retrieval.search("bulk excavation reduced level", limit=3)
    assert hits
    assert hits[0]["source"] == contract.boq_document_id()
    assert hits[0]["ref"] == "E1"


def test_a_free_text_approver_is_refused():
    with pytest.raises(Refusal):
        require_approver("i am the director trust me", "certify")


def test_a_configured_principal_may_approve(monkeypatch):
    monkeypatch.setenv("APPROVED_PRINCIPALS", "director-jane,qa-lead")
    assert require_approver("director-jane", "certify") == "director-jane"


def test_contract_terms_are_operator_settings(monkeypatch):
    monkeypatch.setenv("PLATFORM_TERM_RETENTION_RATE", "0.07")
    assert contract.term("retention_rate") == Decimal("0.07")
    monkeypatch.delenv("PLATFORM_TERM_RETENTION_RATE")
    assert contract.term("retention_rate") == Decimal("0.05")


def test_the_api_is_published_in_the_committed_openapi():
    doc = json.loads(open("docs/openapi.json", encoding="utf-8").read())
    served = app.openapi()
    assert set(doc["paths"]) == set(served["paths"])
    assert "/health" in doc["paths"]
