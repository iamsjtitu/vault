import { useState, useEffect } from "react";
import { toast } from "sonner";
import { Fingerprint } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import api, { setToken, errDetail } from "@/lib/api";
import { biometricSupported, registerPasskey, getLocalCredId, clearLocalCredId, deviceBioEnabled } from "@/lib/webauthn";

export default function ChangePinDialog({ open, onOpenChange, lockMinutes, onLockMinutesChange }) {
  const [oldPin, setOldPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [saving, setSaving] = useState(false);
  const [bioStatus, setBioStatus] = useState(null);
  const [bioBusy, setBioBusy] = useState(false);
  const bioSupported = biometricSupported();
  const thisDeviceEnabled = deviceBioEnabled(bioStatus);
  const otherDevices = (bioStatus?.count || 0) - (thisDeviceEnabled ? 1 : 0);

  const refreshBio = () => {
    api.get("/webauthn/status").then(({ data }) => setBioStatus(data)).catch(() => {});
  };

  useEffect(() => {
    if (open && bioSupported) refreshBio();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, bioSupported]);

  const enableBio = async () => {
    setBioBusy(true);
    try {
      await registerPasskey();
      refreshBio();
      toast.success("Biometric unlock enabled on this device");
    } catch (e) {
      if (e?.name !== "NotAllowedError" && e?.name !== "AbortError") {
        toast.error(e?.response ? errDetail(e) : "Could not enable biometric unlock");
      }
    } finally {
      setBioBusy(false);
    }
  };

  const disableBio = async () => {
    setBioBusy(true);
    try {
      await api.delete("/webauthn/credentials", { params: { credential_id: getLocalCredId() } });
      clearLocalCredId();
      refreshBio();
      toast.success("Biometric unlock disabled on this device");
    } catch (e) {
      toast.error(errDetail(e));
    } finally {
      setBioBusy(false);
    }
  };

  const removeAllBio = async () => {
    setBioBusy(true);
    try {
      await api.delete("/webauthn/credentials");
      clearLocalCredId();
      refreshBio();
      toast.success("Biometric unlock removed from all devices");
    } catch (e) {
      toast.error(errDetail(e));
    } finally {
      setBioBusy(false);
    }
  };

  const digits = (v) => v.replace(/\D/g, "").slice(0, 4);

  const reset = () => {
    setOldPin("");
    setNewPin("");
    setConfirmPin("");
  };

  const submit = async () => {
    if (newPin.length !== 4) return toast.error("New PIN must be 4 digits");
    if (newPin !== confirmPin) return toast.error("New PINs don't match");
    setSaving(true);
    try {
      await api.post("/auth/change-pin", { old_pin: oldPin, new_pin: newPin });
      try {
        const { data } = await api.post("/auth/unlock", { pin: newPin });
        setToken(data.token);
      } catch {
        // will re-lock on next request; user unlocks with new PIN
      }
      toast.success("PIN changed successfully");
      reset();
      onOpenChange(false);
    } catch (e) {
      toast.error(errDetail(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) reset(); onOpenChange(o); }}>
      <DialogContent className="max-w-sm rounded-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading">Settings</DialogTitle>
          <DialogDescription>Auto-lock timing aur Master PIN yahan se manage karo.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label>Auto-Lock After (inactivity)</Label>
            <div className="flex gap-2">
              {[2, 5, 10].map((m) => (
                <button
                  key={m}
                  type="button"
                  data-testid={`lock-time-${m}`}
                  onClick={() => onLockMinutesChange(m)}
                  className={`flex-1 py-2 rounded-full text-sm font-medium transition-colors active:scale-95 ${
                    lockMinutes === m ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {m} min
                </button>
              ))}
            </div>
          </div>
          <div className="border-t border-slate-200 pt-4 space-y-2">
            <Label className="flex items-center gap-1.5">
              <Fingerprint className="w-4 h-4 text-emerald-600" /> Biometric Unlock
            </Label>
            {!bioSupported ? (
              <p className="text-xs text-slate-400" data-testid="biometric-unsupported">
                Is browser me fingerprint/face unlock supported nahi hai.
              </p>
            ) : bioStatus === null ? (
              <p className="text-xs text-slate-400">Loading...</p>
            ) : thisDeviceEnabled ? (
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-slate-500" data-testid="biometric-this-device-status">
                  Is device pe enabled hai{otherDevices > 0 ? ` (+${otherDevices} aur device)` : ""}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  data-testid="biometric-disable-button"
                  onClick={disableBio}
                  disabled={bioBusy}
                  className="rounded-full text-rose-600 border-rose-200 hover:bg-rose-50"
                >
                  {bioBusy ? "..." : "Disable"}
                </Button>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs text-slate-500" data-testid="biometric-this-device-status">
                  {otherDevices > 0
                    ? `${otherDevices} device pe enabled hai — is device pe bhi enable karo`
                    : "Fingerprint/face se vault unlock karo"}
                </p>
                <Button
                  type="button"
                  size="sm"
                  data-testid="biometric-enable-button"
                  onClick={enableBio}
                  disabled={bioBusy}
                  className="rounded-full bg-emerald-600 hover:bg-emerald-700"
                >
                  {bioBusy ? "Waiting..." : "Enable"}
                </Button>
              </div>
            )}
            {bioSupported && (bioStatus?.count || 0) > (thisDeviceEnabled ? 1 : 0) && (
              <button
                type="button"
                data-testid="biometric-remove-all-button"
                onClick={removeAllBio}
                disabled={bioBusy}
                className="text-xs text-rose-500 hover:text-rose-700 underline underline-offset-2"
              >
                Sab devices se biometric hatao
              </button>
            )}
          </div>
          <div className="border-t border-slate-200 pt-4">
            <p className="text-sm font-medium text-slate-900 mb-3">Change Master PIN</p>
          </div>
          <div className="space-y-1.5">
            <Label>Current PIN</Label>
            <Input
              data-testid="old-pin-input"
              type="password"
              inputMode="numeric"
              placeholder="••••"
              value={oldPin}
              onChange={(e) => setOldPin(digits(e.target.value))}
              className="rounded-xl font-mono tracking-widest"
            />
          </div>
          <div className="space-y-1.5">
            <Label>New PIN</Label>
            <Input
              data-testid="new-pin-input"
              type="password"
              inputMode="numeric"
              placeholder="••••"
              value={newPin}
              onChange={(e) => setNewPin(digits(e.target.value))}
              className="rounded-xl font-mono tracking-widest"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Confirm New PIN</Label>
            <Input
              data-testid="confirm-pin-input"
              type="password"
              inputMode="numeric"
              placeholder="••••"
              value={confirmPin}
              onChange={(e) => setConfirmPin(digits(e.target.value))}
              className="rounded-xl font-mono tracking-widest"
            />
          </div>
          <Button
            data-testid="change-pin-submit"
            onClick={submit}
            disabled={saving}
            className="w-full rounded-full h-11 bg-slate-900 hover:bg-slate-700"
          >
            {saving ? "Changing..." : "Change PIN"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
