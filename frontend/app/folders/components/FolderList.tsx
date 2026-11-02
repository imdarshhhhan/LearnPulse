"use client";

import { useState } from "react";

import type { StudentFolder } from "@/services/foldersApi";

import styles from "../folders.module.css";

interface FolderListProps {
  folders: StudentFolder[];
  selectedFolderId: number | null;
  busy: boolean;
  onCreateFolder: (name: string) => Promise<boolean>;
  onSelectFolder: (folder: StudentFolder) => void;
}

export function FolderList({
  folders,
  selectedFolderId,
  busy,
  onCreateFolder,
  onSelectFolder,
}: FolderListProps) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;
    if (await onCreateFolder(trimmedName)) {
      setName("");
      setCreating(false);
    }
  };

  return (
    <aside className={styles.sidebar}>
      <div className={styles.sidebarHeading}>
        <div>
          <p className={styles.eyebrow}>Organize your learning</p>
          <h2 className={styles.sectionTitle}>My folders</h2>
        </div>
        <button
          type="button"
          className={styles.secondaryButton}
          onClick={() => setCreating((current) => !current)}
        >
          {creating ? "Cancel" : "+ Create Folder"}
        </button>
      </div>

      {creating && (
        <form onSubmit={submit} className={styles.createForm}>
          <label htmlFor="new-folder-name" className={styles.srOnly}>Folder name</label>
          <input
            id="new-folder-name"
            autoFocus
            required
            maxLength={120}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Operating Systems"
            className={styles.input}
          />
          <button type="submit" disabled={busy || !name.trim()} className={styles.primaryButton}>
            {busy ? "Creating…" : "Create folder"}
          </button>
        </form>
      )}

      {folders.length === 0 ? (
        <div className={styles.folderEmpty}>
          <span className={styles.folderIcon} aria-hidden="true">＋</span>
          <p>No folders yet. Create one to organize your study materials.</p>
        </div>
      ) : (
        <ul className={styles.folderList}>
          {folders.map((folder) => (
            <li key={folder.id}>
              <button
                type="button"
                aria-current={selectedFolderId === folder.id ? "page" : undefined}
                onClick={() => onSelectFolder(folder)}
                className={`${styles.folderButton} ${
                  selectedFolderId === folder.id ? styles.selectedFolder : ""
                }`}
              >
                <span className={styles.folderIcon} aria-hidden="true">▰</span>
                <span className={styles.folderInfo}>
                  <span className={styles.folderName}>{folder.name}</span>
                  <span className={styles.folderCount}>
                    {folder.documentCount} {folder.documentCount === 1 ? "file" : "files"}
                  </span>
                </span>
                <span className={styles.folderArrow} aria-hidden="true">›</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}
