import { useState, useEffect, useMemo } from "react";
import {
  Landmark, Mail, Users, CreditCard, Globe, Plus, Search, Copy, Eye, EyeOff,
  Pencil, Trash2, Wand2, KeyRound,
} from "lucide-react";
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

const CATEGORIES = ["Bank", "Email", "Social", "Card", "Other"];
const CAT_ICONS = {
  Bank: [Landmark, "bg-blue-50 text-blue-600"],
  Email: [Mail, "bg-amber-50 text-amber-600"],
  Social: [Users, "bg-rose-50 text-rose-600"],
  Card: [CreditCard, "bg-emerald-50 text-emerald-600"],
  Other: [Globe, "bg-slate-100 text-slate-600"],
};

const generatePassword = () => {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#$%&*";
  const arr = new Uint32Array(16);
  crypto.getRandomValues(arr);
  return Array.from(arr, (n) => chars[n % chars.length]).join("");
};

const copyText = async (text, label) => {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  } catch {
    toast.error("Copy failed");
  }
};

const EMPTY = { title: "", category: "Bank", member_name: "", username: "", password: "", website: "", notes: "" };

export default function CredentialsTab() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const [deleteId, setDeleteId] = useState(null);
  const [showPw, setShowPw] = useState({});
  const [showFormPw, setShowFormPw] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = () =>
    api.get("/credentials").then(({ data }) => setItems(data)).finally(() => setLoading(false));

  useEffect(() => {
    load();
  }, []);

  const [memberFilter, setMemberFilter] = useState("All");

  const members = useMemo(
    () => [...new Set(items.map((i) => i.member_name).filter(Boolean))],
    [items]
  );

  const visible = useMemo(() => {
    let list = filter === "All" ? items : items.filter((i) => i.category === filter);
    if (memberFilter !== "All") list = list.filter((i) => i.member_name === memberFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (i) =>
          i.title.toLowerCase().includes(q) ||
          i.username.toLowerCase().includes(q) ||
          (i.member_name || "").toLowerCase().includes(q)
      );
    }
    return list;
  }, [items, filter, memberFilter, search]);

  const openAdd = () => {
    setForm(EMPTY);
    setEditId(null);
    setShowFormPw(false);
    setDialogOpen(true);
  };

  const openEdit = (item) => {
    setForm({ ...item });
    setEditId(item.id);
    setShowFormPw(false);
    setDialogOpen(true);
  };

  const save = async () => {
    if (!form.title.trim()) return toast.error("Title is required");
    setSaving(true);
    try {
      if (editId) await api.put(`/credentials/${editId}`, form);
      else await api.post("/credentials", form);
      toast.success(editId ? "Login updated" : "Login saved");
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
      await api.delete(`/credentials/${deleteId}`);
      toast.success("Login deleted");
      setDeleteId(null);
      load();
    } catch (e) {
      toast.error(errDetail(e));
    }
  };

  return (
    <div className="fade-up">
      <div className="relative mt-3">
        <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        <Input
          data-testid="search-credentials-input"
          placeholder="Search logins..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 rounded-xl bg-white border-slate-200 h-11"
        />
      </div>

      <div className="flex gap-2 mt-4 overflow-x-auto pb-1 scrollbar-none">
        {["All", ...CATEGORIES].map((c) => (
          <button
            key={c}
            data-testid={`category-tab-${c.toLowerCase()}`}
            onClick={() => setFilter(c)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors active:scale-95 ${
              filter === c ? "bg-slate-900 text-white" : "bg-slate-100 text-slate-600 hover:bg-slate-200"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {members.length > 0 && (
        <div className="flex gap-2 mt-3 overflow-x-auto pb-1 items-center">
          <Users className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          {["All", ...members].map((m) => (
            <button
              key={m}
              data-testid={`member-tab-${m.toLowerCase()}`}
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

      <div className="mt-5 space-y-3 md:space-y-0 md:grid md:grid-cols-2 md:gap-4 md:items-start">
        {loading && <p className="text-sm text-slate-400 text-center py-10 md:col-span-2">Loading...</p>}
        {!loading && visible.length === 0 && (
          <div className="text-center py-14 md:col-span-2" data-testid="credentials-empty-state">
            <KeyRound className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">No logins yet. Tap + to add your first one.</p>
          </div>
        )}
        {visible.map((item) => {
          const [Icon, iconCls] = CAT_ICONS[item.category] || CAT_ICONS.Other;
          return (
            <div
              key={item.id}
              data-testid={`credential-card-${item.id}`}
              className="bg-white rounded-2xl border border-slate-200 shadow-sm p-4"
            >
              <div className="flex items-center gap-3">
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${iconCls}`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-slate-900 truncate">
                    {item.title}
                    {item.member_name && (
                      <span
                        className="ml-2 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-medium align-middle"
                        data-testid={`credential-member-${item.id}`}
                      >
                        {item.member_name}
                      </span>
                    )}
                  </p>
                  <p className="text-sm text-slate-500 truncate">{item.username || "—"}</p>
                </div>
                <div className="flex gap-1">
                  <button
                    data-testid={`edit-credential-${item.id}`}
                    aria-label="Edit"
                    onClick={() => openEdit(item)}
                    className="w-9 h-9 rounded-full flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 active:scale-95 transition-colors"
                  >
                    <Pencil className="w-4 h-4" />
                  </button>
                  <button
                    data-testid={`delete-credential-${item.id}`}
                    aria-label="Delete"
                    onClick={() => setDeleteId(item.id)}
                    className="w-9 h-9 rounded-full flex items-center justify-center text-slate-400 hover:bg-rose-50 hover:text-rose-600 active:scale-95 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2 bg-slate-50 rounded-xl px-3 py-2">
                <span className="text-sm text-slate-700 font-mono flex-1 truncate" data-testid={`password-display-${item.id}`}>
                  {showPw[item.id] ? item.password : "••••••••••"}
                </span>
                <button
                  data-testid={`toggle-password-${item.id}`}
                  aria-label="Toggle password visibility"
                  onClick={() => setShowPw((s) => ({ ...s, [item.id]: !s[item.id] }))}
                  className="w-8 h-8 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-200 active:scale-95 transition-colors"
                >
                  {showPw[item.id] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
                {item.username && (
                  <button
                    data-testid={`copy-username-${item.id}`}
                    aria-label="Copy username"
                    onClick={() => copyText(item.username, "Username")}
                    className="h-8 px-2.5 rounded-full flex items-center gap-1 text-xs font-medium text-slate-600 hover:bg-slate-200 active:scale-95 transition-colors"
                  >
                    <Copy className="w-3.5 h-3.5" /> ID
                  </button>
                )}
                <button
                  data-testid={`copy-password-${item.id}`}
                  aria-label="Copy password"
                  onClick={() => copyText(item.password, "Password")}
                  className="h-8 px-2.5 rounded-full flex items-center gap-1 text-xs font-medium bg-slate-900 text-white hover:bg-slate-700 active:scale-95 transition-colors"
                >
                  <Copy className="w-3.5 h-3.5" /> Copy
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <button
        data-testid="add-credential-fab"
        aria-label="Add login"
        onClick={openAdd}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-slate-900 text-white shadow-lg shadow-slate-400/40 flex items-center justify-center hover:bg-slate-700 active:scale-95 transition-colors z-40"
      >
        <Plus className="w-6 h-6" />
      </button>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md rounded-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading">{editId ? "Edit Login" : "Add Login"}</DialogTitle>
            <DialogDescription>Details are stored encrypted in your vault.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Title *</Label>
              <Input
                data-testid="credential-title-input"
                placeholder="e.g. SBI Net Banking"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Category</Label>
              <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                <SelectTrigger data-testid="credential-category-select" className="rounded-xl">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c} data-testid={`category-option-${c.toLowerCase()}`}>{c}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Member / For Whom</Label>
              <Input
                data-testid="credential-member-input"
                placeholder="e.g. Father, Mother, Self"
                value={form.member_name}
                onChange={(e) => setForm({ ...form, member_name: e.target.value })}
                className="rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Username / Login ID</Label>
              <Input
                data-testid="credential-username-input"
                placeholder="Your user ID"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
                className="rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Password</Label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Input
                    data-testid="credential-password-input"
                    type={showFormPw ? "text" : "password"}
                    placeholder="Password"
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className="rounded-xl pr-10"
                  />
                  <button
                    type="button"
                    data-testid="form-toggle-password"
                    aria-label="Toggle visibility"
                    onClick={() => setShowFormPw(!showFormPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                  >
                    {showFormPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  data-testid="generate-password-button"
                  onClick={() => {
                    setForm({ ...form, password: generatePassword() });
                    setShowFormPw(true);
                    toast.success("Strong password generated");
                  }}
                  className="rounded-xl shrink-0"
                >
                  <Wand2 className="w-4 h-4 mr-1.5" /> Generate
                </Button>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Website (optional)</Label>
              <Input
                data-testid="credential-website-input"
                placeholder="https://..."
                value={form.website}
                onChange={(e) => setForm({ ...form, website: e.target.value })}
                className="rounded-xl"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Notes (optional)</Label>
              <Textarea
                data-testid="credential-notes-input"
                placeholder="Security questions, hints..."
                value={form.notes}
                onChange={(e) => setForm({ ...form, notes: e.target.value })}
                className="rounded-xl"
                rows={2}
              />
            </div>
            <Button
              data-testid="save-credential-button"
              onClick={save}
              disabled={saving}
              className="w-full rounded-full h-11 bg-slate-900 hover:bg-slate-700"
            >
              {saving ? "Saving..." : editId ? "Update Login" : "Save Login"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!deleteId} onOpenChange={(o) => !o && setDeleteId(null)}>
        <AlertDialogContent className="rounded-2xl max-w-sm">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">Delete this login?</AlertDialogTitle>
            <AlertDialogDescription>This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-button" className="rounded-full">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="confirm-delete-button"
              onClick={remove}
              className="rounded-full bg-rose-600 hover:bg-rose-700"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
