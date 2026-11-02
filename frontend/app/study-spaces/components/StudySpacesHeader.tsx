import styles from "../study-spaces.module.css";

type ActiveTab = "groups" | "communities";

interface StudySpacesHeaderProps {
  groupCount: number;
  communityCount: number;
  activeTab: ActiveTab;
  onTabChange: (tab: ActiveTab) => void;
}

export function StudySpacesHeader({
  groupCount,
  communityCount,
  activeTab,
  onTabChange,
}: StudySpacesHeaderProps) {
  return (
    <>
      <header className={styles.hero}>
        <p className={styles.eyebrow}>Learn together</p>
        <div className={styles.heroContent}>
          <div>
            <h2 className={styles.heroTitle}>Your study community</h2>
            <p className={styles.heroDescription}>
              Start a study group, join with an invite code, or share ideas with your community.
            </p>
          </div>
          <div className={styles.stats}>
            <span className={styles.stat}>
              {groupCount} {groupCount === 1 ? "group" : "groups"}
            </span>
            <span className={styles.stat}>
              {communityCount} {communityCount === 1 ? "community" : "communities"}
            </span>
          </div>
        </div>
      </header>

      <nav className={styles.tabs} aria-label="Study spaces">
        <button
          type="button"
          aria-current={activeTab === "groups" ? "page" : undefined}
          className={`${styles.tab} ${activeTab === "groups" ? styles.activeTab : ""}`}
          onClick={() => onTabChange("groups")}
        >
          Study groups
        </button>
        <button
          type="button"
          aria-current={activeTab === "communities" ? "page" : undefined}
          className={`${styles.tab} ${activeTab === "communities" ? styles.activeTab : ""}`}
          onClick={() => onTabChange("communities")}
        >
          Communities
        </button>
      </nav>
    </>
  );
}
