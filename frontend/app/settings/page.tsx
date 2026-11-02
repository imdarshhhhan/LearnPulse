import { StudentAccountPage } from "@/app/components/StudentAccountPage";

export default function SettingsPage() {
  return (
    <StudentAccountPage
      title="Settings"
      description="Review the account details currently associated with your student profile."
      kind="settings"
    />
  );
}
