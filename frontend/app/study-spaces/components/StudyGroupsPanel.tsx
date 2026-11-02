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
  onRemoveMember?: (groupId: number, memberId: number) => Promise<boolean>;
  onDeleteGroup?: (groupId: number) => Promise<boolean>;
}

export function StudyGroupsPanel({
  groups,
  busy,
  onCreateGroup,
  onJoinGroup,
  onRemoveMember,
  onDeleteGroup,
}: StudyGroupsPanelProps) {
  const [groupName, setGroupName] = useState("");
  const [inviteCode, setInviteCode] = useState("");

  const currentUserId = (() => {
    if (typeof window === "undefined") return null;
    const token = localStorage.getItem("userToken");
    if (!token) return null;
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      return Number(payload.userId ?? payload.sub ?? 0);
    } catch {
      return null;
    }
  })();

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
            Give your group a name and invite peers with its unique code.
          </p>
          <form onSubmit={submitCreate} className={styles.form}>
            <label htmlFor="group-name" className={styles.srOnly}>Group name</label>
            <input
              id="group-name"
              required
              maxLength={120}
              value={groupName}
              onChange={(event) => setGroupName(event.target.value)}
              placeholder="e.g. Operating Systems Study Circle"
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
            {groups.map((group) => {
              const isOwner = currentUserId === group.creatorId;
              return (
                <li key={group.id} className={styles.groupItem}>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className={styles.itemTitle}>{group.name}</h4>
                        {isOwner && (
                          <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-semibold text-blue-700">
                            Group Owner
                          </span>
                        )}
                      </div>
                      <p className={styles.itemMeta}>
                        {group.memberCount} {group.memberCount === 1 ? "member" : "members"}
                        {" · "}created {formatDate(group.createdAt)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={styles.inviteCode}>{group.code}</span>
                      {isOwner && onDeleteGroup && (
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => {
                            if (window.confirm(`Are you sure you want to delete "${group.name}"?`)) {
                              void onDeleteGroup(group.id);
                            }
                          }}
                          className="rounded-lg border border-rose-200 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-100 disabled:opacity-50"
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>

                  {group.members.length > 0 && (
                    <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-slate-600">
                      <span className="font-semibold text-slate-700">Members:</span>
                      {group.members.map((member) => (
                        <span
                          key={member.id}
                          className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 font-medium text-slate-800"
                        >
                          {member.fullName}
                          {member.id === group.creatorId && (
                            <span className="text-[10px] text-blue-600 font-bold">(Owner)</span>
                          )}
                          {isOwner && member.id !== group.creatorId && onRemoveMember && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => {
                                if (window.confirm(`Remove ${member.fullName} from this group?`)) {
                                  void onRemoveMember(group.id, member.id);
                                }
                              }}
                              className="ml-1 text-slate-400 hover:text-rose-600 font-bold"
                              title={`Remove ${member.fullName}`}
                            >
                              ×
                            </button>
                          )}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
