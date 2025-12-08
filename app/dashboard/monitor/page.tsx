"use client";

import React, { useState, useEffect, useRef } from "react";
import { Terminal, Wifi, WifiOff, Pause, Play } from "lucide-react";
import { DashboardLayout } from "@/components/dashboard-layout";
import { AuthGuard } from "@/components/auth-guard";

interface JSONLog {
  id: string;
  timestamp: Date;
  rawJSON: string;
}

export default function MonitorPage() {
  const [jsonLogs, setJsonLogs] = useState<JSONLog[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [messageCount, setMessageCount] = useState(0);

  const terminalRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const maxLogs = 50; // Keep last 50 predictions to prevent overwhelming
  const [isAutoScrollEnabled, setIsAutoScrollEnabled] = useState(true);

  // Enhanced auto-scroll to top for newest messages
  const scrollToTop = () => {
    if (terminalRef.current && !isPaused && isAutoScrollEnabled) {
      terminalRef.current.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    }
  };

  // Pretty print JSON with syntax highlighting
  const formatJSON = (jsonString: string): React.ReactElement => {
    try {
      const parsed = JSON.parse(jsonString);
      const formatted = JSON.stringify(parsed, null, 2);

      // Simple syntax highlighting
      const highlighted = formatted
        .replace(/"([^"]+)":/g, '<span class="text-blue-300">"$1"</span>:') // Keys
        .replace(/: "([^"]*)"/g, ': <span class="text-green-300">"$1"</span>') // String values
        .replace(/: (\d+\.?\d*)/g, ': <span class="text-yellow-300">$1</span>') // Numbers
        .replace(/: (true|false)/g, ': <span class="text-purple-300">$1</span>') // Booleans
        .replace(/: null/g, ': <span class="text-gray-400">null</span>'); // Null

      return <div className="leading-relaxed" dangerouslySetInnerHTML={{ __html: highlighted }} />;
    } catch {
      // Fallback for invalid JSON
      return <div className="text-red-400">Invalid JSON: {jsonString}</div>;
    }
  };

  // WebSocket connection to backend
  const connectWebSocket = () => {
    try {
      setConnectionError(null);
      console.log("🔌 Connecting to WebSocket...");

      // Connect to WebSocket endpoint that streams Redis data
      const ws = new WebSocket("ws://localhost:23335/ws/ml/live");

      ws.onopen = () => {
        console.log("✅ WebSocket connected");
        setIsConnected(true);
        setConnectionError(null);
      };

      ws.onmessage = (event) => {
        if (isPaused) return;

        try {
          const rawData = JSON.parse(event.data);
          console.log("📡 Received Redis data:", rawData);

          // Skip heartbeat and connection status messages
          if (rawData.type === "heartbeat" || rawData.type === "connection_status" || rawData.type === "pong") {
            return;
          }

          // Get the raw JSON from the msg field - this is what's stored in Redis
          const redisJSON = rawData.msg;
          if (redisJSON) {
            const newLog: JSONLog = {
              id: rawData.message_id || Date.now().toString(),
              timestamp: new Date(),
              rawJSON: redisJSON,
            };

            setJsonLogs((prev) => {
              // Add new logs to the beginning of the array (newest first)
              const updated = [newLog, ...prev];
              return updated.slice(0, maxLogs); // Keep only recent logs
            });

            setMessageCount((prev) => prev + 1);

            // Scroll to top to show the newest log if auto-scroll is enabled
            setTimeout(() => {
              scrollToTop();
            }, 100);
          }
        } catch (error) {
          console.error("❌ Failed to parse WebSocket message:", error);
        }
      };

      ws.onclose = () => {
        console.log("🔌 WebSocket disconnected");
        setIsConnected(false);
        // Reconnect after 3 seconds
        setTimeout(connectWebSocket, 3000);
      };

      ws.onerror = (error) => {
        console.error("❌ WebSocket error:", error);
        setConnectionError("WebSocket connection failed");
        setIsConnected(false);
      };

      wsRef.current = ws;
    } catch (error) {
      console.error("❌ Failed to connect WebSocket:", error);
      setConnectionError("Failed to establish WebSocket connection");
      setIsConnected(false);
    }
  };

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const togglePause = () => {
    setIsPaused(!isPaused);
    // When resuming, enable auto-scroll and scroll to top for newest messages
    if (isPaused) {
      setIsAutoScrollEnabled(true);
      setTimeout(() => {
        scrollToTop();
      }, 200);
    }
  };

  // Handle manual scrolling - disable auto-scroll if user scrolls down from top
  const handleScroll = () => {
    if (terminalRef.current && !isPaused) {
      const { scrollTop } = terminalRef.current;
      const isNearTop = scrollTop <= 100;
      setIsAutoScrollEnabled(isNearTop);
    }
  };

  return (
    <AuthGuard>
      <DashboardLayout>
        <style jsx>{`
          @keyframes slideIn {
            from {
              opacity: 0;
              transform: translateY(20px);
            }
            to {
              opacity: 1;
              transform: translateY(0);
            }
          }
          .animate-slideIn {
            animation: slideIn 0.6s ease-out forwards;
          }
        `}</style>
        <div className="h-full bg-black text-green-400 font-mono flex flex-col">
          {/* Terminal Header */}
          <div className="border-b border-green-500/30 p-4 bg-gray-900/50">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Terminal className="w-6 h-6" />
                <div>
                  <h1 className="text-xl font-bold">ML Prediction Stream Monitor</h1>
                  <p className="text-sm text-green-300/70">Real-time Redis stream • Live ML predictions</p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                {/* Connection Status */}
                <div className="flex items-center gap-2">
                  {isConnected ? (
                    <Wifi className="w-5 h-5 text-green-400" />
                  ) : (
                    <WifiOff className="w-5 h-5 text-red-400" />
                  )}
                  <span className="text-sm">{isConnected ? "Connected" : "Disconnected"}</span>
                </div>

                {/* Pause/Play */}
                <button
                  onClick={togglePause}
                  className={`flex items-center gap-2 px-3 py-1 border rounded transition-colors ${
                    isPaused
                      ? "border-green-500/50 bg-green-500/10 text-green-400 hover:bg-green-500/20"
                      : "border-yellow-500/50 bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20"
                  }`}
                >
                  {isPaused ? <Play className="w-4 h-4" /> : <Pause className="w-4 h-4" />}
                  {isPaused ? "Resume" : "Pause"}
                </button>

                {/* Auto-scroll indicator */}
                {!isAutoScrollEnabled && !isPaused && (
                  <button
                    onClick={() => {
                      setIsAutoScrollEnabled(true);
                      scrollToTop();
                    }}
                    className="flex items-center gap-2 px-3 py-1 border border-blue-500/50 bg-blue-500/10 text-blue-400 rounded hover:bg-blue-500/20 animate-pulse"
                  >
                    ↑ Back to Live
                  </button>
                )}

                {/* Stats */}
                <div className="text-right text-sm">
                  <div className="text-green-300">
                    Messages: {messageCount} |<span className="text-blue-400 ml-1">Redis Stream</span>
                  </div>
                  <div className="text-green-300/70">Raw JSON Flow</div>
                </div>
              </div>
            </div>
          </div>

          {/* Connection Error */}
          {connectionError && (
            <div className="p-3 bg-red-900/30 border-b border-red-500/30 text-red-400">❌ {connectionError}</div>
          )}

          {/* Terminal Output */}
          <div
            ref={terminalRef}
            onScroll={handleScroll}
            className="flex-1 overflow-y-auto p-4 bg-black relative"
            style={{
              fontFamily: 'Monaco, "Lucida Console", monospace',
              scrollBehavior: "smooth",
            }}
          >
            {/* Pause overlay */}
            {isPaused && (
              <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-10">
                <div className="bg-yellow-500/20 border border-yellow-500/50 rounded px-4 py-2 text-yellow-400 flex items-center gap-2 animate-pulse">
                  <Pause className="w-4 h-4" />
                  Stream Paused - Click Resume to continue
                </div>
              </div>
            )}

            {jsonLogs.length === 0 ? (
              <div className="text-center py-8 text-green-300/50">
                <Terminal className="w-12 h-12 mx-auto mb-4 opacity-50 animate-pulse" />
                <p className="animate-pulse">Waiting for Redis JSON stream...</p>
                <p className="text-sm mt-2">{isConnected ? "Connected to Redis stream" : "Connecting to backend..."}</p>
              </div>
            ) : (
              <div className="space-y-4">
                {jsonLogs.map((log, index) => (
                  <div
                    key={log.id}
                    className="transform transition-all duration-500 ease-in-out opacity-0 translate-y-2 animate-slideIn"
                    style={{
                      animationDelay: `${index * 50}ms`,
                      animationFillMode: "forwards",
                    }}
                  >
                    {/* Message header */}
                    <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                      <span className="text-cyan-400">#{messageCount - index}</span>
                      <span className="text-green-400">•</span>
                      <span>
                        {log.timestamp.toLocaleTimeString()}.
                        {log.timestamp.getMilliseconds().toString().padStart(3, "0")}
                      </span>
                      {index === 0 && <span className="text-green-400 text-xs font-bold animate-pulse">LATEST</span>}
                    </div>

                    {/* Pretty JSON */}
                    <div className="bg-gray-900/50 rounded-lg p-3 border border-green-500/20 hover:border-green-500/40 transition-colors">
                      <div className="text-sm font-mono">{formatJSON(log.rawJSON)}</div>
                    </div>
                  </div>
                ))}

                {/* Bottom spacer for smooth scrolling */}
                <div className="h-4"></div>
              </div>
            )}
          </div>

          {/* Terminal Footer */}
          <div className="border-t border-green-500/30 p-2 bg-gray-900/50 text-sm text-green-300/70">
            <div className="flex justify-between items-center">
              <span>
                {isPaused ? "⏸️ Stream Paused" : "▶️ Live JSON Stream"} | Showing latest{" "}
                {Math.min(jsonLogs.length, maxLogs)} messages (newest first)
                {!isAutoScrollEnabled && !isPaused && " | 📍 Manual scroll mode"}
              </span>
              <div className="flex items-center gap-3">
                <span className={`flex items-center gap-1 ${isConnected ? "text-green-400" : "text-red-400"}`}>
                  <div
                    className={`w-2 h-2 rounded-full ${isConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`}
                  ></div>
                  {isConnected ? "Redis WebSocket Active" : "Disconnected"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </DashboardLayout>
    </AuthGuard>
  );
}
