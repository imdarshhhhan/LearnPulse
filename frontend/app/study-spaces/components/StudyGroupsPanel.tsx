"use client";

import { useState } from "react";

import { EmptyState } from "@/app/components/DashboardShell";
import { formatDate } from "@/lib/format";
import type { StudyGroup } from "@/services/socialApi";

import styles from "../study-spaces.module.css";

interface StudyGroupsPanelProps {
  groups: StudyGroup[];
  busy: boolean;
  onCreateGroup: (name: string) => Promise<boolean>;
  onJoinGroup: (code: string) => Promise<boolean>;
}

export function StudyGroupsPanel({
  groups,
  busy,
  onCreateGroup,
  onJoinGroup,
}: StudyGroupsPanelProps) {
  const [groupName, setGroupName] = useState("");
  const [inviteCode, setInviteCode] = useState("");

  const submitCreate = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = groupName.trim();
    if (!name) return;
    if (await onCreateGroup(name)) setGroupName("");
  };

  const submitJoin = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const code = inviteCode.trim();
    if (!code) return;
    if (await onJoinGroup(code)) setInviteCode("");
  };

  return (
    <div className={styles.twoColumnLayout}>
      <div className={styles.formStack}>
        <section className={styles.card}>
          <p className={styles.cardEyebrow}>Your next study session</p>
          <h3 className={styles.cardTitle}>Create a group</h3>
          <p className={styles.cardDescription}>
            Give your group a name and invite friends with its unique code.
          </p>
          <form onSubmit={submitCreate} className={styles.form}>
            <label htmlFor="group-name" className={styles.srOnly}>Group name</label>
            <input
              id="group-name"
              required
              maxLength={120}
              value={groupName}
              onChange={(event) => setGroupName(event.target.value)}
              placeholder="e.g. Biology exam prep"
              className={styles.input}
            />
            <button className={`${styles.primaryButton} ${styles.fullWidth}`} disabled={busy || !groupName.trim()}>
              {busy ? "Working…" : "Create study group"}
            </button>
          </form>
        </section>

        <section className={styles.card}>
          <p className={styles.cardEyebrow}>Got an invitation?</p>
          <h3 className={styles.cardTitle}>Join with a code</h3>
          <p className={styles.cardDescription}>Enter the group code shared by its creator.</p>
          <form onSubmit={submitJoin} className={styles.inlineForm}>
            <label htmlFor="invite-code" className={styles.srOnly}>
              Study group invite code
            </label>
            <input
              id="invite-code"
              required
              minLength={6}
              value={inviteCode}
              onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
              placeholder="QZ-XXXXXXXX"
              className={styles.input}
            />
            <button className={styles.primaryButton} disabled={busy || !inviteCode.trim()}>
              {busy ? "Joining…" : "Join group"}
            </button>
          </form>
        </section>
      </div>

      <section className={styles.card}>
        <div className={styles.sectionHeading}>
          <div>
            <h3 className={styles.cardTitle}>Your study groups</h3>
            <p className={styles.cardDescription}>Groups you created or joined.</p>
          </div>
          <span className={styles.countBadge}>{groups.length}</span>
        </div>
        {groups.length === 0 ? (
          <EmptyState>
            Your groups will show up here. Create one or join with an invite code.
          </EmptyState>
        ) : (
          <ul className={styles.itemList}>
            {groups.map((group) => (
              <li key={group.id} className={styles.groupItem}>
                <div className={styles.groupDetails}>
                  <div>
                    <h4 className={styles.itemTitle}>{group.name}</h4>
                    <p className={styles.itemMeta}>
                      {group.memberCount} {group.memberCount === 1 ? "member" : "members"}
                      {" · "}created {formatDate(group.createdAt)}
                    </p>
                  </div>
                  <span className={styles.inviteCode}>{group.code}</span>
                </div>
                {group.members.length > 0 && (
                  <p className={styles.memberNames}>
                    Members: {group.members.map((member) => member.fullName).join(", ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
