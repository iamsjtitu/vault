import { useState, useEffect, useRef, useCallback } from "react";
import { Delete, ShieldCheck, Fingerprint } from "lucide-react";
import { toast } from "sonner";
import api, { setToken, errDetail } from "@/lib/api";
import { biometricSupported, unlockWithPasskey, deviceBioEnabled } from "@/lib/webauthn";

const PIN_LENGTH = 4;

export default function PinScreen({ mode, onUnlock }) {
  const [pin, setPin] = useState("");
  const [firstPin, setFirstPin] = useState(null);
  const [shake, setShake] = useState(false);
  const [busy, setBusy] = useState(false);
  const [bioAvailable, setBioAvailable] = useState(false);
  const autoTriedRef = useRef(false);

  const bioUnlock = useCallback(async () => {
    setBusy(true);
    try {
      const token = await unlockWithPasskey();
      setToken(token);
      onUnlock();
    } catch (e) {
      if (e?.name !== "NotAllowedError" && e?.name !== "AbortError") {
        toast.error(e?.response ? errDetail(e) : "Biometric unlock failed");
      }
    } finally {
      setBusy(false);
    }
  }, [onUnlock]);

  useEffect(() => {
    if (mode === "locked" && biometricSupported()) {
      api
        .get("/webauthn/status")
        .then(({ data }) => {
          const ok = deviceBioEnabled(data);
          setBioAvailable(ok);
          if (ok && !autoTriedRef.current) {
            autoTriedRef.current = true;
            setTimeout(bioUnlock, 350);
          }
        })
        .catch(() => {});
    }
  }, [mode, bioUnlock]);

  const isSetup = mode === "setup";
  const title = isSetup ? (firstPin ? "Confirm your PIN" : "Create a Master PIN") : "Enter your PIN";
  const subtitle = isSetup
    ? firstPin
      ? "Re-enter the same 4-digit PIN"
      : "This PIN will unlock your vault"
    : "Unlock your vault";

  const fail = (msg) => {
    toast.error(msg);
    setShake(true);
    setTimeout(() => setShake(false), 350);
    setPin("");
  };

  const submit = async (fullPin) => {
    if (busy) return;
    if (isSetup && !firstPin) {
      setFirstPin(fullPin);
      setPin("");
      return;
    }
    if (isSetup && fullPin !== firstPin) {
      setFirstPin(null);
      fail("PINs don't match, try again");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post(isSetup ? "/auth/setup" : "/auth/unlock", { pin: fullPin });
      setToken(data.token);
      onUnlock();
    } catch (e) {
      fail(errDetail(e));
    } finally {
      setBusy(false);
    }
  };

  const press = (d) => {
    if (pin.length >= PIN_LENGTH || busy) return;
    const next = pin + d;
    setPin(next);
    if (next.length === PIN_LENGTH) setTimeout(() => submit(next), 150);
  };

  useEffect(() => {
    const onKey = (e) => {
      if (e.key >= "0" && e.key <= "9") press(e.key);
      else if (e.key === "Backspace") setPin((p) => p.slice(0, -1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-6" data-testid="pin-screen">
      <div className="fade-up flex flex-col items-center">
        <div className="w-16 h-16 rounded-2xl bg-slate-900 flex items-center justify-center mb-6">
          <ShieldCheck className="w-8 h-8 text-white" />
        </div>
        <h1 className="font-heading text-2xl font-semibold tracking-tight text-slate-900" data-testid="pin-title">
          {title}
        </h1>
        <p className="text-sm text-slate-500 mt-2">{subtitle}</p>

        <div className={`flex gap-4 my-10 ${shake ? "pin-shake" : ""}`} data-testid="pin-dots">
          {Array.from({ length: PIN_LENGTH }).map((_, i) => (
            <div
              key={`pin-dot-${i}`}
              className={`w-4 h-4 rounded-full ${
                i < pin.length ? "bg-slate-900 pin-dot-filled" : "bg-slate-200"
              }`}
            />
          ))}
        </div>

        <div className="grid grid-cols-3 gap-3">
          {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => (
            <button
              key={d}
              data-testid={`pin-button-${d}`}
              onClick={() => press(String(d))}
              className="w-[72px] h-[72px] rounded-full text-2xl font-medium text-slate-900 hover:bg-slate-200 active:scale-95 active:bg-slate-300 transition-colors"
            >
              {d}
            </button>
          ))}
          <div />
          <button
            data-testid="pin-button-0"
            onClick={() => press("0")}
            className="w-[72px] h-[72px] rounded-full text-2xl font-medium text-slate-900 hover:bg-slate-200 active:scale-95 active:bg-slate-300 transition-colors"
          >
            0
          </button>
          <button
            data-testid="pin-backspace"
            aria-label="Backspace"
            onClick={() => setPin(pin.slice(0, -1))}
            className="w-[72px] h-[72px] rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-200 active:scale-95 transition-colors"
          >
            <Delete className="w-6 h-6" />
          </button>
        </div>

        {bioAvailable && (
          <button
            data-testid="biometric-unlock-button"
            onClick={bioUnlock}
            disabled={busy}
            className="mt-8 flex items-center gap-2 px-5 py-2.5 rounded-full bg-white border border-slate-200 text-sm font-medium text-slate-700 hover:bg-slate-100 active:scale-95 transition-colors shadow-sm"
          >
            <Fingerprint className="w-4 h-4 text-emerald-600" />
            Unlock with fingerprint / face
          </button>
        )}
      </div>
    </div>
  );
}
