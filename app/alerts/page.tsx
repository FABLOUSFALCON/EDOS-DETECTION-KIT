"use client";

import React, { useState, useEffect, useRef } from "react";
import { DashboardLayout } from "@/components/dashboard-layout";
import { AuthGuard } from "@/components/auth-guard";
import { useAuth } from "@/components/auth-context";
import {
  AlertTriangle,
  Shield,
  Eye,
  EyeOff,
  CheckCheck,
  Clock,
  Search,
  RefreshCw,
  TrendingUp,
  Activity,
  Zap,
  MapPin,
} from "lucide-react";

interface Alert {
  id: string;
  level: string;
  message: string;
  source: string;
  timestamp: string;
  time: string;
  read: boolean;
  title: string;
  category: string;
  confidence?: number;
  target_ip?: string;
  target_port?: number;
  detection_method?: string;
  severity: string;
  status: string;
  detected_at: string;
  attack_type: string;
}

interface AlertStats {
  total_alerts: number;
  unread_alerts: number;
  recent_alerts_24h: number;
  level_breakdown: Record<string, number>;
  timestamp: string;
}

export default function AlertsPage() {
  const { user, session, loading: authLoading } = useAuth();

  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [filteredAlerts, setFilteredAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<AlertStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedLevel, setSelectedLevel] = useState<string>("all");
  const [showUnreadOnly, setShowUnreadOnly] = useState(false);

  const [soundEnabled, setSoundEnabled] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Fetch alerts from database
  const fetchAlerts = async () => {
    try {
      setLoading(true);
      setError(null);

      // Check if user is authenticated
      if (!session?.access_token) {
        setError("Authentication required");
        return;
      }

      const response = await fetch("http://localhost:23335/api/alerts/", {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const alertsData = await response.json();
      setAlerts(alertsData);

      // Fetch stats
      const statsResponse = await fetch("http://localhost:23335/api/alerts/stats", {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });

      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats(statsData);
      }
    } catch (err) {
      console.error("Error fetching alerts:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch alerts");
    } finally {
      setLoading(false);
    }
  };

  // Apply filters
  useEffect(() => {
    let filtered = alerts;

    // Search filter
    if (searchTerm) {
      filtered = filtered.filter(
        (alert) =>
          alert.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
          alert.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
          alert.source.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Level filter
    if (selectedLevel !== "all") {
      filtered = filtered.filter((alert) => alert.level.toLowerCase() === selectedLevel.toLowerCase());
    }

    // Unread filter
    if (showUnreadOnly) {
      filtered = filtered.filter((alert) => !alert.read);
    }

    setFilteredAlerts(filtered);
  }, [alerts, searchTerm, selectedLevel, showUnreadOnly]);

  // Mark alert as read
  const markAsRead = async (alertId: string) => {
    try {
      if (!session?.access_token) return;

      const response = await fetch(`http://localhost:23335/api/alerts/${alertId}/read`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        setAlerts((prev) =>
          prev.map((alert) => (alert.id === alertId ? { ...alert, read: true, status: "acknowledged" } : alert))
        );
      }
    } catch (err) {
      console.error("Error marking alert as read:", err);
    }
  };

  // Resolve alert
  const resolveAlert = async (alertId: string) => {
    try {
      if (!session?.access_token) return;

      const response = await fetch(`http://localhost:23335/api/alerts/${alertId}/resolve`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          "Content-Type": "application/json",
        },
      });

      if (response.ok) {
        setAlerts((prev) =>
          prev.map((alert) => (alert.id === alertId ? { ...alert, status: "resolved", read: true } : alert))
        );
      }
    } catch (err) {
      console.error("Error resolving alert:", err);
    }
  };

  // Initial load - wait for authentication
  useEffect(() => {
    if (!authLoading && session) {
      fetchAlerts();
    }
  }, [authLoading, session]);

  // Auto-refresh every 30 seconds (only when authenticated)
  useEffect(() => {
    if (!session) return;

    const interval = setInterval(() => {
      if (session?.access_token) {
        fetchAlerts();
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [session]);

  const getSeverityColor = (level: string) => {
    switch (level.toUpperCase()) {
      case "CRITICAL":
        return "bg-red-500/20 text-red-300 border-red-500/30";
      case "HIGH":
        return "bg-orange-500/20 text-orange-300 border-orange-500/30";
      case "MEDIUM":
        return "bg-yellow-500/20 text-yellow-300 border-yellow-500/30";
      case "LOW":
        return "bg-blue-500/20 text-blue-300 border-blue-500/30";
      case "INFO":
        return "bg-gray-500/20 text-gray-300 border-gray-500/30";
      default:
        return "bg-gray-500/20 text-gray-300 border-gray-500/30";
    }
  };

  const getSeverityIcon = (level: string) => {
    switch (level.toUpperCase()) {
      case "CRITICAL":
      case "HIGH":
        return <AlertTriangle className="w-4 h-4" />;
      case "MEDIUM":
        return <Activity className="w-4 h-4" />;
      case "LOW":
      case "INFO":
        return <Zap className="w-4 h-4" />;
      default:
        return <Shield className="w-4 h-4" />;
    }
  };

  // Show loading while authentication is being checked
  if (authLoading) {
    return (
      <AuthGuard>
        <DashboardLayout>
          <div className="p-6 bg-black min-h-screen">
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-8 h-8 animate-spin text-green-400" />
              <span className="ml-2 text-lg text-green-300">Authenticating...</span>
            </div>
          </div>
        </DashboardLayout>
      </AuthGuard>
    );
  }

  if (loading) {
    return (
      <AuthGuard>
        <DashboardLayout>
          <div className="p-6 bg-black min-h-screen">
            <div className="flex items-center justify-center h-64">
              <RefreshCw className="w-8 h-8 animate-spin text-green-400" />
              <span className="ml-2 text-lg text-green-300">Loading alerts...</span>
            </div>
          </div>
        </DashboardLayout>
      </AuthGuard>
    );
  }

  if (error) {
    return (
      <AuthGuard>
        <DashboardLayout>
          <div className="p-6 bg-black min-h-screen">
            <div className="border border-red-500/30 bg-red-500/10 p-6 rounded-lg">
              <div className="flex items-center">
                <AlertTriangle className="w-5 h-5 text-red-400 mr-2" />
                <p className="text-red-300">Error loading alerts: {error}</p>
              </div>
              <button
                onClick={fetchAlerts}
                className="mt-4 flex items-center gap-2 px-4 py-2 border border-red-500/50 bg-red-500/10 text-red-400 rounded hover:bg-red-500/20 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Retry
              </button>
            </div>
          </div>
        </DashboardLayout>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <DashboardLayout>
        <div className="p-6 space-y-6 bg-black min-h-screen text-green-400">
          {/* Header */}
          <div className="flex justify-between items-center border-b border-green-500/30 pb-4">
            <div>
              <h1 className="text-3xl font-bold text-green-400 flex items-center gap-3">
                <AlertTriangle className="w-8 h-8" />
                Security Alerts
              </h1>
              <p className="text-green-300/70 mt-1">Real-time ML-generated security alerts from Redis stream</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={fetchAlerts}
                className="flex items-center gap-2 px-4 py-2 border border-green-500/50 bg-green-500/10 text-green-400 rounded hover:bg-green-500/20 transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </button>
            </div>
          </div>

          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-gray-900/50 border border-green-500/30 rounded-lg p-4 hover:border-green-500/50 transition-colors">
                <div className="flex items-center">
                  <Shield className="w-8 h-8 text-blue-400" />
                  <div className="ml-4">
                    <p className="text-2xl font-bold text-green-400">{stats.total_alerts}</p>
                    <p className="text-green-300/70 text-sm">Total Alerts</p>
                  </div>
                </div>
              </div>

              <div className="bg-gray-900/50 border border-red-500/30 rounded-lg p-4 hover:border-red-500/50 transition-colors">
                <div className="flex items-center">
                  <AlertTriangle className="w-8 h-8 text-red-400" />
                  <div className="ml-4">
                    <p className="text-2xl font-bold text-red-400">{stats.unread_alerts}</p>
                    <p className="text-green-300/70 text-sm">Unread</p>
                  </div>
                </div>
              </div>

              <div className="bg-gray-900/50 border border-orange-500/30 rounded-lg p-4 hover:border-orange-500/50 transition-colors">
                <div className="flex items-center">
                  <Clock className="w-8 h-8 text-orange-400" />
                  <div className="ml-4">
                    <p className="text-2xl font-bold text-orange-400">{stats.recent_alerts_24h}</p>
                    <p className="text-green-300/70 text-sm">Last 24h</p>
                  </div>
                </div>
              </div>

              <div className="bg-gray-900/50 border border-green-500/30 rounded-lg p-4 hover:border-green-500/50 transition-colors">
                <div className="flex items-center">
                  <TrendingUp className="w-8 h-8 text-green-400" />
                  <div className="ml-4">
                    <p className="text-2xl font-bold text-green-400">{stats.level_breakdown?.CRITICAL || 0}</p>
                    <p className="text-green-300/70 text-sm">Critical</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Filters */}
          <div className="bg-gray-900/50 border border-green-500/30 rounded-lg p-4">
            <h3 className="text-lg font-semibold text-green-400 mb-4 flex items-center gap-2">
              <Search className="w-5 h-5" />
              Filters
            </h3>
            <div className="flex flex-wrap gap-4">
              <div className="flex-1 min-w-[200px]">
                <input
                  placeholder="Search alerts..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full px-3 py-2 bg-black border border-green-500/50 rounded text-green-300 placeholder-green-500/50 focus:outline-none focus:ring-2 focus:ring-green-500/50"
                />
              </div>
              <select
                value={selectedLevel}
                onChange={(e) => setSelectedLevel(e.target.value)}
                className="px-3 py-2 bg-black border border-green-500/50 rounded text-green-300 focus:outline-none focus:ring-2 focus:ring-green-500/50"
              >
                <option value="all">All Levels</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="info">Info</option>
              </select>
              <button
                onClick={() => setShowUnreadOnly(!showUnreadOnly)}
                className={`flex items-center gap-2 px-4 py-2 border rounded transition-colors ${
                  showUnreadOnly
                    ? "border-green-500/50 bg-green-500/20 text-green-400"
                    : "border-green-500/30 bg-green-500/10 text-green-300 hover:bg-green-500/20"
                }`}
              >
                {showUnreadOnly ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                {showUnreadOnly ? "Show All" : "Unread Only"}
              </button>
            </div>
          </div>

          {/* Alert List */}
          <div className="bg-gray-900/50 border border-green-500/30 rounded-lg">
            <div className="border-b border-green-500/30 p-4">
              <h3 className="text-lg font-semibold text-green-400">Recent Alerts</h3>
            </div>
            <div className="p-4">
              {filteredAlerts.length > 0 ? (
                <div className="space-y-4">
                  {filteredAlerts.map((alert) => {
                    const severityColorClass = getSeverityColor(alert.level);
                    return (
                      <div
                        key={alert.id}
                        className={`p-4 border-l-4 bg-gray-900/80 rounded-r-lg hover:bg-gray-800/50 transition-colors cursor-pointer ${
                          alert.level.toUpperCase() === "CRITICAL"
                            ? "border-l-red-500"
                            : alert.level.toUpperCase() === "HIGH"
                            ? "border-l-orange-500"
                            : alert.level.toUpperCase() === "MEDIUM"
                            ? "border-l-yellow-500"
                            : "border-l-blue-500"
                        }`}
                        onClick={() => markAsRead(alert.id)}
                      >
                        <div className="flex justify-between items-start">
                          <div className="flex-1">
                            <div className="flex items-center gap-3 mb-2">
                              <span className={`px-2 py-1 rounded text-xs font-medium ${severityColorClass} border`}>
                                {getSeverityIcon(alert.level)}
                                <span className="ml-1">{alert.level.toUpperCase()}</span>
                              </span>
                              <span className="text-green-300/70 text-sm">
                                {alert.time || new Date(alert.detected_at).toLocaleString()}
                              </span>
                              {!alert.is_read && !alert.read && (
                                <span className="w-2 h-2 bg-red-500 rounded-full"></span>
                              )}
                            </div>

                            <h4 className="font-semibold text-green-300 mb-2">{alert.title || alert.message}</h4>

                            {alert.message && alert.title && (
                              <p className="text-green-300/80 text-sm mb-3">{alert.message}</p>
                            )}

                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                              {(alert.source || alert.source_ip) && (
                                <div>
                                  <p className="text-green-400/70 font-medium">Source IP</p>
                                  <p className="text-green-300 flex items-center">
                                    <MapPin className="w-3 h-3 mr-1" />
                                    {alert.source || alert.source_ip}
                                  </p>
                                </div>
                              )}
                              {alert.target_ip && (
                                <div>
                                  <p className="text-green-400/70 font-medium">Target IP</p>
                                  <p className="text-green-300">{alert.target_ip}</p>
                                </div>
                              )}
                              {alert.target_port && (
                                <div>
                                  <p className="text-green-400/70 font-medium">Target Port</p>
                                  <p className="text-green-300">{alert.target_port}</p>
                                </div>
                              )}
                              {(alert.confidence || alert.confidence_score) && (
                                <div>
                                  <p className="text-green-400/70 font-medium">Confidence</p>
                                  <p className="text-green-300">
                                    {((alert.confidence || alert.confidence_score) * 100).toFixed(1)}%
                                  </p>
                                </div>
                              )}
                            </div>

                            {(alert.detection_method || alert.attack_type) && (
                              <div className="mt-2">
                                <span className="text-xs bg-green-500/10 text-green-400 border border-green-500/30 px-2 py-1 rounded">
                                  {alert.detection_method || alert.attack_type}
                                </span>
                              </div>
                            )}

                            {alert.details && (
                              <div className="text-green-300/80 text-sm mt-3">
                                <pre className="whitespace-pre-wrap font-mono text-xs bg-black/50 p-2 rounded border border-green-500/30">
                                  {JSON.stringify(alert.details, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>

                          <div className="flex flex-col items-center gap-2 ml-4">
                            {!(alert.is_read || alert.read) && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  markAsRead(alert.id);
                                }}
                                className="flex items-center gap-1 px-2 py-1 text-xs border border-green-500/50 bg-green-500/10 text-green-400 rounded hover:bg-green-500/20 transition-colors"
                              >
                                <CheckCheck className="w-3 h-3" />
                                Mark Read
                              </button>
                            )}
                            {alert.status !== "resolved" && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  resolveAlert(alert.id);
                                }}
                                className="flex items-center gap-1 px-2 py-1 text-xs border border-blue-500/50 bg-blue-500/10 text-blue-400 rounded hover:bg-blue-500/20 transition-colors"
                              >
                                <Shield className="w-3 h-3" />
                                Resolve
                              </button>
                            )}
                            <div className="flex items-center">
                              {alert.is_read || alert.read ? (
                                <Eye className="w-4 h-4 text-green-500/50" />
                              ) : (
                                <EyeOff className="w-4 h-4 text-orange-400" />
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="text-center py-8">
                  <Shield className="w-16 h-16 text-green-500/30 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-green-400 mb-2">No Alerts Found</h3>
                  <p className="text-green-300/70">
                    {searchTerm || selectedLevel !== "all" || showUnreadOnly
                      ? "Try adjusting your filters to see more alerts."
                      : "All clear! No security alerts at the moment."}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </DashboardLayout>
    </AuthGuard>
  );
}
