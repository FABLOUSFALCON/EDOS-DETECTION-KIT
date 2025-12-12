"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { DashboardLayout } from "@/components/dashboard-layout";
import { AuthGuard } from "@/components/auth-guard";
import { useAuth } from "@/components/auth-context";
import {
  AlertTriangle,
  Shield,
  Eye,
  CheckCheck,
  Search,
  RefreshCw,
  Filter,
  ChevronLeft,
  ChevronRight,
  MoreHorizontal,
  Trash2,
  Bell,
  BellOff,
  Clock,
  MapPin,
  Activity,
  Check,
  AlertCircle,
} from "lucide-react";

// Types
interface Alert {
  id: string;
  user_id: string;
  resource_id: string | null;
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  description: string;
  source_ip: string | null;
  target_ip: string | null;
  target_port: number | null;
  detection_method: string;
  confidence_score: number;
  status: "new" | "acknowledged" | "investigating" | "resolved" | "false_positive";
  raw_data: Record<string, unknown>;
  detected_at: string;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
  category: {
    name: string;
    color: string;
  };
}

interface AlertResponse {
  alerts: Alert[];
  pagination: {
    total_count: number;
    total_pages: number;
    current_page: number;
    page_size: number;
    has_next: boolean;
    has_prev: boolean;
  };
}

interface AlertStats {
  total_unresolved: number;
  total_unread: number;
  recent_24h: number;
  severity_breakdown: Record<string, number>;
}

interface AlertFilters {
  search: string;
  severity: string[];
  status: string[];
  dateFrom: string;
  dateTo: string;
  sortBy: string;
  sortOrder: "asc" | "desc";
}

// Constants
const SEVERITY_COLORS = {
  critical: "bg-red-500 text-white",
  high: "bg-orange-500 text-white",
  medium: "bg-yellow-500 text-black",
  low: "bg-blue-500 text-white",
  info: "bg-gray-500 text-white",
};

const SEVERITY_ICONS = {
  critical: "🔴",
  high: "🟠",
  medium: "🟡",
  low: "🔵",
  info: "⚪",
};

const STATUS_COLORS = {
  new: "bg-red-100 text-red-800",
  acknowledged: "bg-yellow-100 text-yellow-800",
  investigating: "bg-blue-100 text-blue-800",
  resolved: "bg-[#27d77a]/20 text-[#27d77a]",
  false_positive: "bg-gray-100 text-gray-800",
};

