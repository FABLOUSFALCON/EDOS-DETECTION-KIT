"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  AlertTriangle,
  Shield,
  Eye,
  EyeOff,
  CheckCheck,
  Clock,
  TrendingUp,
  Search,
  RefreshCw,
  Volume2,
  VolumeX,
  MoreHorizontal,
  MapPin,
  Activity,
  Zap,
} from "lucide-react";

import { formatDistanceToNow } from "date-fns";

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
}

interface AlertStats {
  total_alerts: number;
  unread_alerts: number;
  recent_alerts_24h: number;
  level_breakdown: Record<string, number>;
  timestamp: string;
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<AlertStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [filter, setFilter] = useState<{
    level: string | null;
    read: boolean | null;
  }>({ level: null, read: null });
  const [searchQuery, setSearchQuery] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [soundEnabled, setSoundEnabled] = useState(true);

  const [refreshing, setRefreshing] = useState(false);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const previousAlertsRef = useRef<Alert[]>([]);

  // Force fresh login by clearing all tokens
  const forceReauth = async () => {
    console.log("Forcing re-authentication...");
    localStorage.removeItem("token");
    setIsAuthenticated(false);
    setAlerts([]);
    setStats(null);

    const loginSuccess = await login();
    if (loginSuccess) {
      await Promise.all([fetchAlerts(), fetchStats()]);
    }
  };

