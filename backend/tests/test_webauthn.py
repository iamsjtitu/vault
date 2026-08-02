import base64
import hashlib
import json
import os

import cbor2
import pytest
import requests
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

BASE_URL = "http://localhost:8001"
PIN = "1234"
RP_HOST = "testvault.local"
ORIGIN = f"https://{RP_HOST}"
HDRS = {"Origin": ORIGIN, "Host": RP_HOST}


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class FakeAuthenticator:
    """Minimal software authenticator (EC P-256, UV flag set, fmt=none)."""

    def __init__(self):
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.cred_id = os.urandom(32)
        self.sign_count = 0

    def _cose_key(self) -> bytes:
        nums = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")})

    def create(self, options: dict) -> dict:
        client_data = json.dumps({
            "type": "webauthn.create",
            "challenge": options["challenge"],
            "origin": ORIGIN,
            "crossOrigin": False,
        }).encode()
        rp_hash = hashlib.sha256(options["rp"]["id"].encode()).digest()
        attested = bytes(16) + len(self.cred_id).to_bytes(2, "big") + self.cred_id + self._cose_key()
        auth_data = rp_hash + bytes([0x45]) + self.sign_count.to_bytes(4, "big") + attested
        att_obj = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": b64url(self.cred_id),
            "rawId": b64url(self.cred_id),
            "type": "public-key",
            "response": {"clientDataJSON": b64url(client_data), "attestationObject": b64url(att_obj)},
            "clientExtensionResults": {},
        }

    def get(self, options: dict, tamper_challenge: bool = False) -> dict:
        self.sign_count += 1
        challenge = b64url(os.urandom(32)) if tamper_challenge else options["challenge"]
        client_data = json.dumps({
            "type": "webauthn.get",
            "challenge": challenge,
            "origin": ORIGIN,
            "crossOrigin": False,
        }).encode()
        rp_hash = hashlib.sha256(options["rpId"].encode()).digest()
        auth_data = rp_hash + bytes([0x05]) + self.sign_count.to_bytes(4, "big")
        sig = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        return {
            "id": b64url(self.cred_id),
            "rawId": b64url(self.cred_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64url(client_data),
                "authenticatorData": b64url(auth_data),
                "signature": b64url(sig),
                "userHandle": None,
            },
            "clientExtensionResults": {},
        }


@pytest.fixture(scope="module")
def token():
    r = requests.get(f"{BASE_URL}/api/auth/status")
    if not r.json()["pin_set"]:
        r = requests.post(f"{BASE_URL}/api/auth/setup", json={"pin": PIN})
    else:
        r = requests.post(f"{BASE_URL}/api/auth/unlock", json={"pin": PIN})
    return r.json()["token"]


