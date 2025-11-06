import ComingSoonPage from "@/components/coming-soon";

export default function NetworkPage() {
  return (
    <ComingSoonPage
      title="Network Traffic Analysis"
      description="Advanced network traffic monitoring and deep packet inspection system. Analyze network patterns, detect anomalies, and identify potential DDoS attacks before they impact your infrastructure."
      features={[
        "Deep packet inspection",
        "Traffic pattern analysis",
        "Bandwidth utilization monitoring",
        "Protocol distribution charts",
        "Anomaly detection algorithms",
        "Network topology mapping",
      ]}
      estimatedTime="Q1 2026"
    />
  );
}
