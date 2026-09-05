import { useState } from "react";
import type { ImportPreview, ImportResult } from "../types";
import { apiErrorMessage } from "../utils/apiError";

type Props = {
  title: string;
  description: string;
  contextReady: boolean;
  downloadTemplate?: () => Promise<Blob>;
  templateUrl?: string;
  templateFilename: string;
  previewImport: (file: File) => Promise<ImportPreview>;
  confirmImport: (file: File, sha256: string) => Promise<ImportResult>;
  onImported?: () => Promise<void> | void;
  requireContextBeforeFile?: boolean;
  requireContextBeforeTemplate?: boolean;
  contextMessage?: string;
};

export default function BulkImportPanel(props: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const download = async () => {
    setError("");
    try {
      if (props.templateUrl) {
        const a = document.createElement("a");
        a.href = props.templateUrl;
        a.download = props.templateFilename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        return;
      }
      if (!props.downloadTemplate) throw new Error("Template source is not configured.");
      const blob = await props.downloadTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = props.templateFilename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e) { setError(apiErrorMessage(e, "Failed to download template")); }
  };
  const runPreview = async () => {
    if (!file) return setError("Select an .xlsx file first.");
    if (!props.contextReady) return setError("Complete the selections above before previewing the workbook.");
    setBusy(true); setError(""); setMessage("");
    try { setPreview(await props.previewImport(file)); }
    catch (e) { setPreview(null); setError(apiErrorMessage(e, "Failed to preview import")); }
    finally { setBusy(false); }
  };
  const confirm = async () => {
    if (!file || !preview) return;
    if (preview.error_count > 0) return setError("Fix all validation errors and preview again before importing.");
    setBusy(true); setError("");
    try {
      const result = await props.confirmImport(file, preview.sha256);
      if (result.classes_created !== undefined || result.sections_created !== undefined) {
        const classes = result.classes_created ?? 0;
        const sections = result.sections_created ?? 0;
        setMessage(`${classes} class${classes === 1 ? "" : "es"} and ${sections} section${sections === 1 ? "" : "s"} created successfully.`);
      } else {
        setMessage(`${result.imported} record${result.imported === 1 ? "" : "s"} imported successfully.`);
      }
      setFile(null); setPreview(null); await props.onImported?.();
    } catch (e) { setError(apiErrorMessage(e, "Import failed")); }
    finally { setBusy(false); }
  };

  return <section className="card space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h2 className="text-lg font-semibold">{props.title}</h2><p className="text-sm text-gray-500 mt-1">{props.description}</p></div>
      <button className="btn-secondary" type="button" disabled={!!props.requireContextBeforeTemplate && !props.contextReady} onClick={() => void download()}>Download Template</button>
    </div>
    {error && <div className="rounded-lg bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{error}</div>}
    {message && <div className="rounded-lg bg-green-50 border border-green-200 text-green-700 px-4 py-3 text-sm">{message}</div>}
    {!props.contextReady && props.contextMessage && <div className="rounded-lg bg-amber-50 border border-amber-200 text-amber-800 px-4 py-3 text-sm">{props.contextMessage}</div>}
    <div className="flex flex-wrap items-center gap-3">
      <input
        type="file"
        disabled={!!props.requireContextBeforeFile && !props.contextReady}
        accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        onChange={e => { setFile(e.target.files?.[0] || null); setPreview(null); setMessage(""); }}
      />
      <button className="btn-secondary" type="button" disabled={busy || !file || !props.contextReady} onClick={() => void runPreview()}>{busy ? "Checking…" : "Validate & Preview"}</button>
      {preview && preview.error_count === 0 && <button className="btn-primary" type="button" disabled={busy} onClick={() => void confirm()}>{busy ? "Importing…" : "Confirm Import"}</button>}
    </div>
    {preview && <div className="space-y-3 text-sm">
      <div className="flex flex-wrap gap-4"><span><b>Rows:</b> {preview.row_count}</span><span className="text-green-700"><b>Valid:</b> {preview.valid_count}</span><span className={preview.error_count ? "text-red-700" : "text-gray-600"}><b>Errors:</b> {preview.error_count}</span></div>
      {preview.summary && <div className="rounded-lg border border-blue-200 bg-blue-50 p-3 flex flex-wrap gap-4">{Object.entries(preview.summary).map(([k,v])=><span key={k}><b>{k.replace(/_/g," ")}:</b> {String(v)}</span>)}</div>}
      {preview.errors.length > 0 && <div className="rounded-lg border border-red-200 bg-red-50 p-3"><div className="font-semibold text-red-700 mb-2">Validation errors</div>{preview.errors.slice(0,20).map((x,i)=><div key={i} className="text-red-700">Row {x.row}{x.field ? ` · ${x.field}` : ""}: {x.message}</div>)}</div>}
      {preview.warnings.length > 0 && <div className="rounded-lg border border-amber-200 bg-amber-50 p-3"><div className="font-semibold text-amber-800 mb-2">Warnings</div>{preview.warnings.slice(0,20).map((x,i)=><div key={i} className="text-amber-800">Row {x.row}{x.field ? ` · ${x.field}` : ""}: {x.message}</div>)}</div>}
      {preview.preview.length > 0 && <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="border-b">{Object.keys(preview.preview[0]).map(k=><th className="text-left py-2 pr-4" key={k}>{k.replace(/_/g," ")}</th>)}</tr></thead><tbody>{preview.preview.slice(0,10).map((row,i)=><tr className="border-b last:border-0" key={i}>{Object.keys(preview.preview[0]).map(k=><td className="py-2 pr-4" key={k}>{String(row[k] ?? "")}</td>)}</tr>)}</tbody></table></div>}
    </div>}
  </section>;
}
