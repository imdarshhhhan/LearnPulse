const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export interface StudentFolder {
  id: number;
  name: string;
  folderType: string;
  createdAt: string | null;
  documentCount: number;
}

export interface FolderDocument {
  id: number;
  folderId: number;
  title: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number | null;
  createdAt: string | null;
  downloadUrl: string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("userToken");
  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}${path}`, {
      ...init,
      headers: {
        ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `Could not reach the backend at ${BACKEND_URL}. Check that it is running and allows this frontend origin.`,
        { cause: error },
      );
    }
    throw error;
  }

  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }

  return response.json();
}

async function responseErrorMessage(response: Response): Promise<string> {
  const body = await response.text();
  if (!body) return `Request failed with status ${response.status}.`;
  try {
    const errorBody: unknown = JSON.parse(body);
    if (
      typeof errorBody === "object" &&
      errorBody !== null &&
      "detail" in errorBody &&
      typeof errorBody.detail === "string"
    ) {
      return errorBody.detail;
    }
  } catch {
    return body;
  }
  return body;
}

export function listStudentFolders(): Promise<{ folders: StudentFolder[] }> {
  return request("/social/folders");
}

export function createStudentFolder(name: string): Promise<{ folder: StudentFolder }> {
  return request("/social/folders", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function renameStudentFolder(
  folderId: number,
  name: string,
): Promise<{ folder: StudentFolder }> {
  return request(`/social/folders/${folderId}`, {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export function deleteStudentFolder(folderId: number): Promise<{ message: string }> {
  return request(`/social/folders/${folderId}`, { method: "DELETE" });
}

export function listFolderDocuments(
  folderId: number,
): Promise<{ folder: StudentFolder; documents: FolderDocument[] }> {
  return request(`/social/folders/${folderId}/documents`);
}

export function uploadFolderFile(
  folderId: number,
  file: File,
): Promise<{ document: FolderDocument; message: string }> {
  const form = new FormData();
  form.append("file", file);
  return request(`/social/folders/${folderId}/files`, {
    method: "POST",
    body: form,
  });
}

export function deleteFolderDocument(
  folderId: number,
  documentId: number,
): Promise<{ message: string }> {
  return request(`/social/folders/${folderId}/documents/${documentId}`, {
    method: "DELETE",
  });
}

export async function fetchFolderFile(
  folderId: number,
  documentId: number,
): Promise<Blob> {
  const token = localStorage.getItem("userToken");
  let response: Response;
  try {
    response = await fetch(
      `${BACKEND_URL}/social/folders/${folderId}/documents/${documentId}?download=true`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} },
    );
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `Could not reach the backend at ${BACKEND_URL}. Check that it is running and allows this frontend origin.`,
        { cause: error },
      );
    }
    throw error;
  }
  if (!response.ok) {
    throw new Error(await responseErrorMessage(response));
  }
  return response.blob();
}
