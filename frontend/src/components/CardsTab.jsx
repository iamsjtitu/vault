import { useState, useEffect, useMemo, useCallback } from "react";
import { Plus, Pencil, Trash2, Copy, Eye, EyeOff, CreditCard, Wifi, Users, Paperclip, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import api, { errDetail } from "@/lib/api";
import DocumentsDialog from "@/components/DocumentsDialog";
import MemberChips from "@/components/MemberChips";

const EMPTY = {
  bank_name: "", card_name: "", card_type: "Debit", member_name: "", card_number: "",
  expiry: "", cvv: "", cardholder_name: "", notes: "",
};

const groupDigits = (n) => (n || "").replace(/\D/g, "").replace(/(.{4})/g, "$1 ").trim();
const maskNumber = (n) => {
  const digits = (n || "").replace(/\D/g, "");
  return digits ? `•••• •••• •••• ${digits.slice(-4)}` : "•••• •••• •••• ••••";
};

const copyText = async (text, label) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  } catch {
    toast.error("Copy failed");
  }
};

const expiryStatus = (expiry) => {
  const m = /^(\d{2})\s*\/\s*(\d{2})$/.exec((expiry || "").trim());
  if (!m) return null;
  const month = parseInt(m[1], 10);
  if (month < 1 || month > 12) return null;
  const end = new Date(2000 + parseInt(m[2], 10), month, 0, 23, 59, 59);
  const days = Math.ceil((end - Date.now()) / 86400000);
  if (days < 0) return { state: "expired", days };
  if (days <= 60) return { state: "soon", days };
  return null;
};

const expiryText = (s) =>
  s.state === "expired"
    ? `Expired ${Math.abs(s.days)} day${Math.abs(s.days) === 1 ? "" : "s"} ago`
    : s.days === 0
    ? "Expires today"
    : `Expires in ${s.days} day${s.days === 1 ? "" : "s"}`;

