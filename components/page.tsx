"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Activity, Shield, AlertTriangle, TrendingUp, Cpu, Users, Server, Play, Pause, RefreshCw } from "lucide-react";

// Types for the API responses
interface MLPrediction {
  is_attack: boolean;
  attack_probability: number;
  benign_probability: number;
  confidence: number;
  model_version: string;
  attack_type?: string;
}

interface BatchStatistics {
  total_flows: number;
  attack_predictions: number;
  benign_predictions: number;
  processing_time_ms: number;
  throughput_flows_per_sec: number;
  average_confidence: number;
}

interface LiveBatchResult {
  message_id: string;
  timestamp: string;
  client_id: string;
  resource_id: string;
  source: string;
  predictions: MLPrediction[];
  statistics: BatchStatistics;
}

interface ThreatSummary {
  total_flows_monitored: number;
  total_attacks_detected: number;
  attack_rate_percent: number;
  threat_level: string;
  active_clients: number;
  active_resources: number;
  last_update: string;
}

interface LiveMonitoringResponse {
  total_entries: number;
  latest_batches: LiveBatchResult[];
  threat_summary: ThreatSummary;
}

export default function LiveMonitorPage() {
  const [data, setData] = useState<LiveMonitoringResponse | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  // Fetch latest predictions
  const fetchPredictions = async () => {
    try {
      const response = await fetch("http://localhost:23335/api/ml/live/latest?limit=10");
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const newData: LiveMonitoringResponse = await response.json();
      setData(newData);
      setError(null);
      setIsConnected(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch data");
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  // Start/stop real-time monitoring
  const startMonitoring = () => {
    if (intervalRef.current) return;

    fetchPredictions(); // Initial fetch
    intervalRef.current = setInterval(fetchPredictions, 2000); // Update every 2 seconds
    setIsConnected(true);
  };

  const stopMonitoring = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsConnected(false);
  };

  // Auto-start monitoring on component mount
  useEffect(() => {
    startMonitoring();
    return () => stopMonitoring();
  }, []);

  const getThreatLevelColor = (level: string) => {
    switch (level) {
      case "CRITICAL":
        return "bg-red-500";
      case "HIGH":
        return "bg-orange-500";
      case "MEDIUM":
        return "bg-yellow-500";
      case "LOW":
        return "bg-blue-500";
      default:
        return "bg-green-500";
    }
  };

  const getThreatLevelText = (level: string) => {
    switch (level) {
      case "CRITICAL":
        return "text-red-400";
      case "HIGH":
        return "text-orange-400";
      case "MEDIUM":
        return "text-yellow-400";
      case "LOW":
        return "text-blue-400";
      default:
        return "text-green-400";
    }
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const getLatestPrediction = (): MLPrediction | null => {
    if (!data?.latest_batches.length) return null;
    const latestBatch = data.latest_batches[0];
    return latestBatch.predictions.length > 0 ? latestBatch.predictions[0] : null;
  };

  if (isLoading) {
    return (
      <div className="p-8 space-y-8 bg-gray-900 min-h-screen">
        <div className="flex items-center justify-center">
          <RefreshCw className="animate-spin h-8 w-8 text-blue-400 mr-2" />
          <span className="text-blue-400 text-lg">Connecting to ML Pipeline...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 bg-gray-900 min-h-screen">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Shield className="h-8 w-8 text-blue-400" />
          <div>
            <h1 className="text-3xl font-bold text-white">Live ML Monitor</h1>
            <p className="text-gray-400">Real-time Machine Learning Threat Detection</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <div
            className={`flex items-center px-3 py-2 rounded-lg ${isConnected ? "bg-green-900/50" : "bg-red-900/50"}`}
          >
            <div
              className={`w-2 h-2 rounded-full mr-2 ${isConnected ? "bg-green-400 animate-pulse" : "bg-red-400"}`}
            ></div>
            <span className={`text-sm font-medium ${isConnected ? "text-green-400" : "text-red-400"}`}>
              {isConnected ? "Live" : "Disconnected"}
            </span>
          </div>

          {isConnected ? (
            <Button onClick={stopMonitoring} variant="outline" size="sm">
              <Pause className="h-4 w-4 mr-1" />
              Pause
            </Button>
          ) : (
            <Button onClick={startMonitoring} variant="outline" size="sm">
              <Play className="h-4 w-4 mr-1" />
              Start
            </Button>
          )}

          <Button onClick={fetchPredictions} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Card className="border-red-500/20 bg-red-900/10">
          <CardContent className="p-4">
            <div className="flex items-center text-red-400">
              <AlertTriangle className="h-5 w-5 mr-2" />
              <span>Error: {error}</span>
            </div>
          </CardContent>
        </Card>
      )}

      {data && (
        <>
          {/* Threat Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card className="bg-gray-800/50 border-gray-700">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-400">Threat Level</p>
                    <p className={`text-2xl font-bold ${getThreatLevelText(data.threat_summary.threat_level)}`}>
                      {data.threat_summary.threat_level}
                    </p>
                  </div>
                  <div
                    className={`w-12 h-12 rounded-lg ${getThreatLevelColor(
                      data.threat_summary.threat_level
                    )} flex items-center justify-center`}
                  >
                    <Shield className="h-6 w-6 text-white" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gray-800/50 border-gray-700">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-400">Attack Rate</p>
                    <p className="text-2xl font-bold text-red-400">
                      {data.threat_summary.attack_rate_percent.toFixed(1)}%
                    </p>
                  </div>
                  <div className="w-12 h-12 rounded-lg bg-red-500 flex items-center justify-center">
                    <AlertTriangle className="h-6 w-6 text-white" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gray-800/50 border-gray-700">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-400">Total Flows</p>
                    <p className="text-2xl font-bold text-blue-400">
                      {data.threat_summary.total_flows_monitored.toLocaleString()}
                    </p>
                  </div>
                  <div className="w-12 h-12 rounded-lg bg-blue-500 flex items-center justify-center">
                    <Activity className="h-6 w-6 text-white" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-gray-800/50 border-gray-700">
              <CardContent className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-400">Active Resources</p>
                    <p className="text-2xl font-bold text-green-400">{data.threat_summary.active_resources}</p>
                  </div>
                  <div className="w-12 h-12 rounded-lg bg-green-500 flex items-center justify-center">
                    <Server className="h-6 w-6 text-white" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Latest Prediction Highlight */}
          {(() => {
            const latestPrediction = getLatestPrediction();
            const latestBatch = data.latest_batches[0];
            if (!latestPrediction || !latestBatch) return null;

            return (
              <Card className="bg-gradient-to-r from-blue-900/20 to-purple-900/20 border-blue-500/30">
                <CardHeader>
                  <CardTitle className="flex items-center text-white">
                    <Cpu className="h-5 w-5 mr-2 text-blue-400" />
                    Latest ML Prediction
                    <Badge className={`ml-auto ${latestPrediction.is_attack ? "bg-red-500" : "bg-green-500"}`}>
                      {latestPrediction.is_attack ? "ATTACK" : "BENIGN"}
                    </Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <p className="text-sm text-gray-400">Client → Resource</p>
                      <p className="text-lg text-white font-mono">
                        {latestBatch.client_id} → {latestBatch.resource_id}
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-400">Confidence Score</p>
                      <p className="text-lg text-blue-400 font-bold">
                        {(latestPrediction.confidence * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-400">Timestamp</p>
                      <p className="text-lg text-green-400">{formatTime(latestBatch.timestamp)}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })()}

          {/* Live Predictions Stream */}
          <Card className="bg-gray-800/50 border-gray-700">
            <CardHeader>
              <CardTitle className="flex items-center text-white">
                <TrendingUp className="h-5 w-5 mr-2 text-green-400" />
                Live Prediction Stream
                <Badge className="ml-auto bg-blue-500">{data.total_entries} Total Predictions</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4 max-h-96 overflow-y-auto">
                {data.latest_batches.map((batch, index) => (
                  <div
                    key={batch.message_id}
                    className={`p-4 rounded-lg border ${
                      index === 0 ? "border-blue-500/50 bg-blue-900/10" : "border-gray-600 bg-gray-700/30"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline" className="text-gray-300">
                          {batch.client_id}
                        </Badge>
                        <span className="text-gray-400">→</span>
                        <Badge variant="outline" className="text-gray-300">
                          {batch.resource_id}
                        </Badge>
                      </div>
                      <span className="text-sm text-gray-400">{formatTime(batch.timestamp)}</span>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <p className="text-gray-400">Flows Processed</p>
                        <p className="text-white font-semibold">{batch.statistics.total_flows}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Attacks Detected</p>
                        <p className="text-red-400 font-semibold">{batch.statistics.attack_predictions}</p>
                      </div>
                      <div>
                        <p className="text-gray-400">Processing Time</p>
                        <p className="text-blue-400 font-semibold">
                          {batch.statistics.processing_time_ms.toFixed(1)}ms
                        </p>
                      </div>
                      <div>
                        <p className="text-gray-400">Avg Confidence</p>
                        <p className="text-green-400 font-semibold">
                          {(batch.statistics.average_confidence * 100).toFixed(1)}%
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
