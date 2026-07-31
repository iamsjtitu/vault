import { useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import api, { errDetail } from "@/lib/api";

export default function ChangePinDialog({ open, onOpenChange }) {
  const [oldPin, setOldPin] = useState("");
  const [newPin, setNewPin] = useState("");
  const [confirmPin, setConfirmPin] = useState("");
  const [saving, setSaving] = useState(false);

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
          <DialogTitle className="font-heading">Change Master PIN</DialogTitle>
          <DialogDescription>Enter your current PIN and choose a new 4-digit PIN.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
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