export default function CardsTab() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [docFor, setDocFor] = useState(null);
  const [reveal, setReveal] = useState({});
  const [saving, setSaving] = useState(false);
  const [memberSuggestions, setMemberSuggestions] = useState([]);
  const [docCounts, setDocCounts] = useState({});

  const load = useCallback(() => {
    api.get("/cards").then(({ data }) => setItems(data)).finally(() => setLoading(false));
    api.get("/members").then(({ data }) => setMemberSuggestions(data)).catch(() => {});
    api.get("/documents/counts", { params: { parent_type: "card" } }).then(({ data }) => setDocCounts(data)).catch(() => {});
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const [memberFilter, setMemberFilter] = useState("All");

  const members = useMemo(
    () => [...new Set(items.map((i) => i.member_name).filter(Boolean))],
    [items]
  );

  const visible = useMemo(
    () => (memberFilter === "All" ? items : items.filter((i) => i.member_name === memberFilter)),
    [items, memberFilter]
  );

  const expiryAlerts = useMemo(
    () =>
      items
        .map((i) => ({ item: i, status: expiryStatus(i.expiry) }))
        .filter((r) => r.status)
        .sort((a, b) => a.status.days - b.status.days),
    [items]
  );

  const openAdd = () => {
    setForm(EMPTY);
    setEditId(null);
    setDialogOpen(true);
  };

  const openEdit = (item) => {
    setForm({ ...EMPTY, ...item });
    setEditId(item.id);
    setDialogOpen(true);
  };

  const save = async () => {
    if (!form.bank_name.trim()) return toast.error("Bank name is required");
    setSaving(true);
    try {
      if (editId) await api.put(`/cards/${editId}`, form);
      else await api.post("/cards", form);
      toast.success(editId ? "Card updated" : "Card saved");
      setDialogOpen(false);
      load();
    } catch (e) {
      toast.error(errDetail(e));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    try {
      await api.delete(`/cards/${deleteId}`);
      toast.success("Card deleted");
      setDeleteId(null);
      load();
    } catch (e) {
      toast.error(errDetail(e));
    }
  };

  return (
    <div className="fade-up">
      {members.length > 0 && (
        <div className="flex gap-2 mt-3 overflow-x-auto pb-1 items-center">
          <Users className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          {["All", ...members].map((m) => (
            <button
              key={m}
              data-testid={`card-member-tab-${m.toLowerCase()}`}
              onClick={() => setMemberFilter(m)}
              className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors active:scale-95 ${
                memberFilter === m ? "bg-emerald-600 text-white" : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
              }`}
            >
              {m === "All" ? "All Members" : m}
            </button>
          ))}
        </div>
      )}
      {expiryAlerts.length > 0 && (
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded-2xl p-4" data-testid="card-expiry-alerts">
          <p className="text-sm font-semibold text-amber-800 flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4" /> Card Expiry Alerts
          </p>
          <div className="space-y-1.5">
            {expiryAlerts.map(({ item, status }) => (
              <div key={item.id} className="flex items-center justify-between text-sm" data-testid={`expiry-alert-${item.id}`}>
                <span className="text-slate-700 truncate">
                  {item.bank_name}
                  {item.card_name ? ` ${item.card_name}` : ""} •••• {(item.card_number || "").replace(/\D/g, "").slice(-4)}
                </span>
                <span className={`font-medium whitespace-nowrap ml-2 ${status.state === "expired" ? "text-rose-600" : "text-amber-700"}`}>
                  {expiryText(status)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5 space-y-4 md:space-y-0 md:grid md:grid-cols-2 md:gap-4 md:items-start">
        {loading && <p className="text-sm text-slate-400 text-center py-10 md:col-span-2">Loading...</p>}
        {!loading && visible.length === 0 && (
          <div className="text-center py-14 md:col-span-2" data-testid="cards-empty-state">
            <CreditCard className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">
              {items.length === 0 ? "No cards yet. Tap + to add your debit/credit card." : "No cards for this member."}
            </p>
          </div>
        )}
        {visible.map((item) => (
          <div key={item.id} data-testid={`card-item-${item.id}`}>
            <div className="rounded-2xl bg-slate-900 text-white p-5 relative overflow-hidden shadow-md">
              <div className="absolute -top-10 -right-10 w-40 h-40 rounded-full bg-white/5" />
              <div className="absolute -bottom-16 -left-8 w-44 h-44 rounded-full bg-white/5" />
              <div className="flex items-start justify-between relative">
                <div>
                  <p className="font-medium">{item.bank_name}</p>
                  <p className="text-xs text-slate-400">{item.card_name || ""}</p>
                  {item.member_name && (
                    <span
                      className="inline-block mt-1 px-2 py-0.5 rounded-full bg-emerald-400/20 text-emerald-300 text-[10px] font-medium"
                      data-testid={`card-member-${item.id}`}
                    >
                      {item.member_name}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Wifi className="w-4 h-4 text-slate-500 rotate-90" />
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${item.card_type === "Credit" ? "bg-amber-400/20 text-amber-300" : "bg-emerald-400/20 text-emerald-300"}`}>
                    {item.card_type}
                  </span>
                </div>
              </div>
              <p className="font-mono text-lg tracking-widest mt-5 relative" data-testid={`card-number-${item.id}`}>
                {reveal[item.id] ? groupDigits(item.card_number) || "—" : maskNumber(item.card_number)}
              </p>
              <div className="flex items-end justify-between mt-4 relative">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-slate-500">Card Holder</p>
                  <p className="text-sm">{item.cardholder_name || "—"}</p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-slate-500">Expiry</p>
                  <p className="text-sm font-mono">
                    {item.expiry || "—"}
                    {(() => {
                      const s = expiryStatus(item.expiry);
                      if (!s) return null;
                      return (
                        <span
                          data-testid={`expiry-badge-${item.id}`}
                          className={`ml-1.5 px-1.5 py-0.5 rounded-full text-[9px] font-sans font-semibold align-middle ${
                            s.state === "expired" ? "bg-rose-400/20 text-rose-300" : "bg-amber-400/20 text-amber-300"
                          }`}
                        >
                          {s.state === "expired" ? "EXPIRED" : "SOON"}
                        </span>
                      );
                    })()}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-slate-500">CVV</p>
                  <p className="text-sm font-mono" data-testid={`card-cvv-${item.id}`}>
                    {reveal[item.id] ? item.cvv || "—" : "•••"}
                  </p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1 mt-2 px-1">
              <button
                data-testid={`toggle-card-${item.id}`}
                aria-label="Show card details"
                onClick={() => setReveal((s) => ({ ...s, [item.id]: !s[item.id] }))}
                className="h-8 px-3 rounded-full flex items-center gap-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 active:scale-95 transition-colors"
              >
                {reveal[item.id] ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                {reveal[item.id] ? "Hide" : "Show"}
              </button>
              <button
                data-testid={`copy-card-number-${item.id}`}
                aria-label="Copy card number"
                onClick={() => copyText((item.card_number || "").replace(/\D/g, ""), "Card number")}
                className="h-8 px-3 rounded-full flex items-center gap-1.5 text-xs font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 active:scale-95 transition-colors"
              >
                <Copy className="w-3.5 h-3.5" /> Copy No.
              </button>
              <div className="flex-1" />
              <button
                data-testid={`docs-card-${item.id}`}
                aria-label="Documents"
                onClick={() => setDocFor({ id: item.id, title: item.bank_name })}
                className="relative w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 active:scale-95 transition-colors"
              >
                <Paperclip className="w-4 h-4" />
                {docCounts[item.id] > 0 && (
                  <span
                    data-testid={`doc-count-${item.id}`}
                    className="absolute -top-0.5 -right-0.5 min-w-[16px] h-4 px-1 rounded-full bg-blue-600 text-white text-[10px] font-semibold flex items-center justify-center"
                  >
                    {docCounts[item.id]}
                  </span>
                )}
              </button>
              <button
                data-testid={`edit-card-${item.id}`}
                aria-label="Edit card"
                onClick={() => openEdit(item)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 active:scale-95 transition-colors"
              >
                <Pencil className="w-4 h-4" />
              </button>
              <button
                data-testid={`delete-card-${item.id}`}
                aria-label="Delete card"
                onClick={() => setDeleteId(item.id)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:bg-rose-50 hover:text-rose-600 active:scale-95 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <button
        data-testid="add-card-fab"
        aria-label="Add card"
        onClick={openAdd}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-slate-900 text-white shadow-lg shadow-slate-400/40 flex items-center justify-center hover:bg-slate-700 active:scale-95 transition-colors z-40"
      >
        <Plus className="w-6 h-6" />
      </button>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md rounded-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">{editId ? "Edit Card" : "Add Card"}</DialogTitle>
            <DialogDescription>Card number & CVV are stored encrypted.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Bank Name *</Label>
                <Input
                  data-testid="card-bank-input"
                  placeholder="e.g. HDFC Bank"
                  value={form.bank_name}
                  onChange={(e) => setForm({ ...form, bank_name: e.target.value })}
                  className="rounded-xl"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Card Type</Label>
                <Select value={form.card_type} onValueChange={(v) => setForm({ ...form, card_type: v })}>
                  <SelectTrigger data-testid="card-type-select" className="rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="Debit">Debit</SelectItem>
                    <SelectItem value="Credit">Credit</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Card Name (optional)</Label>
              <Input
                data-testid="card-name-input"
                placeholder="e.g. Millennia, Platinum"
                value={form.card_name}
                onChange={(e) => setForm({ ...form, card_name: e.target.value })}
                className="rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Member / For Whom</Label>
              <Input
                data-testid="card-member-input"
                placeholder="e.g. Father, Mother, Self"
                value={form.member_name}
                onChange={(e) => setForm({ ...form, member_name: e.target.value })}
                className="rounded-xl"
              />
              <MemberChips
                suggestions={memberSuggestions}
                current={form.member_name}
                onPick={(m) => setForm({ ...form, member_name: m })}
                testId="card-member-suggestions"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Card Number</Label>
              <Input
                data-testid="card-number-input"
                inputMode="numeric"
                placeholder="1234 5678 9012 3456"
                value={groupDigits(form.card_number)}
                onChange={(e) => setForm({ ...form, card_number: e.target.value.replace(/\D/g, "").slice(0, 19) })}
                className="rounded-xl font-mono"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Expiry (MM/YY)</Label>
                <Input
                  data-testid="card-expiry-input"
                  placeholder="08/29"
                  maxLength={5}
                  value={form.expiry}
                  onChange={(e) => setForm({ ...form, expiry: e.target.value })}
                  className="rounded-xl font-mono"
                />
              </div>
              <div className="space-y-1.5">
                <Label>CVV</Label>
                <Input
                  data-testid="card-cvv-input"
                  inputMode="numeric"
                  placeholder="123"
                  maxLength={4}
                  value={form.cvv}
                  onChange={(e) => setForm({ ...form, cvv: e.target.value.replace(/\D/g, "") })}
                  className="rounded-xl font-mono"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Cardholder Name</Label>
              <Input
                data-testid="card-holder-input"
                placeholder="Name on card"
                value={form.cardholder_name}
                onChange={(e) => setForm({ ...form, cardholder_name: e.target.value })}
                className="rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Notes (optional)</Label>
              <Textarea
                data-testid="card-notes-input"
                placeholder="ATM PIN hint, limits..."
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="rounded-xl"
                rows={2}
              />
            </div>
            <Button
              data-testid="save-card-button"
              onClick={save}
              disabled={saving}
              className="w-full rounded-full h-11 bg-slate-900 hover:bg-slate-700"
            >
              {saving ? "Saving..." : editId ? "Update Card" : "Save Card"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={(o) => !o && setDeleteId(null)}>
        <AlertDialogContent className="rounded-2xl max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">Delete this card?</AlertDialogTitle>
            <AlertDialogDescription>This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-card" className="rounded-full">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-delete-card"
              onClick={remove}
              className="rounded-full bg-rose-600 hover:bg-rose-700"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <DocumentsDialog
        open={!!docFor}
        onOpenChange={(o) => {
          if (!o) {
            setDocFor(null);
            load();
          }
        }}
        parentType="card"
        parentId={docFor?.id}
        title={docFor?.title}
      />
    </div>
  );
}