@pytest.fixture
def auth_hdrs(token):
    return {**HDRS, "Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def cleanup(auth_hdrs):
    yield
    requests.delete(f"{BASE_URL}/api/webauthn/credentials", headers=auth_hdrs)


def test_status_disabled_initially():
    r = requests.get(f"{BASE_URL}/api/webauthn/status", headers=HDRS)
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_register_requires_auth():
    r = requests.post(f"{BASE_URL}/api/webauthn/register/options", headers=HDRS)
    assert r.status_code == 401


def test_auth_options_404_without_credentials():
    r = requests.post(f"{BASE_URL}/api/webauthn/auth/options", headers=HDRS)
    assert r.status_code == 404


def test_cross_origin_rejected(token):
    r = requests.post(
        f"{BASE_URL}/api/webauthn/register/options",
        headers={"Origin": "https://evil.com", "Host": RP_HOST, "Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_full_ceremony_register_and_unlock(auth_hdrs):
    device = FakeAuthenticator()

    r = requests.post(f"{BASE_URL}/api/webauthn/register/options", headers=auth_hdrs)
    assert r.status_code == 200
    opts = r.json()
    assert opts["rp"]["id"] == RP_HOST

    r = requests.post(f"{BASE_URL}/api/webauthn/register/verify", headers=auth_hdrs, json=device.create(opts))
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is True

    r = requests.get(f"{BASE_URL}/api/webauthn/status", headers=HDRS)
    body = r.json()
    assert body["enabled"] is True and body["count"] == 1
    assert body["credential_ids"] == [b64url(device.cred_id)]

    r = requests.post(f"{BASE_URL}/api/webauthn/auth/options", headers=HDRS)
    assert r.status_code == 200
    auth_opts = r.json()
    assert auth_opts["rpId"] == RP_HOST

    r = requests.post(f"{BASE_URL}/api/webauthn/auth/verify", headers=HDRS, json=device.get(auth_opts))
    assert r.status_code == 200, r.text
    new_token = r.json()["token"]

    r = requests.get(f"{BASE_URL}/api/credentials", headers={"Authorization": f"Bearer {new_token}"})
    assert r.status_code == 200


def test_replay_and_tampered_assertion_rejected(auth_hdrs):
    device = FakeAuthenticator()
    opts = requests.post(f"{BASE_URL}/api/webauthn/register/options", headers=auth_hdrs).json()
    requests.post(f"{BASE_URL}/api/webauthn/register/verify", headers=auth_hdrs, json=device.create(opts))

    auth_opts = requests.post(f"{BASE_URL}/api/webauthn/auth/options", headers=HDRS).json()
    assertion = device.get(auth_opts)
    r = requests.post(f"{BASE_URL}/api/webauthn/auth/verify", headers=HDRS, json=assertion)
    assert r.status_code == 200

    r = requests.post(f"{BASE_URL}/api/webauthn/auth/verify", headers=HDRS, json=assertion)
    assert r.status_code in (400, 401)

    auth_opts = requests.post(f"{BASE_URL}/api/webauthn/auth/options", headers=HDRS).json()
    r = requests.post(f"{BASE_URL}/api/webauthn/auth/verify", headers=HDRS, json=device.get(auth_opts, tamper_challenge=True))
    assert r.status_code == 401


def test_unknown_credential_rejected(auth_hdrs):
    device = FakeAuthenticator()
    opts = requests.post(f"{BASE_URL}/api/webauthn/register/options", headers=auth_hdrs).json()
    requests.post(f"{BASE_URL}/api/webauthn/register/verify", headers=auth_hdrs, json=device.create(opts))

    stranger = FakeAuthenticator()
    auth_opts = requests.post(f"{BASE_URL}/api/webauthn/auth/options", headers=HDRS).json()
    r = requests.post(f"{BASE_URL}/api/webauthn/auth/verify", headers=HDRS, json=stranger.get(auth_opts))
    assert r.status_code == 401


def test_multi_device_register_and_targeted_unlock(auth_hdrs):
    android = FakeAuthenticator()
    iphone = FakeAuthenticator()
    for device in (android, iphone):
        opts = requests.post(f"{BASE_URL}/api/webauthn/register/options", headers=auth_hdrs).json()
        r = requests.post(f"{BASE_URL}/api/webauthn/register/verify", headers=auth_hdrs, json=device.create(opts))
        assert r.status_code == 200, r.text

    status = requests.get(f"{BASE_URL}/api/webauthn/status", headers=HDRS).json()
    assert status["count"] == 2
    assert set(status["credential_ids"]) == {b64url(android.cred_id), b64url(iphone.cred_id)}

    for device in (android, iphone):
        auth_opts = requests.post(
            f"{BASE_URL}/api/webauthn/auth/options", headers=HDRS,
            json={"credential_id": b64url(device.cred_id)},
        ).json()
        assert [c["id"] for c in auth_opts["allowCredentials"]] == [b64url(device.cred_id)]
        r = requests.post(f"{BASE_URL}/api/webauthn/auth/verify", headers=HDRS, json=device.get(auth_opts))
        assert r.status_code == 200, r.text

    r = requests.delete(
        f"{BASE_URL}/api/webauthn/credentials",
        headers=auth_hdrs, params={"credential_id": b64url(android.cred_id)},
    )
    assert r.json()["deleted"] == 1
    status = requests.get(f"{BASE_URL}/api/webauthn/status", headers=HDRS).json()
    assert status["credential_ids"] == [b64url(iphone.cred_id)]

    auth_opts = requests.post(f"{BASE_URL}/api/webauthn/auth/options", headers=HDRS, json={}).json()
    r = requests.post(f"{BASE_URL}/api/webauthn/auth/verify", headers=HDRS, json=iphone.get(auth_opts))
    assert r.status_code == 200


def test_disable_biometric(auth_hdrs):
    device = FakeAuthenticator()
    opts = requests.post(f"{BASE_URL}/api/webauthn/register/options", headers=auth_hdrs).json()
    requests.post(f"{BASE_URL}/api/webauthn/register/verify", headers=auth_hdrs, json=device.create(opts))

    r = requests.delete(f"{BASE_URL}/api/webauthn/credentials", headers=auth_hdrs)
    assert r.status_code == 200
    assert r.json()["deleted"] >= 1

    r = requests.get(f"{BASE_URL}/api/webauthn/status", headers=HDRS)
    assert r.json()["enabled"] is False
    r = requests.post(f"{BASE_URL}/api/webauthn/auth/options", headers=HDRS)
    assert r.status_code == 404