  // Debug: Log alerts state changes
  useEffect(() => {
    console.log("Alerts state changed:", alerts.length, alerts);
  }, [alerts]);
  const login = async () => {
    try {
      console.log("Attempting to login...");
      const response = await fetch("http://localhost:8000/api/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: "puneet",
          password: "12345",
        }),
      });

      console.log("Login response status:", response.status);

      if (response.ok) {
        const data = await response.json();
        console.log("Login successful, token received");
        localStorage.setItem("token", data.access_token);
        setIsAuthenticated(true);
        return true;
      } else {
        const errorText = await response.text();
        console.error("Login failed:", response.status, errorText);
      }
    } catch (error) {
      console.error("Login error:", error);
    }
    return false;
  }; // Enhanced fetchAlerts with notification support
  const fetchAlerts = useCallback(async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        console.log("No token found, cannot fetch alerts");
        return;
      }

      console.log("Fetching alerts...");
      setRefreshing(true);
      const queryParams = new URLSearchParams();
      if (filter.level) queryParams.append("level", filter.level);
      if (filter.read !== null) queryParams.append("read", filter.read.toString());

      const url = `http://localhost:8000/api/alerts/?${queryParams}`;
      console.log("Fetching from:", url);

      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      console.log("Alerts response status:", response.status);

      if (response.ok) {
        const data = await response.json();
        console.log(`Fetched ${data.length} alerts:`, data);
        console.log("Setting alerts state with:", data);

        // Notifications are now handled globally - no need for page-specific notifications

        previousAlertsRef.current = data;
        setAlerts(data);
        console.log("Alerts state updated successfully");
      } else if (response.status === 401) {
        console.log("Token expired/invalid, attempting re-login...");
        // Clear the invalid token
        localStorage.removeItem("token");
        setIsAuthenticated(false);

        // Try to login again
        const loginSuccess = await login();
        if (loginSuccess) {
          console.log("Re-login successful, retrying fetch...");
          // Retry the fetch with new token
          const retryResponse = await fetch(url, {
            headers: {
              Authorization: `Bearer ${localStorage.getItem("token")}`,
            },
          });

          if (retryResponse.ok) {
            const retryData = await retryResponse.json();
            console.log(`Retry fetch successful: ${retryData.length} alerts`);
            previousAlertsRef.current = retryData;
            setAlerts(retryData);
          } else {
            console.error("Retry fetch also failed:", retryResponse.status);
          }
        }
      } else {
        const errorText = await response.text();
        console.error("Failed to fetch alerts:", response.status, errorText);
      }
    } catch (error) {
      console.error("Error fetching alerts:", error);
      console.error("Failed to fetch alerts");
    } finally {
      setRefreshing(false);
    }
  }, [filter.level, filter.read]);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        console.log("No token found, cannot fetch stats");
        return;
      }

      console.log("Fetching alert stats...");
      const response = await fetch("http://localhost:8000/api/alerts/stats", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      console.log("Stats response status:", response.status);

      if (response.ok) {
        const data = await response.json();
        console.log("Stats data:", data);
        setStats(data);
      } else if (response.status === 401) {
        console.log("Stats: Token expired/invalid, attempting re-login...");
        // The fetchAlerts function will handle the re-login, so just log here
      } else {
        const errorText = await response.text();
        console.error("Failed to fetch stats:", response.status, errorText);
      }
    } catch (error) {
      console.error("Error fetching alert stats:", error);
    }
  };

  const markAsRead = async (alertId: string) => {
    try {
      const token = localStorage.getItem("token");
      if (!token) return;

      const response = await fetch(`http://localhost:8000/api/alerts/${alertId}/read`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        // Update the alert in the local state
        setAlerts((prev) => prev.map((alert) => (alert.id === alertId ? { ...alert, read: true } : alert)));
        // Refresh stats
        fetchStats();
      }
    } catch (error) {
      console.error("Error marking alert as read:", error);
    }
  };

  const markAllRead = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) return;

      const response = await fetch("http://localhost:8000/api/alerts/mark-all-read", {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        setAlerts((prev) => prev.map((alert) => ({ ...alert, read: true })));
        fetchStats();
      }
    } catch (error) {
      console.error("Error marking all alerts as read:", error);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);

      // Check if we have a token
      const token = localStorage.getItem("token");
      console.log("Token check:", token ? `Found token: ${token.substring(0, 20)}...` : "No token found");

      if (!token) {
        console.log("No token found, attempting login...");
        // Try to login automatically
        const loginSuccess = await login();
        if (!loginSuccess) {
          console.log("Login failed, stopping data load");
          setLoading(false);
          return;
        }
      } else {
        console.log("Token found, setting authenticated");
        setIsAuthenticated(true);
      }

      console.log("Loading alerts and stats...");
      await Promise.all([fetchAlerts(), fetchStats()]);
      console.log("Data loading complete");
      setLoading(false);
    };

    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  // Auto-refresh functionality
  useEffect(() => {
    if (autoRefresh && isAuthenticated) {
      intervalRef.current = setInterval(() => {
        fetchAlerts(); // Auto-refresh alerts
        fetchStats();
      }, 10000); // Refresh every 10 seconds

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    }
  }, [autoRefresh, isAuthenticated, fetchAlerts]);

  const getLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case "critical":
        return "bg-red-900 text-red-100 border-red-500";
      case "high":
        return "bg-orange-900 text-orange-100 border-orange-500";
      case "medium":
        return "bg-yellow-900 text-yellow-100 border-yellow-500";
      case "low":
        return "bg-green-900 text-green-100 border-green-500";
      default:
        return "bg-gray-900 text-gray-100 border-gray-500";
    }
  };

  const getLevelIcon = (level: string) => {
    switch (level.toLowerCase()) {
      case "critical":
        return <AlertTriangle className="h-4 w-4" />;
      case "high":
        return <Shield className="h-4 w-4" />;
      default:
        return <Eye className="h-4 w-4" />;
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-full text-green-400 font-mono">
          <div className="text-center">
            <div className="animate-spin text-4xl mb-4">⚡</div>
            <div>[LOADING] Analyzing threat intelligence...</div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (!isAuthenticated) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-full text-green-400 font-mono">
          <div className="text-center">
            <Shield className="h-16 w-16 mx-auto mb-4 text-red-400" />
            <div className="text-red-400 mb-4">[ACCESS DENIED] Authentication Required</div>
            <Button
              onClick={async () => {
                setLoading(true);
                const success = await login();
                if (success) {
                  await Promise.all([fetchAlerts(), fetchStats()]);
                }
                setLoading(false);
              }}
              className="bg-green-700 hover:bg-green-600 text-black font-bold"
            >
              <Shield className="h-4 w-4 mr-2" />
              Authenticate System
            </Button>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Clean Professional Header */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-bold text-white mb-2">Security Alerts</h1>
            <p className="text-gray-400">Monitor and manage security threats across your infrastructure</p>
          </div>
          <div className="flex items-center gap-3">
            {stats && stats.unread_alerts > 0 && (
              <div className="text-sm text-gray-400 bg-gray-800 px-3 py-2 rounded-lg border border-gray-700">
                {stats.unread_alerts} unread alert{stats.unread_alerts !== 1 ? "s" : ""}
              </div>
            )}
            <Button
              onClick={markAllRead}
              disabled={!stats || stats.unread_alerts === 0}
              className="group relative overflow-hidden bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium px-6 py-2.5 rounded-lg transition-all duration-200 disabled:cursor-not-allowed shadow-lg hover:shadow-blue-600/25"
            >
              <div className="flex items-center">
                <CheckCheck className="h-4 w-4 mr-2 group-hover:scale-110 transition-transform duration-200" />
                <span className="relative">{!stats || stats.unread_alerts === 0 ? "All Read" : "Mark All Read"}</span>
              </div>
              {stats && stats.unread_alerts > 0 && (
                <div className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity duration-200 rounded-lg" />
              )}
            </Button>
          </div>
        </div>

        {/* Clean Professional Stats */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="bg-gray-900 border-gray-800 hover:border-gray-700 transition-colors">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-400">Total Alerts</p>
                    <p className="text-3xl font-bold text-white">{stats.total_alerts}</p>
                  </div>
                  <AlertTriangle className="h-8 w-8 text-blue-400" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gray-900 border-gray-800 hover:border-gray-700 transition-colors">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-400">Unread</p>
                    <p className="text-3xl font-bold text-white">{stats.unread_alerts}</p>
                  </div>
                  <div className="relative">
                    <EyeOff className="h-8 w-8 text-orange-400" />
                    {stats.unread_alerts > 0 && (
                      <div className="absolute -top-1 -right-1 h-3 w-3 bg-red-500 rounded-full" />
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gray-900 border-gray-800 hover:border-gray-700 transition-colors">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-400">Last 24h</p>
                    <p className="text-3xl font-bold text-white">{stats.recent_alerts_24h}</p>
                  </div>
                  <Clock className="h-8 w-8 text-green-400" />
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gray-900 border-gray-800 hover:border-gray-700 transition-colors">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-400">Critical</p>
                    <p className="text-3xl font-bold text-white">{stats.level_breakdown.CRITICAL || 0}</p>
                  </div>
                  <div className="relative">
                    <TrendingUp className="h-8 w-8 text-red-400" />
                    {(stats.level_breakdown.CRITICAL || 0) > 0 && (
                      <div className="absolute -top-1 -right-1 h-3 w-3 bg-red-500 rounded-full animate-pulse" />
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Clean Controls */}
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
            <Input
              placeholder="Search alerts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 bg-gray-900 border-gray-700 text-white placeholder-gray-400 focus:border-gray-600"
            />
          </div>

          {/* Control Buttons */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`transition-colors ${
                autoRefresh
                  ? "bg-blue-600 text-white border-blue-600 hover:bg-blue-700"
                  : "border-gray-600 text-gray-300 hover:bg-gray-800"
              }`}
            >
              {autoRefresh ? <Activity className="h-4 w-4 mr-2" /> : <RefreshCw className="h-4 w-4 mr-2" />}
              Auto-refresh
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setSoundEnabled(!soundEnabled)}
              className={`transition-colors ${
                soundEnabled
                  ? "bg-green-600 text-white border-green-600 hover:bg-green-700"
                  : "border-gray-600 text-gray-300 hover:bg-gray-800"
              }`}
            >
              {soundEnabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
            </Button>

            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                fetchAlerts();
                fetchStats();
                console.log("Alerts refreshed");
              }}
              disabled={refreshing}
              className="border-gray-600 text-gray-300 hover:bg-gray-800 disabled:opacity-50"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            </Button>

            {/* Debug: Force Re-auth Button */}
            <Button
              variant="outline"
              size="sm"
              onClick={forceReauth}
              className="border-red-600 text-red-300 hover:bg-red-800"
              title="Force re-authentication (debug)"
            >
              🔑 Re-auth
            </Button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2">
          <Badge
            variant={filter.level === null ? "default" : "outline"}
            className={`cursor-pointer ${
              filter.level === null
                ? "bg-green-700 text-black"
                : "border-green-500 text-green-400 hover:bg-green-700 hover:text-black"
            }`}
            onClick={() => setFilter({ ...filter, level: null })}
          >
            All Levels
          </Badge>
          {["CRITICAL", "HIGH", "MEDIUM", "LOW"].map((level) => (
            <Badge
              key={level}
              variant={filter.level === level ? "default" : "outline"}
              className={`cursor-pointer ${
                filter.level === level
                  ? "bg-green-700 text-black"
                  : "border-green-500 text-green-400 hover:bg-green-700 hover:text-black"
              }`}
              onClick={() => setFilter({ ...filter, level })}
            >
              {level}
            </Badge>
          ))}
          <div className="border-l border-green-500/30 mx-2"></div>
          <Badge
            variant={filter.read === null ? "default" : "outline"}
            className={`cursor-pointer ${
              filter.read === null
                ? "bg-green-700 text-black"
                : "border-green-500 text-green-400 hover:bg-green-700 hover:text-black"
            }`}
            onClick={() => setFilter({ ...filter, read: null })}
          >
            All Status
          </Badge>
          <Badge
            variant={filter.read === false ? "default" : "outline"}
            className={`cursor-pointer ${
              filter.read === false
                ? "bg-green-700 text-black"
                : "border-green-500 text-green-400 hover:bg-green-700 hover:text-black"
            }`}
            onClick={() => setFilter({ ...filter, read: false })}
          >
            Unread
          </Badge>
          <Badge
            variant={filter.read === true ? "default" : "outline"}
            className={`cursor-pointer ${
              filter.read === true
                ? "bg-green-700 text-black"
                : "border-green-500 text-green-400 hover:bg-green-700 hover:text-black"
            }`}
            onClick={() => setFilter({ ...filter, read: true })}
          >
            Read
          </Badge>
        </div>

        {/* Alerts List */}
        <div className="space-y-3">
          {/* Debug Info */}
          {typeof window !== "undefined" && (
            <div className="text-xs text-gray-500 mb-2">
              DEBUG: alerts.length = {alerts.length}, isAuthenticated = {isAuthenticated.toString()}, loading ={" "}
              {loading.toString()}
            </div>
          )}
          {alerts.length === 0 ? (
            <Card className="bg-gray-900 border-green-500/30">
              <CardContent className="p-8 text-center">
                <Shield className="h-12 w-12 mx-auto mb-4 text-green-600" />
                <div className="text-green-600">[STATUS] No threats detected. System secure.</div>
              </CardContent>
            </Card>
          ) : (
            alerts
              .filter(
                (alert) =>
                  searchQuery === "" ||
                  alert.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
                  alert.source.toLowerCase().includes(searchQuery.toLowerCase()) ||
                  alert.title.toLowerCase().includes(searchQuery.toLowerCase())
              )
              .map((alert) => (
                <Card
                  key={alert.id}
                  className={`bg-gray-900/50 backdrop-blur-sm border-l-4 transition-all duration-300 hover:bg-gray-800/60 hover:shadow-lg hover:shadow-green-500/10 ${
                    alert.read ? "opacity-70" : ""
                  } ${getLevelColor(alert.level).split(" ")[2].replace("border-", "border-l-")}`}
                >
                  <CardContent className="p-6">
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        {/* Enhanced Header */}
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-3">
                            {getLevelIcon(alert.level)}
                            <Badge className={`${getLevelColor(alert.level)} font-semibold`}>{alert.level}</Badge>
                            <Badge variant="outline" className="border-green-500/30 text-green-400 font-medium">
                              {alert.category?.toUpperCase() || "NETWORK"}
                            </Badge>
                            {!alert.read && (
                              <Badge variant="outline" className="border-red-500/30 text-red-400 animate-pulse">
                                <Zap className="h-3 w-3 mr-1" />
                                NEW
                              </Badge>
                            )}
                          </div>
                          <div className="text-xs text-green-600">
                            {formatDistanceToNow(new Date(alert.timestamp), { addSuffix: true })}
                          </div>
                        </div>

                        {/* Enhanced Title and Message */}
                        <h3 className="text-green-300 font-bold text-lg mb-2 leading-tight">{alert.title}</h3>
                        <p className="text-green-600 mb-4 leading-relaxed">{alert.message}</p>

                        {/* Enhanced Information Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4 text-sm bg-gray-800/30 rounded-lg p-4 border border-green-500/10">
                          <div className="flex items-center space-x-2">
                            <MapPin className="h-4 w-4 text-green-500" />
                            <div>
                              <span className="text-green-600 block text-xs">Source IP</span>
                              <div className="text-green-400 font-mono font-semibold">{alert.source}</div>
                            </div>
                          </div>

                          {alert.target_ip && (
                            <div className="flex items-center space-x-2">
                              <Shield className="h-4 w-4 text-orange-500" />
                              <div>
                                <span className="text-green-600 block text-xs">Target IP</span>
                                <div className="text-green-400 font-mono font-semibold">
                                  {alert.target_ip}
                                  {alert.target_port && <span className="text-green-600">:{alert.target_port}</span>}
                                </div>
                              </div>
                            </div>
                          )}

                          {alert.confidence && (
                            <div className="flex items-center space-x-2">
                              <TrendingUp className="h-4 w-4 text-blue-500" />
                              <div>
                                <span className="text-green-600 block text-xs">Confidence</span>
                                <div className="text-green-400 font-semibold">
                                  {(alert.confidence * 100).toFixed(1)}%
                                </div>
                              </div>
                            </div>
                          )}

                          {alert.detection_method && (
                            <div className="flex items-center space-x-2">
                              <Activity className="h-4 w-4 text-purple-500" />
                              <div>
                                <span className="text-green-600 block text-xs">Detection</span>
                                <div className="text-green-400 font-semibold capitalize">
                                  {alert.detection_method.replace("_", " ")}
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      {/* Enhanced Action Buttons */}
                      <div className="flex flex-col gap-2 ml-6">
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-green-500/50 text-green-400 hover:bg-green-700 hover:text-black transition-all duration-200"
                          onClick={() => setSelectedAlert(alert)}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>

                        {!alert.read && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-blue-500/50 text-blue-400 hover:bg-blue-700 hover:text-black transition-all duration-200"
                            onClick={() => markAsRead(alert.id)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
          )}
        </div>

        {/* Alert Details Modal */}
        {selectedAlert && (
          <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
            <Card className="bg-gray-900 border-green-500/30 w-full max-w-4xl max-h-[90vh] overflow-y-auto">
              <CardHeader className="border-b border-green-500/20">
                <div className="flex justify-between items-start">
                  <div>
                    <CardTitle className="text-green-300 text-xl flex items-center gap-3">
                      {getLevelIcon(selectedAlert.level)}
                      {selectedAlert.title}
                    </CardTitle>
                    <div className="flex items-center gap-3 mt-2">
                      <Badge className={getLevelColor(selectedAlert.level)}>{selectedAlert.level}</Badge>
                      <Badge variant="outline" className="border-green-500/30 text-green-400">
                        {selectedAlert.category?.toUpperCase() || "NETWORK"}
                      </Badge>
                      <span className="text-sm text-green-600">
                        {formatDistanceToNow(new Date(selectedAlert.timestamp), { addSuffix: true })}
                      </span>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedAlert(null)}
                    className="border-red-500/50 text-red-400 hover:bg-red-700 hover:text-white"
                  >
                    ✕
                  </Button>
                </div>
              </CardHeader>

              <CardContent className="p-6">
                <div className="space-y-6">
                  {/* Alert Description */}
                  <div>
                    <h3 className="text-green-400 font-semibold mb-2 flex items-center">
                      <AlertTriangle className="h-4 w-4 mr-2" />
                      Threat Description
                    </h3>
                    <p className="text-green-600 bg-gray-800/30 p-4 rounded border border-green-500/10">
                      {selectedAlert.message}
                    </p>
                  </div>

                  {/* Technical Details */}
                  <div>
                    <h3 className="text-green-400 font-semibold mb-3 flex items-center">
                      <Activity className="h-4 w-4 mr-2" />
                      Technical Analysis
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="bg-gray-800/30 p-4 rounded border border-green-500/10">
                        <div className="space-y-3">
                          <div>
                            <span className="text-green-600 text-sm">Source IP Address</span>
                            <div className="text-green-400 font-mono font-semibold text-lg">{selectedAlert.source}</div>
                          </div>
                          {selectedAlert.target_ip && (
                            <div>
                              <span className="text-green-600 text-sm">Target IP Address</span>
                              <div className="text-green-400 font-mono font-semibold text-lg">
                                {selectedAlert.target_ip}
                                {selectedAlert.target_port && (
                                  <span className="text-green-600">:{selectedAlert.target_port}</span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="bg-gray-800/30 p-4 rounded border border-green-500/10">
                        <div className="space-y-3">
                          {selectedAlert.confidence && (
                            <div>
                              <span className="text-green-600 text-sm">Detection Confidence</span>
                              <div className="flex items-center space-x-2">
                                <div className="text-green-400 font-semibold text-lg">
                                  {(selectedAlert.confidence * 100).toFixed(1)}%
                                </div>
                                <div className="flex-1 bg-gray-700 rounded-full h-2">
                                  <div
                                    className="bg-green-500 h-2 rounded-full transition-all duration-300"
                                    style={{ width: `${selectedAlert.confidence * 100}%` }}
                                  />
                                </div>
                              </div>
                            </div>
                          )}
                          {selectedAlert.detection_method && (
                            <div>
                              <span className="text-green-600 text-sm">Detection Method</span>
                              <div className="text-green-400 font-semibold text-lg capitalize">
                                {selectedAlert.detection_method.replace("_", " ")}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="flex gap-3 pt-4 border-t border-green-500/20">
                    {!selectedAlert.read && (
                      <Button
                        onClick={() => {
                          markAsRead(selectedAlert.id);
                          setSelectedAlert(null);
                        }}
                        className="bg-green-700 hover:bg-green-600 text-black font-semibold"
                      >
                        <Eye className="h-4 w-4 mr-2" />
                        Mark as Read
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      onClick={() => setSelectedAlert(null)}
                      className="border-green-500/50 text-green-400"
                    >
                      Close Details
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
