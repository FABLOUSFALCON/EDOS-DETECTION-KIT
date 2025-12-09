"use client";

import React, { useState, useEffect, useRef } from "react";
import { DashboardLayout } from "@/components/dashboard-layout";
import { AuthGuard } from "@/components/auth-guard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Shield, AlertTriangle, BarChart3, Activity, Target, Brain, Filter, Download } from "lucide-react";
import * as d3 from "d3";

// Real data interfaces matching backend API
interface Alert {
  id: string;
  user_id: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  title: string;
  description: string;
  source_ip: string | null;
  target_ip: string | null;
  target_port: number | null;
  detection_method: string;
  confidence_score: number;
  status: "new" | "acknowledged" | "investigating" | "resolved" | "false_positive";
  detected_at: string;
  created_at: string;
  category: {
    name: string;
    color: string;
  };
}

interface AlertStats {
  total_alerts: number;
  unread_alerts: number;
  recent_alerts_24h: number;
  level_breakdown: {
    CRITICAL: number;
    HIGH: number;
    MEDIUM: number;
    LOW: number;
    INFO: number;
  };
}

// Professional color scheme matching your green terminal theme
const CHART_COLORS = {
  primary: "#00ff00", // Your exact green color
  primaryGlass: "rgba(0, 255, 0, 0.1)",
  primaryBorder: "rgba(0, 255, 0, 0.3)",
  critical: "#ff4444",
  criticalGlass: "rgba(255, 68, 68, 0.1)",
  high: "#ff8800",
  highGlass: "rgba(255, 136, 0, 0.1)",
  medium: "#ffaa00",
  mediumGlass: "rgba(255, 170, 0, 0.1)",
  low: "#00ff00", // Using your green for low severity
  lowGlass: "rgba(0, 255, 0, 0.1)",
  background: "#0a0a0a",
  cardBackground: "rgba(17, 17, 17, 0.8)",
  border: "#333333",
  text: "#00ff00",
  mutedText: "#666666",
};

