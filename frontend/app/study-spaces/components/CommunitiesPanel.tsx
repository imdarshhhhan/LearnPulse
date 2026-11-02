"use client";

import { useState } from "react";

import { EmptyState } from "@/app/components/DashboardShell";
import type { Community } from "@/services/socialApi";

import styles from "../study-spaces.module.css";

interface CommunitiesPanelProps {
  communities: Community[];
  selectedCommunityId: number | null;
  busy: boolean;
  onCreateCommunity: (name: string, description: string) => Promise<boolean>;
  onJoinCommunity: (communityId: number) => Promise<boolean>;
  onSelectCommunity: (community: Community) => void;
}

export function CommunitiesPanel({
  communities,
  selectedCommunityId,
  busy,
  onCreateCommunity,
  onJoinCommunity,
  onSelectCommunity,
}: CommunitiesPanelProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [communityId, setCommunityId] = useState("");

  const submitCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;
    if (await onCreateCommunity(trimmedName, description.trim())) {
      setName("");
      setDescription("");
    }
  };

  const submitJoin = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const id = Number(communityId);
    if (!Number.isInteger(id) || id < 1) return;
    if (await onJoinCommunity(id)) setCommunityId("");
  };

  return (
    <div className={styles.formStack}>
      <section className={styles.card}>
        <p className={styles.cardEyebrow}>Bring learners together</p>
        <h3 className={styles.cardTitle}>Create a community</h3>
        <p className={styles.cardDescription}>
          Make a space for a subject, class, or shared interest.
        </p>
        <form onSubmit={submitCreate} className={styles.form}>
          <label htmlFor="community-name" className={styles.srOnly}>Community name</label>
          <input
            id="community-name"
            required
            maxLength={120}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Science learners"
            className={styles.input}
          />
          <label htmlFor="community-description" className={styles.srOnly}>Description</label>
          <textarea
            id="community-description"
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What is this community about?"
            className={`${styles.input} ${styles.textarea}`}
          />
          <button className={`${styles.primaryButton} ${styles.fullWidth}`} disabled={busy || !name.trim()}>
            {busy ? "Working…" : "Create community"}
          </button>
        </form>
      </section>

      <section className={styles.card}>
        <h3 className={styles.cardTitle}>Join a community</h3>
        <p className={styles.cardDescription}>Enter the community ID shared by a member.</p>
        <form onSubmit={submitJoin} className={styles.inlineForm}>
          <label htmlFor="community-id" className={styles.srOnly}>Community ID</label>
          <input
            id="community-id"
            required
            min={1}
            step={1}
            type="number"
            value={communityId}
            onChange={(event) => setCommunityId(event.target.value)}
            placeholder="Community ID"
            className={styles.input}
          />
          <button className={styles.primaryButton} disabled={busy || !communityId}>
            {busy ? "Joining…" : "Join"}
          </button>
        </form>
      </section>

      <section className={styles.card}>
        <h3 className={styles.cardTitle}>Your communities</h3>
        <p className={styles.cardDescription}>Spaces you created or have joined.</p>
        {communities.length === 0 ? (
          <EmptyState>Create a community to start a conversation.</EmptyState>
        ) : (
          <ul className={styles.communityList}>
            {communities.map((community) => (
              <li key={community.id}>
                <button
                  type="button"
                  aria-pressed={selectedCommunityId === community.id}
                  onClick={() => onSelectCommunity(community)}
                  className={`${styles.communityButton} ${
                    selectedCommunityId === community.id ? styles.selectedCommunity : ""
                  }`}
                >
                  <span className={styles.itemTitle}>{community.name}</span>
                  <span className={styles.communityDescription}>
                    {community.description || "A place to learn and share."}
                  </span>
                  <span className={styles.itemMeta}>
                    ID {community.id} · {community.memberCount}{" "}
                    {community.memberCount === 1 ? "member" : "members"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
