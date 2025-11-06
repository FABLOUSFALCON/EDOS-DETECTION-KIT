"use client";

import { useEffect, useState } from "react";
import { DashboardLayout } from "@/components/dashboard-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Shield, Eye, EyeOff, CheckCheck, Clock, TrendingUp } from "lucide-react";

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

  const login = async () => {
    try {
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

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem("token", data.access_token);
        setIsAuthenticated(true);
        return true;
      }
    } catch (error) {
      console.error("Error logging in:", error);
    }
    return false;
  };

  const fetchAlerts = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) {
        setIsAuthenticated(false);
        return;
      }

      const params = new URLSearchParams();
      if (filter.level) params.append("level", filter.level);
      if (filter.read !== null) params.append("read", filter.read.toString());
      params.append("limit", "100");

      const response = await fetch(`http://localhost:8000/api/alerts/?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setAlerts(data);
        setIsAuthenticated(true);
      } else if (response.status === 401) {
        // Token expired, try to login again
        const loginSuccess = await login();
        if (loginSuccess) {
          // Retry fetching alerts
          await fetchAlerts();
        }
      }
    } catch (error) {
      console.error("Error fetching alerts:", error);
    }
  };

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) return;

      const response = await fetch("http://localhost:8000/api/alerts/stats", {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        setStats(data);
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
      if (!token) {
        // Try to login automatically
        const loginSuccess = await login();
        if (!loginSuccess) {
          setLoading(false);
          return;
        }
      } else {
        setIsAuthenticated(true);
      }

      await Promise.all([fetchAlerts(), fetchStats()]);
      setLoading(false);
    };

    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

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
      <div className="p-6 text-green-400 font-mono space-y-6">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-green-400">[SECURITY-ALERTS] Threat Detection System</h1>
            <p className="text-sm text-green-600">Real-time monitoring and threat analysis</p>
          </div>
          <Button onClick={markAllRead} className="bg-green-700 hover:bg-green-600 text-black font-bold">
            <CheckCheck className="h-4 w-4 mr-2" />
            Mark All Read
          </Button>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="bg-gray-900 border-green-500/30">
              <CardHeader className="pb-3">
                <CardTitle className="text-green-400 flex items-center">
                  <AlertTriangle className="h-5 w-5 mr-2" />
                  Total Alerts
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-300">{stats.total_alerts}</div>
              </CardContent>
            </Card>

            <Card className="bg-gray-900 border-red-500/30">
              <CardHeader className="pb-3">
                <CardTitle className="text-red-400 flex items-center">
                  <EyeOff className="h-5 w-5 mr-2" />
                  Unread
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-300">{stats.unread_alerts}</div>
              </CardContent>
            </Card>

            <Card className="bg-gray-900 border-blue-500/30">
              <CardHeader className="pb-3">
                <CardTitle className="text-blue-400 flex items-center">
                  <Clock className="h-5 w-5 mr-2" />
                  Last 24h
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-300">{stats.recent_alerts_24h}</div>
              </CardContent>
            </Card>

            <Card className="bg-gray-900 border-purple-500/30">
              <CardHeader className="pb-3">
                <CardTitle className="text-purple-400 flex items-center">
                  <TrendingUp className="h-5 w-5 mr-2" />
                  Critical
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-purple-300">{stats.level_breakdown.CRITICAL || 0}</div>
              </CardContent>
            </Card>
          </div>
        )}

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
          {alerts.length === 0 ? (
            <Card className="bg-gray-900 border-green-500/30">
              <CardContent className="p-8 text-center">
                <Shield className="h-12 w-12 mx-auto mb-4 text-green-600" />
                <div className="text-green-600">[STATUS] No threats detected. System secure.</div>
              </CardContent>
            </Card>
          ) : (
            alerts.map((alert) => (
              <Card
                key={alert.id}
                className={`bg-gray-900 border-l-4 ${alert.read ? "opacity-70" : ""} ${getLevelColor(alert.level)
                  .split(" ")[2]
                  .replace("border-", "border-l-")}`}
              >
                <CardContent className="p-4">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        {getLevelIcon(alert.level)}
                        <Badge className={getLevelColor(alert.level)}>{alert.level}</Badge>
                        <Badge variant="outline" className="border-green-500/30 text-green-400">
                          {alert.category}
                        </Badge>
                        {!alert.read && (
                          <Badge variant="outline" className="border-red-500/30 text-red-400">
                            NEW
                          </Badge>
                        )}
                      </div>

                      <h3 className="text-green-300 font-semibold mb-1">{alert.title}</h3>

                      <p className="text-green-600 mb-2">{alert.message}</p>

                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-green-600">Source:</span>
                          <div className="text-green-400">{alert.source}</div>
                        </div>
                        {alert.target_ip && (
                          <div>
                            <span className="text-green-600">Target:</span>
                            <div className="text-green-400">{alert.target_ip}</div>
                          </div>
                        )}
                        {alert.confidence && (
                          <div>
                            <span className="text-green-600">Confidence:</span>
                            <div className="text-green-400">{(alert.confidence * 100).toFixed(1)}%</div>
                          </div>
                        )}
                        <div>
                          <span className="text-green-600">Time:</span>
                          <div className="text-green-400">{alert.time}</div>
                        </div>
                      </div>
                    </div>

                    <div className="flex gap-2 ml-4">
                      {!alert.read && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-green-500 text-green-400 hover:bg-green-700 hover:text-black"
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
      </div>
    </DashboardLayout>
  );
}
