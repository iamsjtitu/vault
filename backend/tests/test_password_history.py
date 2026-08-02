"""Backend tests for Password History feature (iteration 11)"""
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


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(autouse=True)
def clear_lockout(mongo_db):
    mongo_db.login_attempts.delete_many({})
    yield


@pytest.fixture
def auth_headers(mongo_db):
    r = requests.get(f"{BASE_URL}/api/auth/status")
    if not r.json()["pin_set"]:
        requests.post(f"{BASE_URL}/api/auth/setup", json={"pin": PIN})
    r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


class TestPasswordHistory:
    def test_full_flow_and_dedupe(self, auth_headers):
        # Create
        payload = {"title": "TEST_PWHist", "category": "Bank", "username": "u",
                   "password": "AAA111!", "website": "", "notes": ""}
        r = requests.post(f"{BASE_URL}/api/credentials", json=payload, headers=auth_headers)
        assert r.status_code == 200, r.text
        cid = r.json()["id"]

        try:
            # Update 1: AAA -> BBB (should add AAA to history)
            upd = {**payload, "password": "BBB222@"}
            r = requests.put(f"{BASE_URL}/api/credentials/{cid}", json=upd, headers=auth_headers)
            assert r.status_code == 200
            assert r.json()["password"] == "BBB222@"

            # Update 2: BBB -> BBB (identical - must NOT push)
            r = requests.put(f"{BASE_URL}/api/credentials/{cid}", json=upd, headers=auth_headers)
            assert r.status_code == 200

            # Update 3: BBB -> CCC (adds BBB to history)
            upd2 = {**payload, "password": "CCC333#"}
            r = requests.put(f"{BASE_URL}/api/credentials/{cid}", json=upd2, headers=auth_headers)
            assert r.status_code == 200

            # Fetch history - expect newest first: BBB then AAA
            r = requests.get(f"{BASE_URL}/api/credentials/{cid}/password-history", headers=auth_headers)
            assert r.status_code == 200, r.text
            history = r.json()
            assert isinstance(history, list)
            assert len(history) == 2, f"Expected 2, got {len(history)}: {history}"
            assert history[0]["password"] == "BBB222@"
            assert history[1]["password"] == "AAA111!"
            assert history[0]["changed_at"] and "T" in history[0]["changed_at"]
            assert history[1]["changed_at"] and "T" in history[1]["changed_at"]

            # List endpoint MUST NOT leak password_history field
            r = requests.get(f"{BASE_URL}/api/credentials", headers=auth_headers)
            assert r.status_code == 200
            for c in r.json():
                assert "password_history" not in c, f"Leak: {c}"

            # Same-password update shouldn't add
            r = requests.put(f"{BASE_URL}/api/credentials/{cid}", json=upd2, headers=auth_headers)
            assert r.status_code == 200
            r = requests.get(f"{BASE_URL}/api/credentials/{cid}/password-history", headers=auth_headers)
            assert len(r.json()) == 2
        finally:
            requests.delete(f"{BASE_URL}/api/credentials/{cid}", headers=auth_headers)

    def test_history_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/credentials/nonexistent/password-history")
        assert r.status_code == 401

    def test_history_404_unknown(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/credentials/does-not-exist-xyz/password-history",
                         headers=auth_headers)
        assert r.status_code == 404

    def test_no_history_returns_empty(self, auth_headers):
        payload = {"title": "TEST_NoHist", "category": "Other", "password": "onlyone"}
        r = requests.post(f"{BASE_URL}/api/credentials", json=payload, headers=auth_headers)
        cid = r.json()["id"]
        try:
            r = requests.get(f"{BASE_URL}/api/credentials/{cid}/password-history", headers=auth_headers)
            assert r.status_code == 200
            assert r.json() == []
        finally:
            requests.delete(f"{BASE_URL}/api/credentials/{cid}", headers=auth_headers)

    def test_delete_credential_removes(self, auth_headers):
        payload = {"title": "TEST_DelHist", "category": "Other", "password": "p1"}
        r = requests.post(f"{BASE_URL}/api/credentials", json=payload, headers=auth_headers)
        cid = r.json()["id"]
        # add history
        upd = {**payload, "password": "p2"}
        requests.put(f"{BASE_URL}/api/credentials/{cid}", json=upd, headers=auth_headers)
        # delete
        r = requests.delete(f"{BASE_URL}/api/credentials/{cid}", headers=auth_headers)
        assert r.status_code == 200
        r = requests.get(f"{BASE_URL}/api/credentials/{cid}/password-history", headers=auth_headers)
        assert r.status_code == 404
