"use client";

import { useState } from "react";

import { EmptyState } from "@/app/components/DashboardShell";
import { formatDate } from "@/lib/format";
import type { Community, CommunityPost } from "@/services/socialApi";

import styles from "../study-spaces.module.css";

interface CommunityFeedProps {
  community: Community | null;
  posts: CommunityPost[];
  loading: boolean;
  busy: boolean;
  onPublishPost: (content: string) => Promise<boolean>;
}

export function CommunityFeed({
  community,
  posts,
  loading,
  busy,
  onPublishPost,
}: CommunityFeedProps) {
  const [content, setContent] = useState("");

  const submitPost = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedContent = content.trim();
    if (!trimmedContent) return;
    if (await onPublishPost(trimmedContent)) setContent("");
  };

  return (
    <section className={styles.feed}>
      {community ? (
        <>
          <header className={styles.feedHeader}>
            <p className={styles.cardEyebrow}>Community conversation</p>
            <h3 className={styles.feedTitle}>{community.name}</h3>
            {community.description && (
              <p className={styles.cardDescription}>{community.description}</p>
            )}
          </header>
          <form onSubmit={submitPost} className={styles.postForm}>
            <label htmlFor="community-post" className={styles.srOnly}>Write a post</label>
            <textarea
              id="community-post"
              required
              maxLength={2000}
              rows={3}
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Share a question, resource, or idea…"
              className={`${styles.input} ${styles.textarea}`}
            />
            <div className={styles.postActions}>
              <span className={styles.characterCount}>{content.length}/2000</span>
              <button className={styles.primaryButton} disabled={busy || !content.trim()}>
                {busy ? "Posting…" : "Publish post"}
              </button>
            </div>
          </form>
          <div className={styles.posts}>
            {loading ? (
              <p className={styles.loadingText}>Loading conversation…</p>
            ) : posts.length === 0 ? (
              <EmptyState>No posts yet. Start the conversation!</EmptyState>
            ) : (
              <ul className={styles.postList}>
                {posts.map((post) => (
                  <li key={post.id} className={styles.post}>
                    <div className={styles.postMeta}>
                      <span className={styles.authorName}>{post.authorName}</span>
                      <time className={styles.characterCount}>{formatDate(post.createdAt)}</time>
                    </div>
                    <p className={styles.postContent}>{post.content}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      ) : (
        <div className={styles.feedEmpty}>
          <span className={styles.sparkle} aria-hidden="true">✦</span>
          <h3 className={styles.cardTitle}>Make space for good ideas</h3>
          <p className={styles.emptyDescription}>
            Select a community to read and publish posts, or create a community to get started.
          </p>
        </div>
      )}
    </section>
  );
}
