"use client";

import { AuthGuard } from "@/components/auth-guard";
import { DashboardLayout } from "@/components/dashboard-layout";
import ThreatMap from "@/components/threat-map";

export default function MapPage() {
  return (
    <AuthGuard>
      <DashboardLayout>
        <div className="space-y-6 pr-6 pl-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-primary font-mono">Threat Map</h1>
              <p className="text-muted-foreground mt-2 font-mono">
                Real-time visualization of global cyber threats and attack patterns
              </p>
            </div>
          </div>

          <ThreatMap />
        </div>
      </DashboardLayout>
    </AuthGuard>
  );
}
