"use client";

import { AlertTriangle, CheckCircle2, FileSpreadsheet, UploadCloud } from "lucide-react";
import { ChangeEvent, useRef, useState } from "react";

import { uploadDataset } from "@/app/api/client";
import type { UploadResult } from "@/types/api";
import styles from "./operations.module.css";

export function DatasetUpload({ onUploaded }: { onUploaded: () => Promise<void> }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    setSelectedFile(event.target.files?.[0] ?? null);
    setResult(null);
    setError(null);
  }

  async function submit() {
    if (!selectedFile) return;
    setUploading(true);
    setError(null);
    try {
      const uploadResult = await uploadDataset(selectedFile);
      setResult(uploadResult);
      setSelectedFile(null);
      if (inputRef.current) inputRef.current.value = "";
      await onUploaded();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The dataset could not be processed.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className={styles.uploadCard} aria-labelledby="upload-heading">
      <div className={styles.uploadIcon}><UploadCloud size={21} aria-hidden="true" /></div>
      <div><p className={styles.kicker}>Dataset evaluation</p><h2 id="upload-heading">Upload trip data</h2><p className={styles.uploadIntro}>CSV records are validated before metrics and incidents are updated.</p></div>
      <label className={styles.filePicker}>
        <FileSpreadsheet size={20} aria-hidden="true" />
        <span><strong>{selectedFile ? selectedFile.name : "Choose a CSV file"}</strong><small>{selectedFile ? `${Math.max(1, Math.round(selectedFile.size / 1024))} KB selected` : "UTF-8 encoded trip records"}</small></span>
        <input ref={inputRef} type="file" accept=".csv,text/csv" onChange={selectFile} disabled={uploading} />
      </label>
      <button className={styles.uploadAction} onClick={() => void submit()} disabled={!selectedFile || uploading}>{uploading ? "Evaluating dataset…" : "Upload and evaluate"}</button>
      {result && <div className={styles.uploadSuccess}><CheckCircle2 size={18} aria-hidden="true" /><div><strong>{result.incidentCreated ? "Evaluation complete — attention raised" : "Evaluation complete"}</strong><p>{result.validRows} valid · {result.invalidRows} invalid · {result.skippedRows} skipped</p></div></div>}
      {error && <div className={styles.uploadError} role="alert"><AlertTriangle size={18} aria-hidden="true" /><span>{error}</span></div>}
    </section>
  );
}
