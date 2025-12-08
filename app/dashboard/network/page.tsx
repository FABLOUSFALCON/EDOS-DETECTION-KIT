"use client";

import React, { useState, useEffect, useRef } from "react";
import { DashboardLayout } from "@/components/dashboard-layout";
import { AuthGuard } from "@/components/auth-guard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Activity,
  Wifi,
  Server,
  Shield,
  AlertTriangle,
  RefreshCw,
  Monitor,
  Network,
  Cpu,
  HardDrive,
  Eye,
  EyeOff,
} from "lucide-react";
import * as d3 from "d3";

// Data interfaces
interface NetworkSpeed {
  timestamp: string;
  download: number; // Mbps
  upload: number; // Mbps
}

interface OpenPort {
  port: number;
  protocol: string;
  service: string;
  program: string;
  status: "open" | "filtered" | "closed";
  risk: "low" | "medium" | "high";
}

interface SystemMetrics {
  cpu: {
    usage: number;
    cores: number;
    processes: number;
  };
  memory: {
    used: number;
    total: number;
    available: number;
  };
  disk: {
    used: number;
    total: number;
    readSpeed: number;
    writeSpeed: number;
  };
}

interface NetworkAnalysisData {
  networkSpeeds: NetworkSpeed[];
  systemMetrics: SystemMetrics;
  openPorts: OpenPort[];
  isConnected: boolean;
  lastUpdate: string;
}

