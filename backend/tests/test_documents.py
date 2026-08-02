"""Backend tests for MyVault Documents feature (GridFS + Fernet encrypted at rest)."""
import io
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

# minimal valid PDF bytes
PDF_BYTES = (b"%PDF-1.4\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
             b"2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n"
             b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>endobj\n"
             b"xref\n0 4\n0000000000 65535 f \ntrailer<< /Size 4 /Root 1 0 R >>\n%%EOF")


@pytest.fixture(scope="session")
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
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def credential(auth_headers):
    r = requests.post(f"{BASE_URL}/api/credentials",
                      json={"title": "TEST_DocParent", "category": "Other", "member_name": "Self"},
                      headers=auth_headers)
    assert r.status_code == 200
    cid = r.json()["id"]
    yield cid
    # ensure deletion at teardown (idempotent)
    requests.delete(f"{BASE_URL}/api/credentials/{cid}", headers=auth_headers)


class TestDocumentUpload:
    def test_upload_requires_auth(self, credential):
        r = requests.post(
            f"{BASE_URL}/api/documents/upload",
            params={"parent_type": "credential", "parent_id": credential},
            files={"file": ("t.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
        )
        assert r.status_code == 401

    def test_upload_invalid_parent_type(self, auth_headers, credential):
        r = requests.post(
            f"{BASE_URL}/api/documents/upload",
            params={"parent_type": "invalid", "parent_id": credential},
            files={"file": ("t.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert "parent" in r.json()["detail"].lower()

    def test_upload_disallowed_extension(self, auth_headers, credential):
        r = requests.post(
            f"{BASE_URL}/api/documents/upload",
            params={"parent_type": "credential", "parent_id": credential},
            files={"file": ("evil.exe", io.BytesIO(b"MZ\x00\x00"), "application/x-msdownload")},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert ".exe" in r.json()["detail"].lower()

    def test_upload_too_large(self, auth_headers, credential):
        big = b"a" * (10 * 1024 * 1024 + 100)
        r = requests.post(
            f"{BASE_URL}/api/documents/upload",
            params={"parent_type": "credential", "parent_id": credential},
            files={"file": ("big.pdf", io.BytesIO(big), "application/pdf")},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert "10 mb" in r.json()["detail"].lower()

    def test_upload_success_returns_metadata_no_gridfs_leak(self, auth_headers, credential):
        r = requests.post(
            f"{BASE_URL}/api/documents/upload",
            params={"parent_type": "credential", "parent_id": credential},
            files={"file": ("hello.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["filename"] == "hello.pdf"
        assert j["content_type"] == "application/pdf"
        assert j["size"] == len(PDF_BYTES)
        assert "id" in j and isinstance(j["id"], str) and len(j["id"]) > 10
        # no leakage of internal identifiers
        assert "gridfs_id" not in j
        assert "_id" not in j
        # cleanup
        requests.delete(f"{BASE_URL}/api/documents/{j['id']}", headers=auth_headers)


class TestDocumentListDownloadDelete:
    def test_list_download_delete_flow(self, auth_headers, credential, mongo_db):
        # upload
        r = requests.post(
            f"{BASE_URL}/api/documents/upload",
            params={"parent_type": "credential", "parent_id": credential},
            files={"file": ("doc1.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
            headers=auth_headers,
        )
        assert r.status_code == 200
        did = r.json()["id"]

        # list — no gridfs_id / _id leaked
        r = requests.get(f"{BASE_URL}/api/documents",
                         params={"parent_type": "credential", "parent_id": credential},
                         headers=auth_headers)
        assert r.status_code == 200
        docs = r.json()
        assert any(d["id"] == did for d in docs)
        target = next(d for d in docs if d["id"] == did)
        assert "gridfs_id" not in target
        assert "_id" not in target
        assert target["filename"] == "doc1.pdf"
        assert target["size"] == len(PDF_BYTES)

        # download — bytes match, correct content-type + disposition
        r = requests.get(f"{BASE_URL}/api/documents/{did}/download", headers=auth_headers)
        assert r.status_code == 200
        assert r.content == PDF_BYTES
        assert r.headers["content-type"].startswith("application/pdf")
        assert 'filename="doc1.pdf"' in r.headers["content-disposition"]

        # gridfs at-rest encryption verification
        # find fs.files entry for this doc, then check its chunks are Fernet-encrypted
        mongo_doc = mongo_db.documents.find_one({"id": did})
        assert mongo_doc is not None
        from bson import ObjectId
        gridfs_id = ObjectId(mongo_doc["gridfs_id"])
        chunks = list(mongo_db.fs.chunks.find({"files_id": gridfs_id}))
        assert len(chunks) >= 1
        raw = b"".join(c["data"] for c in chunks)
        # Fernet tokens (raw bytes) start with b"\x80" version byte; base64-encoded form starts with 'gAAAA'
        import base64
        # Fernet.encrypt returns urlsafe-base64 bytes → stored as-is in GridFS
        assert raw.startswith(b"gAAAA"), raw[:20]
        # crucially it does NOT contain the raw PDF header
        assert b"%PDF" not in raw

        # delete
        r = requests.delete(f"{BASE_URL}/api/documents/{did}", headers=auth_headers)
        assert r.status_code == 200

        # verify both metadata + gridfs file gone
        assert mongo_db.documents.find_one({"id": did}) is None
        assert mongo_db.fs.files.find_one({"_id": gridfs_id}) is None
        assert mongo_db.fs.chunks.find_one({"files_id": gridfs_id}) is None

        # download after delete → 404
        r = requests.get(f"{BASE_URL}/api/documents/{did}/download", headers=auth_headers)
        assert r.status_code == 404


class TestParentDeletionCascade:
    def test_delete_credential_cascades_documents(self, auth_headers, mongo_db):
        # create parent credential
        r = requests.post(f"{BASE_URL}/api/credentials",
                          json={"title": "TEST_CascadeParent", "category": "Other"},
                          headers=auth_headers)
        assert r.status_code == 200
        cid = r.json()["id"]

        # attach 2 docs
        for name in ("a.pdf", "b.txt"):
            data = PDF_BYTES if name.endswith(".pdf") else b"hello txt"
            ct = "application/pdf" if name.endswith(".pdf") else "text/plain"
            r = requests.post(
                f"{BASE_URL}/api/documents/upload",
                params={"parent_type": "credential", "parent_id": cid},
                files={"file": (name, io.BytesIO(data), ct)},
                headers=auth_headers,
            )
            assert r.status_code == 200, r.text

        # confirm 2 docs present
        assert mongo_db.documents.count_documents({"parent_type": "credential", "parent_id": cid}) == 2
        files_before = mongo_db.fs.files.count_documents({})

        # delete parent credential
        r = requests.delete(f"{BASE_URL}/api/credentials/{cid}", headers=auth_headers)
        assert r.status_code == 200

        # cascade: documents collection empty for this parent, fs.files count decreased by 2
        assert mongo_db.documents.count_documents({"parent_type": "credential", "parent_id": cid}) == 0
        files_after = mongo_db.fs.files.count_documents({})
        assert files_after == files_before - 2, f"fs.files: {files_before} -> {files_after}"


class TestExistingSeedDocument:
    """Iteration 5 seed: LIC insurance (bc63fc20-091f-45cb-8d4c-f7c2a9ee502a) has test_policy.pdf attached."""
    def test_lic_has_seed_document(self, auth_headers):
        LIC_ID = "bc63fc20-091f-45cb-8d4c-f7c2a9ee502a"
        r = requests.get(f"{BASE_URL}/api/documents",
                         params={"parent_type": "insurance", "parent_id": LIC_ID},
                         headers=auth_headers)
        assert r.status_code == 200
        docs = r.json()
        # If seed present, verify it; otherwise skip (main agent might have cleaned)
        if not docs:
            pytest.skip("No seed document present for LIC")
        assert any(d["filename"] == "test_policy.pdf" for d in docs), [d["filename"] for d in docs]
