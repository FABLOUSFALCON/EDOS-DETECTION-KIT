"use client";

import React, { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useResource } from "@/components/resource-context";

interface ThreatLocation {
  id: string;
  country: string;
  lat: number;
  lng: number;
  attacks: number;
  severity: "critical" | "high" | "medium" | "low";
  lastAttack: Date;
}

interface AttackFlow {
  id: string;
  source: [number, number]; // [lng, lat]
  target: [number, number]; // [lng, lat]
  severity: "critical" | "high" | "medium" | "low";
  timestamp: Date;
}

// Mock data for demonstration
const mockThreatData: ThreatLocation[] = [
  {
    id: "1",
    country: "Russia",
    lat: 55.7558,
    lng: 37.6176,
    attacks: 245,
    severity: "critical",
    lastAttack: new Date(),
  },
  { id: "2", country: "China", lat: 39.9042, lng: 116.4074, attacks: 189, severity: "high", lastAttack: new Date() },
  {
    id: "3",
    country: "North Korea",
    lat: 39.0392,
    lng: 125.7625,
    attacks: 156,
    severity: "critical",
    lastAttack: new Date(),
  },
  { id: "4", country: "Iran", lat: 35.6892, lng: 51.389, attacks: 134, severity: "high", lastAttack: new Date() },
  { id: "5", country: "Brazil", lat: -14.235, lng: -51.9253, attacks: 87, severity: "medium", lastAttack: new Date() },
  { id: "6", country: "Turkey", lat: 38.9637, lng: 35.2433, attacks: 76, severity: "medium", lastAttack: new Date() },
  { id: "7", country: "Romania", lat: 45.9432, lng: 24.9668, attacks: 65, severity: "medium", lastAttack: new Date() },
  { id: "8", country: "India", lat: 20.5937, lng: 78.9629, attacks: 54, severity: "low", lastAttack: new Date() },
  { id: "9", country: "Vietnam", lat: 14.0583, lng: 108.2772, attacks: 43, severity: "low", lastAttack: new Date() },
  { id: "10", country: "Pakistan", lat: 30.3753, lng: 69.3451, attacks: 38, severity: "low", lastAttack: new Date() },
];

// Your server location (approximate location)
const SERVER_LOCATION: [number, number] = [-74.006, 40.7128]; // New York

