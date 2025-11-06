import ComingSoonPage from "@/components/coming-soon";

export default function ResourcesPage() {
  return (
    <ComingSoonPage
      title="System Resources Monitor"
      description="Comprehensive system resource monitoring for servers, virtual machines, and cloud infrastructure. Track CPU, memory, disk usage, and detect resource-based attacks like resource exhaustion."
      features={[
        "Real-time CPU & memory monitoring",
        "Disk I/O performance tracking",
        "Network interface statistics",
        "Process-level resource analysis",
        "Resource exhaustion detection",
        "Performance optimization insights",
      ]}
      estimatedTime="Q1 2026"
    />
  );
}
