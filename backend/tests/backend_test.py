"""Backend tests for MyVault (PIN auth + credentials + insurance)"""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # Read frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")
PIN = "1234"


@pytest.fixture(scope="session")
def mongo_db():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture(autouse=True)
def clear_lockout(mongo_db):
    mongo_db.login_attempts.delete_many({})
    yield


@pytest.fixture
def token(mongo_db):
    # Ensure PIN is set
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


# -------- Auth --------
class TestAuth:
    def test_status(self):
        r = requests.get(f"{BASE_URL}/api/auth/status")
        assert r.status_code == 200
        assert "pin_set" in r.json()

    def test_unlock_success(self, mongo_db):
        r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN})
        assert r.status_code == 200
        assert "token" in r.json()
        assert isinstance(r.json()["token"], str)

    def test_unlock_wrong_pin(self):
        r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": "9999"})
        assert r.status_code == 401

    def test_brute_force_lockout(self, mongo_db):
        for _ in range(5):
            requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": "9999"})
        r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": "9999"})
        assert r.status_code == 429
        # Cleanup so subsequent tests can unlock
        mongo_db.login_attempts.delete_many({})

    def test_protected_no_token(self):
        r = requests.get(f"{BASE_URL}/api/credentials")
        assert r.status_code == 401

    def test_protected_bad_token(self):
        r = requests.get(f"{BASE_URL}/api/credentials", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401


# -------- Credentials CRUD --------
class TestCredentials:
    def test_crud_full_flow(self, auth_headers, mongo_db):
        # Create
        payload = {
            "title": "TEST_Login", "category": "Bank",
            "username": "user1", "password": "SecretP@ss123",
            "website": "https://example.com", "notes": "test note",
        }
        r = requests.post(f"{BASE_URL}/api/credentials", json=payload, headers=auth_headers)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["title"] == "TEST_Login"
        assert created["password"] == "SecretP@ss123"  # API returns plaintext
        cid = created["id"]

        # Verify encrypted at rest
        doc = mongo_db.credentials.find_one({"id": cid})
        assert doc is not None
        assert doc["password"].startswith("gAAAA"), f"password not Fernet-encrypted: {doc['password'][:20]}"

        # List
        r = requests.get(f"{BASE_URL}/api/credentials", headers=auth_headers)
        assert r.status_code == 200
        found = [x for x in r.json() if x["id"] == cid]
        assert found and found[0]["password"] == "SecretP@ss123"

        # Update
        upd = {**payload, "title": "TEST_Login2", "password": "NewPass!"}
        r = requests.put(f"{BASE_URL}/api/credentials/{cid}", json=upd, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["title"] == "TEST_Login2"
        assert r.json()["password"] == "NewPass!"
        doc = mongo_db.credentials.find_one({"id": cid})
        assert doc["password"].startswith("gAAAA")

        # Delete
        r = requests.delete(f"{BASE_URL}/api/credentials/{cid}", headers=auth_headers)
        assert r.status_code == 200
        r = requests.delete(f"{BASE_URL}/api/credentials/{cid}", headers=auth_headers)
        assert r.status_code == 404


# -------- Insurance CRUD --------
class TestInsurance:
    def test_crud_full_flow(self, auth_headers):
        payload = {
            "company_name": "TEST_LIC", "plan_name": "Jeevan", "policy_number": "P123",
            "premium_amount": 25000, "premium_frequency": "Yearly", "term_years": 20,
            "sum_assured": 1000000, "maturity_amount": 1500000,
            "maturity_date": "2045-01-01", "nominee": "Spouse", "notes": "n",
        }
        r = requests.post(f"{BASE_URL}/api/insurance", json=payload, headers=auth_headers)
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        assert r.json()["company_name"] == "TEST_LIC"
        assert r.json()["sum_assured"] == 1000000

        r = requests.get(f"{BASE_URL}/api/insurance", headers=auth_headers)
        assert r.status_code == 200
        assert any(x["id"] == pid for x in r.json())

        upd = {**payload, "plan_name": "Updated Plan", "premium_amount": 30000}
        r = requests.put(f"{BASE_URL}/api/insurance/{pid}", json=upd, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["plan_name"] == "Updated Plan"
        assert r.json()["premium_amount"] == 30000

        r = requests.delete(f"{BASE_URL}/api/insurance/{pid}", headers=auth_headers)
        assert r.status_code == 200
        r = requests.delete(f"{BASE_URL}/api/insurance/{pid}", headers=auth_headers)
        assert r.status_code == 404