const ThreatMap: React.FC = () => {
  const mapRef = useRef<SVGSVGElement>(null);
  const { currentResource } = useResource();
  const [threatData, setThreatData] = useState<ThreatLocation[]>(mockThreatData);
  const [attackFlows, setAttackFlows] = useState<AttackFlow[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<ThreatLocation | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("all");
  const [isRealTimeMode, setIsRealTimeMode] = useState(false);
  const [searchCountry, setSearchCountry] = useState("");

  // WebSocket connection for real-time updates
  useEffect(() => {
    if (!isRealTimeMode || !currentResource) return;

    const ws = new WebSocket(`ws://localhost:23335/ws/threat_map/${currentResource.id}`);

    ws.onopen = () => {
      console.log(`🌍 Connected to threat map WebSocket for resource: ${currentResource.name}`);
    };

    ws.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data);
        if (update.type === "threat_update") {
          handleRealTimeUpdate(update.data);
        }
      } catch (error) {
        console.error("WebSocket message error:", error);
      }
    };

    ws.onclose = () => {
      console.log(`🌍 Threat map WebSocket disconnected for resource: ${currentResource.name}`);
    };

    return () => {
      ws.close();
    };
  }, [isRealTimeMode, currentResource?.id]);

  const handleRealTimeUpdate = (data: any) => {
    const newThreat: ThreatLocation = {
      id: `live_${Date.now()}`,
      country: data.country,
      lat: data.lat,
      lng: data.lng,
      attacks: 1,
      severity: data.severity,
      lastAttack: new Date(data.timestamp),
    };

    setThreatData((prev) => {
      const existing = prev.find((t) => t.country === data.country);
      if (existing) {
        return prev.map((t) =>
          t.country === data.country ? { ...t, attacks: t.attacks + 1, lastAttack: new Date(data.timestamp) } : t
        );
      } else {
        return [...prev, newThreat];
      }
    });
  };

  // Filter threats based on severity and search
  const filteredThreats = threatData.filter((threat) => {
    const matchesSeverity = filterSeverity === "all" || threat.severity === filterSeverity;
    const matchesSearch = threat.country.toLowerCase().includes(searchCountry.toLowerCase());
    return matchesSeverity && matchesSearch;
  });

  useEffect(() => {
    if (!mapRef.current) return;

    const svg = d3.select(mapRef.current);
    svg.selectAll("*").remove();

    const width = 1200;
    const height = 600;
    const margin = { top: 20, right: 20, bottom: 20, left: 20 };

    svg.attr("width", width).attr("height", height);

    // Create projection and path generator
    const projection = d3
      .geoNaturalEarth1()
      .scale(200)
      .translate([width / 2, height / 2]);

    const path = d3.geoPath().projection(projection);

    // Create zoom behavior
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 8])
      .on("zoom", (event) => {
        // Apply transform only to the map group to keep all elements together
        mapGroup.attr("transform", event.transform);
      });

    svg.call(zoom);

    // Create main group for all map elements
    const mapGroup = svg.append("g").attr("class", "map-group");

    // Load world map data
    d3.json("https://raw.githubusercontent.com/holtzy/D3-graph-gallery/master/DATA/world.geojson")
      .then((world: any) => {
        // Draw countries
        mapGroup
          .selectAll("path")
          .data(world.features)
          .enter()
          .append("path")
          .attr("d", path)
          .attr("fill", "#1a1a1a")
          .attr("stroke", "#27d77a")
          .attr("stroke-width", 0.5)
          .attr("opacity", 0.8)
          .on("mouseover", function (event, d) {
            d3.select(this).attr("fill", "#27d77a").attr("opacity", 0.3);
          })
          .on("mouseout", function (event, d) {
            d3.select(this).attr("fill", "#1a1a1a").attr("opacity", 0.8);
          });

        // Add threat locations
        addThreatMarkers(mapGroup, projection);

        // Add server location
        addServerMarker(mapGroup, projection);

        // Start attack flow animations
        startAttackFlowAnimations(mapGroup, projection);
      })
      .catch((error) => {
        console.error("Error loading world map data:", error);
        // Fallback: just show threat markers without country borders
        addThreatMarkers(mapGroup, projection);
        addServerMarker(mapGroup, projection);
        startAttackFlowAnimations(mapGroup, projection);
      });
  }, [threatData]);

  const addThreatMarkers = (
    group: d3.Selection<SVGGElement, unknown, null, undefined>,
    projection: d3.GeoProjection
  ) => {
    const markers = group
      .selectAll(".threat-marker")
      .data(threatData)
      .enter()
      .append("g")
      .attr("class", "threat-marker")
      .attr("transform", (d) => {
        const coords = projection([d.lng, d.lat]);
        return coords ? `translate(${coords[0]}, ${coords[1]})` : "translate(0, 0)";
      });

    // Pulsing circles for threats
    markers.each(function (d) {
      const marker = d3.select(this);

      // Main circle
      marker
        .append("circle")
        .attr("r", Math.sqrt(d.attacks) * 0.8)
        .attr("fill", getSeverityColor(d.severity))
        .attr("opacity", 0.8)
        .attr("stroke", "#ffffff")
        .attr("stroke-width", 1);

      // Pulsing ring
      const pulseRing = marker
        .append("circle")
        .attr("r", Math.sqrt(d.attacks) * 0.8)
        .attr("fill", "none")
        .attr("stroke", getSeverityColor(d.severity))
        .attr("stroke-width", 2)
        .attr("opacity", 1);

      // Pulse animation
      pulseRing
        .transition()
        .duration(2000)
        .ease(d3.easeLinear)
        .attr("r", Math.sqrt(d.attacks) * 2)
        .attr("opacity", 0)
        .on("end", function () {
          d3.select(this)
            .attr("r", Math.sqrt(d.attacks) * 0.8)
            .attr("opacity", 1);
        });

      // Repeat pulse
      setInterval(() => {
        pulseRing
          .transition()
          .duration(2000)
          .ease(d3.easeLinear)
          .attr("r", Math.sqrt(d.attacks) * 2)
          .attr("opacity", 0)
          .on("end", function () {
            d3.select(this)
              .attr("r", Math.sqrt(d.attacks) * 0.8)
              .attr("opacity", 1);
          });
      }, 3000);

      // Click handler
      marker
        .style("cursor", "pointer")
        .on("click", () => setSelectedCountry(d))
        .on("mouseover", function () {
          d3.select(this).select("circle").attr("stroke-width", 3);
        })
        .on("mouseout", function () {
          d3.select(this).select("circle").attr("stroke-width", 1);
        });
    });
  };

  const addServerMarker = (
    group: d3.Selection<SVGGElement, unknown, null, undefined>,
    projection: d3.GeoProjection
  ) => {
    const serverCoords = projection(SERVER_LOCATION);
    if (!serverCoords) return;

    // Server marker with transform instead of absolute positioning
    const serverMarker = group
      .append("g")
      .attr("class", "server-marker")
      .attr("transform", `translate(${serverCoords[0]}, ${serverCoords[1]})`);

    // Server icon background
    serverMarker
      .append("circle")
      .attr("r", 12)
      .attr("fill", "#27d77a")
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 2)
      .attr("opacity", 0.9);

    // Server text label
    serverMarker
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .attr("font-size", "12px")
      .attr("fill", "#000000")
      .attr("font-weight", "bold")
      .text("S");

    // Server pulsing ring
    const serverRing = serverMarker
      .append("circle")
      .attr("r", 12)
      .attr("fill", "none")
      .attr("stroke", "#27d77a")
      .attr("stroke-width", 3)
      .attr("opacity", 1);

    // Server pulse animation
    setInterval(() => {
      serverRing
        .transition()
        .duration(2000)
        .attr("r", 25)
        .attr("opacity", 0)
        .on("end", function () {
          d3.select(this).attr("r", 12).attr("opacity", 1);
        });
    }, 2000);
  };

  const startAttackFlowAnimations = (
    group: d3.Selection<SVGGElement, unknown, null, undefined>,
    projection: d3.GeoProjection
  ) => {
    const createAttackFlow = () => {
      const randomThreat = threatData[Math.floor(Math.random() * threatData.length)];
      const source = projection([randomThreat.lng, randomThreat.lat]);
      const target = projection(SERVER_LOCATION);

      if (!source || !target) return;

      const flowLine = group
        .append("path")
        .attr("class", "attack-flow")
        .attr("d", createArcPath(source, target))
        .attr("stroke", getSeverityColor(randomThreat.severity))
        .attr("stroke-width", 2)
        .attr("fill", "none")
        .attr("opacity", 0.8)
        .attr("stroke-dasharray", "5,5");

      // Animate the flow
      const totalLength = flowLine.node()?.getTotalLength() || 0;

      flowLine
        .attr("stroke-dasharray", `0,${totalLength}`)
        .transition()
        .duration(3000)
        .ease(d3.easeLinear)
        .attr("stroke-dasharray", `${totalLength},${totalLength}`)
        .on("end", () => {
          flowLine.remove();
        });

      // Add moving dot
      const dot = group
        .append("circle")
        .attr("class", "attack-dot")
        .attr("r", 4)
        .attr("fill", getSeverityColor(randomThreat.severity))
        .attr("opacity", 1);

      dot
        .transition()
        .duration(3000)
        .ease(d3.easeLinear)
        .attrTween("transform", () => {
          const interpolate = d3.interpolate(0, 1);
          return (t: number) => {
            const point = flowLine.node()?.getPointAtLength(t * totalLength);
            return point ? `translate(${point.x}, ${point.y})` : "translate(0, 0)";
          };
        })
        .on("end", () => {
          dot.remove();
        });
    };

    // Create attack flows at random intervals
    setInterval(createAttackFlow, 2000);
  };

  const createArcPath = (source: [number, number], target: [number, number]): string => {
    const dx = target[0] - source[0];
    const dy = target[1] - source[1];
    const dr = Math.sqrt(dx * dx + dy * dy) * 0.3;

    return `M ${source[0]},${source[1]} Q ${source[0] + dx / 2},${source[1] + dy / 2 - dr} ${target[0]},${target[1]}`;
  };

  const getSeverityColor = (severity: string): string => {
    switch (severity) {
      case "critical":
        return "#ff4444";
      case "high":
        return "#ff8800";
      case "medium":
        return "#ffcc00";
      case "low":
        return "#27d77a";
      default:
        return "#27d77a";
    }
  };

  const getTotalAttacks = () => threatData.reduce((sum, threat) => sum + threat.attacks, 0);
  const getTopThreat = () =>
    threatData.reduce((max, threat) => (threat.attacks > max.attacks ? threat : max), threatData[0]);

  return (
    <div className="w-full space-y-6">
      {/* Main Map */}
      <Card className="bg-card/20 backdrop-blur-xl border-primary/20">
        <CardContent className="p-2">
          <div className="relative bg-black/50 rounded-lg overflow-hidden">
            <svg ref={mapRef} className="w-full h-auto" style={{ minHeight: "700px" }}></svg>

            {/* Compact Statistics - Top Left */}
            <div className="absolute top-4 left-4 space-y-2">
              <div className="bg-black/80 backdrop-blur-sm rounded-lg p-3 text-center min-w-[120px]">
                <p className="text-lg font-bold text-primary">{threatData.length}</p>
                <p className="text-xs text-muted-foreground">Active Threats</p>
              </div>
              <div className="bg-black/80 backdrop-blur-sm rounded-lg p-3 text-center">
                <p className="text-lg font-bold text-red-400">{getTotalAttacks()}</p>
                <p className="text-xs text-muted-foreground">Total Attacks</p>
              </div>
            </div>

            {/* Legend - Top Right */}
            <div className="absolute top-4 right-4 bg-black/80 backdrop-blur-sm rounded-lg p-4 space-y-2">
              <h4 className="text-primary font-semibold text-sm mb-2">Threat Levels</h4>
              <div className="flex items-center space-x-2 text-xs">
                <div className="w-3 h-3 rounded-full bg-red-500"></div>
                <span className="text-white">Critical</span>
              </div>
              <div className="flex items-center space-x-2 text-xs">
                <div className="w-3 h-3 rounded-full bg-orange-500"></div>
                <span className="text-white">High</span>
              </div>
              <div className="flex items-center space-x-2 text-xs">
                <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                <span className="text-white">Medium</span>
              </div>
              <div className="flex items-center space-x-2 text-xs">
                <div className="w-3 h-3 rounded-full bg-green-500"></div>
                <span className="text-white">Low</span>
              </div>
              <div className="flex items-center space-x-2 text-xs mt-3">
                <div className="w-3 h-3 rounded-full bg-primary"></div>
                <span className="text-white">Your Server</span>
              </div>
            </div>

            {/* Country Info Panel */}
            {selectedCountry && (
              <div className="absolute bottom-4 left-4 bg-black/80 backdrop-blur-sm rounded-lg p-4 max-w-xs">
                <h4 className="text-primary font-semibold mb-2">{selectedCountry.country}</h4>
                <div className="space-y-1 text-sm text-white">
                  <p>
                    Attacks: <span className="text-primary">{selectedCountry.attacks}</span>
                  </p>
                  <p>
                    Severity:{" "}
                    <Badge
                      variant="outline"
                      className={`border-${getSeverityColor(selectedCountry.severity).replace("#", "")}`}
                    >
                      {selectedCountry.severity.toUpperCase()}
                    </Badge>
                  </p>
                  <p>
                    Last Attack:{" "}
                    <span className="text-muted-foreground">{selectedCountry.lastAttack.toLocaleTimeString()}</span>
                  </p>
                </div>
                <button onClick={() => setSelectedCountry(null)} className="mt-2 text-xs text-primary hover:underline">
                  Close
                </button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ThreatMap;
