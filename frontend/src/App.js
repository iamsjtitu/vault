import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import { Toaster, toast } from "sonner";
import { ShieldCheck, Lock, KeyRound, FileText, LogOut, Settings, CreditCard } from "lucide-react";
import api, { clearToken } from "@/lib/api";
import PinScreen from "@/components/PinScreen";
import CredentialsTab from "@/components/CredentialsTab";
import InsuranceTab from "@/components/InsuranceTab";
import CardsTab from "@/components/CardsTab";
import ChangePinDialog from "@/components/ChangePinDialog";

const AUTO_LOCK_MS = 5 * 60 * 1000;

function App() {
  const [phase, setPhase] = useState("loading"); // loading | setup | locked | unlocked
  const [tab, setTab] = useState("logins");
  const [settingsOpen, setSettingsOpen] = useState(false);

  const lock = useCallback(() => {
    clearToken();
    setPhase("locked");
  }, []);

  useEffect(() => {
    const id = api.interceptors.response.use(
      (r) => r,
      (e) => {
        if (
          e.response?.status === 401 &&
          !e.config?.url?.includes("/auth/change-pin") &&
          localStorage.getItem("vault_token")
        )
          lock();
        return Promise.reject(e);
      }
    );
    return () => api.interceptors.response.eject(id);
  }, [lock]);

  useEffect(() => {
    if (phase !== "unlocked") return;
    let timer;
    const reset = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        lock();
        toast.info("Vault locked due to inactivity");
      }, AUTO_LOCK_MS);
    };
    const events = ["mousedown", "keydown", "touchstart", "scroll"];
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    reset();
    return () => {
      clearTimeout(timer);
      events.forEach((e) => window.removeEventListener(e, reset));
    };
  }, [phase, lock]);

  useEffect(() => {
    api
      .get("/auth/status")
      .then(({ data }) => {
        if (!data.pin_set) setPhase("setup");
        else if (localStorage.getItem("vault_token")) setPhase("unlocked");
        else setPhase("locked");
      })
      .catch(() => setPhase("locked"));
  }, []);

  if (phase === "loading") {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <ShieldCheck className="w-10 h-10 text-slate-300 animate-pulse" />
      </div>
    );
  }

  if (phase === "setup" || phase === "locked") {
    return (
      <>
        <PinScreen mode={phase} onUnlock={() => setPhase("unlocked")} />
        <Toaster position="top-center" richColors />
      </>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="max-w-md md:max-w-4xl mx-auto min-h-screen flex flex-col bg-slate-50">
        <header className="px-5 pt-8 pb-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-xl bg-slate-900 flex items-center justify-center">
                <ShieldCheck className="w-5 h-5 text-white" />
              </div>
              <h1 className="font-heading text-2xl font-semibold tracking-tight text-slate-900">MyVault</h1>
            </div>
            <p className="text-sm text-slate-500 mt-1.5">Your logins & insurance, safely stored</p>
          </div>
          <div className="flex gap-2">
            <button
              data-testid="settings-button"
              onClick={() => setSettingsOpen(true)}
              aria-label="Settings"
              className="w-10 h-10 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-600 hover:bg-slate-100 active:scale-95 transition-colors"
            >
              <Settings className="w-4 h-4" />
            </button>
            <button
              data-testid="lock-vault-button"
              onClick={lock}
              aria-label="Lock vault"
              className="w-10 h-10 rounded-full bg-white border border-slate-200 flex items-center justify-center text-slate-600 hover:bg-slate-100 active:scale-95 transition-colors"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </header>

        <div className="px-5 pb-2">
          <div className="flex gap-2 p-1 bg-slate-100 rounded-full">
            <button
              data-testid="tab-logins"
              onClick={() => setTab("logins")}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-full text-sm font-medium transition-colors active:scale-95 ${
                tab === "logins" ? "bg-slate-900 text-white shadow-sm" : "text-slate-600"
              }`}
            >
              <KeyRound className="w-4 h-4" /> Logins
            </button>
            <button
              data-testid="tab-cards"
              onClick={() => setTab("cards")}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-full text-sm font-medium transition-colors active:scale-95 ${
                tab === "cards" ? "bg-slate-900 text-white shadow-sm" : "text-slate-600"
              }`}
            >
              <CreditCard className="w-4 h-4" /> Cards
            </button>
            <button
              data-testid="tab-insurance"
              onClick={() => setTab("insurance")}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-full text-sm font-medium transition-colors active:scale-95 ${
                tab === "insurance" ? "bg-slate-900 text-white shadow-sm" : "text-slate-600"
              }`}
            >
              <FileText className="w-4 h-4" /> Insurance
            </button>
          </div>
        </div>

        <main className="flex-1 px-5 pb-24">
          {tab === "logins" ? <CredentialsTab /> : tab === "cards" ? <CardsTab /> : <InsuranceTab />}
        </main>

        <footer className="px-5 pb-6 flex items-center justify-center gap-1.5 text-xs text-slate-400">
          <Lock className="w-3 h-3" /> Passwords encrypted at rest
        </footer>
      </div>
      <ChangePinDialog open={settingsOpen} onOpenChange={setSettingsOpen} />
      <Toaster position="top-center" richColors />
    </div>
  );
}

export default App;
