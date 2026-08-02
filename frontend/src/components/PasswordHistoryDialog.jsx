import { useState, useEffect } from "react";
import { Copy, Eye, EyeOff, History } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import api from "@/lib/api";

const fmtDate = (iso) => {
  try {
    return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });
  } catch {
    return iso;
  }
};

const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.success("Old password copied to clipboard");
  } catch {
    toast.error("Copy failed");
  }
};

export default function PasswordHistoryDialog({ open, onOpenChange, credId, title }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [show, setShow] = useState({});

  useEffect(() => {
    if (open && credId) {
      setLoading(true);
      setShow({});
      api
        .get(`/credentials/${credId}/password-history`)
        .then(({ data }) => setRows(data))
        .catch(() => setRows([]))
        .finally(() => setLoading(false));
    }
  }, [open, credId]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-2xl max-h-[80vh] overflow-y-auto" data-testid="password-history-dialog">
        <DialogHeader>
          <DialogTitle className="font-heading flex items-center gap-2">
            <History className="w-4 h-4" /> Password History
          </DialogTitle>
          <DialogDescription>{title} — last 5 previous passwords</DialogDescription>
        </DialogHeader>
        {loading && <p className="text-sm text-slate-400 text-center py-6">Loading...</p>}
        {!loading && rows.length === 0 && (
          <p className="text-sm text-slate-500 text-center py-6" data-testid="password-history-empty">
            No previous passwords. Old ones will appear here when you change the password.
          </p>
        )}
        {!loading && rows.length > 0 && (
          <div className="space-y-2">
            {rows.map((r, idx) => (
              <div
                key={idx}
                className="flex items-center gap-2 bg-slate-50 rounded-xl px-3 py-2"
                data-testid={`password-history-row-${idx}`}
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-700 font-mono truncate" data-testid={`password-history-value-${idx}`}>
                    {show[idx] ? r.password : "••••••••••"}
                  </p>
                  <p className="text-[11px] text-slate-400">Changed on {fmtDate(r.changed_at)}</p>
                </div>
                <button
                  data-testid={`password-history-toggle-${idx}`}
                  aria-label="Toggle visibility"
                  onClick={() => setShow((s) => ({ ...s, [idx]: !s[idx] }))}
                  className="w-8 h-8 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-200 active:scale-95 transition-colors"
                >
                  {show[idx] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
                <button
                  data-testid={`password-history-copy-${idx}`}
                  aria-label="Copy old password"
                  onClick={() => copyText(r.password)}
                  className="w-8 h-8 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-200 active:scale-95 transition-colors"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
