"""Backend tests for MyVault (PIN auth + credentials + insurance + cards + change-pin)"""
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
                break
BASE_URL = BASE_URL.rstrip("/")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
PIN = "1234"


@pytest.fixture(scope="session")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(autouse=True)
def clear_lockout(mongo_db):
    mongo_db.login_attempts.delete_many({})
    yield


@pytest.fixture
def token(mongo_db):
    r = requests.get(f"{BASE_URL}/api/auth/status")
    assert r.status_code == 200
    if not r.json()["pin_set"]:
        requests.post(f"{BASE_URL}/api/auth/setup", json={"pin": PIN})
    r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# -------- Auth (regression) --------
class TestAuth:
    def test_status(self):
        r = requests.get(f"{BASE_URL}/api/auth/status")
        assert r.status_code == 200 and "pin_set" in r.json()

    def test_unlock_success(self):
        r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN})
        assert r.status_code == 200 and "token" in r.json()

    def test_unlock_wrong_pin(self):
        r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": "9999"})
        assert r.status_code == 401

    def test_protected_no_token(self):
        r = requests.get(f"{BASE_URL}/api/credentials")
        assert r.status_code == 401


# -------- Change PIN --------
class TestChangePin:
    def test_change_pin_wrong_old(self, auth_headers, mongo_db):
        r = requests.post(f"{BASE_URL}/api/auth/change-pin", json={"old_pin": "0000", "new_pin": "5678"}, headers=auth_headers)
        assert r.status_code == 401

    def test_change_pin_success_and_revert(self, auth_headers, mongo_db):
        # Change 1234 -> 5678
        r = requests.post(f"{BASE_URL}/api/auth/change-pin", json={"old_pin": PIN, "new_pin": "5678"}, headers=auth_headers)
        assert r.status_code == 200, r.text
        # Verify new PIN works
        r2 = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": "5678"})
        assert r2.status_code == 200
        new_token = r2.json()["token"]
        # Revert back
        r3 = requests.post(
            f"{BASE_URL}/api/auth/change-pin",
            json={"old_pin": "5678", "new_pin": PIN},
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert r3.status_code == 200
        r4 = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN})
        assert r4.status_code == 200

    def test_change_pin_no_auth(self):
        r = requests.post(f"{BASE_URL}/api/auth/change-pin", json={"old_pin": PIN, "new_pin": "1111"})
        assert r.status_code == 401


# -------- Cards CRUD --------
class TestCards:
    def test_cards_crud_and_encryption(self, auth_headers, mongo_db):
        payload = {
            "bank_name": "TEST_HDFC", "card_name": "Millennia", "card_type": "Credit",
            "card_number": "4111222233334444", "expiry": "08/29", "cvv": "123",
            "cardholder_name": "TEST User", "notes": "test",
        }
        r = requests.post(f"{BASE_URL}/api/cards", json=payload, headers=auth_headers)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["card_number"] == "4111222233334444"
        assert created["cvv"] == "123"
        cid = created["id"]

        # Fernet-encrypted at rest
        doc = mongo_db.cards.find_one({"id": cid})
        assert doc is not None
        assert doc["card_number"].startswith("gAAAA"), doc["card_number"][:20]
        assert doc["cvv"].startswith("gAAAA"), doc["cvv"][:20]

        # List returns decrypted
        r = requests.get(f"{BASE_URL}/api/cards", headers=auth_headers)
        assert r.status_code == 200
        got = next(x for x in r.json() if x["id"] == cid)
        assert got["card_number"] == "4111222233334444"
        assert got["cvv"] == "123"

        # Update
        upd = {**payload, "bank_name": "TEST_HDFC2", "card_number": "5555666677778888", "cvv": "999"}
        r = requests.put(f"{BASE_URL}/api/cards/{cid}", json=upd, headers=auth_headers)
        assert r.status_code == 200
        j = r.json()
        assert j["bank_name"] == "TEST_HDFC2"
        assert j["card_number"] == "5555666677778888"
        assert j["cvv"] == "999"
        doc = mongo_db.cards.find_one({"id": cid})
        assert doc["card_number"].startswith("gAAAA")
        assert doc["cvv"].startswith("gAAAA")

        # Delete
        r = requests.delete(f"{BASE_URL}/api/cards/{cid}", headers=auth_headers)
        assert r.status_code == 200
        r = requests.delete(f"{BASE_URL}/api/cards/{cid}", headers=auth_headers)
        assert r.status_code == 404


# -------- Insurance with new fields --------
class TestInsuranceNewFields:
    def test_insurance_member_and_due_date(self, auth_headers):
        payload = {
            "company_name": "TEST_LIC", "plan_name": "Jeevan", "policy_number": "P1",
            "member_name": "Father", "premium_amount": 25000, "premium_frequency": "Yearly",
            "premium_due_date": "2026-08-15", "term_years": 20, "sum_assured": 1000000,
            "maturity_amount": 1500000, "maturity_date": "2045-01-01", "nominee": "Spouse", "notes": "n",
        }
        r = requests.post(f"{BASE_URL}/api/insurance", json=payload, headers=auth_headers)
        assert r.status_code == 200
        j = r.json()
        assert j["member_name"] == "Father"
        assert j["premium_due_date"] == "2026-08-15"
        pid = j["id"]

        r = requests.get(f"{BASE_URL}/api/insurance", headers=auth_headers)
        got = next(x for x in r.json() if x["id"] == pid)
        assert got["member_name"] == "Father"
        assert got["premium_due_date"] == "2026-08-15"

        # cleanup
        requests.delete(f"{BASE_URL}/api/insurance/{pid}", headers=auth_headers)


# -------- PWA --------
class TestPWA:
    def test_manifest(self):
        r = requests.get(f"{BASE_URL}/manifest.json")
        assert r.status_code == 200, r.text
        j = r.json()
        assert "icons" in j and len(j["icons"]) >= 1
        assert j.get("display") == "standalone"

    def test_sw(self):
        r = requests.get(f"{BASE_URL}/sw.js")
        assert r.status_code == 200

    def test_icon(self):
        r = requests.get(f"{BASE_URL}/icon-192.png")
        assert r.status_code == 200
