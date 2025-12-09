"use client";

import React, { useState, useEffect, useRef } from "react";
import { DashboardLayout } from "@/components/dashboard-layout";
import { AuthGuard } from "@/components/auth-guard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  TrendingUp,
  Shield,
  AlertTriangle,
  BarChart3,
  Activity,
  Target,
  Zap,
  Brain,
  Clock,
  Filter,
  Download,
} from "lucide-react";
import * as d3 from "d3";

// Data interfaces matching our project theme
interface AlertData {
  id: string;
  severity: "critical" | "high" | "medium" | "low";
  category: string;
  created_at: string;
  status: "new" | "acknowledged" | "resolved";
  detection_method: string;
  confidence_score: number;
  source_ip: string;
  target_port: number;
}

interface AlertStats {
  total_alerts: number;
  unread_alerts: number;
  recent_alerts_24h: number;
  level_breakdown: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
}

function AnalyticsContent() {
  const [alerts, setAlerts] = useState<AlertData[]>([]);
  const [alertStats, setAlertStats] = useState<AlertStats | null>(null);
  const [timeRange, setTimeRange] = useState("24h");
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // D3 chart refs - professional and minimal
  const severityChartRef = useRef<SVGSVGElement>(null);
  const timelineChartRef = useRef<SVGSVGElement>(null);
  const categoryChartRef = useRef<SVGSVGElement>(null);
  const confidenceChartRef = useRef<SVGSVGElement>(null);

  // Generate realistic mock data for development
  const generateMockData = () => {
    const severities: ("critical" | "high" | "medium" | "low")[] = ["critical", "high", "medium", "low"];
    const methods = ["ML_Detection", "Signature_Based", "Behavioral_Analysis", "Network_Anomaly"];
    const categories = ["Intrusion", "Malware", "DDoS", "Data_Breach", "Phishing"];

    const mockAlerts: AlertData[] = Array.from({ length: 250 }, (_, i) => {
      const severity = severities[Math.floor(Math.random() * severities.length)];
      const category = categories[Math.floor(Math.random() * categories.length)];

      return {
        id: `alert-${i}`,
        severity,
        category,
        created_at: new Date(Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000).toISOString(),
        status: Math.random() > 0.7 ? "new" : Math.random() > 0.5 ? "acknowledged" : "resolved",
        detection_method: methods[Math.floor(Math.random() * methods.length)],
        confidence_score:
          severity === "critical"
            ? 0.9 + Math.random() * 0.1
            : severity === "high"
            ? 0.8 + Math.random() * 0.15
            : severity === "medium"
            ? 0.6 + Math.random() * 0.25
            : 0.4 + Math.random() * 0.3,
        source_ip: `192.168.1.${Math.floor(Math.random() * 255)}`,
        target_port: [80, 443, 22, 25, 53, 3389, 8080][Math.floor(Math.random() * 7)],
      };
    });

    return mockAlerts;
  };

  useEffect(() => {
    const loadAnalyticsData = async () => {
      try {
        // For now, use mock data - replace with real API call later
        const mockData = generateMockData();
        setAlerts(mockData);

        // Calculate statistics
        const stats: AlertStats = {
          total_alerts: mockData.length,
          unread_alerts: mockData.filter((a) => a.status === "new").length,
          recent_alerts_24h: mockData.filter((a) => new Date(a.created_at) > new Date(Date.now() - 24 * 60 * 60 * 1000))
            .length,
          level_breakdown: mockData.reduce(
            (acc, alert) => {
              acc[alert.severity] = (acc[alert.severity] || 0) + 1;
              return acc;
            },
            { critical: 0, high: 0, medium: 0, low: 0 }
          ),
        };

        setAlertStats(stats);
        setLoading(false);
      } catch (error) {
        console.error("Failed to load analytics data:", error);
        setLoading(false);
      }
    };

    loadAnalyticsData();
  }, [timeRange]);

  // Professional severity distribution chart
  useEffect(() => {
    if (!alertStats || !severityChartRef.current) return;

    const svg = d3.select(severityChartRef.current);
    svg.selectAll("*").remove();

    const width = 300;
    const height = 200;
    const margin = { top: 20, right: 20, bottom: 40, left: 40 };
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;

    const data = Object.entries(alertStats.level_breakdown).map(([severity, count]) => ({
      severity,
      count,
    }));

    const x = d3
      .scaleBand()
      .domain(data.map((d) => d.severity))
      .range([0, chartWidth])
      .padding(0.2);

    const y = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => d.count) || 0])
      .range([chartHeight, 0]);

    const colorMap: { [key: string]: string } = {
      critical: "#ff4444",
      high: "#ff8800",
      medium: "#ffaa00",
      low: "#00ff00",
    };

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Bars with professional styling
    g.selectAll(".bar")
      .data(data)
      .enter()
      .append("rect")
      .attr("class", "bar")
      .attr("x", (d) => x(d.severity) || 0)
      .attr("width", x.bandwidth())
      .attr("y", (d) => y(d.count))
      .attr("height", (d) => chartHeight - y(d.count))
      .attr("fill", (d) => colorMap[d.severity])
      .attr("opacity", 0.8)
      .style("filter", "drop-shadow(0 2px 4px rgba(0,255,0,0.2))")
      .on("mouseover", function (event, d) {
        d3.select(this).attr("opacity", 1);
      })
      .on("mouseout", function (event, d) {
        d3.select(this).attr("opacity", 0.8);
      });

    // Value labels on bars
    g.selectAll(".label")
      .data(data)
      .enter()
      .append("text")
      .attr("class", "label")
      .attr("x", (d) => (x(d.severity) || 0) + x.bandwidth() / 2)
      .attr("y", (d) => y(d.count) - 5)
      .attr("text-anchor", "middle")
      .attr("fill", "#00ff00")
      .attr("font-size", "12px")
      .attr("font-weight", "600")
      .text((d) => d.count);

    // X-axis
    g.append("g")
      .attr("transform", `translate(0,${chartHeight})`)
      .call(d3.axisBottom(x))
      .selectAll("text")
      .attr("fill", "#00ff00")
      .attr("font-size", "11px")
      .style("text-transform", "capitalize");

    // Y-axis
    g.append("g").call(d3.axisLeft(y).ticks(5)).selectAll("text").attr("fill", "#00ff00").attr("font-size", "11px");

    // Style axis lines
    g.selectAll(".domain, .tick line").attr("stroke", "#333333");
  }, [alertStats]);

  // Professional timeline chart
  useEffect(() => {
    if (!alerts.length || !timelineChartRef.current) return;

    const svg = d3.select(timelineChartRef.current);
    svg.selectAll("*").remove();

    const width = 500;
    const height = 200;
    const margin = { top: 20, right: 30, bottom: 40, left: 50 };
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;

    // Group alerts by hour over the last 24 hours
    const hourlyData = d3.rollup(
      alerts.filter((a) => new Date(a.created_at) > new Date(Date.now() - 24 * 60 * 60 * 1000)),
      (v) => v.length,
      (d) => d3.timeHour.floor(new Date(d.created_at))
    );

    const data = Array.from(hourlyData, ([date, count]) => ({ date, count })).sort(
      (a, b) => a.date.getTime() - b.date.getTime()
    );

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
      .curve(d3.curveMonotoneX);

    const area = d3
      .area<{ date: Date; count: number }>()
      .x((d) => x(d.date))
      .y0(chartHeight)
      .y1((d) => y(d.count))
      .curve(d3.curveMonotoneX);

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Gradient definition
    const gradient = svg
      .append("defs")
      .append("linearGradient")
      .attr("id", "area-gradient")
      .attr("gradientUnits", "userSpaceOnUse")
      .attr("x1", 0)
      .attr("y1", chartHeight)
      .attr("x2", 0)
      .attr("y2", 0);

    gradient.append("stop").attr("offset", "0%").attr("stop-color", "#00ff00").attr("stop-opacity", 0.1);

    gradient.append("stop").attr("offset", "100%").attr("stop-color", "#00ff00").attr("stop-opacity", 0.4);

    // Area fill
    g.append("path").datum(data).attr("fill", "url(#area-gradient)").attr("d", area);

    // Line
    g.append("path").datum(data).attr("fill", "none").attr("stroke", "#00ff00").attr("stroke-width", 2).attr("d", line);

    // Data points
    g.selectAll(".dot")
      .data(data)
      .enter()
      .append("circle")
      .attr("class", "dot")
      .attr("cx", (d) => x(d.date))
      .attr("cy", (d) => y(d.count))
      .attr("r", 3)
      .attr("fill", "#00ff00")
      .style("filter", "drop-shadow(0 2px 4px rgba(0,255,0,0.5))");

    // Axes
    g.append("g")
      .attr("transform", `translate(0,${chartHeight})`)
      .call(d3.axisBottom(x).ticks(6))
      .selectAll("text")
      .attr("fill", "#00ff00")
      .attr("font-size", "10px");

    g.append("g").call(d3.axisLeft(y).ticks(5)).selectAll("text").attr("fill", "#00ff00").attr("font-size", "10px");

    g.selectAll(".domain, .tick line").attr("stroke", "#333333");
  }, [alerts, timeRange]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex items-center space-x-2">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <span className="text-primary font-mono">Loading analytics...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-primary font-mono">Security Analytics</h1>
          <p className="text-muted-foreground font-mono text-sm mt-1">
            Advanced threat intelligence and security metrics analysis
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button variant="outline" size="sm">
            <Filter className="h-4 w-4 mr-2" />
            Filter
          </Button>
          <Button variant="outline" size="sm">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Key Metrics Cards */}
      {alertStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium font-mono">Total Alerts</CardTitle>
              <Shield className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-primary font-mono">
                {alertStats.total_alerts.toLocaleString()}
              </div>
              <p className="text-xs text-muted-foreground font-mono">+12% from last week</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium font-mono">Critical Threats</CardTitle>
              <AlertTriangle className="h-4 w-4 text-destructive" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-destructive font-mono">{alertStats.level_breakdown.critical}</div>
              <p className="text-xs text-muted-foreground font-mono">Requires immediate attention</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium font-mono">Response Rate</CardTitle>
              <Target className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-primary font-mono">
                {Math.round(((alertStats.total_alerts - alertStats.unread_alerts) / alertStats.total_alerts) * 100)}%
              </div>
              <p className="text-xs text-muted-foreground font-mono">Alerts acknowledged</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium font-mono">Detection Accuracy</CardTitle>
              <Brain className="h-4 w-4 text-primary" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-primary font-mono">
                {Math.round((alerts.reduce((acc, alert) => acc + alert.confidence_score, 0) / alerts.length) * 100)}%
              </div>
              <p className="text-xs text-muted-foreground font-mono">ML confidence average</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Threat Severity Distribution */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center font-mono">
              <BarChart3 className="h-5 w-5 mr-2 text-primary" />
              Threat Severity Distribution
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex justify-center">
              <svg ref={severityChartRef} className="border border-muted rounded"></svg>
            </div>
          </CardContent>
        </Card>

        {/* 24-Hour Alert Timeline */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center font-mono">
              <Activity className="h-5 w-5 mr-2 text-primary" />
              24-Hour Alert Timeline
            </CardTitle>
          </CardHeader>
          <CardContent>
            <svg ref={timelineChartRef} className="border border-muted rounded"></svg>
          </CardContent>
        </Card>
      </div>

      {/* Detailed Analysis */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Threat Categories */}
        <Card>
          <CardHeader>
            <CardTitle className="font-mono">Threat Categories</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(
              alerts.reduce((acc, alert) => {
                acc[alert.category] = (acc[alert.category] || 0) + 1;
                return acc;
              }, {} as Record<string, number>)
            ).map(([category, count]) => (
              <div key={category} className="flex items-center justify-between">
                <span className="text-sm font-mono">{category}</span>
                <Badge variant="outline" className="font-mono">
                  {count}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Detection Methods */}
        <Card>
          <CardHeader>
            <CardTitle className="font-mono">Detection Methods</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(
              alerts.reduce((acc, alert) => {
                acc[alert.detection_method] = (acc[alert.detection_method] || 0) + 1;
                return acc;
              }, {} as Record<string, number>)
            ).map(([method, count]) => (
              <div key={method} className="flex items-center justify-between">
                <span className="text-sm font-mono">{method.replace("_", " ")}</span>
                <Badge variant="outline" className="font-mono">
                  {count}
                </Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* System Health */}
        <Card>
          <CardHeader>
            <CardTitle className="font-mono">System Health</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between text-sm font-mono">
                <span>Detection System</span>
                <Badge className="bg-green-500/20 text-green-400">Online</Badge>
              </div>
              <div className="flex justify-between text-sm font-mono">
                <span>ML Pipeline</span>
                <Badge className="bg-green-500/20 text-green-400">Active</Badge>
              </div>
              <div className="flex justify-between text-sm font-mono">
                <span>Data Processing</span>
                <Badge className="bg-yellow-500/20 text-yellow-400">Degraded</Badge>
              </div>
              <div className="flex justify-between text-sm font-mono">
                <span>Alert Processing</span>
                <Badge className="bg-green-500/20 text-green-400">Normal</Badge>
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
