"use client";

import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Construction, Code, Zap, Clock, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";

interface ComingSoonPageProps {
  title?: string;
  description?: string;
  features?: string[];
  estimatedTime?: string;
}

export default function ComingSoonPage({
  title = "Feature Under Development",
  description = "This advanced security module is currently under active development by our cybersecurity team.",
  features = [
    "Real-time threat monitoring",
    "Advanced analytics dashboard",
    "Machine learning integration",
    "Automated response systems",
  ],
  estimatedTime = "Coming Soon™",
}: ComingSoonPageProps) {
  const router = useRouter();

  return (
    <DashboardLayout>
      <div className="min-h-screen flex items-center justify-center p-6 text-green-400 font-mono">
        <div className="max-w-2xl mx-auto text-center space-y-8">
          {/* Terminal Header */}
          <div className="space-y-4">
            <div className="flex justify-center">
              <div className="relative">
                <Construction className="h-20 w-20 text-green-400 animate-pulse" />
                <div className="absolute -top-2 -right-2">
                  <Code className="h-8 w-8 text-yellow-400 animate-bounce" />
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <h1 className="text-3xl font-bold text-green-300">[SYSTEM] {title}</h1>
              <Badge variant="outline" className="border-yellow-500 text-yellow-400">
                <Clock className="h-3 w-3 mr-1" />
                STATUS: IN_DEVELOPMENT
              </Badge>
            </div>
          </div>

          {/* Main Content Card */}
          <Card className="bg-gray-900 border-green-500/30">
            <CardContent className="p-8 space-y-6">
              {/* Terminal Window */}
              <div className="bg-black border border-green-500/50 rounded p-4 text-left">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-green-500/30">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                  <span className="ml-2 text-xs text-green-600">root@security-dashboard:~/dev</span>
                </div>

                <div className="space-y-1 text-sm">
                  <div className="text-green-400">
                    <span className="text-green-600">$</span> ./initialize_module.sh --verbose
                  </div>
                  <div className="text-green-300">[INFO] Initializing security module...</div>
                  <div className="text-blue-300">[DEBUG] Loading ML algorithms...</div>
                  <div className="text-yellow-300">[WARN] Advanced features under development</div>
                  <div className="text-green-300">[INFO] ETA: {estimatedTime}</div>
                  <div className="flex items-center">
                    <span className="text-green-400 animate-pulse">█</span>
                    <span className="ml-2 text-green-600 animate-pulse">Compiling neural networks...</span>
                  </div>
                </div>
              </div>

              {/* Description */}
              <div className="text-center space-y-4">
                <p className="text-green-300 leading-relaxed">{description}</p>

                {/* Features List */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-6">
                  {features.map((feature, index) => (
                    <div
                      key={index}
                      className="flex items-center space-x-2 text-sm text-green-400 bg-gray-800/50 p-2 rounded border border-green-500/20"
                    >
                      <Zap className="h-3 w-3 text-yellow-400" />
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>

                {/* Progress Indicator */}
                <div className="space-y-2 mt-8">
                  <div className="flex justify-between text-xs text-green-600">
                    <span>Development Progress</span>
                    <span>73%</span>
                  </div>
                  <div className="w-full bg-gray-800 rounded-full h-2 border border-green-500/30">
                    <div
                      className="bg-gradient-to-r from-green-600 to-green-400 h-2 rounded-full relative overflow-hidden"
                      style={{ width: "73%" }}
                    >
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse"></div>
                    </div>
                  </div>
                </div>

                {/* Back Button */}
                <div className="pt-6">
                  <Button
                    onClick={() => router.back()}
                    variant="outline"
                    className="border-green-500 text-green-400 hover:bg-green-700 hover:text-black"
                  >
                    <ArrowLeft className="h-4 w-4 mr-2" />
                    [RETURN] Go Back
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Footer */}
          <div className="text-xs text-green-600 space-y-1">
            <div>[NOTICE] This module is being developed with cutting-edge security protocols</div>
            <div>[SECURITY] All development follows OWASP guidelines and industry best practices</div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
