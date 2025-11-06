import ComingSoonPage from "@/components/coming-soon";

export default function SettingsPage() {
  return (
    <ComingSoonPage
      title="System Settings & Configuration"
      description="Comprehensive system configuration panel for customizing your cybersecurity dashboard. Configure alerts, notifications, integrations, and system-wide security preferences."
      features={[
        "Alert threshold configuration",
        "Notification preferences",
        "Third-party integrations (SIEM)",
        "Dashboard customization",
        "API key management",
        "Backup & restore settings",
      ]}
      estimatedTime="Q1 2026"
    />
  );
}
