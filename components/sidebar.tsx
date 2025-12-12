"use client";

import { useRouter, usePathname } from "next/navigation";
import { useSidebar } from "@/components/sidebar-context";
import { useAuth } from "@/components/auth-context";
import { ResourceSwitcher } from "@/components/resource-switcher";
import {
  Shield,
  Activity,
  AlertTriangle,
  BarChart3,
  Globe,
  Settings,
  Users,
  FileText,
  Network,
  Eye,
  Lock,
  Server,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Home,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SidebarProps {
  className?: string;
}

const navigation = [
  {
    name: "Dashboard",
    href: "/dashboard",
    icon: Home,
    current: true,
    badge: null,
  },
  {
    name: "Live Monitor",
    href: "/dashboard/monitor",
    icon: Eye,
    current: false,
    badge: "LIVE",
  },
  {
    name: "Alerts",
    icon: AlertTriangle,
    href: "/alerts",
    count: 12,
  },
  {
    name: "Network Traffic",
    href: "/dashboard/network",
    icon: Network,
    current: false,
    badge: null,
  },
  {
    name: "Analytics",
    href: "/dashboard/analytics",
    icon: BarChart3,
    current: false,
    badge: null,
  },
  {
    name: "Threat Map",
    href: "/dashboard/map",
    icon: Globe,
    current: false,
    badge: "NEW",
  },
  {
    name: "Resources",
    href: "/dashboard/resources",
    icon: Server,
    current: false,
    badge: null,
  },
];

const bottomNavigation = [
  {
    name: "Settings",
    href: "/dashboard/settings",
    icon: Settings,
    current: false,
  },
];

export function Sidebar({ className }: SidebarProps) {
  const { collapsed, setCollapsed } = useSidebar();
  const { user, signOut } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  const handleLogout = async () => {
    try {
      console.log("🚪 Sidebar: Initiating logout...");
      await signOut();
      console.log("🏠 Sidebar: Redirecting to home page...");
      router.push("/");
    } catch (error) {
      console.error("❌ Sidebar: Logout error:", error);
      // Force redirect even if Supabase logout fails
      console.log("🔄 Sidebar: Force redirecting to home...");
      router.push("/");
    }
  };

  return (
    <div
      className={cn(
        "fixed left-0 top-0 z-40 flex flex-col h-screen bg-gray-900 border-r border-green-500/30 transition-all duration-300",
        collapsed ? "w-16" : "w-64",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-green-500/30">
        {!collapsed && (
          <div className="flex items-center space-x-2">
            <Shield className="h-6 w-6 text-green-400" />
            <span className="font-bold text-green-400 font-mono">EDOS-SHIELD</span>
          </div>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setCollapsed(!collapsed)}
          className="text-green-400 hover:text-green-300 hover:bg-green-500/10"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      {/* Status Indicator */}
      <div className="p-4 border-b border-green-500/30">
        <div className="flex items-center space-x-2">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
          {!collapsed && <span className="text-xs text-green-400 font-mono">SYSTEM OPERATIONAL</span>}
        </div>
      </div>

      {/* Resource Switcher */}
      {!collapsed && (
        <div className="p-4 border-b border-green-500/30">
          <ResourceSwitcher />
        </div>
      )}

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2 space-y-1">
        {navigation.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Button
              key={item.name}
              variant="ghost"
              onClick={() => router.push(item.href)}
              className={cn(
                "w-full justify-start text-left font-mono h-9",
                collapsed ? "px-2" : "px-3",
                isActive
                  ? "bg-green-500/20 text-green-300 border border-green-500/30"
                  : "text-green-400 hover:bg-green-500/10 hover:text-green-300"
              )}
            >
              <Icon className={cn("h-4 w-4 shrink-0", collapsed ? "" : "mr-3")} />
              {!collapsed && (
                <>
                  <span className="flex-1">{item.name}</span>
                  {item.badge && (
                    <Badge
                      className={cn(
                        "ml-2 text-xs font-mono",
                        item.badge === "LIVE"
                          ? "bg-red-500/20 text-red-300 border-red-500/30"
                          : item.badge === "NEW"
                          ? "bg-blue-500/20 text-blue-300 border-blue-500/30"
                          : "bg-yellow-500/20 text-yellow-300 border-yellow-500/30"
                      )}
                    >
                      {item.badge}
                    </Badge>
                  )}
                </>
              )}
            </Button>
          );
        })}
      </nav>

      {/* Bottom Navigation */}
      <div className="border-t border-green-500/30 p-3 space-y-1">
        {bottomNavigation.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;

          return (
            <Button
              key={item.name}
              variant="ghost"
              onClick={() => router.push(item.href)}
              className={cn(
                "w-full justify-start text-left font-mono h-9",
                collapsed ? "px-2" : "px-3",
                isActive
                  ? "bg-green-500/20 text-green-300 border border-green-500/30"
                  : "text-green-400 hover:bg-green-500/10 hover:text-green-300"
              )}
            >
              <Icon className={cn("h-4 w-4 shrink-0", collapsed ? "" : "mr-3")} />
              {!collapsed && <span>{item.name}</span>}
            </Button>
          );
        })}

        {/* Logout Button */}
        <Button
          variant="ghost"
          onClick={handleLogout}
          className={cn(
            "w-full justify-start text-left font-mono h-9 text-red-400 hover:bg-red-500/10 hover:text-red-300",
            collapsed ? "px-2" : "px-3"
          )}
        >
          <LogOut className={cn("h-4 w-4 shrink-0", collapsed ? "" : "mr-3")} />
          {!collapsed && <span>Logout</span>}
        </Button>
      </div>

      {/* User Info (when expanded) */}
      {!collapsed && user && (
        <div className="border-t border-green-500/30 p-3">
          <div className="text-xs text-green-500 font-mono">
            <div>{user.email}</div>
            <div className="text-green-600">clearance: {user.user_metadata?.full_name ? "admin" : "user"}</div>
            <div className="text-green-600 text-[10px]">auth: supabase</div>
          </div>
        </div>
      )}
    </div>
  );
}
