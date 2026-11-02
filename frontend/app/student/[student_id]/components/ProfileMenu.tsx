"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import type { SyncedUser } from "@/services/api";

import styles from "../student.module.css";

const menuItems = [
  { href: "/achievements", label: "Achievements", icon: "✧" },
  { href: "/settings", label: "Settings", icon: "⚙" },
  { href: "/study-spaces?tab=groups", label: "Groups", icon: "▣" },
  { href: "/study-spaces?tab=communities", label: "Joined Communities", icon: "◉" },
  { href: "/about-us", label: "About Us", icon: "ⓘ" },
];

export function ProfileMenu({ user }: { user: SyncedUser }) {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const handlePointerDown = (event: PointerEvent) => {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        rootRef.current?.querySelector<HTMLButtonElement>("[aria-haspopup='menu']")?.focus();
      }
    };
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const handleMenuKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const items = Array.from(
      rootRef.current?.querySelectorAll<HTMLElement>("[role='menuitem']") ?? [],
    );
    const activeIndex = items.indexOf(document.activeElement as HTMLElement);
    const nextIndex =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? items.length - 1
          : (activeIndex + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    event.preventDefault();
    items[nextIndex]?.focus();
  };

  const logout = () => {
    localStorage.removeItem("userToken");
    localStorage.removeItem("userRole");
    router.replace("/auth");
  };

  return (
    <div className={styles.profileRoot} ref={rootRef}>
      <button
        type="button"
        aria-label="Open profile menu"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="student-profile-menu"
        className={styles.avatarButton}
        onClick={() => setOpen((current) => !current)}
      >
        {user.avatarUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img className={styles.avatarImage} src={user.avatarUrl} alt="" />
        ) : (
          <span aria-hidden="true">{user.fullName.trim().charAt(0).toUpperCase() || "S"}</span>
        )}
      </button>
      {open && (
        <div
          id="student-profile-menu"
          className={styles.profileMenu}
          role="menu"
          aria-label="Profile menu"
          onKeyDown={handleMenuKeyDown}
        >
          <div className={styles.profileIdentity}>
            <span className={styles.profileName}>{user.fullName}</span>
            <span className={styles.profileEmail}>{user.email}</span>
          </div>
          <div className={styles.menuDivider} />
          {menuItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              role="menuitem"
              className={styles.menuItem}
              onClick={() => setOpen(false)}
            >
              <span className={styles.menuIcon} aria-hidden="true">{item.icon}</span>
              {item.label}
            </Link>
          ))}
          <div className={styles.menuDivider} />
          <button
            type="button"
            role="menuitem"
            className={`${styles.menuItem} ${styles.logoutItem}`}
            onClick={logout}
          >
            <span className={styles.menuIcon} aria-hidden="true">↪</span>
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