export default function NetworkPage() {
  const [data, setData] = useState<NetworkAnalysisData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [showClosedPorts, setShowClosedPorts] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const [error, setError] = useState<string | null>(null);

  // D3 chart refs
  const networkChartRef = useRef<SVGSVGElement>(null);
  const cpuChartRef = useRef<SVGSVGElement>(null);
  const memoryChartRef = useRef<SVGSVGElement>(null);

  // WebSocket ref
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // WebSocket connection
  const connectWebSocket = () => {
    try {
      const wsUrl =
        process.env.NODE_ENV === "production"
          ? "wss://your-domain.com/ws/network-analysis"
          : "ws://localhost:23335/ws/network-analysis";

      console.log("🔄 Attempting to connect to WebSocket:", wsUrl);
      setConnectionStatus("connecting");

      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log("🌐 Network analysis WebSocket connected");
        setConnectionStatus("connected");
        setError(null);
        setIsLoading(false);
      };

      wsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);

          if (message.type === "network_analysis" && message.data) {
            // Convert timestamp strings to Date objects for D3
            const networkData = {
              ...message.data,
              networkSpeeds: message.data.networkSpeeds.map((speed: NetworkSpeed) => ({
                ...speed,
                timestamp: new Date(speed.timestamp),
              })),
            };

            setData(networkData);
            setError(null);
            console.log("📊 Received network analysis data:", networkData);
          } else if (message.type === "error") {
            setError(message.message || "Unknown error");
            console.error("❌ WebSocket error:", message.message);
          }
        } catch (err) {
          console.error("❌ Failed to parse WebSocket message:", err);
          setError("Failed to parse data");
        }
      };

      wsRef.current.onclose = (event) => {
        console.log("🔌 Network analysis WebSocket disconnected:", event.code, event.reason);
        setConnectionStatus("disconnected");

        // Try REST API fallback immediately on disconnect
        if (!isPaused) {
          console.log("📡 Falling back to REST API...");
          fetchDataFallback();

          // Also attempt to reconnect WebSocket after 5 seconds
          reconnectTimeoutRef.current = setTimeout(() => {
            if (!isPaused && event.code !== 1000) {
              console.log("🔄 Attempting to reconnect WebSocket...");
              connectWebSocket();
            }
          }, 5000);
        }
      };

      wsRef.current.onerror = (error) => {
        console.error("💥 WebSocket connection error. Falling back to REST API.");
        setConnectionStatus("disconnected");
        setError("WebSocket unavailable, using REST API");

        // Immediately try REST API fallback on WebSocket error
        if (!isPaused) {
          fetchDataFallback();
        }
      };
    } catch (err) {
      console.error("❌ Failed to create WebSocket connection:", err);
      setConnectionStatus("disconnected");
      setError("WebSocket unavailable, using REST API");
      setIsLoading(false);

      // Try REST API as fallback
      if (!isPaused) {
        fetchDataFallback();
      }
    }
  };

  // Initialize WebSocket connection
  useEffect(() => {
    if (!isPaused) {
      connectWebSocket();
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close(1000, "Component unmounting");
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, [isPaused]);

  // Polling fallback when WebSocket is not available
  useEffect(() => {
    let pollInterval: NodeJS.Timeout;

    if (connectionStatus === "disconnected" && !isPaused) {
      console.log("🔄 Starting REST API polling...");

      // Poll every 5 seconds when WebSocket is not available
      pollInterval = setInterval(() => {
        if (connectionStatus === "disconnected" && !isPaused) {
          fetchDataFallback();
        }
      }, 5000);
    }

    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [connectionStatus, isPaused]);

  // Fallback data fetching via REST API
  const fetchDataFallback = async () => {
    try {
      const apiUrl =
        process.env.NODE_ENV === "production"
          ? "/api/network-analysis/latest"
          : "http://localhost:23335/api/network-analysis/latest";

      const response = await fetch(apiUrl);
      if (response.ok) {
        const result = await response.json();
        if (result.success && result.data) {
          // Convert timestamp strings to Date objects
          const networkData = {
            ...result.data,
            networkSpeeds: result.data.networkSpeeds.map((speed: any) => ({
              ...speed,
              timestamp: new Date(speed.timestamp),
            })),
          };
          setData(networkData);
          setError(null);
        }
      } else {
        setError("Failed to fetch data");
      }
    } catch (err) {
      console.error("❌ Failed to fetch network data:", err);
      setError("Failed to fetch data");
    } finally {
      setIsLoading(false);
    }
  };

  // Manual refresh function
  const handleRefresh = () => {
    if (connectionStatus === "connected" && wsRef.current) {
      // WebSocket is connected, data will come automatically
      console.log("🔄 WebSocket is connected, data refreshing automatically");
    } else {
      // WebSocket not connected, try fallback API
      console.log("🔄 Refreshing via REST API...");
      setIsLoading(true);
      fetchDataFallback();
    }
  };

  // Test backend connection
  const testConnection = async () => {
    try {
      const apiUrl =
        process.env.NODE_ENV === "production"
          ? "/api/network-analysis/status"
          : "http://localhost:23335/api/network-analysis/status";

      const response = await fetch(apiUrl);
      if (response.ok) {
        const result = await response.json();
        console.log("🔍 Backend status:", result);
        return result.service_running;
      }
    } catch (err) {
      console.log("🔍 Backend not available:", err);
      return false;
    }
    return false;
  };

  // D3.js Network Speed Chart
  useEffect(() => {
    if (!data || !networkChartRef.current) return;

    const svg = d3.select(networkChartRef.current);
    svg.selectAll("*").remove();

    const margin = { top: 30, right: 40, bottom: 60, left: 80 };
    const width = 1000 - margin.left - margin.right; // Increased width
    const height = 280 - margin.bottom - margin.top; // Increased height

    const g = svg
      .attr("width", width + margin.left + margin.right)
      .attr("height", height + margin.top + margin.bottom)
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Scales
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(data.networkSpeeds, (d) => d.timestamp) as [Date, Date])
      .range([0, width]);

    const yScale = d3
      .scaleLinear()
      .domain([0, d3.max(data.networkSpeeds, (d) => Math.max(d.download, d.upload)) as number])
      .nice()
      .range([height, 0]);

    // Line generators with smooth curves
    const downloadLine = d3
      .line<NetworkSpeed>()
      .x((d) => xScale(d.timestamp))
      .y((d) => yScale(d.download))
      .curve(d3.curveCatmullRom);

    const uploadLine = d3
      .line<NetworkSpeed>()
      .x((d) => xScale(d.timestamp))
      .y((d) => yScale(d.upload))
      .curve(d3.curveCatmullRom);

    // Add gradient definitions
    const defs = svg.append("defs");

    const downloadGradient = defs
      .append("linearGradient")
      .attr("id", "downloadGradient")
      .attr("gradientUnits", "userSpaceOnUse")
      .attr("x1", 0)
      .attr("y1", height)
      .attr("x2", 0)
      .attr("y2", 0);
    downloadGradient.append("stop").attr("offset", "0%").attr("stop-color", "#3b82f6").attr("stop-opacity", 0.1);
    downloadGradient.append("stop").attr("offset", "100%").attr("stop-color", "#3b82f6").attr("stop-opacity", 0.8);

    const uploadGradient = defs
      .append("linearGradient")
      .attr("id", "uploadGradient")
      .attr("gradientUnits", "userSpaceOnUse")
      .attr("x1", 0)
      .attr("y1", height)
      .attr("x2", 0)
      .attr("y2", 0);
    uploadGradient.append("stop").attr("offset", "0%").attr("stop-color", "#ef4444").attr("stop-opacity", 0.1);
    uploadGradient.append("stop").attr("offset", "100%").attr("stop-color", "#ef4444").attr("stop-opacity", 0.8);

    // Add grid lines
    g.append("g")
      .attr("class", "grid")
      .attr("transform", `translate(0,${height})`)
      .call(
        d3
          .axisBottom(xScale)
          .tickSize(-height)
          .tickFormat(() => "")
      )
      .style("stroke-dasharray", "3,3")
      .style("opacity", 0.1)
      .style("stroke", "#10b981");

    g.append("g")
      .attr("class", "grid")
      .call(
        d3
          .axisLeft(yScale)
          .tickSize(-width)
          .tickFormat(() => "")
      )
      .style("stroke-dasharray", "3,3")
      .style("opacity", 0.1)
      .style("stroke", "#10b981");

    // Add axes with enhanced styling
    g.append("g")
      .attr("transform", `translate(0,${height})`)
      .call(d3.axisBottom(xScale).tickFormat(d3.timeFormat("%H:%M:%S")))
      .style("color", "#10b981")
      .style("font-size", "12px")
      .style("font-family", "monospace");

    g.append("g")
      .call(d3.axisLeft(yScale).tickFormat((d) => `${d} Mbps`))
      .style("color", "#10b981")
      .style("font-size", "14px") // Increased font size
      .style("font-family", "monospace")
      .style("font-weight", "500");

    // Add area fills
    const downloadArea = d3
      .area<NetworkSpeed>()
      .x((d) => xScale(d.timestamp))
      .y0(height)
      .y1((d) => yScale(d.download))
      .curve(d3.curveCatmullRom);

    const uploadArea = d3
      .area<NetworkSpeed>()
      .x((d) => xScale(d.timestamp))
      .y0(height)
      .y1((d) => yScale(d.upload))
      .curve(d3.curveCatmullRom);

    // Add download area
    g.append("path")
      .datum(data.networkSpeeds)
      .attr("fill", "url(#downloadGradient)")
      .attr("d", downloadArea)
      .style("opacity", 0.3);

    // Add upload area
    g.append("path")
      .datum(data.networkSpeeds)
      .attr("fill", "url(#uploadGradient)")
      .attr("d", uploadArea)
      .style("opacity", 0.3);

    // Add download line with glow effect
    g.append("path")
      .datum(data.networkSpeeds)
      .attr("fill", "none")
      .attr("stroke", "#3b82f6")
      .attr("stroke-width", 3)
      .attr("d", downloadLine)
      .style("filter", "drop-shadow(0px 0px 6px #3b82f6)")
      .style("stroke-linecap", "round");

    // Add upload line with glow effect
    g.append("path")
      .datum(data.networkSpeeds)
      .attr("fill", "none")
      .attr("stroke", "#ef4444")
      .attr("stroke-width", 3)
      .attr("d", uploadLine)
      .style("filter", "drop-shadow(0px 0px 6px #ef4444)")
      .style("stroke-linecap", "round");

    // Enhanced data points
    g.selectAll(".download-dot")
      .data(data.networkSpeeds.slice(-5)) // Show last 5 points
      .enter()
      .append("circle")
      .attr("class", "download-dot")
      .attr("cx", (d) => xScale(d.timestamp))
      .attr("cy", (d) => yScale(d.download))
      .attr("r", 4)
      .style("fill", "#3b82f6")
      .style("stroke", "#1e40af")
      .style("stroke-width", 2)
      .style("filter", "drop-shadow(0px 0px 4px #3b82f6)")
      .style("opacity", 0.8);

    g.selectAll(".upload-dot")
      .data(data.networkSpeeds.slice(-5)) // Show last 5 points
      .enter()
      .append("circle")
      .attr("class", "upload-dot")
      .attr("cx", (d) => xScale(d.timestamp))
      .attr("cy", (d) => yScale(d.upload))
      .attr("r", 4)
      .style("fill", "#ef4444")
      .style("stroke", "#dc2626")
      .style("stroke-width", 2)
      .style("filter", "drop-shadow(0px 0px 4px #ef4444)")
      .style("opacity", 0.8);

    // Add legend
    const legend = g.append("g").attr("transform", `translate(${width - 100}, 20)`);

    legend.append("rect").attr("width", 12).attr("height", 2).attr("fill", "#3b82f6");
    legend
      .append("text")
      .attr("x", 20)
      .attr("y", 5)
      .attr("fill", "#10b981")
      .style("font-size", "12px")
      .style("font-family", "monospace")
      .text("Download");

    legend.append("rect").attr("y", 15).attr("width", 12).attr("height", 2).attr("fill", "#ef4444");
    legend
      .append("text")
      .attr("x", 20)
      .attr("y", 20)
      .attr("fill", "#10b981")
      .style("font-size", "12px")
      .style("font-family", "monospace")
      .text("Upload");
  }, [data]);

  // CPU Usage Chart
  useEffect(() => {
    if (!data || !cpuChartRef.current) return;

    const svg = d3.select(cpuChartRef.current);
    svg.selectAll("*").remove();

    const width = 200;
    const height = 200;
    const radius = Math.min(width, height) / 2;

    const g = svg
      .attr("width", width)
      .attr("height", height)
      .append("g")
      .attr("transform", `translate(${width / 2},${height / 2})`);

    // Create arc
    const arc = d3
      .arc()
      .innerRadius(radius - 30)
      .outerRadius(radius - 10)
      .startAngle(0)
      .endAngle((data.systemMetrics.cpu.usage / 100) * 2 * Math.PI);

    const backgroundArc = d3
      .arc()
      .innerRadius(radius - 30)
      .outerRadius(radius - 10)
      .startAngle(0)
      .endAngle(2 * Math.PI);

    // Background circle
    g.append("path").attr("d", backgroundArc).attr("fill", "#374151");

    // Usage arc
    g.append("path").attr("d", arc).attr("fill", "#10b981");

    // Center text
    g.append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .attr("fill", "#10b981")
      .style("font-size", "24px")
      .style("font-weight", "bold")
      .style("font-family", "monospace")
      .text(`${data.systemMetrics.cpu.usage.toFixed(1)}%`);
  }, [data]);

  // Memory Usage Chart
  useEffect(() => {
    if (!data || !memoryChartRef.current) return;

    const svg = d3.select(memoryChartRef.current);
    svg.selectAll("*").remove();

    const width = 300;
    const height = 60;
    const barHeight = 20;

    const g = svg.attr("width", width).attr("height", height).append("g").attr("transform", `translate(10, 20)`);

    const usagePercent = (data.systemMetrics.memory.used / data.systemMetrics.memory.total) * 100;
    const usageWidth = (data.systemMetrics.memory.used / data.systemMetrics.memory.total) * (width - 20);

    // Background bar
    g.append("rect")
      .attr("width", width - 20)
      .attr("height", barHeight)
      .attr("fill", "#374151")
      .attr("rx", 4);

    // Usage bar
    g.append("rect").attr("width", usageWidth).attr("height", barHeight).attr("fill", "#10b981").attr("rx", 4);

    // Text
    g.append("text")
      .attr("x", (width - 20) / 2)
      .attr("y", barHeight / 2 + 5)
      .attr("text-anchor", "middle")
      .attr("fill", "#ffffff")
      .style("font-size", "12px")
      .style("font-weight", "bold")
      .style("font-family", "monospace")
      .text(`${data.systemMetrics.memory.used.toFixed(1)}GB / ${data.systemMetrics.memory.total}GB`);
  }, [data]);

  const filteredPorts = showClosedPorts
    ? data?.openPorts || []
    : data?.openPorts.filter((port) => port.status === "open") || [];

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case "high":
        return "bg-red-500/20 text-red-300 border-red-500/30";
      case "medium":
        return "bg-yellow-500/20 text-yellow-300 border-yellow-500/30";
      default:
        return "bg-green-500/20 text-green-300 border-green-500/30";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "open":
        return "text-green-400";
      case "filtered":
        return "text-yellow-400";
      default:
        return "text-red-400";
    }
  };

  if (isLoading) {
    return (
      <AuthGuard>
        <DashboardLayout>
          <div className="min-h-screen bg-black text-green-400 font-mono flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-green-500 mx-auto mb-4"></div>
              <div className="text-xl">$ initializing network analysis...</div>
            </div>
          </div>
        </DashboardLayout>
      </AuthGuard>
    );
  }

  return (
    <AuthGuard>
      <DashboardLayout>
        <div className="min-h-screen bg-black text-green-400 font-mono p-6">
          {/* Header */}
          <div className="backdrop-blur-xl bg-linear-to-r from-gray-900/60 to-gray-800/30 border border-green-500/20 rounded-2xl p-6 mb-8 shadow-2xl">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold bg-linear-to-r from-green-400 to-emerald-300 bg-clip-text text-transparent mb-3">
                  [NETWORK-ANALYSIS] Real-time Monitor
                </h1>
                <div className="flex items-center space-x-4 text-sm">
                  <div className="flex items-center space-x-2 px-3 py-1 rounded-lg bg-green-500/10 border border-green-500/20">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span className="text-green-300 font-medium">
                      Last update: {data?.lastUpdate ? new Date(data.lastUpdate).toLocaleTimeString() : "No data"}
                    </span>
                  </div>
                  <span className="text-green-600">|</span>
                  <div className="flex items-center space-x-2 px-3 py-1 rounded-lg bg-black/20 border border-green-500/10">
                    <span className="text-green-300 font-medium">WebSocket:</span>
                    <span
                      className={`font-bold ${
                        connectionStatus === "connected"
                          ? "text-green-400"
                          : connectionStatus === "connecting"
                          ? "text-yellow-400"
                          : "text-red-400"
                      }`}
                    >
                      {connectionStatus.toUpperCase()}
                    </span>
                  </div>
                  <span className="text-green-600">|</span>
                  <div className="flex items-center space-x-2 px-3 py-1 rounded-lg bg-black/20 border border-green-500/10">
                    <span className="text-green-300 font-medium">Data:</span>
                    <span className={`font-bold ${data?.isConnected ? "text-green-400" : "text-red-400"}`}>
                      {data?.isConnected ? "LIVE" : "OFFLINE"}
                    </span>
                  </div>
                  {error && (
                    <>
                      <span className="text-green-600">|</span>
                      <div className="px-3 py-1 rounded-lg bg-red-500/10 border border-red-500/20">
                        <span className="text-red-400 font-medium">Error: {error}</span>
                      </div>
                    </>
                  )}
                </div>
              </div>
              <div className="flex space-x-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsPaused(!isPaused)}
                  className="text-green-400 border-green-500/30 hover:bg-green-500/10 backdrop-blur-sm px-4 py-2"
                >
                  {isPaused ? <Eye className="w-4 h-4 mr-2" /> : <EyeOff className="w-4 h-4 mr-2" />}
                  {isPaused ? "Resume" : "Pause"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRefresh}
                  className="text-green-400 border-green-500/30 hover:bg-green-500/10 backdrop-blur-sm px-4 py-2"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Refresh
                </Button>
              </div>
            </div>
          </div>

          {/* Network Speed Chart - Enhanced */}
          <div className="relative z-10 mb-8">
            <Card className="backdrop-blur-xl bg-linear-to-br from-gray-900/40 to-gray-800/20 border border-green-500/20 shadow-2xl hover:shadow-green-500/10 transition-all duration-500 group">
              <CardHeader>
                <CardTitle className="text-green-400 font-mono flex items-center text-xl">
                  <div className="p-2 rounded-lg bg-green-500/10 mr-3 group-hover:bg-green-500/20 transition-colors duration-300">
                    <Wifi className="w-6 h-6" />
                  </div>
                  Network Traffic Analysis
                  <div className="ml-auto">
                    <div className="flex items-center space-x-4">
                      <div className="flex items-center space-x-2">
                        <div className="w-3 h-3 bg-blue-400 rounded-full shadow-lg shadow-blue-400/50"></div>
                        <span className="text-sm text-blue-400 font-semibold">Download</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <div className="w-3 h-3 bg-red-400 rounded-full shadow-lg shadow-red-400/50"></div>
                        <span className="text-sm text-red-400 font-semibold">Upload</span>
                      </div>
                    </div>
                  </div>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex justify-center">
                  <div className="backdrop-blur-sm bg-black/20 rounded-2xl p-6 border border-green-500/10">
                    <svg ref={networkChartRef} className="text-green-400 drop-shadow-2xl"></svg>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* System Overview */}
          <div className="mb-8">
            <Card className="backdrop-blur-xl bg-linear-to-br from-gray-900/40 to-gray-800/20 border border-green-500/20 shadow-2xl hover:shadow-green-500/10 transition-all duration-500">
              <CardHeader>
                <CardTitle className="text-green-400 font-mono flex items-center text-xl">
                  <div className="p-2 rounded-lg bg-green-500/10 mr-3">
                    <Server className="w-6 h-6" />
                  </div>
                  System Overview
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="text-center p-4 rounded-xl bg-black/20 border border-green-500/10">
                    <div className="text-3xl font-bold text-blue-400 mb-2">{data?.systemMetrics.cpu.cores}</div>
                    <div className="text-sm text-green-300">CPU Cores</div>
                  </div>
                  <div className="text-center p-4 rounded-xl bg-black/20 border border-yellow-500/10">
                    <div className="text-3xl font-bold text-yellow-400 mb-2">{data?.systemMetrics.cpu.processes}</div>
                    <div className="text-sm text-green-300">Active Processes</div>
                  </div>
                  <div className="text-center p-4 rounded-xl bg-black/20 border border-purple-500/10">
                    <div className="text-3xl font-bold text-purple-400 mb-2">{data?.systemMetrics.memory.total}GB</div>
                    <div className="text-sm text-green-300">Total Memory</div>
                  </div>
                  <div className="text-center p-4 rounded-xl bg-black/20 border border-red-500/10">
                    <div className="text-3xl font-bold text-red-400 mb-2">{data?.systemMetrics.disk.total}GB</div>
                    <div className="text-sm text-green-300">Total Storage</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* System Resources */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
            {/* CPU Usage */}
            <Card className="backdrop-blur-xl bg-linear-to-br from-gray-900/40 to-gray-800/20 border border-green-500/20 shadow-2xl hover:shadow-green-500/10 transition-all duration-500 group">
              <CardHeader>
                <CardTitle className="text-green-400 font-mono flex items-center text-lg">
                  <div className="p-2 rounded-lg bg-green-500/10 mr-3 group-hover:bg-green-500/20 transition-colors duration-300">
                    <Cpu className="w-5 h-5" />
                  </div>
                  CPU Performance
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex justify-center mb-4">
                  <div className="backdrop-blur-sm bg-black/20 rounded-xl p-4 border border-green-500/10">
                    <svg ref={cpuChartRef}></svg>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex justify-between items-center p-3 rounded-lg bg-black/20 border border-green-500/10">
                    <span className="text-sm font-medium">Cores:</span>
                    <span className="text-blue-400 font-bold">{data?.systemMetrics.cpu.cores}</span>
                  </div>
                  <div className="flex justify-between items-center p-3 rounded-lg bg-black/20 border border-green-500/10">
                    <span className="text-sm font-medium">Processes:</span>
                    <span className="text-yellow-400 font-bold">{data?.systemMetrics.cpu.processes}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Memory Usage */}
            <Card className="backdrop-blur-xl bg-linear-to-br from-gray-900/40 to-gray-800/20 border border-green-500/20 shadow-2xl hover:shadow-green-500/10 transition-all duration-500 group">
              <CardHeader>
                <CardTitle className="text-green-400 font-mono flex items-center text-lg">
                  <div className="p-2 rounded-lg bg-green-500/10 mr-3 group-hover:bg-green-500/20 transition-colors duration-300">
                    <Monitor className="w-5 h-5" />
                  </div>
                  Memory Usage
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="backdrop-blur-sm bg-black/20 rounded-xl p-4 border border-green-500/10">
                    <svg ref={memoryChartRef}></svg>
                  </div>
                  <div className="grid grid-cols-1 gap-2">
                    <div className="flex justify-between items-center p-2 rounded-lg bg-green-500/10 border border-green-500/20">
                      <span className="text-sm font-medium">Available:</span>
                      <span className="text-green-400 font-bold">
                        {data?.systemMetrics.memory.available.toFixed(1)}GB
                      </span>
                    </div>
                    <div className="flex justify-between items-center p-2 rounded-lg bg-blue-500/10 border border-blue-500/20">
                      <span className="text-sm font-medium">Used:</span>
                      <span className="text-blue-400 font-bold">{data?.systemMetrics.memory.used.toFixed(1)}GB</span>
                    </div>
                    <div className="flex justify-between items-center p-2 rounded-lg bg-purple-500/10 border border-purple-500/20">
                      <span className="text-sm font-medium">Usage:</span>
                      <span className="text-purple-400 font-bold">
                        {data
                          ? ((data.systemMetrics.memory.used / data.systemMetrics.memory.total) * 100).toFixed(1)
                          : 0}
                        %
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Disk I/O */}
            <Card className="backdrop-blur-xl bg-linear-to-br from-gray-900/40 to-gray-800/20 border border-green-500/20 shadow-2xl hover:shadow-green-500/10 transition-all duration-500 group">
              <CardHeader>
                <CardTitle className="text-green-400 font-mono flex items-center text-lg">
                  <div className="p-2 rounded-lg bg-green-500/10 mr-3 group-hover:bg-green-500/20 transition-colors duration-300">
                    <HardDrive className="w-5 h-5" />
                  </div>
                  Disk I/O
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex justify-between items-center p-3 rounded-lg bg-black/20 border border-green-500/10">
                    <span className="text-sm font-medium">Read Speed:</span>
                    <span className="text-blue-400 font-bold">
                      {data?.systemMetrics.disk.readSpeed.toFixed(1)} MB/s
                    </span>
                  </div>
                  <div className="flex justify-between items-center p-3 rounded-lg bg-black/20 border border-green-500/10">
                    <span className="text-sm font-medium">Write Speed:</span>
                    <span className="text-red-400 font-bold">
                      {data?.systemMetrics.disk.writeSpeed.toFixed(1)} MB/s
                    </span>
                  </div>
                  <div className="flex justify-between items-center p-3 rounded-lg bg-black/20 border border-green-500/10">
                    <span className="text-sm font-medium">Used:</span>
                    <span className="text-green-400 font-bold">
                      {data?.systemMetrics.disk.used.toFixed(0)}GB / {data?.systemMetrics.disk.total}GB
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Open Ports Table */}
          <Card className="backdrop-blur-xl bg-linear-to-br from-gray-900/40 to-gray-800/20 border border-green-500/20 shadow-2xl hover:shadow-green-500/10 transition-all duration-500">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-green-400 font-mono flex items-center text-xl">
                <div className="p-2 rounded-lg bg-green-500/10 mr-3">
                  <Shield className="w-6 h-6" />
                </div>
                Port Analysis ({filteredPorts.length} ports)
              </CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowClosedPorts(!showClosedPorts)}
                className="text-green-400 border-green-500/30 hover:bg-green-500/10 backdrop-blur-sm"
              >
                {showClosedPorts ? "Hide Closed" : "Show All"}
              </Button>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-green-500/30">
                      <th className="text-left py-2 text-green-400">Port</th>
                      <th className="text-left py-2 text-green-400">Protocol</th>
                      <th className="text-left py-2 text-green-400">Service</th>
                      <th className="text-left py-2 text-green-400">Program</th>
                      <th className="text-left py-2 text-green-400">Status</th>
                      <th className="text-left py-2 text-green-400">Risk</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredPorts.map((port) => (
                      <tr key={port.port} className="border-b border-green-500/10 hover:bg-green-500/5">
                        <td className="py-2 font-mono text-white">{port.port}</td>
                        <td className="py-2 text-green-600">{port.protocol}</td>
                        <td className="py-2 text-blue-400">{port.service}</td>
                        <td className="py-2 text-yellow-400">{port.program || "Unknown"}</td>
                        <td className={`py-2 font-mono ${getStatusColor(port.status)}`}>{port.status.toUpperCase()}</td>
                        <td className="py-2">
                          <Badge className={`font-mono ${getRiskColor(port.risk)}`}>{port.risk.toUpperCase()}</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>
      </DashboardLayout>
    </AuthGuard>
  );
}
