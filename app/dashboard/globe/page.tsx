import ComingSoonPage from "@/components/coming-soon";

export default function GlobePage() {
  return (
    <ComingSoonPage
      title="3D Global Threat Map"
      description="Interactive 3D globe visualization displaying real-time cyber attacks, threat origins, and global security intelligence. Experience cybersecurity like never before with immersive threat visualization."
      features={[
        "Interactive 3D Earth globe",
        "Real-time attack animations",
        "Geolocation-based threats",
        "Country-wise attack statistics",
        "Threat trajectory visualization",
        "WebGL-powered graphics",
      ]}
      estimatedTime="Q2 2026"
    />
  );
}
