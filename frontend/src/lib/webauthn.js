import api from "@/lib/api";

const b64urlToBytes = (s) =>
  Uint8Array.from(
    atob(s.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (s.length % 4)) % 4)),
    (c) => c.charCodeAt(0)
  );

const bytesToB64url = (buf) =>
  btoa(String.fromCharCode(...new Uint8Array(buf)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");

export const biometricSupported = () =>
  typeof window !== "undefined" && !!window.PublicKeyCredential && !!navigator.credentials;

const CRED_KEY = "vault_bio_cred";
export const getLocalCredId = () => localStorage.getItem(CRED_KEY);
export const clearLocalCredId = () => localStorage.removeItem(CRED_KEY);
export const deviceBioEnabled = (status) =>
  !!status?.enabled && !!getLocalCredId() && (status.credential_ids || []).includes(getLocalCredId());

export async function registerPasskey() {
  const { data: o } = await api.post("/webauthn/register/options");
  const publicKey = {
    ...o,
    challenge: b64urlToBytes(o.challenge),
    user: { ...o.user, id: b64urlToBytes(o.user.id) },
    excludeCredentials: (o.excludeCredentials || []).map((c) => ({ ...c, id: b64urlToBytes(c.id) })),
  };
  const cred = await navigator.credentials.create({ publicKey });
  if (!cred) throw new Error("Registration cancelled");
  const r = cred.response;
  await api.post("/webauthn/register/verify", {
    id: cred.id,
    rawId: bytesToB64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bytesToB64url(r.clientDataJSON),
      attestationObject: bytesToB64url(r.attestationObject),
    },
    clientExtensionResults: cred.getClientExtensionResults(),
    authenticatorAttachment: cred.authenticatorAttachment,
  });
  localStorage.setItem(CRED_KEY, cred.id);
}

export async function unlockWithPasskey() {
  const localId = getLocalCredId();
  const { data: o } = await api.post("/webauthn/auth/options", localId ? { credential_id: localId } : {});
  const publicKey = {
    ...o,
    challenge: b64urlToBytes(o.challenge),
    allowCredentials: (o.allowCredentials || []).map((c) => ({ ...c, id: b64urlToBytes(c.id) })),
  };
  const cred = await navigator.credentials.get({ publicKey });
  if (!cred) throw new Error("Cancelled");
  const r = cred.response;
  const { data } = await api.post("/webauthn/auth/verify", {
    id: cred.id,
    rawId: bytesToB64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bytesToB64url(r.clientDataJSON),
      authenticatorData: bytesToB64url(r.authenticatorData),
      signature: bytesToB64url(r.signature),
      userHandle: r.userHandle ? bytesToB64url(r.userHandle) : null,
    },
    clientExtensionResults: cred.getClientExtensionResults(),
    authenticatorAttachment: cred.authenticatorAttachment,
  });
  return data.token;
}
