"""Tests for POST /api/insurance/{id}/undo-paid (iteration 8)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://vault-login-6.preview.emergentagent.com").rstrip("/")
PIN = "1234"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN})
    assert r.status_code == 200, f"Unlock failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def temp_policy(headers):
    """Create a temp monthly policy; cleanup after."""
    payload = {
        "company_name": "TEST_UndoCo",
        "member_name": "TEST_Member",
        "premium_amount": 1000,
        "premium_frequency": "Monthly",
        "premium_due_date": "2026-08-10",
    }
    r = requests.post(f"{BASE_URL}/api/insurance", json=payload, headers=headers)
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    yield pid
    requests.delete(f"{BASE_URL}/api/insurance/{pid}", headers=headers)


# --- Auth ---
def test_undo_no_auth():
    r = requests.post(f"{BASE_URL}/api/insurance/anything/undo-paid")
    assert r.status_code == 401


def test_undo_unknown_policy(headers):
    r = requests.post(f"{BASE_URL}/api/insurance/nonexistent-id-xxx/undo-paid", headers=headers)
    assert r.status_code == 404


def test_undo_with_no_payments(headers, temp_policy):
    r = requests.post(f"{BASE_URL}/api/insurance/{temp_policy}/undo-paid", headers=headers)
    assert r.status_code == 400
    assert "No payment to undo" in r.json().get("detail", "")


# --- Single pay + undo restores original state ---
def test_pay_then_undo_restores(headers, temp_policy):
    pid = temp_policy
    # Confirm original state
    lst = requests.get(f"{BASE_URL}/api/insurance", headers=headers).json()
    orig = next(p for p in lst if p["id"] == pid)
    assert orig["premium_due_date"] == "2026-08-10"
    assert orig["last_paid_on"] == ""

    # Pay
    r = requests.post(f"{BASE_URL}/api/insurance/{pid}/mark-paid", headers=headers)
    assert r.status_code == 200
    after_pay = r.json()
    assert after_pay["premium_due_date"] == "2026-09-10"  # +1 month
    assert after_pay["last_paid_on"] != ""

    # Undo
    r = requests.post(f"{BASE_URL}/api/insurance/{pid}/undo-paid", headers=headers)
    assert r.status_code == 200
    undone = r.json()
    assert undone["premium_due_date"] == "2026-08-10"
    assert undone["last_paid_on"] == ""

    # Payment record deleted
    pays = requests.get(f"{BASE_URL}/api/insurance/{pid}/payments", headers=headers).json()
    assert len(pays) == 0


# --- Multi pay: pay 3x then undo 1x ---
def test_multi_pay_then_single_undo(headers, temp_policy):
    pid = temp_policy
    for _ in range(3):
        r = requests.post(f"{BASE_URL}/api/insurance/{pid}/mark-paid", headers=headers)
        assert r.status_code == 200

    lst = requests.get(f"{BASE_URL}/api/insurance", headers=headers).json()
    pol = next(p for p in lst if p["id"] == pid)
    assert pol["premium_due_date"] == "2026-11-10"  # +3 months
    pays = requests.get(f"{BASE_URL}/api/insurance/{pid}/payments", headers=headers).json()
    assert len(pays) == 3

    # Undo once → step back one period, 2 payments remain
    r = requests.post(f"{BASE_URL}/api/insurance/{pid}/undo-paid", headers=headers)
    assert r.status_code == 200
    undone = r.json()
    assert undone["premium_due_date"] == "2026-10-10"
    assert undone["last_paid_on"] != ""  # previous payment's paid_on

    pays = requests.get(f"{BASE_URL}/api/insurance/{pid}/payments", headers=headers).json()
    assert len(pays) == 2


# --- Regression: seed LIC intact ---
def test_seed_lic_unaffected(headers):
    lst = requests.get(f"{BASE_URL}/api/insurance", headers=headers).json()
    lic = [p for p in lst if p.get("company_name") == "LIC"]
    assert len(lic) >= 1
    assert lic[0]["premium_due_date"] == "2026-08-15"
