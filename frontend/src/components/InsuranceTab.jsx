import { useState, useEffect, useMemo } from "react";
import { Plus, Pencil, Trash2, FileText, ShieldPlus, CalendarDays, User, Search, BellRing, Paperclip } from "lucide-react";
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

const EMPTY = {
  company_name: "", plan_name: "", policy_number: "", member_name: "", premium_amount: "",
  premium_frequency: "Yearly", premium_due_date: "", term_years: "", sum_assured: "",
  maturity_amount: "", maturity_date: "", nominee: "", notes: "",
};

const inr = (n) =>
  n == null || n === "" ? "—" : `₹${Number(n).toLocaleString("en-IN")}`;

export default function InsuranceTab() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [docFor, setDocFor] = useState(null);
  const [saving, setSaving] = useState(false);
  const [memberSuggestions, setMemberSuggestions] = useState([]);

  const load = () => {
    api.get("/insurance").then(({ data }) => setItems(data)).finally(() => setLoading(false));
    api.get("/members").then(({ data }) => setMemberSuggestions(data)).catch(() => {});
  };

  useEffect(() => {
    load();
  }, []);

  const visible = useMemo(() => {
    if (!search.trim()) return items;
    const q = search.toLowerCase();
    return items.filter((i) =>
      [i.company_name, i.plan_name, i.member_name, i.policy_number, i.nominee].some((v) =>
        (v || "").toLowerCase().includes(q)
      )
    );
  }, [items, search]);

  const reminders = useMemo(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    return items
      .filter((i) => i.premium_due_date)
      .map((i) => ({ ...i, days: Math.round((new Date(i.premium_due_date) - today) / 86400000) }))
      .filter((i) => i.days <= 30)
      .sort((a, b) => a.days - b.days);
  }, [items]);

  const dueText = (d) =>
    d < 0 ? `Overdue by ${-d} day${-d > 1 ? "s" : ""}` : d === 0 ? "Due today" : `Due in ${d} day${d > 1 ? "s" : ""}`;

  const openAdd = () => {
    setForm(EMPTY);
    setEditId(null);
    setDialogOpen(true);
  };

  const openEdit = (item) => {
    setForm({
      ...item,
      premium_amount: item.premium_amount ?? "",
      term_years: item.term_years ?? "",
      sum_assured: item.sum_assured ?? "",
      maturity_amount: item.maturity_amount ?? "",
    });
    setEditId(item.id);
    setDialogOpen(true);
  };

  const save = async () => {
    if (!form.company_name.trim()) return toast.error("Company name is required");
    setSaving(true);
    const payload = {
      ...form,
      premium_amount: form.premium_amount === "" ? null : Number(form.premium_amount),
      term_years: form.term_years === "" ? null : Number(form.term_years),
      sum_assured: form.sum_assured === "" ? null : Number(form.sum_assured),
      maturity_amount: form.maturity_amount === "" ? null : Number(form.maturity_amount),
    };
    try {
      if (editId) await api.put(`/insurance/${editId}`, payload);
      else await api.post("/insurance", payload);
      toast.success(editId ? "Policy updated" : "Policy saved");
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
      await api.delete(`/insurance/${deleteId}`);
      toast.success("Policy deleted");
      setDeleteId(null);
      load();
    } catch (e) {
      toast.error(errDetail(e));
    }
  };

  const numField = (label, key, testid, placeholder) => (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input
        data-testid={testid}
        type="number"
        placeholder={placeholder}
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
        className="rounded-xl"
      />
    </div>
  );

  return (
    <div className="fade-up">
      <div className="relative mt-3">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <Input
          data-testid="search-insurance-input"
          placeholder="Search by member, company, plan..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 rounded-xl bg-white border-slate-200 h-11"
        />
      </div>

      {reminders.length > 0 && (
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded-2xl p-4" data-testid="premium-reminders">
          <p className="text-sm font-semibold text-amber-800 flex items-center gap-2 mb-2">
            <BellRing className="w-4 h-4" /> Upcoming Premiums
          </p>
          <div className="space-y-2">
            {reminders.map((r) => (
              <div key={r.id} className="flex items-center justify-between text-sm" data-testid={`reminder-${r.id}`}>
                <span className="text-slate-700 truncate">
                  {r.company_name}
                  {r.member_name ? ` · ${r.member_name}` : ""}
                </span>
                <span className={`font-medium whitespace-nowrap ml-2 ${r.days < 0 ? "text-rose-600" : "text-amber-700"}`}>
                  {inr(r.premium_amount)} · {dueText(r.days)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-5 space-y-3 md:space-y-0 md:grid md:grid-cols-2 md:gap-4 md:items-start">
        {loading && <p className="text-sm text-slate-400 text-center py-10 md:col-span-2">Loading...</p>}
        {!loading && visible.length === 0 && (
          <div className="text-center py-14 md:col-span-2" data-testid="insurance-empty-state">
            <ShieldPlus className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">
              {items.length === 0 ? "No policies yet. Tap + to add your insurance details." : "No matching policies found."}
            </p>
          </div>
        )}
        {visible.map((item) => (
          <div
            key={item.id}
            data-testid={`insurance-card-${item.id}`}
            className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4"
          >
            <div className="flex items-start gap-3">
              <div className="w-11 h-11 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shrink-0">
                <FileText className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-slate-900 truncate">{item.company_name}</p>
                <p className="text-sm text-slate-500 truncate">{item.plan_name || "—"}</p>
                {item.member_name && (
                  <span
                    className="inline-block mt-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium"
                    data-testid={`insurance-member-${item.id}`}
                  >
                    {item.member_name}
                  </span>
                )}
                {item.policy_number && (
                  <p className="text-xs text-slate-400 mt-0.5 font-mono">Policy: {item.policy_number}</p>
                )}
              </div>
              <div className="flex gap-1">
                <button
                  data-testid={`docs-insurance-${item.id}`}
                  aria-label="Documents"
                  onClick={() => setDocFor({ id: item.id, title: item.company_name })}
                  className="w-9 h-9 rounded-full flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 active:scale-95 transition-colors"
                >
                  <Paperclip className="w-4 h-4" />
                </button>
                <button
                  data-testid={`edit-insurance-${item.id}`}
                  aria-label="Edit policy"
                  onClick={() => openEdit(item)}
                  className="w-9 h-9 rounded-full flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 active:scale-95 transition-colors"
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  data-testid={`delete-insurance-${item.id}`}
                  aria-label="Delete policy"
                  onClick={() => setDeleteId(item.id)}
                  className="w-9 h-9 rounded-full flex items-center justify-center text-slate-400 hover:bg-rose-50 hover:text-rose-600 active:scale-95 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2 mt-3">
              <div className="col-span-2 bg-indigo-50/60 rounded-xl px-3 py-2.5">
                <p className="text-xs text-slate-500">Sum Assured / Benefit</p>
                <p className="font-heading font-semibold text-lg text-slate-900">{inr(item.sum_assured)}</p>
              </div>
              <div className="bg-slate-50 rounded-xl px-3 py-2.5">
                <p className="text-xs text-slate-500">Premium ({item.premium_frequency})</p>
                <p className="font-medium text-slate-900">{inr(item.premium_amount)}</p>
              </div>
              <div className="bg-slate-50 rounded-xl px-3 py-2.5">
                <p className="text-xs text-slate-500">Term</p>
                <p className="font-medium text-slate-900">{item.term_years ? `${item.term_years} years` : "—"}</p>
              </div>
              <div className="bg-slate-50 rounded-xl px-3 py-2.5">
                <p className="text-xs text-slate-500">Maturity Amount</p>
                <p className="font-medium text-slate-900">{inr(item.maturity_amount)}</p>
              </div>
              <div className="bg-slate-50 rounded-xl px-3 py-2.5">
                <p className="text-xs text-slate-500 flex items-center gap-1"><CalendarDays className="w-3 h-3" /> Maturity Date</p>
                <p className="font-medium text-slate-900">{item.maturity_date || "—"}</p>
              </div>
              <div className="bg-amber-50/70 rounded-xl px-3 py-2.5">
                <p className="text-xs text-slate-500 flex items-center gap-1"><BellRing className="w-3 h-3" /> Next Premium Due</p>
                <p className="font-medium text-slate-900">{item.premium_due_date || "—"}</p>
              </div>
            </div>
            {item.nominee && (
              <p className="text-xs text-slate-500 mt-2 flex items-center gap-1">
                <User className="w-3 h-3" /> Nominee: {item.nominee}
              </p>
            )}
            {item.notes && <p className="text-xs text-slate-500 mt-1">{item.notes}</p>}
          </div>
        ))}
      </div>

      <button
        data-testid="add-insurance-fab"
        aria-label="Add policy"
        onClick={openAdd}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-slate-900 text-white shadow-lg shadow-slate-400/40 flex items-center justify-center hover:bg-slate-700 active:scale-95 transition-colors z-40"
      >
        <Plus className="w-6 h-6" />
      </button>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md rounded-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">{editId ? "Edit Policy" : "Add Insurance Policy"}</DialogTitle>
            <DialogDescription>Keep all your policy details in one place.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Insurance Company *</Label>
              <Input
                data-testid="insurance-company-input"
                placeholder="e.g. LIC, HDFC Life"
                value={form.company_name}
                onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                className="rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Plan Name</Label>
              <Input
                data-testid="insurance-plan-input"
                placeholder="e.g. Jeevan Anand"
                value={form.plan_name}
                onChange={(e) => setForm({ ...form, plan_name: e.target.value })}
                className="rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Member / For Whom</Label>
              <Input
                data-testid="insurance-member-input"
                placeholder="e.g. Father, Mother, Self"
                value={form.member_name}
                onChange={(e) => setForm({ ...form, member_name: e.target.value })}
                className="rounded-xl"
              />
              {memberSuggestions.length > 0 && (
                <div className="flex flex-wrap gap-1.5 pt-1" data-testid="insurance-member-suggestions">
                  {memberSuggestions
                    .filter((m) => m !== form.member_name)
                    .map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setForm({ ...form, member_name: m })}
                        className="px-2.5 py-1 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium hover:bg-emerald-100 active:scale-95 transition-colors"
                      >
                        {m}
                      </button>
                    ))}
                </div>
              )}
            </div>
            <div className="space-y-1.5">
              <Label>Policy Number</Label>
              <Input
                data-testid="insurance-policy-number-input"
                placeholder="Policy no."
                value={form.policy_number}
                onChange={(e) => setForm({ ...form, policy_number: e.target.value })}
                className="rounded-xl"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              {numField("Premium Amount (₹)", "premium_amount", "insurance-premium-input", "e.g. 25000")}
              <div className="space-y-1.5">
                <Label>Frequency</Label>
                <Select value={form.premium_frequency} onValueChange={(v) => setForm({ ...form, premium_frequency: v })}>
                  <SelectTrigger data-testid="insurance-frequency-select" className="rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {["Yearly", "Half-Yearly", "Quarterly", "Monthly", "One-time"].map((f) => (
                      <SelectItem key={f} value={f}>{f}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              {numField("Term (Years)", "term_years", "insurance-term-input", "e.g. 20")}
              {numField("Sum Assured (₹)", "sum_assured", "insurance-sum-assured-input", "e.g. 1000000")}
            </div>
            <div className="grid grid-cols-2 gap-3">
              {numField("Maturity Amount (₹)", "maturity_amount", "insurance-maturity-amount-input", "e.g. 1500000")}
              <div className="space-y-1.5">
                <Label>Maturity Date</Label>
                <Input
                  data-testid="insurance-maturity-date-input"
                  type="date"
                  value={form.maturity_date}
                  onChange={(e) => setForm({ ...form, maturity_date: e.target.value })}
                  className="rounded-xl"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Next Premium Due</Label>
                <Input
                  data-testid="insurance-premium-due-input"
                  type="date"
                  value={form.premium_due_date}
                  onChange={(e) => setForm({ ...form, premium_due_date: e.target.value })}
                  className="rounded-xl"
                />
              </div>
              <div className="space-y-1.5">
                <Label>Nominee</Label>
                <Input
                  data-testid="insurance-nominee-input"
                  placeholder="Nominee name"
                  value={form.nominee}
                  onChange={(e) => setForm({ ...form, nominee: e.target.value })}
                  className="rounded-xl"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Benefits / Notes</Label>
              <Textarea
                data-testid="insurance-notes-input"
                placeholder="Death benefit, riders, bonus details..."
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="rounded-xl"
                rows={2}
              />
            </div>
            <Button
              data-testid="save-insurance-button"
              onClick={save}
              disabled={saving}
              className="w-full rounded-full h-11 bg-slate-900 hover:bg-slate-700"
            >
              {saving ? "Saving..." : editId ? "Update Policy" : "Save Policy"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={(o) => !o && setDeleteId(null)}>
        <AlertDialogContent className="rounded-2xl max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">Delete this policy?</AlertDialogTitle>
            <AlertDialogDescription>This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-insurance" className="rounded-full">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-delete-insurance"
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
        onOpenChange={(o) => !o && setDocFor(null)}
        parentType="insurance"
        parentId={docFor?.id}
        title={docFor?.title}
      />
    </div>
  );
}
