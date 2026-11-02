"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  listStudentFolders,
  type StudentFolder,
} from "@/services/foldersApi";
import {
  ApiError,
  fetchStudentDashboard,
  type StudentDashboardData,
} from "@/services/dashboardApi";
import { listCommunities, listGroups, type Community, type StudyGroup } from "@/services/socialApi";

export interface StudentHomeData {
  dashboard: StudentDashboardData;
  folders: StudentFolder[] | null;
  groups: StudyGroup[] | null;
  communities: Community[] | null;
  sectionErrors: {
    folders: string;
    groups: string;
    communities: string;
  };
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Could not load this section.";
}

export function useStudentHome(studentId: string) {
  const router = useRouter();
  const [data, setData] = useState<StudentHomeData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;

    Promise.allSettled([
      fetchStudentDashboard(),
      listStudentFolders(),
      listGroups(),
      listCommunities(),
    ]).then(([dashboardResult, folderResult, groupResult, communityResult]) => {
      if (!active) return;
      if (dashboardResult.status === "rejected") {
        const dashboardError = dashboardResult.reason;
        if (dashboardError instanceof ApiError && dashboardError.status === 401) {
          router.replace("/auth");
          return;
        }
        if (dashboardError instanceof ApiError && dashboardError.status === 403) {
          router.replace("/teacher");
          return;
        }
        setError(message(dashboardError));
        setLoading(false);
        return;
      }

      const dashboard = dashboardResult.value;
      if (String(dashboard.profile.userId) !== studentId) {
        router.replace(`/student/${dashboard.profile.userId}`);
        return;
      }

      setData({
        dashboard,
        folders: folderResult.status === "fulfilled" ? folderResult.value.folders : null,
        groups: groupResult.status === "fulfilled" ? groupResult.value.groups : null,
        communities:
          communityResult.status === "fulfilled" ? communityResult.value.communities : null,
        sectionErrors: {
          folders: folderResult.status === "rejected" ? message(folderResult.reason) : "",
          groups: groupResult.status === "rejected" ? message(groupResult.reason) : "",
          communities:
            communityResult.status === "rejected" ? message(communityResult.reason) : "",
        },
      });
      setLoading(false);
    });

    return () => {
      active = false;
    };
  }, [studentId, router, reloadKey]);

  const reload = useCallback(() => {
    setLoading(true);
    setError("");
    setReloadKey((key) => key + 1);
  }, []);

  return { data, error, loading, reload };
}
