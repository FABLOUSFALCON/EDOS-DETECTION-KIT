import ComingSoonPage from "@/components/coming-soon";

export default function UsersPage() {
  return (
    <ComingSoonPage
      title="User Management System"
      description="Advanced user access control and identity management system. Manage user permissions, track user activities, and implement zero-trust security policies across your organization."
      features={[
        "Role-based access control (RBAC)",
        "Multi-factor authentication (MFA)",
        "User activity monitoring",
        "Session management & tracking",
        "Privilege escalation detection",
        "Identity governance & compliance",
      ]}
      estimatedTime="Q1 2026"
    />
  );
}
