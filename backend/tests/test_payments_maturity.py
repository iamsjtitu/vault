"""Tests for Payment History (premium_payments) and cascade delete."""
import os
import pytest
import requests
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

LIC_ID = "bc63fc20-091f-45cb-8d4c-f7c2a9ee502a"
ORIGINAL_DUE = "2026-08-15"


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": "1234"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _create(headers, **overrides):
    payload = {
        "company_name": "TEST_PaymentPolicy",
        "premium_frequency": "Yearly",
        "premium_due_date": "2026-06-15",
        "premium_amount": 12345,
    }
    payload.update(overrides)
    r = requests.post(f"{BASE_URL}/api/insurance", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _delete(headers, pid):
    requests.delete(f"{BASE_URL}/api/insurance/{pid}", headers=headers)


# ---------- Auth ----------

def test_list_payments_no_auth():
    r = requests.get(f"{BASE_URL}/api/insurance/{LIC_ID}/payments")
    assert r.status_code in (401, 403)


# ---------- Payment recording ----------

def test_mark_paid_creates_payment_record(headers):
    p = _create(headers, premium_frequency="Yearly", premium_due_date="2026-06-15", premium_amount=25000)
    try:
        # before: no payments
        r = requests.get(f"{BASE_URL}/api/insurance/{p['id']}/payments", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

        # mark paid
        r = requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        assert r.status_code == 200

        # after: 1 payment, with paid_on=today, due_date=OLD due (2026-06-15), amount=25000
        r = requests.get(f"{BASE_URL}/api/insurance/{p['id']}/payments", headers=headers)
        assert r.status_code == 200
        rows = r.json()
        assert len(rows) == 1
        row = rows[0]
        assert row["paid_on"] == date.today().isoformat()
        assert row["due_date"] == "2026-06-15"
        assert row["amount"] == 25000
        assert row["policy_id"] == p["id"]
        assert "_id" not in row
        assert "id" in row
    finally:
        _delete(headers, p["id"])


def test_payments_sorted_newest_first(headers):
    p = _create(headers, premium_frequency="Monthly", premium_due_date="2026-03-15", premium_amount=1000)
    try:
        requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        r = requests.get(f"{BASE_URL}/api/insurance/{p['id']}/payments", headers=headers)
        rows = r.json()
        assert len(rows) == 3
        # newest first by created_at
        created = [row["created_at"] for row in rows]
        assert created == sorted(created, reverse=True)
        # due_dates should be OLD dues: 2026-03-15, 2026-04-15, 2026-05-15
        due_dates = [row["due_date"] for row in rows]
        assert due_dates == ["2026-05-15", "2026-04-15", "2026-03-15"]
    finally:
        _delete(headers, p["id"])


def test_delete_policy_cascades_payments(headers):
    p = _create(headers, premium_frequency="Yearly", premium_due_date="2026-06-15", premium_amount=500)
    requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
    # confirm payment exists
    r = requests.get(f"{BASE_URL}/api/insurance/{p['id']}/payments", headers=headers)
    assert len(r.json()) == 1

    # delete policy
    r = requests.delete(f"{BASE_URL}/api/insurance/{p['id']}", headers=headers)
    assert r.status_code == 200

    # payments should now be empty (endpoint still works, returns [])
    r = requests.get(f"{BASE_URL}/api/insurance/{p['id']}/payments", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


def test_payments_empty_for_unknown_policy(headers):
    r = requests.get(f"{BASE_URL}/api/insurance/does-not-exist/payments", headers=headers)
    assert r.status_code == 200
    assert r.json() == []


# ---------- LIC final-state safety ----------

def test_lic_final_state_intact(headers):
    items = requests.get(f"{BASE_URL}/api/insurance", headers=headers).json()
    lic = next((i for i in items if i["id"] == LIC_ID), None)
    assert lic is not None
    # If prior tests marked LIC paid, restore
    if lic["premium_due_date"] != ORIGINAL_DUE:
        restore_payload = {
            "company_name": lic["company_name"],
            "plan_name": lic.get("plan_name", ""),
            "policy_number": lic.get("policy_number", ""),
            "member_name": lic.get("member_name", ""),
            "premium_amount": lic.get("premium_amount"),
            "premium_frequency": lic["premium_frequency"],
            "premium_due_date": ORIGINAL_DUE,
            "term_years": lic.get("term_years"),
            "sum_assured": lic.get("sum_assured"),
            "maturity_amount": lic.get("maturity_amount"),
            "maturity_date": lic.get("maturity_date", ""),
            "nominee": lic.get("nominee", ""),
            "notes": lic.get("notes", ""),
        }
        r = requests.put(f"{BASE_URL}/api/insurance/{LIC_ID}", json=restore_payload, headers=headers)
        assert r.status_code == 200
    items = requests.get(f"{BASE_URL}/api/insurance", headers=headers).json()
    lic = next(i for i in items if i["id"] == LIC_ID)
    assert lic["premium_due_date"] == ORIGINAL_DUE
