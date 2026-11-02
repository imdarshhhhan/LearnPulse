const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

export interface SocialMember {
  id: number;
  fullName: string;
  email: string;
}

export interface StudyGroup {
  id: number;
  name: string;
  code: string;
  creatorId: number;
  createdAt: string | null;
  memberCount: number;
  members: SocialMember[];
}

export interface Community {
  id: number;
  name: string;
  description: string | null;
  creatorId: number;
  createdAt: string | null;
  memberCount: number;
  members: SocialMember[];
}

export interface CommunityPost {
  id: number;
  communityId: number;
  authorId: number;
  authorName: string;
  content: string;
  createdAt: string | null;
}

function getAuthHeaders(): HeadersInit {
  const token = typeof window === "undefined" ? "" : localStorage.getItem("userToken");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BACKEND_URL}${path}`, {
      ...init,
      headers: {
        ...getAuthHeaders(),
        ...(init.headers ?? {}),
      },
    });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        `Could not reach the backend at ${BACKEND_URL}. Check that the backend is running and that this frontend origin is allowed.`,
        { cause: error },
      );
    }
    throw error;
  }

  if (!response.ok) {
    const body = await response.text();
    if (!body) throw new Error("Request failed.");

    let errorBody: unknown;
    try {
      errorBody = JSON.parse(body);
    } catch {
      throw new Error(body);
    }
    if (
      typeof errorBody === "object" &&
      errorBody !== null &&
      "detail" in errorBody &&
      typeof errorBody.detail === "string"
    ) {
      throw new Error(errorBody.detail);
    }
    throw new Error(body);
  }

  return response.json();
}

export async function listGroups(): Promise<{ groups: StudyGroup[] }> {
  return request("/social/groups");
}

export async function createGroup(name: string): Promise<{ group: StudyGroup; message: string }> {
  return request("/social/groups/create", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function joinGroup(code: string): Promise<{ group: StudyGroup; message: string }> {
  return request("/social/groups/join", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export async function listCommunities(): Promise<{ communities: Community[] }> {
  return request("/social/communities");
}

export async function createCommunity(
  name: string,
  description?: string,
): Promise<{ community: Community; message: string }> {
  return request("/social/communities/create", {
    method: "POST",
    body: JSON.stringify({ name, description }),
  });
}

export async function joinCommunity(
  communityId: number,
): Promise<{ community: Community; message: string }> {
  return request(`/social/communities/${communityId}/join`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function fetchCommunityPosts(
  communityId: number,
): Promise<{ community: Community; posts: CommunityPost[] }> {
  return request(`/social/communities/${communityId}/posts`);
}

export async function publishCommunityPost(
  communityId: number,
  content: string,
): Promise<{ message: string; post: CommunityPost }> {
  return request(`/social/communities/${communityId}/posts`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export async function listFolders(): Promise<{ folders: Array<Record<string, unknown>> }> {
  return request("/social/folders");
}

export async function createFolder(name: string, folderType: string = "subject") {
  return request("/social/folders/create", {
    method: "POST",
    body: JSON.stringify({ name, folderType }),
  });
}

export async function uploadFolderDocument(folderId: number, payload: {
  title: string;
  fileName: string;
  mimeType?: string;
  content: string;
}) {
  return request(`/social/folders/${folderId}/documents`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function fetchFolderDocuments(folderId: number) {
  return request(`/social/folders/${folderId}/documents`);
}
