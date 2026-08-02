"""Security hardening tests: token versioning, progressive lockout, security headers,
document upload sanitation, CORS restriction, auth on all protected endpoints."""
import io
import os
import time
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
ALLOWED_ORIGIN = "https://vault-login-6.preview.emergentagent.com"
EVIL_ORIGIN = "https://evil.example.com"


@pytest.fixture(scope="module")
def mongo_db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(autouse=True)
def clear_lockout(mongo_db):
    mongo_db.login_attempts.delete_many({})
    yield
    mongo_db.login_attempts.delete_many({})


def _unlock(pin=PIN):
    r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": pin})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture
def token():
    return _unlock()


@pytest.fixture
def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- 1. Token revocation on change-pin ----------
class TestTokenRevocation:
    def test_old_token_revoked_after_pin_change(self, mongo_db):
        token_a = _unlock(PIN)
        h_a = {"Authorization": f"Bearer {token_a}"}
        # confirm A works
        r = requests.get(f"{BASE_URL}/api/credentials", headers=h_a)
        assert r.status_code == 200
        # change PIN 1234 -> 5678
        r = requests.post(f"{BASE_URL}/api/auth/change-pin",
                          json={"old_pin": PIN, "new_pin": "5678"}, headers=h_a)
        assert r.status_code == 200, r.text
        try:
            # token A must now be invalid
            r = requests.get(f"{BASE_URL}/api/credentials", headers=h_a)
            assert r.status_code == 401, f"Expected 401, got {r.status_code}"
            # new PIN unlocks
            token_b = _unlock("5678")
            h_b = {"Authorization": f"Bearer {token_b}"}
            r = requests.get(f"{BASE_URL}/api/credentials", headers=h_b)
            assert r.status_code == 200
        finally:
            # revert to 1234 with a fresh token
            token_b = _unlock("5678")
            h_b = {"Authorization": f"Bearer {token_b}"}
            r = requests.post(f"{BASE_URL}/api/auth/change-pin",
                              json={"old_pin": "5678", "new_pin": PIN}, headers=h_b)
            assert r.status_code == 200
            # confirm 1234 restored
            assert requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN}).status_code == 200


# ---------- 2. Progressive lockout ----------
class TestProgressiveLockout:
    def test_five_wrong_pins_locks(self, mongo_db):
        mongo_db.login_attempts.delete_many({})
        for i in range(5):
            r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": "9999"})
            assert r.status_code == 401, f"attempt {i+1} => {r.status_code}"
        # 6th attempt should be 429
        r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN})
        assert r.status_code == 429, r.text
        detail = r.json().get("detail", "")
        assert "min" in detail.lower()
        # DB persists count
        rec = mongo_db.login_attempts.find_one({"identifier": "vault"})
        assert rec and rec.get("count", 0) >= 5
        # Cleanup so subsequent tests can unlock
        mongo_db.login_attempts.delete_many({})
        r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN})
        assert r.status_code == 200