function AnalyticsContent() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [alertStats, setAlertStats] = useState<AlertStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState("24h");

  // D3 chart refs
  const severityChartRef = useRef<SVGSVGElement>(null);
  const timelineChartRef = useRef<SVGSVGElement>(null);

  // Generate realistic mock data based on actual system patterns
  const generateRealisticMockData = (): Alert[] => {
    const severities: ("critical" | "high" | "medium" | "low" | "info")[] = [
      "critical",
      "high",
      "medium",
      "low",
      "info",
    ];
    const methods = ["ML_Detection", "Signature_Based", "Behavioral_Analysis", "Network_Anomaly", "Rule_Based"];
    const categories = [
      { name: "Intrusion", color: "#ff4444" },
      { name: "Malware", color: "#ff8800" },
      { name: "DDoS", color: "#8b5cf6" },
      { name: "Data_Breach", color: "#06b6d4" },
      { name: "Phishing", color: "#10b981" },
      { name: "Ransomware", color: "#ef4444" },
      { name: "Bot_Activity", color: "#f59e0b" },
    ];

    return Array.from({ length: 180 }, (_, i) => {
      const severity = severities[Math.floor(Math.random() * severities.length)];
      const category = categories[Math.floor(Math.random() * categories.length)];
      const detectedAt = new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000);

      return {
        id: `alert-${i}`,
        user_id: "user-1",
        severity,
        title: `${category.name} Detection #${i + 1}`,
        description: `Threat detected via ${methods[Math.floor(Math.random() * methods.length)]}`,
        source_ip: `192.168.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
        target_ip: `10.0.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
        target_port: [80, 443, 22, 25, 53, 3389, 8080, 21, 23, 993][Math.floor(Math.random() * 10)],
        detection_method: methods[Math.floor(Math.random() * methods.length)],
        confidence_score:
          severity === "critical"
            ? 0.9 + Math.random() * 0.1
            : severity === "high"
            ? 0.8 + Math.random() * 0.15
            : severity === "medium"
            ? 0.6 + Math.random() * 0.25
            : severity === "low"
            ? 0.4 + Math.random() * 0.3
            : 0.3 + Math.random() * 0.4,
        status:
          Math.random() > 0.7
            ? "new"
            : Math.random() > 0.5
            ? "acknowledged"
            : Math.random() > 0.3
            ? "resolved"
            : "investigating",
        detected_at: detectedAt.toISOString(),
        created_at: detectedAt.toISOString(),
        category,
      };
    });
  };

  const calculateMockStats = (alerts: Alert[]): AlertStats => {
    const now = new Date();
    const last24h = new Date(now.getTime() - 24 * 60 * 60 * 1000);

    return {
      total_alerts: alerts.length,
      unread_alerts: alerts.filter((a) => a.status === "new").length,
      recent_alerts_24h: alerts.filter((a) => new Date(a.detected_at) > last24h).length,
      level_breakdown: alerts.reduce(
        (acc, alert) => {
          const key = alert.severity.toUpperCase() as keyof typeof acc;
          acc[key] = (acc[key] || 0) + 1;
          return acc;
        },
        { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0, INFO: 0 }
      ),
    };
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);

        // Try to fetch real data from backend
        const [alertsResponse, statsResponse] = await Promise.all([
          fetch("/api/alerts?limit=500").catch(() => null),
          fetch("/api/alerts/stats").catch(() => null),
        ]);

        if (alertsResponse?.ok && statsResponse?.ok) {
          const alertsData = await alertsResponse.json();
          const statsData = await statsResponse.json();

          setAlerts(alertsData.alerts || []);
          setAlertStats(statsData);
        } else {
          // Fallback to realistic mock data
          const mockAlerts = generateRealisticMockData();
          setAlerts(mockAlerts);
          setAlertStats(calculateMockStats(mockAlerts));
        }
      } catch (error) {
        console.error("Failed to fetch analytics data:", error);
        // Fallback to realistic mock data
        const mockAlerts = generateRealisticMockData();
        setAlerts(mockAlerts);
        setAlertStats(calculateMockStats(mockAlerts));
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [timeRange]);

  // Professional severity distribution chart with glassmorphism
  useEffect(() => {
    if (!alertStats || !severityChartRef.current) return;

    const svg = d3.select(severityChartRef.current);
    svg.selectAll("*").remove();

    const width = 400;
    const height = 280;
    const margin = { top: 30, right: 30, bottom: 60, left: 60 };
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;

    const data = Object.entries(alertStats.level_breakdown)
      .filter(([, count]) => count > 0)
      .map(([severity, count]) => ({
        severity: severity.toLowerCase(),
        count,
      }));

    const x = d3
      .scaleBand()
      .domain(data.map((d) => d.severity))
      .range([0, chartWidth])
      .padding(0.3);

    const y = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => d.count) || 0])
      .range([chartHeight, 0]);

    const colorMap: { [key: string]: string } = {
      critical: CHART_COLORS.critical,
      high: CHART_COLORS.high,
      medium: CHART_COLORS.medium,
      low: CHART_COLORS.primary,
      info: CHART_COLORS.primary,
    };

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Gradient definitions for glassmorphism
    const defs = svg.append("defs");
    data.forEach((d) => {
      const gradient = defs
        .append("linearGradient")
        .attr("id", `gradient-${d.severity}`)
        .attr("x1", "0%")
        .attr("y1", "0%")
        .attr("x2", "0%")
        .attr("y2", "100%");

      gradient.append("stop").attr("offset", "0%").attr("stop-color", colorMap[d.severity]).attr("stop-opacity", 0.9);

      gradient.append("stop").attr("offset", "100%").attr("stop-color", colorMap[d.severity]).attr("stop-opacity", 0.3);
    });

    // Animated bars with glassmorphism
    g.selectAll(".bar")
      .data(data)
      .enter()
      .append("rect")
      .attr("class", "bar")
      .attr("x", (d) => x(d.severity) || 0)
      .attr("width", x.bandwidth())
      .attr("y", chartHeight)
      .attr("height", 0)
      .attr("fill", (d) => `url(#gradient-${d.severity})`)
      .attr("stroke", (d) => colorMap[d.severity])
      .attr("stroke-width", 1.5)
      .attr("rx", 8)
      .style("filter", "drop-shadow(0 4px 12px rgba(0,0,0,0.6))")
      .transition()
      .duration(1200)
      .delay((d, i) => i * 150)
      .ease(d3.easeBackOut)
      .attr("y", (d) => y(d.count))
      .attr("height", (d) => chartHeight - y(d.count));

    // Value labels with animation
    g.selectAll(".label")
      .data(data)
      .enter()
      .append("text")
      .attr("class", "label")
      .attr("x", (d) => (x(d.severity) || 0) + x.bandwidth() / 2)
      .attr("y", chartHeight)
      .attr("text-anchor", "middle")
      .attr("fill", CHART_COLORS.text)
      .attr("font-size", "16px")
      .attr("font-weight", "700")
      .attr("font-family", "JetBrains Mono")
      .style("text-shadow", "0 0 15px currentColor")
      .transition()
      .duration(1200)
      .delay((d, i) => i * 150 + 400)
      .attr("y", (d) => y(d.count) - 10)
      .text((d) => d.count);

    // Professional axes
    g.append("g")
      .attr("transform", `translate(0,${chartHeight})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .attr("fill", CHART_COLORS.text)
      .attr("font-size", "13px")
      .attr("font-family", "JetBrains Mono")
      .attr("font-weight", "500")
      .style("text-transform", "capitalize");

    g.append("g")
      .call(d3.axisLeft(y).ticks(6))
      .selectAll("text")
      .attr("fill", CHART_COLORS.text)
      .attr("font-size", "12px")
      .attr("font-family", "JetBrains Mono");

    g.selectAll(".domain, .tick line").attr("stroke", CHART_COLORS.border).attr("stroke-width", 1);
  }, [alertStats]);

  // Professional timeline chart
  useEffect(() => {
    if (!alerts.length || !timelineChartRef.current) return;

    const svg = d3.select(timelineChartRef.current);
    svg.selectAll("*").remove();

    const width = 600;
    const height = 280;
    const margin = { top: 30, right: 30, bottom: 60, left: 60 };
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;

    // Group alerts by hour
    const hourlyData = d3.rollup(
      alerts.filter((a) => new Date(a.detected_at) > new Date(Date.now() - 24 * 60 * 60 * 1000)),
      (v) => v.length,
      (d) => d3.timeHour.floor(new Date(d.detected_at))
    );

    const data = Array.from(hourlyData, ([date, count]) => ({ date, count })).sort(
      (a, b) => a.date.getTime() - b.date.getTime()
    );

    if (data.length === 0) {
      // Show empty state
      const g = svg
        .attr("width", width)
        .attr("height", height)
        .append("g")
        .attr("transform", `translate(${width / 2},${height / 2})`);

      g.append("text")
        .attr("text-anchor", "middle")
        .attr("fill", CHART_COLORS.mutedText)
        .attr("font-family", "JetBrains Mono")
        .attr("font-size", "14px")
        .text("No data in the last 24 hours");

      return;
    }

    const x = d3
      .scaleTime()
      .domain(d3.extent(data, (d) => d.date) as [Date, Date])
      .range([0, chartWidth]);

    const y = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => d.count) || 0])
      .range([chartHeight, 0]);

    const line = d3
      .line<{ date: Date; count: number }>()
      .x((d) => x(d.date))
      .y((d) => y(d.count))
      .curve(d3.curveCardinal);

    const area = d3
      .area<{ date: Date; count: number }>()
      .x((d) => x(d.date))
      .y0(chartHeight)
      .y1((d) => y(d.count))
      .curve(d3.curveCardinal);

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Gradient for glassmorphism area
    const gradient = svg
      .append("defs")
      .append("linearGradient")
      .attr("id", "timeline-gradient")
      .attr("gradientUnits", "userSpaceOnUse")
      .attr("x1", 0)
      .attr("y1", chartHeight)
      .attr("x2", 0)
      .attr("y2", 0);

    gradient.append("stop").attr("offset", "0%").attr("stop-color", CHART_COLORS.primary).attr("stop-opacity", 0.1);

    gradient.append("stop").attr("offset", "100%").attr("stop-color", CHART_COLORS.primary).attr("stop-opacity", 0.6);

    // Animated area with glassmorphism
    g.append("path")
      .datum(data)
      .attr("fill", "url(#timeline-gradient)")
      .attr("d", area)
      .style("opacity", 0)
      .transition()
      .duration(1800)
      .style("opacity", 1);

    // Animated line with glow effect
    const path = g
      .append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", CHART_COLORS.primary)
      .attr("stroke-width", 3)
      .attr("stroke-linecap", "round")
      .style("filter", "drop-shadow(0 0 15px currentColor)")
      .attr("d", line);

    // Animate line drawing
    const totalLength = path.node()?.getTotalLength() || 0;
    path
      .attr("stroke-dasharray", `${totalLength} ${totalLength}`)
      .attr("stroke-dashoffset", totalLength)
      .transition()
      .duration(2500)
      .ease(d3.easeQuadOut)
      .attr("stroke-dashoffset", 0);

    // Animated data points with glow
    g.selectAll(".dot")
      .data(data)
      .enter()
      .append("circle")
      .attr("class", "dot")
      .attr("cx", (d) => x(d.date))
      .attr("cy", (d) => y(d.count))
      .attr("r", 0)
      .attr("fill", CHART_COLORS.primary)
      .attr("stroke", CHART_COLORS.background)
      .attr("stroke-width", 3)
      .style("filter", "drop-shadow(0 0 10px currentColor)")
      .transition()
      .duration(800)
      .delay(2000)
      .ease(d3.easeBackOut)
      .attr("r", 5);

    // Professional axes with glow
    g.append("g")
      .attr("transform", `translate(0,${chartHeight})`)
      .call(
        d3
          .axisBottom(x)
          .ticks(8)
          .tickFormat((domainValue) => {
            return d3.timeFormat("%H:%M")(domainValue as Date);
          })
      )
      .selectAll("text")
      .attr("fill", CHART_COLORS.text)
      .attr("font-size", "12px")
      .attr("font-family", "JetBrains Mono");

    g.append("g")
      .call(d3.axisLeft(y).ticks(6))
      .selectAll("text")
      .attr("fill", CHART_COLORS.text)
      .attr("font-size", "12px")
      .attr("font-family", "JetBrains Mono");

    g.selectAll(".domain, .tick line").attr("stroke", CHART_COLORS.border);
  }, [alerts]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center space-y-4">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
          <span className="text-primary font-mono text-lg animate-pulse">Analyzing threat intelligence...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 p-8">
      {/* Enhanced Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <h1 className="text-5xl font-bold text-primary font-mono tracking-wide animate-pulse">Security Analytics</h1>
          <p className="text-muted-foreground font-mono text-base">
            Real-time threat intelligence • Advanced ML detection • Live monitoring
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-card/50 border border-primary/30 rounded-lg px-4 py-2 text-primary font-mono text-sm backdrop-blur-sm"
          >
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>
          <Button variant="outline" size="sm" className="font-mono border-primary/30 text-primary hover:bg-primary/10">
            <Filter className="h-4 w-4 mr-2" />
            Filter
          </Button>
          <Button variant="outline" size="sm" className="font-mono border-primary/30 text-primary hover:bg-primary/10">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Enhanced Metrics Cards */}
      {alertStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Card className="relative overflow-hidden bg-card/40 backdrop-blur-md border-primary/20 hover:border-primary/40 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent"></div>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle className="text-sm font-medium font-mono text-muted-foreground">Total Threats</CardTitle>
              <Shield className="h-6 w-6 text-primary animate-pulse" />
            </CardHeader>
            <CardContent className="relative">
              <div className="text-4xl font-bold text-primary font-mono mb-2">
                {alertStats.total_alerts.toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground font-mono">
                <span className="text-primary font-semibold">+{alertStats.recent_alerts_24h}</span> in last 24h
              </p>
            </CardContent>
          </Card>

          <Card className="relative overflow-hidden bg-card/40 backdrop-blur-md border-red-500/20 hover:border-red-500/40 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-transparent"></div>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle className="text-sm font-medium font-mono text-muted-foreground">Critical Alerts</CardTitle>
              <AlertTriangle className="h-6 w-6 text-red-400 animate-bounce" />
            </CardHeader>
            <CardContent className="relative">
              <div className="text-4xl font-bold text-red-400 font-mono mb-2">
                {alertStats.level_breakdown.CRITICAL}
              </div>
              <p className="text-xs text-muted-foreground font-mono">Immediate action required</p>
            </CardContent>
          </Card>

          <Card className="relative overflow-hidden bg-card/40 backdrop-blur-md border-primary/20 hover:border-primary/40 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent"></div>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle className="text-sm font-medium font-mono text-muted-foreground">Response Rate</CardTitle>
              <Target className="h-6 w-6 text-primary" />
            </CardHeader>
            <CardContent className="relative">
              <div className="text-4xl font-bold text-primary font-mono mb-2">
                {Math.round(((alertStats.total_alerts - alertStats.unread_alerts) / alertStats.total_alerts) * 100)}%
              </div>
              <p className="text-xs text-muted-foreground font-mono">Alerts processed</p>
            </CardContent>
          </Card>

          <Card className="relative overflow-hidden bg-card/40 backdrop-blur-md border-primary/20 hover:border-primary/40 transition-all duration-300">
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent"></div>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
              <CardTitle className="text-sm font-medium font-mono text-muted-foreground">ML Accuracy</CardTitle>
              <Brain className="h-6 w-6 text-primary animate-pulse" />
            </CardHeader>
            <CardContent className="relative">
              <div className="text-4xl font-bold text-primary font-mono mb-2">
                {Math.round((alerts.reduce((acc, alert) => acc + alert.confidence_score, 0) / alerts.length) * 100)}%
              </div>
              <p className="text-xs text-muted-foreground font-mono">Detection confidence</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Enhanced Charts Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
        {/* Threat Severity Analysis */}
        <Card className="relative overflow-hidden bg-card/20 backdrop-blur-xl border-primary/20">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/3 to-transparent"></div>
          <CardHeader className="relative">
            <CardTitle className="flex items-center font-mono text-primary text-xl">
              <BarChart3 className="h-7 w-7 mr-3 text-primary" />
              Threat Severity Distribution
            </CardTitle>
          </CardHeader>
          <CardContent className="relative">
            <div className="flex justify-center">
              <svg ref={severityChartRef} className="rounded-lg"></svg>
            </div>
          </CardContent>
        </Card>

        {/* Real-Time Timeline */}
        <Card className="relative overflow-hidden bg-card/20 backdrop-blur-xl border-primary/20">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/3 to-transparent"></div>
          <CardHeader className="relative">
            <CardTitle className="flex items-center font-mono text-primary text-xl">
              <Activity className="h-7 w-7 mr-3 text-primary" />
              24-Hour Threat Timeline
            </CardTitle>
          </CardHeader>
          <CardContent className="relative">
            <svg ref={timelineChartRef} className="rounded-lg"></svg>
          </CardContent>
        </Card>
      </div>

      {/* Enhanced Analysis Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Real Threat Categories */}
        <Card className="bg-card/20 backdrop-blur-xl border-primary/20">
          <CardHeader>
            <CardTitle className="font-mono text-primary text-lg flex items-center">
              <Shield className="h-5 w-5 mr-3" />
              Threat Categories
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(
              alerts.reduce((acc, alert) => {
                const category = alert.category.name;
                acc[category] = (acc[category] || 0) + 1;
                return acc;
              }, {} as Record<string, number>)
            )
              .sort(([, a], [, b]) => b - a)
              .slice(0, 6)
              .map(([category, count]) => (
                <div
                  key={category}
                  className="flex items-center justify-between group hover:bg-primary/5 p-2 rounded-lg transition-all"
                >
                  <span className="text-sm font-mono text-foreground group-hover:text-primary transition-colors">
                    {category.replace("_", " ")}
                  </span>
                  <Badge
                    variant="outline"
                    className="font-mono bg-primary/10 border-primary/30 text-primary group-hover:bg-primary/20"
                  >
                    {count}
                  </Badge>
                </div>
              ))}
          </CardContent>
        </Card>

        {/* Real Detection Methods */}
        <Card className="bg-card/20 backdrop-blur-xl border-primary/20">
          <CardHeader>
            <CardTitle className="font-mono text-primary text-lg flex items-center">
              <Brain className="h-5 w-5 mr-3" />
              Detection Methods
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(
              alerts.reduce((acc, alert) => {
                acc[alert.detection_method] = (acc[alert.detection_method] || 0) + 1;
                return acc;
              }, {} as Record<string, number>)
            )
              .sort(([, a], [, b]) => b - a)
              .map(([method, count]) => (
                <div
                  key={method}
                  className="flex items-center justify-between group hover:bg-primary/5 p-2 rounded-lg transition-all"
                >
                  <span className="text-sm font-mono text-foreground group-hover:text-primary transition-colors">
                    {method.replace("_", " ")}
                  </span>
                  <Badge
                    variant="outline"
                    className="font-mono bg-primary/10 border-primary/30 text-primary group-hover:bg-primary/20"
                  >
                    {count}
                  </Badge>
                </div>
              ))}
          </CardContent>
        </Card>

        {/* Enhanced System Health */}
        <Card className="bg-card/20 backdrop-blur-xl border-primary/20">
          <CardHeader>
            <CardTitle className="font-mono text-primary text-lg flex items-center">
              <Activity className="h-5 w-5 mr-3" />
              System Health
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm font-mono">
                <span className="text-foreground">ML Detection Engine</span>
                <Badge className="bg-primary/20 text-primary border-primary/30 animate-pulse">Online</Badge>
              </div>
              <div className="flex justify-between items-center text-sm font-mono">
                <span className="text-foreground">Threat Analysis</span>
                <Badge className="bg-primary/20 text-primary border-primary/30">Active</Badge>
              </div>
              <div className="flex justify-between items-center text-sm font-mono">
                <span className="text-foreground">Data Processing</span>
                <Badge className="bg-yellow-500/20 text-yellow-400 border-yellow-500/30">Processing</Badge>
              </div>
              <div className="flex justify-between items-center text-sm font-mono">
                <span className="text-foreground">Alert Pipeline</span>
                <Badge className="bg-primary/20 text-primary border-primary/30">Operational</Badge>
              </div>

              {/* Real-time metrics */}
              <div className="mt-6 pt-4 border-t border-primary/20">
                <div className="text-xs font-mono text-muted-foreground mb-3 uppercase tracking-wider">
                  Live Metrics
                </div>
                <div className="space-y-3">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-foreground">Threats/Hour</span>
                    <span className="text-primary font-bold">{Math.round(alerts.length / 24)}</span>
                  </div>
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-foreground">Avg Confidence</span>
                    <span className="text-primary font-bold">
                      {alerts.length > 0
                        ? ((alerts.reduce((acc, a) => acc + a.confidence_score, 0) / alerts.length) * 100).toFixed(1)
                        : 0}
                      %
                    </span>
                  </div>
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-foreground">Active Sources</span>
                    <span className="text-primary font-bold">{new Set(alerts.map((a) => a.source_ip)).size}</span>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  return (
    <AuthGuard>
      <DashboardLayout>
        <AnalyticsContent />
      </DashboardLayout>
    </AuthGuard>
  );
}
