import { useState, useEffect, useRef } from "react";
import { FileText, Upload, Trash2, Eye, Paperclip } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import api, { errDetail } from "@/lib/api";

const fmtSize = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1024))} KB`);

export default function DocumentsDialog({ open, onOpenChange, parentType, parentId, title }) {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const load = () => {
    if (!parentId) return;
    setLoading(true);
    api
      .get("/documents", { params: { parent_type: parentType, parent_id: parentId } })
      .then(({ data }) => setDocs(data))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (open) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, parentId]);

  const upload = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) return toast.error("Max file size is 10 MB");
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api.post(`/documents/upload?parent_type=${parentType}&parent_id=${parentId}`, fd);
      toast.success("Document uploaded");
      load();
    } catch (err) {
      toast.error(errDetail(err));
    } finally {
      setUploading(false);
    }
  };

  const view = async (doc) => {
    try {
      const { data } = await api.get(`/documents/${doc.id}/download`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([data], { type: doc.content_type }));
      const w = window.open(url, "_blank");
      if (!w) {
        const a = document.createElement("a");
        a.href = url;
        a.download = doc.filename;
        a.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      toast.error(errDetail(err));
    }
  };

  const remove = async (doc) => {
    try {
      await api.delete(`/documents/${doc.id}`);
      toast.success("Document deleted");
      load();
    } catch (err) {
      toast.error(errDetail(err));
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md rounded-2xl">
        <DialogHeader>
          <DialogTitle className="font-heading flex items-center gap-2">
            <Paperclip className="w-4 h-4" /> Documents
          </DialogTitle>
          <DialogDescription>{title} — PDFs & photos, encrypted at rest</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          {loading && <p className="text-sm text-slate-400 text-center py-6">Loading...</p>}
          {!loading && docs.length === 0 && (
            <div className="text-center py-8" data-testid="documents-empty-state">
              <FileText className="w-8 h-8 text-slate-300 mx-auto mb-2" />
              <p className="text-sm text-slate-500">No documents yet. Upload policy PDF, photos etc.</p>
            </div>
          )}
          {docs.map((doc) => (
            <div
              key={doc.id}
              data-testid={`document-row-${doc.id}`}
              className="flex items-center gap-3 bg-slate-50 rounded-xl px-3 py-2.5"
            >
              <FileText className="w-5 h-5 text-slate-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-slate-900 truncate">{doc.filename}</p>
                <p className="text-xs text-slate-500">{fmtSize(doc.size)}</p>
              </div>
              <button
                data-testid={`view-document-${doc.id}`}
                aria-label="View document"
                onClick={() => view(doc)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-500 hover:bg-slate-200 active:scale-95 transition-colors"
              >
                <Eye className="w-4 h-4" />
              </button>
              <button
                data-testid={`delete-document-${doc.id}`}
                aria-label="Delete document"
                onClick={() => remove(doc)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:bg-rose-50 hover:text-rose-600 active:scale-95 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.heic,.doc,.docx,.xls,.xlsx,.txt"
            className="hidden"
            data-testid="document-file-input"
            onChange={upload}
          />
          <Button
            data-testid="upload-document-button"
            onClick={() => fileRef.current?.click()}
            disabled={uploading || !parentId}
            className="w-full rounded-full h-11 bg-slate-900 hover:bg-slate-700"
          >
            <Upload className="w-4 h-4 mr-2" />
            {uploading ? "Uploading..." : "Upload Document"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