export default function AlertsPage() {
  const { user, session } = useAuth();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<AlertStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedAlerts, setSelectedAlerts] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(20);
  const [pagination, setPagination] = useState<AlertResponse["pagination"] | null>(null);
  const [lastAlertCount, setLastAlertCount] = useState<number>(0);
  const [newAlertsCount, setNewAlertsCount] = useState<number>(0);
  const [alertActionsMenu, setAlertActionsMenu] = useState<string | null>(null);

  // Filters
  const [filters, setFilters] = useState<AlertFilters>({
    search: "",
    severity: [],
    status: [],
    dateFrom: "",
    dateTo: "",
    sortBy: "detected_at",
    sortOrder: "desc",
  });

  // UI State
  const [showFilters, setShowFilters] = useState(false);
  const [bulkActionMenuOpen, setBulkActionMenuOpen] = useState(false);
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false);

  // Debounced search
  const [searchDebounce, setSearchDebounce] = useState<NodeJS.Timeout | null>(null);

  const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:23335";

  // Memoized API URL
  const apiUrl = useMemo(() => {
    const params = new URLSearchParams();
    params.set("page", currentPage.toString());
    params.set("limit", pageSize.toString());
    params.set("sort_by", filters.sortBy);
    params.set("sort_order", filters.sortOrder);

    if (filters.search.trim()) {
      params.set("search", filters.search.trim());
    }

    filters.severity.forEach((sev) => {
      params.append("severity", sev);
    });

    filters.status.forEach((status) => {
      params.append("status", status);
    });

    if (filters.dateFrom) {
      params.set("date_from", filters.dateFrom);
    }

    if (filters.dateTo) {
      params.set("date_to", filters.dateTo);
    }

    return `${baseUrl}/api/alerts-new/?${params.toString()}`;
  }, [baseUrl, currentPage, pageSize, filters]);

  // Fetch alerts
  const fetchAlerts = useCallback(async () => {
    try {
      setRefreshing(true);

      // Check if we have a valid session token
      if (!session?.access_token) {
        console.log("🔒 No access token available, skipping alerts fetch");
        return;
      }

      const response = await fetch(apiUrl, {
        headers: {
          Authorization: `Bearer ${session?.access_token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: AlertResponse = await response.json();
      setAlerts(data.alerts);
      setPagination(data.pagination);

      // Debug: Log alert information
      const userIds = [...new Set(data.alerts.map((a) => a.user_id))];
      console.log("🔍 Fetched alerts:", {
        total: data.alerts.length,
        unread: data.alerts.filter((a) => a.status === "new").length,
        user_ids: userIds,
        sample_alerts: data.alerts.slice(0, 2).map((a) => ({
          id: a.id,
          status: a.status,
          user_id: a.user_id,
        })),
      });
      console.log("🆔 Alert user IDs in database:", userIds);
      console.log("👤 Current logged-in user ID:", user?.id);
    } catch (error) {
      console.error("Failed to fetch alerts:", error);
      setAlerts([]);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  }, [apiUrl, session?.access_token]);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      // Check if we have a valid session token
      if (!session?.access_token) {
        console.log("🔒 No access token available, skipping stats fetch");
        return;
      }

      const response = await fetch(`${baseUrl}/api/alerts-new/stats`, {
        headers: {
          Authorization: `Bearer ${session?.access_token}`,
        },
      });
      if (response.ok) {
        const data: AlertStats = await response.json();

        // Check for new alerts
        if (lastAlertCount > 0 && data.total_unresolved > lastAlertCount) {
          setNewAlertsCount(data.total_unresolved - lastAlertCount);
          // Show notification
          if ("Notification" in window && Notification.permission === "granted") {
            new Notification("New Security Alert", {
              body: `${data.total_unresolved - lastAlertCount} new alert(s) detected`,
              icon: "/favicon.ico",
            });
          }
        }

        setLastAlertCount(data.total_unresolved);
        setStats(data);
      }
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    }
  }, [baseUrl, lastAlertCount, session?.access_token]);

  // Select/deselect all alerts
  const toggleSelectAll = useCallback(() => {
    if (selectedAlerts.size === alerts.length) {
      setSelectedAlerts(new Set());
    } else {
      setSelectedAlerts(new Set(alerts.map((alert) => alert.id)));
    }
  }, [selectedAlerts.size, alerts]);

  // Bulk mark as read
  const bulkMarkAsRead = useCallback(async () => {
    if (selectedAlerts.size === 0) return;

    try {
      const response = await fetch(`${baseUrl}/api/alerts-new/bulk-update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({
          alert_ids: Array.from(selectedAlerts),
          status: "acknowledged",
          acknowledged_by: user?.id,
        }),
      });

      if (response.ok) {
        setSelectedAlerts(new Set());
        setBulkActionMenuOpen(false);
        await fetchAlerts();
        await fetchStats();
      }
    } catch (error) {
      console.error("Failed to bulk mark as read:", error);
    }
  }, [selectedAlerts, baseUrl, user?.id, fetchAlerts, fetchStats, session?.access_token]);

  // Bulk resolve alerts
  const bulkResolveAlerts = useCallback(async () => {
    if (selectedAlerts.size === 0) return;

    try {
      const response = await fetch(`${baseUrl}/api/alerts-new/bulk-update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({
          alert_ids: Array.from(selectedAlerts),
          status: "resolved",
          acknowledged_by: user?.id,
        }),
      });

      if (response.ok) {
        setSelectedAlerts(new Set());
        setBulkActionMenuOpen(false);
        await fetchAlerts();
        await fetchStats();
      }
    } catch (error) {
      console.error("Failed to bulk resolve alerts:", error);
    }
  }, [selectedAlerts, baseUrl, user?.id, fetchAlerts, fetchStats, session?.access_token]);

  // Bulk delete alerts
  const bulkDeleteAlerts = useCallback(async () => {
    if (selectedAlerts.size === 0) return;

    // Confirm delete action
    if (
      !confirm(
        `Are you sure you want to permanently delete ${selectedAlerts.size} alert(s)? This action cannot be undone.`
      )
    ) {
      return;
    }

    try {
      const response = await fetch(`${baseUrl}/api/alerts-new/bulk-delete`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({
          alert_ids: Array.from(selectedAlerts),
        }),
      });

      if (response.ok) {
        setSelectedAlerts(new Set());
        setBulkActionMenuOpen(false);
        await fetchAlerts();
        await fetchStats();
      }
    } catch (error) {
      console.error("Failed to bulk delete alerts:", error);
    }
  }, [selectedAlerts, baseUrl, fetchAlerts, fetchStats, session?.access_token]);

  // Effects
  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  useEffect(() => {
    // Request notification permission
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }

    // Close alert actions menu on outside click
    const handleClickOutside = (e: MouseEvent) => {
      if (alertActionsMenu && !(e.target as Element).closest(".relative")) {
        setAlertActionsMenu(null);
      }
      if (bulkActionMenuOpen && !(e.target as Element).closest(".relative")) {
        setBulkActionMenuOpen(false);
      }
    };

    document.addEventListener("click", handleClickOutside);

    // Keyboard shortcuts
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case "r":
            e.preventDefault();
            fetchAlerts();
            break;
          case "a":
            e.preventDefault();
            toggleSelectAll();
            break;
          case "m":
            e.preventDefault();
            if (selectedAlerts.size > 0) {
              bulkMarkAsRead();
            }
            break;
          case "/":
            e.preventDefault();
            setShowFilters((prev) => !prev);
            break;
          case "h":
            e.preventDefault();
            setShowKeyboardHelp(true);
            break;
        }
      }
    };

    document.addEventListener("keydown", handleKeyPress);

    fetchStats();
    const statsInterval = setInterval(fetchStats, 30000); // Refresh stats every 30s
    const alertsInterval = setInterval(fetchAlerts, 60000); // Refresh alerts every 60s
    return () => {
      clearInterval(statsInterval);
      clearInterval(alertsInterval);
      document.removeEventListener("keydown", handleKeyPress);
      document.removeEventListener("click", handleClickOutside);
    };
  }, [
    fetchStats,
    fetchAlerts,
    selectedAlerts.size,
    toggleSelectAll,
    bulkMarkAsRead,
    alertActionsMenu,
    bulkActionMenuOpen,
  ]);

  // Debounced search effect
  useEffect(() => {
    if (searchDebounce) {
      clearTimeout(searchDebounce);
    }

    const timeout = setTimeout(() => {
      setCurrentPage(1); // Reset to first page on search
      fetchAlerts();
    }, 500);

    setSearchDebounce(timeout);

    return () => {
      if (timeout) clearTimeout(timeout);
    };
  }, [filters.search, fetchAlerts]); // Handle filter changes
  const handleFilterChange = (key: keyof AlertFilters, value: string | string[]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setCurrentPage(1); // Reset to first page
  };

  // Handle search change
  const handleSearchChange = (value: string) => {
    setFilters((prev) => ({ ...prev, search: value }));
  };

  // Handle severity filter toggle
  const toggleSeverityFilter = (severity: string) => {
    setFilters((prev) => ({
      ...prev,
      severity: prev.severity.includes(severity)
        ? prev.severity.filter((s) => s !== severity)
        : [...prev.severity, severity],
    }));
    setCurrentPage(1);
  };

  // Handle status filter toggle
  const toggleStatusFilter = (status: string) => {
    setFilters((prev) => ({
      ...prev,
      status: prev.status.includes(status) ? prev.status.filter((s) => s !== status) : [...prev.status, status],
    }));
    setCurrentPage(1);
  };

  // Select/deselect alert
  const toggleAlertSelection = (alertId: string) => {
    setSelectedAlerts((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(alertId)) {
        newSet.delete(alertId);
      } else {
        newSet.add(alertId);
      }
      return newSet;
    });
  };

  // Mark single alert as read
  const markAsRead = async (alertId: string) => {
    try {
      const response = await fetch(`${baseUrl}/api/alerts-new/${alertId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({
          status: "acknowledged",
          acknowledged_by: user?.id,
        }),
      });

      if (response.ok) {
        await fetchAlerts();
        await fetchStats();
      }
    } catch (error) {
      console.error("Failed to mark alert as read:", error);
    }
  };

  // Resolve single alert
  const resolveAlert = async (alertId: string) => {
    try {
      const response = await fetch(`${baseUrl}/api/alerts-new/${alertId}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({
          status: "resolved",
          acknowledged_by: user?.id,
        }),
      });

      if (response.ok) {
        setAlertActionsMenu(null);
        await fetchAlerts();
        await fetchStats();
      }
    } catch (error) {
      console.error("Failed to resolve alert:", error);
    }
  };

  // Delete single alert
  const deleteAlert = async (alertId: string) => {
    if (!confirm("Are you sure you want to permanently delete this alert? This action cannot be undone.")) {
      return;
    }

    try {
      const response = await fetch(`${baseUrl}/api/alerts-new/bulk-delete`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify({
          alert_ids: [alertId],
        }),
      });

      if (response.ok) {
        setAlertActionsMenu(null);
        await fetchAlerts();
        await fetchStats();
      }
    } catch (error) {
      console.error("Failed to delete alert:", error);
    }
  };

  // Mark all as read
  const markAllAsRead = async () => {
    console.log("🔔 markAllAsRead clicked!");
    console.log("👤 Current user:", { id: user?.id, email: user?.email });
    console.log("🔐 Session token available:", !!session?.access_token);

    if (!user?.id) {
      console.error("❌ No user ID found", { user });
      return;
    }

    if (!session?.access_token) {
      console.error("❌ No session token found");
      return;
    }

    console.log("📡 Making mark-all-read request with:", {
      filters:
        filters.severity.length > 0 || filters.dateFrom || filters.dateTo
          ? {
              severity: filters.severity,
              date_from: filters.dateFrom || undefined,
              date_to: filters.dateTo || undefined,
            }
          : null,
    });

    try {
      const response = await fetch(`${baseUrl}/api/alerts-new/mark-all-read`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          filters:
            filters.severity.length > 0 || filters.dateFrom || filters.dateTo
              ? {
                  severity: filters.severity,
                  date_from: filters.dateFrom || undefined,
                  date_to: filters.dateTo || undefined,
                }
              : null,
        }),
      });

      console.log("📊 Response status:", response.status);

      if (response.ok) {
        const result = await response.json();
        console.log("✅ Mark all as read successful:", result);

        // Debug: Check current alerts and stats
        console.log("📊 Current alerts count:", alerts.length);
        console.log("📊 Current unread count:", stats?.total_unread || "unknown");
        console.log(
          "🔍 Sample alerts status:",
          alerts.slice(0, 3).map((a) => ({
            id: a.id,
            status: a.status,
            user_id: a.user_id,
          }))
        );

        await fetchAlerts();
        await fetchStats();
      } else {
        const errorData = await response.text();
        console.error("❌ Mark all as read failed:", response.status, errorData);
      }
    } catch (error) {
      console.error("❌ Failed to mark all as read:", error);
    }
  };

  // Clear filters
  const clearFilters = () => {
    setFilters({
      search: "",
      severity: [],
      status: [],
      dateFrom: "",
      dateTo: "",
      sortBy: "detected_at",
      sortOrder: "desc",
    });
    setCurrentPage(1);
  };

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;

    return date.toLocaleDateString();
  };

  if (loading) {
    return (
      <AuthGuard>
        <DashboardLayout>
          <div className="flex items-center justify-center h-96">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
            <span className="ml-2 text-lg">Loading alerts...</span>
          </div>
        </DashboardLayout>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <DashboardLayout>
        <div className="p-6 space-y-6 bg-[#0a0a0a] min-h-screen">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-[#27d77a]">Security Alerts</h1>
              <p className="text-gray-400">Monitor and manage security incidents</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowFilters(!showFilters)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
                  showFilters || filters.severity.length > 0 || filters.status.length > 0 || filters.search
                    ? "bg-[#27d77a] text-black border-[#27d77a]"
                    : "bg-[#111111] text-[#27d77a] border-[#333333] hover:bg-[#1a1a1a]"
                }`}
              >
                <Filter className="w-4 h-4" />
                Filters
                {(filters.severity.length > 0 || filters.status.length > 0 || filters.search) && (
                  <span className="bg-white text-blue-500 text-xs px-2 py-1 rounded-full">
                    {filters.severity.length + filters.status.length + (filters.search ? 1 : 0)}
                  </span>
                )}
              </button>
              <button
                onClick={fetchAlerts}
                disabled={refreshing}
                className="flex items-center gap-2 px-4 py-2 bg-[#27d77a] text-black rounded-lg hover:bg-[#22c55e] disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
                Refresh
              </button>
              <button
                onClick={() => setShowKeyboardHelp(true)}
                className="flex items-center gap-2 px-4 py-2 bg-[#1a1a1a] text-[#27d77a] border border-[#333333] rounded-lg hover:bg-[#333333]"
                title="Keyboard shortcuts (Ctrl+H)"
              >
                ?
              </button>
            </div>
          </div>

          {/* New Alerts Notification */}
          {newAlertsCount > 0 && (
            <div className="bg-[#1a1a1a] border border-[#ff4444] rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <AlertTriangle className="w-5 h-5 text-[#ff4444]" />
                  <span className="text-sm font-medium text-[#ff4444]">
                    {newAlertsCount} new alert{newAlertsCount > 1 ? "s" : ""} detected
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => {
                      setNewAlertsCount(0);
                      fetchAlerts();
                    }}
                    className="flex items-center gap-1 px-3 py-1 bg-[#ff4444] text-black rounded text-sm hover:bg-[#cc3333]"
                  >
                    <RefreshCw className="w-4 h-4" />
                    View New Alerts
                  </button>
                  <button onClick={() => setNewAlertsCount(0)} className="p-1 text-[#ff4444] hover:text-[#cc3333]">
                    ✕
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div className="bg-[#111111] p-6 rounded-lg shadow-sm border border-[#333333]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-400">Unresolved</p>
                    <p className="text-2xl font-bold text-[#27d77a]">{stats.total_unresolved}</p>
                  </div>
                  <AlertTriangle className="w-8 h-8 text-[#ff4444]" />
                </div>
              </div>
              <div className="bg-[#111111] p-6 rounded-lg shadow-sm border border-[#333333]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-400">Unread</p>
                    <p className="text-2xl font-bold text-[#ff4444]">{stats.total_unread}</p>
                  </div>
                  <Bell className="w-8 h-8 text-[#ff4444]" />
                </div>
              </div>
              <div className="bg-[#111111] p-6 rounded-lg shadow-sm border border-[#333333]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-400">Last 24h</p>
                    <p className="text-2xl font-bold text-[#27d77a]">{stats.recent_24h}</p>
                  </div>
                  <Clock className="w-8 h-8 text-[#00ff00]" />
                </div>
              </div>
              <div className="bg-[#111111] p-6 rounded-lg shadow-sm border border-[#333333]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-400">Critical</p>
                    <p className="text-2xl font-bold text-[#ff4444]">{stats.severity_breakdown.critical || 0}</p>
                  </div>
                  <AlertCircle className="w-8 h-8 text-[#ff4444]" />
                </div>
              </div>
              <div className="bg-[#111111] p-6 rounded-lg shadow-sm border border-[#333333]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-gray-400">High Priority</p>
                    <p className="text-2xl font-bold text-orange-400">{stats.severity_breakdown.high || 0}</p>
                  </div>
                  <Activity className="w-8 h-8 text-orange-400" />
                </div>
              </div>
            </div>
          )}

          {/* Filters Panel */}
          {showFilters && (
            <div className="bg-[#111111] p-6 rounded-lg shadow-sm border border-[#333333] space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-[#00ff00]">Filters</h3>
                <button onClick={clearFilters} className="text-sm text-gray-400 hover:text-[#00ff00]">
                  Clear All
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Search */}
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Search</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-500 w-4 h-4" />
                    <input
                      type="text"
                      placeholder="Search alerts..."
                      value={filters.search}
                      onChange={(e) => handleSearchChange(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded-lg focus:ring-2 focus:ring-[#00ff00] focus:border-transparent placeholder-gray-500"
                    />
                  </div>
                </div>

                {/* Date From */}
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">From Date</label>
                  <input
                    type="date"
                    value={filters.dateFrom}
                    onChange={(e) => handleFilterChange("dateFrom", e.target.value)}
                    className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded-lg focus:ring-2 focus:ring-[#00ff00] focus:border-transparent"
                  />
                </div>

                {/* Date To */}
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">To Date</label>
                  <input
                    type="date"
                    value={filters.dateTo}
                    onChange={(e) => handleFilterChange("dateTo", e.target.value)}
                    className="w-full px-3 py-2 bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded-lg focus:ring-2 focus:ring-[#00ff00] focus:border-transparent"
                  />
                </div>
              </div>

              {/* Severity Filters */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Severity</label>
                <div className="flex flex-wrap gap-2">
                  {["critical", "high", "medium", "low", "info"].map((severity) => (
                    <button
                      key={severity}
                      onClick={() => toggleSeverityFilter(severity)}
                      className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                        filters.severity.includes(severity)
                          ? SEVERITY_COLORS[severity as keyof typeof SEVERITY_COLORS]
                          : "bg-[#1a1a1a] text-gray-400 border border-[#333333] hover:bg-[#333333]"
                      }`}
                    >
                      {SEVERITY_ICONS[severity as keyof typeof SEVERITY_ICONS]} {severity}
                    </button>
                  ))}
                </div>
              </div>

              {/* Status Filters */}
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-2">Status</label>
                <div className="flex flex-wrap gap-2">
                  {["new", "acknowledged", "investigating", "resolved", "false_positive"].map((status) => (
                    <button
                      key={status}
                      onClick={() => toggleStatusFilter(status)}
                      className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                        filters.status.includes(status)
                          ? STATUS_COLORS[status as keyof typeof STATUS_COLORS]
                          : "bg-[#1a1a1a] text-gray-400 border border-[#333333] hover:bg-[#333333]"
                      }`}
                    >
                      {status.replace("_", " ")}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Bulk Actions */}
          {selectedAlerts.size > 0 && (
            <div className="bg-[#1a1a1a] border border-[#00ff00] rounded-lg p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-[#00ff00]">
                    {selectedAlerts.size} alert{selectedAlerts.size > 1 ? "s" : ""} selected
                  </span>
                  <button
                    onClick={() => setSelectedAlerts(new Set())}
                    className="text-sm text-gray-400 hover:text-[#00ff00]"
                  >
                    Clear selection
                  </button>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={bulkMarkAsRead}
                    className="flex items-center gap-1 px-3 py-1 bg-[#00ff00] text-black rounded text-sm hover:bg-[#00cc00]"
                  >
                    <CheckCheck className="w-4 h-4" />
                    Mark as Read
                  </button>
                  <div className="relative">
                    <button
                      onClick={() => setBulkActionMenuOpen(!bulkActionMenuOpen)}
                      className="flex items-center gap-1 px-3 py-1 bg-[#333333] text-[#00ff00] rounded text-sm hover:bg-[#444444]"
                    >
                      <MoreHorizontal className="w-4 h-4" />
                      More
                    </button>
                    {bulkActionMenuOpen && (
                      <div className="absolute right-0 top-8 bg-[#111111] border border-[#333333] rounded-lg shadow-lg z-10 min-w-40">
                        <button
                          onClick={() => {
                            bulkResolveAlerts();
                          }}
                          className="w-full text-left px-4 py-2 text-sm text-[#00ff00] hover:bg-[#1a1a1a] flex items-center gap-2"
                        >
                          <Check className="w-4 h-4 text-[#00ff00]" />
                          Resolve
                        </button>
                        <button
                          onClick={() => {
                            bulkDeleteAlerts();
                          }}
                          className="w-full text-left px-4 py-2 text-sm text-[#ff4444] hover:bg-[#1a1a1a] flex items-center gap-2"
                        >
                          <Trash2 className="w-4 h-4" />
                          Delete
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Mark All as Read Button */}
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-4">
              <button
                onClick={markAllAsRead}
                className="flex items-center gap-2 px-4 py-2 bg-[#00ff00] text-black rounded-lg hover:bg-[#00cc00] transition-colors"
              >
                <BellOff className="w-4 h-4" />
                Mark All as Read
              </button>

              {pagination && (
                <p className="text-sm text-gray-400">
                  Showing {Math.min(pagination.current_page * pagination.page_size, pagination.total_count)} of{" "}
                  {pagination.total_count} alerts
                </p>
              )}
            </div>

            {/* Sort Controls */}
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Sort by:</span>
              <select
                value={filters.sortBy}
                onChange={(e) => handleFilterChange("sortBy", e.target.value)}
                className="text-sm bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded px-2 py-1"
              >
                <option value="detected_at">Date Detected</option>
                <option value="severity">Severity</option>
                <option value="status">Status</option>
                <option value="confidence_score">Confidence</option>
              </select>
              <button
                onClick={() => handleFilterChange("sortOrder", filters.sortOrder === "asc" ? "desc" : "asc")}
                className="text-sm px-2 py-1 bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded hover:bg-[#333333]"
              >
                {filters.sortOrder === "asc" ? "↑" : "↓"}
              </button>
            </div>
          </div>

          {/* Alerts List */}
          <div className="bg-[#111111] rounded-lg shadow-sm border border-[#333333] overflow-hidden">
            {alerts.length === 0 ? (
              <div className="p-8 text-center">
                <Shield className="w-12 h-12 text-gray-500 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-[#00ff00] mb-2">No alerts found</h3>
                <p className="text-gray-400">
                  {filters.search || filters.severity.length > 0 || filters.status.length > 0
                    ? "Try adjusting your filters to see more results."
                    : "All clear! No security alerts at this time."}
                </p>
              </div>
            ) : (
              <>
                {/* Table Header */}
                <div className="bg-[#1a1a1a] px-6 py-3 border-b border-[#333333]">
                  <div className="flex items-center">
                    <input
                      type="checkbox"
                      checked={selectedAlerts.size === alerts.length && alerts.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-[#333333] text-[#00ff00] bg-[#1a1a1a] mr-4 focus:ring-[#00ff00]"
                    />
                    <div className="grid grid-cols-12 gap-4 w-full text-xs font-medium text-gray-400 uppercase tracking-wider">
                      <div className="col-span-4">Alert</div>
                      <div className="col-span-2">Severity</div>
                      <div className="col-span-2">Status</div>
                      <div className="col-span-2">Source</div>
                      <div className="col-span-2">Date</div>
                    </div>
                  </div>
                </div>

                {/* Table Body */}
                <div className="divide-y divide-[#333333]">
                  {alerts.map((alert) => (
                    <div
                      key={alert.id}
                      className={`px-6 py-4 hover:bg-[#1a1a1a] transition-colors ${
                        selectedAlerts.has(alert.id) ? "bg-[#1a1a1a] border-l-2 border-[#00ff00]" : ""
                      }`}
                    >
                      <div className="flex items-center">
                        <input
                          type="checkbox"
                          checked={selectedAlerts.has(alert.id)}
                          onChange={() => toggleAlertSelection(alert.id)}
                          className="rounded border-[#333333] text-[#00ff00] bg-[#1a1a1a] mr-4 focus:ring-[#00ff00]"
                        />
                        <div className="grid grid-cols-12 gap-4 w-full">
                          {/* Alert Info */}
                          <div className="col-span-4">
                            <div className="flex items-start space-x-3">
                              <div className="shrink-0">
                                <div
                                  className={`w-2 h-2 rounded-full mt-2 ${
                                    alert.severity === "critical"
                                      ? "bg-[#ff4444]"
                                      : alert.severity === "high"
                                      ? "bg-orange-400"
                                      : alert.severity === "medium"
                                      ? "bg-yellow-400"
                                      : alert.severity === "low"
                                      ? "bg-blue-400"
                                      : "bg-gray-400"
                                  }`}
                                />
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="text-sm font-medium text-[#00ff00] truncate">{alert.title}</p>
                                <p className="text-sm text-gray-400 line-clamp-2">{alert.description}</p>
                                <div className="flex items-center mt-1 space-x-2 text-xs text-gray-500">
                                  <span>{alert.detection_method}</span>
                                  <span>•</span>
                                  <span>{alert.confidence_score.toFixed(1)}% confidence</span>
                                </div>
                              </div>
                            </div>
                          </div>

                          {/* Severity */}
                          <div className="col-span-2">
                            <span
                              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                SEVERITY_COLORS[alert.severity]
                              }`}
                            >
                              {SEVERITY_ICONS[alert.severity]} {alert.severity}
                            </span>
                          </div>

                          {/* Status */}
                          <div className="col-span-2">
                            <span
                              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                STATUS_COLORS[alert.status]
                              }`}
                            >
                              {alert.status.replace("_", " ")}
                            </span>
                            {alert.acknowledged_at && (
                              <p className="text-xs text-gray-500 mt-1">Read {formatDate(alert.acknowledged_at)}</p>
                            )}
                          </div>

                          {/* Source */}
                          <div className="col-span-2">
                            <div className="text-sm">
                              {alert.source_ip && (
                                <div className="flex items-center space-x-1">
                                  <MapPin className="w-3 h-3 text-gray-500" />
                                  <span className="font-mono text-xs text-gray-300">{alert.source_ip}</span>
                                </div>
                              )}
                              {alert.target_port && <p className="text-xs text-gray-500">Port {alert.target_port}</p>}
                            </div>
                          </div>

                          {/* Date & Actions */}
                          <div className="col-span-2">
                            <div className="flex items-center justify-between">
                              <div className="text-sm text-gray-400">{formatDate(alert.detected_at)}</div>
                              <div className="flex items-center space-x-1">
                                {alert.status === "new" && (
                                  <button
                                    onClick={() => markAsRead(alert.id)}
                                    className="p-1 text-gray-500 hover:text-[#00ff00] transition-colors"
                                    title="Mark as read"
                                  >
                                    <Eye className="w-4 h-4" />
                                  </button>
                                )}
                                <div className="relative">
                                  <button
                                    onClick={() => setAlertActionsMenu(alertActionsMenu === alert.id ? null : alert.id)}
                                    className="p-1 text-gray-500 hover:text-[#00ff00] transition-colors"
                                    title="More actions"
                                  >
                                    <MoreHorizontal className="w-4 h-4" />
                                  </button>
                                  {alertActionsMenu === alert.id && (
                                    <div className="absolute right-0 top-8 bg-[#111111] border border-[#333333] rounded-lg shadow-lg z-10 min-w-32">
                                      <button
                                        onClick={() => resolveAlert(alert.id)}
                                        className="w-full text-left px-3 py-2 text-sm text-[#00ff00] hover:bg-[#1a1a1a] flex items-center gap-2"
                                      >
                                        <Check className="w-4 h-4" />
                                        Resolve
                                      </button>
                                      <button
                                        onClick={() => deleteAlert(alert.id)}
                                        className="w-full text-left px-3 py-2 text-sm text-[#ff4444] hover:bg-[#1a1a1a] flex items-center gap-2"
                                      >
                                        <Trash2 className="w-4 h-4" />
                                        Delete
                                      </button>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Pagination */}
          {pagination && pagination.total_pages > 1 && (
            <div className="flex items-center justify-between bg-[#111111] px-6 py-3 border border-[#333333] rounded-lg">
              <div className="flex items-center text-sm text-[#00ff00]">
                <span>
                  Page {pagination.current_page} of {pagination.total_pages}
                </span>
                <span className="ml-2 text-gray-400">({pagination.total_count} total alerts)</span>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                  disabled={!pagination.has_prev}
                  className="flex items-center px-3 py-1 text-sm bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded-md hover:bg-[#333333] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  Previous
                </button>

                <div className="flex items-center space-x-1">
                  {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                    let pageNum;
                    if (pagination.total_pages <= 5) {
                      pageNum = i + 1;
                    } else if (pagination.current_page <= 3) {
                      pageNum = i + 1;
                    } else if (pagination.current_page >= pagination.total_pages - 2) {
                      pageNum = pagination.total_pages - 4 + i;
                    } else {
                      pageNum = pagination.current_page - 2 + i;
                    }

                    return (
                      <button
                        key={pageNum}
                        onClick={() => setCurrentPage(pageNum)}
                        className={`px-3 py-1 text-sm rounded-md ${
                          pageNum === pagination.current_page
                            ? "bg-[#00ff00] text-black"
                            : "bg-[#1a1a1a] border border-[#333333] text-[#00ff00] hover:bg-[#333333]"
                        }`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                </div>

                <button
                  onClick={() => setCurrentPage(Math.min(pagination.total_pages, currentPage + 1))}
                  disabled={!pagination.has_next}
                  className="flex items-center px-3 py-1 text-sm bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded-md hover:bg-[#333333] disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Next
                  <ChevronRight className="w-4 h-4 ml-1" />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Keyboard Shortcuts Help */}
        {showKeyboardHelp && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-medium text-[#00ff00]">Keyboard Shortcuts</h3>
                <button onClick={() => setShowKeyboardHelp(false)} className="text-gray-400 hover:text-[#00ff00]">
                  ✕
                </button>
              </div>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-300">Refresh alerts</span>
                  <kbd className="px-2 py-1 bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded text-xs">
                    Ctrl+R
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300">Select all</span>
                  <kbd className="px-2 py-1 bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded text-xs">
                    Ctrl+A
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300">Mark selected as read</span>
                  <kbd className="px-2 py-1 bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded text-xs">
                    Ctrl+M
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300">Toggle filters</span>
                  <kbd className="px-2 py-1 bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded text-xs">
                    Ctrl+/
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-300">Show this help</span>
                  <kbd className="px-2 py-1 bg-[#1a1a1a] border border-[#333333] text-[#00ff00] rounded text-xs">
                    Ctrl+H
                  </kbd>
                </div>
              </div>
              <div className="mt-6 text-center">
                <button
                  onClick={() => setShowKeyboardHelp(false)}
                  className="px-4 py-2 bg-[#00ff00] text-black rounded hover:bg-[#00cc00]"
                >
                  Got it
                </button>
              </div>
            </div>
          </div>
        )}
      </DashboardLayout>
    </AuthGuard>
  );
}
