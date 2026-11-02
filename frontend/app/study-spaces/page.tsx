"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  DashboardShell,
  ErrorBanner,
  LoadingState,
} from "@/app/components/DashboardShell";
import {
  createCommunity,
  createGroup,
  deleteGroup,
  fetchCommunityPosts,
  joinCommunity,
  joinGroup,
  listCommunities,
  listGroups,
  publishCommunityPost,
  removeGroupMember,
  type Community,
  type CommunityPost,
  type StudyGroup,
} from "@/services/socialApi";

import { CommunityFeed } from "./components/CommunityFeed";
import { CommunitiesPanel } from "./components/CommunitiesPanel";
import { StudyGroupsPanel } from "./components/StudyGroupsPanel";
import { StudySpacesHeader } from "./components/StudySpacesHeader";
import styles from "./study-spaces.module.css";

type ActiveTab = "groups" | "communities";

function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function StudySpacesContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tab: ActiveTab =
    searchParams.get("tab") === "communities" ? "communities" : "groups";
  const [groups, setGroups] = useState<StudyGroup[]>([]);
  const [communities, setCommunities] = useState<Community[]>([]);
  const [selectedCommunity, setSelectedCommunity] = useState<Community | null>(null);
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [postsLoading, setPostsLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!localStorage.getItem("userToken")) {
      window.location.replace("/auth");
      return;
    }

    let active = true;
    Promise.all([listGroups(), listCommunities()])
      .then(([groupResult, communityResult]) => {
        if (!active) return;
        setGroups(groupResult.groups);
        setCommunities(communityResult.communities);
      })
      .catch((loadError: unknown) => {
        if (active) setError(getErrorMessage(loadError, "Could not load your study spaces."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const clearFeedback = () => {
    setError("");
    setNotice("");
  };

  const openCommunity = async (community: Community) => {
    setSelectedCommunity(community);
    setPosts([]);
    setPostsLoading(true);
    setError("");
    try {
      const result = await fetchCommunityPosts(community.id);
      setPosts(result.posts);
    } catch (loadError) {
      setError(getErrorMessage(loadError, "Could not load community posts."));
    } finally {
      setPostsLoading(false);
    }
  };

  const handleCreateGroup = async (name: string): Promise<boolean> => {
    setBusy(true);
    clearFeedback();
    try {
      const result = await createGroup(name);
      setGroups((current) => [
        result.group,
        ...current.filter((item) => item.id !== result.group.id),
      ]);
      setNotice(`Study group created. Share this invite code: ${result.group.code}`);
      return true;
    } catch (createError) {
      setError(getErrorMessage(createError, "Could not create the study group."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleJoinGroup = async (code: string): Promise<boolean> => {
    setBusy(true);
    clearFeedback();
    try {
      const result = await joinGroup(code);
      setGroups((current) => [
        result.group,
        ...current.filter((item) => item.id !== result.group.id),
      ]);
      setNotice(result.message);
      return true;
    } catch (joinError) {
      setError(getErrorMessage(joinError, "Could not join the study group."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleRemoveMember = async (groupId: number, memberId: number): Promise<boolean> => {
    setBusy(true);
    clearFeedback();
    try {
      const res = await removeGroupMember(groupId, memberId);
      setGroups((current) => current.map((g) => (g.id === groupId ? res.group : g)));
      setNotice(res.message || "Member removed from group.");
      return true;
    } catch (err) {
      setError(getErrorMessage(err, "Could not remove member from group."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteGroup = async (groupId: number): Promise<boolean> => {
    setBusy(true);
    clearFeedback();
    try {
      await deleteGroup(groupId);
      setGroups((current) => current.filter((g) => g.id !== groupId));
      setNotice("Study group deleted.");
      return true;
    } catch (err) {
      setError(getErrorMessage(err, "Could not delete study group."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleCreateCommunity = async (
    name: string,
    description: string,
  ): Promise<boolean> => {
    setBusy(true);
    clearFeedback();
    try {
      const result = await createCommunity(name, description);
      setCommunities((current) => [
        result.community,
        ...current.filter((item) => item.id !== result.community.id),
      ]);
      setNotice(`Community "${result.community.name}" created.`);
      await openCommunity(result.community);
      return true;
    } catch (createError) {
      setError(getErrorMessage(createError, "Could not create the community."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handleJoinCommunity = async (communityId: number): Promise<boolean> => {
    setBusy(true);
    clearFeedback();
    try {
      const result = await joinCommunity(communityId);
      setCommunities((current) => [
        result.community,
        ...current.filter((item) => item.id !== result.community.id),
      ]);
      setNotice(result.message);
      await openCommunity(result.community);
      return true;
    } catch (joinError) {
      setError(getErrorMessage(joinError, "Could not join the community."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  const handlePublishPost = async (content: string): Promise<boolean> => {
    if (!selectedCommunity) return false;

    setBusy(true);
    clearFeedback();
    try {
      const result = await publishCommunityPost(selectedCommunity.id, content);
      setPosts((current) => [result.post, ...current]);
      setNotice("Your post is live.");
      return true;
    } catch (publishError) {
      setError(getErrorMessage(publishError, "Could not publish your post."));
      return false;
    } finally {
      setBusy(false);
    }
  };

  return (
    <DashboardShell title="Study spaces" user={null}>
      <div className={styles.page}>
        <StudySpacesHeader
          groupCount={groups.length}
          communityCount={communities.length}
          activeTab={tab}
          onTabChange={(nextTab) => {
            clearFeedback();
            router.replace(`/study-spaces?tab=${nextTab}`, { scroll: false });
          }}
        />

        <div className={styles.feedback} aria-live="polite">
          <ErrorBanner message={error} />
          {notice && <p className={styles.notice}>{notice}</p>}
        </div>

        {loading ? (
          <LoadingState />
        ) : tab === "groups" ? (
          <StudyGroupsPanel
            groups={groups}
            busy={busy}
            onCreateGroup={handleCreateGroup}
            onJoinGroup={handleJoinGroup}
            onRemoveMember={handleRemoveMember}
            onDeleteGroup={handleDeleteGroup}
          />
        ) : (
          <div className={styles.communityLayout}>
            <CommunitiesPanel
              communities={communities}
              selectedCommunityId={selectedCommunity?.id ?? null}
              busy={busy}
              onCreateCommunity={handleCreateCommunity}
              onJoinCommunity={handleJoinCommunity}
              onSelectCommunity={(community) => void openCommunity(community)}
            />
            <CommunityFeed
              community={selectedCommunity}
              posts={posts}
              loading={postsLoading}
              busy={busy}
              onPublishPost={handlePublishPost}
            />
          </div>
        )}
      </div>
    </DashboardShell>
  );
}

export default function StudySpacesPage() {
  return (
    <Suspense fallback={<LoadingState />}>
      <StudySpacesContent />
    </Suspense>
  );
}
