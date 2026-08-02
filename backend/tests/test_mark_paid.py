"""Tests for POST /api/insurance/{id}/mark-paid + frequency math."""
import os
import pytest
import requests
from datetime import date

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback to reading frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

LIC_ID = "bc63fc20-091f-45cb-8d4c-f7c2a9ee502a"
ORIGINAL_DUE = "2026-08-15"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": "1234"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create(headers, **overrides):
    payload = {
        "company_name": "TEST_Policy",
        "premium_frequency": "Yearly",
        "premium_due_date": "2026-06-15",
    }
    payload.update(overrides)
    r = requests.post(f"{BASE_URL}/api/insurance", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _delete(headers, pid):
    requests.delete(f"{BASE_URL}/api/insurance/{pid}", headers=headers)


# ---------- Auth ----------

def test_mark_paid_no_auth():
    r = requests.post(f"{BASE_URL}/api/insurance/{LIC_ID}/mark-paid")
    assert r.status_code in (401, 403)


def test_mark_paid_unknown_id(headers):
    r = requests.post(f"{BASE_URL}/api/insurance/does-not-exist/mark-paid", headers=headers)
    assert r.status_code == 404


def test_mark_paid_no_due_date(headers):
    p = _create(headers, premium_due_date="")
    try:
        r = requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        assert r.status_code == 400
    finally:
        _delete(headers, p["id"])


# ---------- Frequency math ----------

def test_monthly(headers):
    p = _create(headers, premium_frequency="Monthly", premium_due_date="2026-06-15")
    try:
        r = requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["premium_due_date"] == "2026-07-15"
        assert data["last_paid_on"] == date.today().isoformat()
    finally:
        _delete(headers, p["id"])


def test_monthly_month_end_edge(headers):
    p = _create(headers, premium_frequency="Monthly", premium_due_date="2026-01-31")
    try:
        r = requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        assert r.status_code == 200
        assert r.json()["premium_due_date"] == "2026-02-28"
    finally:
        _delete(headers, p["id"])


def test_quarterly(headers):
    p = _create(headers, premium_frequency="Quarterly", premium_due_date="2026-06-15")
    try:
        r = requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        assert r.json()["premium_due_date"] == "2026-09-15"
    finally:
        _delete(headers, p["id"])


def test_half_yearly(headers):
    p = _create(headers, premium_frequency="Half-Yearly", premium_due_date="2026-06-15")
    try:
        r = requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        assert r.json()["premium_due_date"] == "2026-12-15"
    finally:
        _delete(headers, p["id"])


def test_one_time_clears_date(headers):
    p = _create(headers, premium_frequency="One-time", premium_due_date="2026-06-15")
    try:
        r = requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["premium_due_date"] == ""
        assert data["last_paid_on"] == date.today().isoformat()
    finally:
        _delete(headers, p["id"])


# ---------- GET returns last_paid_on ----------

def test_list_insurance_has_last_paid_on(headers):
    r = requests.get(f"{BASE_URL}/api/insurance", headers=headers)
    assert r.status_code == 200
    for item in r.json():
        assert "last_paid_on" in item


# ---------- PUT does not wipe last_paid_on ----------

def test_put_preserves_last_paid_on(headers):
    p = _create(headers, premium_frequency="Yearly", premium_due_date="2026-06-15")
    try:
        # mark paid to set last_paid_on
        requests.post(f"{BASE_URL}/api/insurance/{p['id']}/mark-paid", headers=headers)
        # get current state
        items = requests.get(f"{BASE_URL}/api/insurance", headers=headers).json()
        cur = next(i for i in items if i["id"] == p["id"])
        assert cur["last_paid_on"] == date.today().isoformat()

        # PUT with editable fields (no last_paid_on in payload)
        put_payload = {
            "company_name": "TEST_Policy_Updated",
            "premium_frequency": "Yearly",
            "premium_due_date": "2027-06-15",
        }
        r = requests.put(f"{BASE_URL}/api/insurance/{p['id']}", json=put_payload, headers=headers)
        assert r.status_code == 200

        items = requests.get(f"{BASE_URL}/api/insurance", headers=headers).json()
        cur = next(i for i in items if i["id"] == p["id"])
        assert cur["last_paid_on"] == date.today().isoformat(), "PUT wiped last_paid_on!"
        assert cur["company_name"] == "TEST_Policy_Updated"
    finally:
        _delete(headers, p["id"])


# ---------- LIC seed policy flow with restore ----------

def test_lic_mark_paid_and_restore(headers):
    # snapshot
    items = requests.get(f"{BASE_URL}/api/insurance", headers=headers).json()
    lic = next((i for i in items if i["id"] == LIC_ID), None)
    assert lic is not None, "LIC seed policy missing"
    assert lic["premium_due_date"] == ORIGINAL_DUE
    assert lic["premium_frequency"] == "Yearly"

    # mark paid
    r = requests.post(f"{BASE_URL}/api/insurance/{LIC_ID}/mark-paid", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["premium_due_date"] == "2027-08-15"
    assert data["last_paid_on"] == date.today().isoformat()

    # RESTORE original due date via PUT
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
    assert r.json()["premium_due_date"] == ORIGINAL_DUE

    # verify persistence
    items = requests.get(f"{BASE_URL}/api/insurance", headers=headers).json()
    lic_after = next(i for i in items if i["id"] == LIC_ID)
    assert lic_after["premium_due_date"] == ORIGINAL_DUE
