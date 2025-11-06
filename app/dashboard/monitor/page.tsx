import ComingSoonPage from "@/components/coming-soon";

export default function MonitorPage() {
  return (
    <ComingSoonPage
      title="Live Monitor"
      description="Real-time cybersecurity monitoring dashboard with live threat detection, system performance metrics, and attack visualization. This module will provide instant insights into your network's security posture."
      features={[
        "Real-time threat visualization",
        "Live attack map with geolocation",
        "System performance monitoring",
        "Traffic flow analysis",
        "Instant alert notifications",
        "Automated threat response",
      ]}
      estimatedTime="Q1 2026"
    />
  );
}
