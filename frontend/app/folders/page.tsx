"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  DashboardShell,
  ErrorBanner,
  LoadingState,
} from "@/app/components/DashboardShell";
import { fetchCurrentUser } from "@/services/api";
import {
  createStudentFolder,
  deleteFolderDocument,
  deleteStudentFolder,
  listFolderDocuments,
  listStudentFolders,
  renameStudentFolder,
  uploadFolderFile,
  type FolderDocument,
  type StudentFolder,
} from "@/services/foldersApi";

import { FolderContents } from "./components/FolderContents";
import { FolderList } from "./components/FolderList";
import styles from "./folders.module.css";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export default function FoldersPage() {
  const [folders, setFolders] = useState<StudentFolder[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<StudentFolder | null>(null);
  const [documents, setDocuments] = useState<FolderDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [accessState, setAccessState] = useState<"checking" | "allowed" | "denied" | "error">(
    "checking",
  );
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const documentRequestId = useRef(0);

  useEffect(() => {
    if (!localStorage.getItem("userToken")) {
      window.location.replace("/auth");
      return;
    }
    let active = true;
    const loadForStudent = async () => {
      try {
        const currentUser = await fetchCurrentUser();
        if (!active) return;
        if (currentUser.role !== "student") {
          setAccessState("denied");
          window.location.replace(currentUser.role === "teacher" ? "/teacher" : "/");
          return;
        }

        setAccessState("allowed");
        const result = await listStudentFolders();
        if (active) setFolders(result.folders);
      } catch (loadError) {
        if (!active) return;
        setAccessState("error");
        setError(errorMessage(loadError, "Could not verify your student account."));
      } finally {
        if (active) setLoading(false);
      }
    };
    void loadForStudent();
    return () => {
      active = false;
    };
  }, []);

  const loadDocuments = useCallback(async (folder: StudentFolder) => {
    const requestId = ++documentRequestId.current;
    setSelectedFolder(folder);
    setDocuments([]);
    setDocumentsLoading(true);
    setError("");
    try {
      const result = await listFolderDocuments(folder.id);
      if (documentRequestId.current !== requestId) return;
      setDocuments(result.documents);
      setSelectedFolder(result.folder);
      setFolders((current) =>
        current.map((item) => (item.id === result.folder.id ? result.folder : item)),
      );
    } catch (loadError) {
      if (documentRequestId.current === requestId) {
        setError(errorMessage(loadError, "Could not load this folder."));
      }
    } finally {
      if (documentRequestId.current === requestId) setDocumentsLoading(false);
    }
  }, []);

  const handleCreateFolder = async (name: string): Promise<boolean> => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await createStudentFolder(name);
      documentRequestId.current += 1;
      setFolders((current) => [result.folder, ...current]);
      setSelectedFolder(result.folder);
      setDocuments([]);
      setNotice(`Folder "${result.folder.name}" created.`);
      return true;
    } catch (createError) {
      setError(errorMessage(createError, "Could not create the folder."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleUpload = async (file: File): Promise<boolean> => {
    if (!selectedFolder) return false;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await uploadFolderFile(selectedFolder.id, file);
      setDocuments((current) => [result.document, ...current]);
      setFolders((current) =>
        current.map((folder) =>
          folder.id === selectedFolder.id
            ? { ...folder, documentCount: folder.documentCount + 1 }
            : folder,
        ),
      );
      setSelectedFolder((current) =>
        current ? { ...current, documentCount: current.documentCount + 1 } : current,
      );
      setNotice(`"${result.document.fileName}" uploaded.`);
      return true;
    } catch (uploadError) {
      setError(errorMessage(uploadError, "Could not upload the file."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleRename = async (name: string): Promise<boolean> => {
    if (!selectedFolder) return false;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await renameStudentFolder(selectedFolder.id, name);
      setSelectedFolder(result.folder);
      setFolders((current) =>
        current.map((folder) => (folder.id === result.folder.id ? result.folder : folder)),
      );
      setNotice("Folder renamed.");
      return true;
    } catch (renameError) {
      setError(errorMessage(renameError, "Could not rename the folder."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteFolder = async () => {
    if (!selectedFolder) return;
    if (!window.confirm(`Delete "${selectedFolder.name}" and all its stored materials?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await deleteStudentFolder(selectedFolder.id);
      documentRequestId.current += 1;
      setFolders((current) => current.filter((folder) => folder.id !== selectedFolder.id));
      setSelectedFolder(null);
      setDocuments([]);
      setNotice("Folder and its materials deleted.");
    } catch (deleteError) {
      setError(errorMessage(deleteError, "Could not delete the folder."));
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteDocument = async (document: FolderDocument) => {
    if (!selectedFolder) return;
    if (!window.confirm(`Delete "${document.fileName}"?`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await deleteFolderDocument(selectedFolder.id, document.id);
      setDocuments((current) => current.filter((item) => item.id !== document.id));
      setFolders((current) =>
        current.map((folder) =>
          folder.id === selectedFolder.id
            ? { ...folder, documentCount: Math.max(0, folder.documentCount - 1) }
            : folder,
        ),
      );
      setSelectedFolder((current) =>
        current
          ? { ...current, documentCount: Math.max(0, current.documentCount - 1) }
          : current,
      );
      setNotice("Material deleted.");
    } catch (deleteError) {
      setError(errorMessage(deleteError, "Could not delete the material."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <DashboardShell title="My folders" user={null}>
      {accessState === "checking" || (accessState === "allowed" && loading) ? (
        <LoadingState />
      ) : accessState !== "allowed" ? (
        <ErrorBanner message={error || "Student access is required to use folders."} />
      ) : (
        <div className={styles.page}>
          <header className={styles.pageHeader}>
            <div>
              <p className={styles.eyebrow}>Your personal library</p>
              <h1 className={styles.pageTitle}>Study folders</h1>
              <p className={styles.pageDescription}>
                Keep class notes, exam prep, and useful resources together in your own way.
              </p>
            </div>
            <span className={styles.folderTotal}>
              {folders.length} {folders.length === 1 ? "folder" : "folders"}
            </span>
          </header>

          <div className={styles.feedback} aria-live="polite">
            <ErrorBanner message={error} />
            {notice && <p className={styles.notice}>{notice}</p>}
          </div>

          <div className={styles.workspace}>
            <FolderList
              folders={folders}
              selectedFolderId={selectedFolder?.id ?? null}
              busy={busy}
              onCreateFolder={handleCreateFolder}
              onSelectFolder={(folder) => void loadDocuments(folder)}
            />
            <FolderContents
              key={selectedFolder?.id ?? "no-folder"}
              folder={selectedFolder}
              documents={documents}
              loading={documentsLoading}
              busy={busy}
              onUpload={handleUpload}
              onRename={handleRename}
              onDeleteFolder={() => void handleDeleteFolder()}
              onDeleteDocument={(document) => void handleDeleteDocument(document)}
              onError={setError}
            />
          </div>
        </div>
      )}
    </DashboardShell>
  );
}
