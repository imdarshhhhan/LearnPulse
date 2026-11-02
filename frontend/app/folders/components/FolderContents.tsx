"use client";

import { useEffect, useRef, useState } from "react";

import { formatDate } from "@/lib/format";
import {
  fetchFolderFile,
  type FolderDocument,
  type StudentFolder,
} from "@/services/foldersApi";

import styles from "../folders.module.css";

interface FolderContentsProps {
  folder: StudentFolder | null;
  documents: FolderDocument[];
  loading: boolean;
  busy: boolean;
  onUpload: (file: File) => Promise<boolean>;
  onRename: (name: string) => Promise<boolean>;
  onDeleteFolder: () => void;
  onDeleteDocument: (document: FolderDocument) => void;
  onError: (message: string) => void;
}

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = ".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.md,.csv,.docx";

function formatSize(size: number | null): string {
  if (size === null) return "Text note";
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function supportsPreview(document: FolderDocument): boolean {
  return (
    document.mimeType === "application/pdf" ||
    document.mimeType.startsWith("image/") ||
    document.mimeType.startsWith("text/")
  );
}

export function FolderContents({
  folder,
  documents,
  loading,
  busy,
  onUpload,
  onRename,
  onDeleteFolder,
  onDeleteDocument,
  onError,
}: FolderContentsProps) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<{
    document: FolderDocument;
    url: string;
  } | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview.url);
    };
  }, [preview]);

  if (!folder) {
    return (
      <section className={`${styles.contents} ${styles.noFolder}`}>
        <span className={styles.emptyIllustration} aria-hidden="true">▱</span>
        <h2 className={styles.contentsTitle}>Your study space, your way</h2>
        <p className={styles.muted}>
          Pick a folder to view its materials, or create a new folder for a subject, exam, or project.
        </p>
      </section>
    );
  }

  const submitRename = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;
    if (await onRename(trimmedName)) setRenaming(false);
  };

  const chooseFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > MAX_FILE_BYTES) {
      onError("Files must be 10 MB or smaller.");
      event.target.value = "";
      return;
    }
    setUploading(true);
    const uploaded = await onUpload(file);
    setUploading(false);
    if (uploaded) event.target.value = "";
  };

  const showPreview = async (document: FolderDocument) => {
    try {
      const blob = await fetchFolderFile(folder.id, document.id);
      const url = URL.createObjectURL(blob);
      setPreview({ document, url });
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not open this file.");
    }
  };

  const download = async (document: FolderDocument) => {
    try {
      const blob = await fetchFolderFile(folder.id, document.id);
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement("a");
      anchor.href = url;
      anchor.download = document.fileName;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      onError(error instanceof Error ? error.message : "Could not download this file.");
    }
  };

  return (
    <section className={styles.contents}>
      <header className={styles.contentsHeader}>
        <div className={styles.titleGroup}>
          <span className={styles.largeFolderIcon} aria-hidden="true">▰</span>
          <div>
            {renaming ? (
              <form onSubmit={submitRename} className={styles.renameForm}>
                <label htmlFor="rename-folder" className={styles.srOnly}>Folder name</label>
                <input
                  id="rename-folder"
                  autoFocus
                  required
                  maxLength={120}
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className={styles.input}
                />
                <button type="submit" disabled={busy || !name.trim()} className={styles.smallButton}>
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setName(folder.name);
                    setRenaming(false);
                  }}
                  className={styles.textButton}
                >
                  Cancel
                </button>
              </form>
            ) : (
              <>
                <h2 className={styles.contentsTitle}>{folder.name}</h2>
                <p className={styles.muted}>
                  {folder.documentCount} {folder.documentCount === 1 ? "item" : "items"}
                  {" · "}created {formatDate(folder.createdAt)}
                </p>
              </>
            )}
          </div>
        </div>
        <div className={styles.headerActions}>
          <input
            ref={fileInput}
            type="file"
            accept={ACCEPTED_TYPES}
            className={styles.srOnly}
            onChange={(event) => void chooseFile(event)}
            aria-label={`Upload file to ${folder.name}`}
          />
          <button
            type="button"
            className={styles.primaryButton}
            disabled={uploading || busy}
            onClick={() => fileInput.current?.click()}
          >
            {uploading ? "Uploading…" : "↑ Upload material"}
          </button>
          {!renaming && (
            <button
              type="button"
              className={styles.textButton}
              onClick={() => {
                setName(folder.name);
                setRenaming(true);
              }}
            >
              Rename
            </button>
          )}
          <button
            type="button"
            className={styles.dangerButton}
            onClick={onDeleteFolder}
            disabled={busy}
          >
            Delete folder
          </button>
        </div>
      </header>

      <p className={styles.uploadHint}>
        PDF, images, text, Markdown, CSV, or Word documents · up to 10 MB per file.
      </p>

      {preview && (
        <section className={styles.preview}>
          <div className={styles.previewHeader}>
            <h3 className={styles.previewTitle}>{preview.document.fileName}</h3>
            <button
              type="button"
              className={styles.textButton}
              onClick={() => setPreview(null)}
            >
              Close preview
            </button>
          </div>
          {preview.document.mimeType.startsWith("image/") ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img className={styles.imagePreview} src={preview.url} alt={preview.document.fileName} />
          ) : (
            <iframe
              title={`Preview of ${preview.document.fileName}`}
              src={preview.url}
              className={styles.filePreview}
            />
          )}
        </section>
      )}

      {loading ? (
        <p className={styles.loading}>Loading folder contents…</p>
      ) : documents.length === 0 ? (
        <div className={styles.folderEmpty}>
          <span className={styles.emptyIllustration} aria-hidden="true">↥</span>
          <h3 className={styles.itemTitle}>This folder is ready for your materials</h3>
          <p className={styles.muted}>Upload notes, PDFs, images, and documents to get started.</p>
          <button
            type="button"
            className={styles.secondaryButton}
            onClick={() => fileInput.current?.click()}
            disabled={uploading || busy}
          >
            Choose a file
          </button>
        </div>
      ) : (
        <ul className={styles.documentList}>
          {documents.map((document) => (
            <li key={document.id} className={styles.documentRow}>
              <span className={styles.documentIcon} aria-hidden="true">
                {document.mimeType === "application/pdf" ? "PDF" : document.mimeType.startsWith("image/") ? "IMG" : "DOC"}
              </span>
              <div className={styles.documentInfo}>
                <span className={styles.documentName}>{document.fileName}</span>
                <span className={styles.documentMeta}>
                  {formatSize(document.sizeBytes)} · {document.mimeType} · {formatDate(document.createdAt)}
                </span>
              </div>
              <div className={styles.documentActions}>
                {supportsPreview(document) && (
                  <button
                    type="button"
                    className={styles.textButton}
                    onClick={() => void showPreview(document)}
                    disabled={busy}
                  >
                    Preview
                  </button>
                )}
                <button
                  type="button"
                  className={styles.textButton}
                  onClick={() => void download(document)}
                  disabled={busy}
                >
                  Download
                </button>
                <button
                  type="button"
                  className={styles.dangerTextButton}
                  onClick={() => onDeleteDocument(document)}
                  disabled={busy}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