# ---------- 3. Security headers ----------
class TestSecurityHeaders:
    def test_headers_present(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/auth/status")
        h = {k.lower(): v for k, v in r.headers.items()}
        assert h.get("x-frame-options") == "DENY"
        assert h.get("x-content-type-options") == "nosniff"
        assert "strict-transport-security" in h
        assert "referrer-policy" in h
        assert "permissions-policy" in h
        # /api path => Cache-Control no-store
        assert "no-store" in h.get("cache-control", "").lower()


# ---------- 4. Document upload hardening ----------
class TestDocumentUploadHardening:
    def _make_cred(self, headers):
        r = requests.post(f"{BASE_URL}/api/credentials",
                          json={"title": "TEST_SEC", "category": "Other"}, headers=headers)
        assert r.status_code == 200
        return r.json()["id"]

    def test_malicious_filename_sanitized_and_txt_downloads_as_attachment(self, auth_headers):
        cid = self._make_cred(auth_headers)
        try:
            evil_name = "../..<script>evil</script>.txt"
            files = {"file": (evil_name, b"hello world", "text/html")}  # client says html!
            r = requests.post(
                f"{BASE_URL}/api/documents/upload?parent_type=credential&parent_id={cid}",
                files=files, headers=auth_headers,
            )
            assert r.status_code == 200, r.text
            doc = r.json()
            fname = doc["filename"]
            # sanitized: no <, >, /, .. sequences
            for bad in ["<", ">", "/", ".."]:
                assert bad not in fname, f"filename still contains {bad!r}: {fname!r}"
            # content type derived from ext, NOT client-supplied
            assert doc["content_type"] == "text/plain"
            doc_id = doc["id"]

            # Download - Content-Type text/plain, attachment disposition
            r = requests.get(f"{BASE_URL}/api/documents/{doc_id}/download", headers=auth_headers)
            assert r.status_code == 200
            assert r.headers.get("Content-Type", "").startswith("text/plain")
            assert r.headers.get("Content-Disposition", "").startswith("attachment"), \
                r.headers.get("Content-Disposition")
            assert r.content == b"hello world"

            # cleanup doc
            requests.delete(f"{BASE_URL}/api/documents/{doc_id}", headers=auth_headers)
        finally:
            requests.delete(f"{BASE_URL}/api/credentials/{cid}", headers=auth_headers)

    @pytest.mark.parametrize("fname,ctype", [
        ("evil.exe", "application/octet-stream"),
        ("evil.html", "text/html"),
        ("evil.svg", "image/svg+xml"),
    ])
    def test_disallowed_extensions_rejected(self, auth_headers, fname, ctype):
        cid = self._make_cred(auth_headers)
        try:
            files = {"file": (fname, b"x", ctype)}
            r = requests.post(
                f"{BASE_URL}/api/documents/upload?parent_type=credential&parent_id={cid}",
                files=files, headers=auth_headers,
            )
            assert r.status_code == 400, f"{fname} got {r.status_code}: {r.text}"
        finally:
            requests.delete(f"{BASE_URL}/api/credentials/{cid}", headers=auth_headers)


# ---------- 5. All protected endpoints require valid token ----------
class TestProtectedEndpointsAuth:
    ENDPOINTS = [
        ("GET", "/api/credentials"),
        ("POST", "/api/credentials"),
        ("GET", "/api/cards"),
        ("POST", "/api/cards"),
        ("GET", "/api/insurance"),
        ("POST", "/api/insurance"),
        ("GET", "/api/documents?parent_type=credential&parent_id=x"),
        ("GET", "/api/documents/counts?parent_type=credential"),
        ("POST", "/api/documents/upload?parent_type=credential&parent_id=x"),
        ("GET", "/api/members"),
        ("POST", "/api/auth/change-pin"),
        ("POST", "/api/insurance/xyz/mark-paid"),
        ("POST", "/api/insurance/xyz/undo-paid"),
        ("GET", "/api/insurance/xyz/payments"),
    ]

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_no_token_returns_401(self, method, path):
        r = requests.request(method, f"{BASE_URL}{path}")
        assert r.status_code == 401, f"{method} {path} => {r.status_code}"

    @pytest.mark.parametrize("method,path", ENDPOINTS)
    def test_garbage_token_returns_401(self, method, path):
        r = requests.request(method, f"{BASE_URL}{path}",
                             headers={"Authorization": "Bearer garbage.token.here"})
        assert r.status_code == 401, f"{method} {path} => {r.status_code}"


# ---------- 6. CORS restriction ----------
# NOTE: The public preview URL sits behind an edge proxy (Cloudflare) that
# overwrites CORS headers to `*` on OPTIONS regardless of what the backend
# says. So CORS enforcement is verified by hitting the backend directly on
# localhost:8001 — that's what a real cross-origin browser would see once
# the user's own nginx (which does NOT rewrite CORS) is in front.
LOCAL_BACKEND = "http://localhost:8001"


class TestCORS:
    def test_allowed_origin_gets_echo(self):
        r = requests.options(
            f"{LOCAL_BACKEND}/api/auth/status",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        allow = r.headers.get("access-control-allow-origin", "")
        assert allow == ALLOWED_ORIGIN, f"expected echo of allowed origin, got {allow!r}"

    def test_evil_origin_not_allowed(self):
        r = requests.options(
            f"{LOCAL_BACKEND}/api/auth/status",
            headers={
                "Origin": EVIL_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        allow = r.headers.get("access-control-allow-origin", "")
        assert allow != EVIL_ORIGIN and allow != "*", \
            f"evil origin allowed! ACAO={allow!r}"
