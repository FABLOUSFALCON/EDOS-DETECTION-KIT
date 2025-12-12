"use client";

import React, { createContext, useContext, useState, useEffect } from "react";

interface Resource {
  id: string;
  name: string;
  type: "server" | "cloud" | "container" | "network";
  status: "online" | "offline" | "warning";
  location?: string;
  lastSeen?: string;
}

interface ResourceContextType {
  currentResource: Resource | null;
  availableResources: Resource[];
  switchResource: (resourceId: string) => void;
  isLoading: boolean;
  error: string | null;
}

const ResourceContext = createContext<ResourceContextType | undefined>(undefined);

export function useResource() {
  const context = useContext(ResourceContext);
  if (context === undefined) {
    throw new Error("useResource must be used within a ResourceProvider");
  }
  return context;
}

export function ResourceProvider({ children }: { children: React.ReactNode }) {
  const [currentResource, setCurrentResource] = useState<Resource | null>(null);
  const [availableResources, setAvailableResources] = useState<Resource[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load available resources on mount
  useEffect(() => {
    loadResources();
  }, []);

  const loadResources = async () => {
    setIsLoading(true);
    try {
      // TODO: Replace with actual API call
      const mockResources: Resource[] = [
        {
          id: "res_001",
          name: "Production Server",
          type: "server",
          status: "online",
          location: "US-East-1",
          lastSeen: new Date().toISOString(),
        },
        {
          id: "res_002",
          name: "Development Environment",
          type: "cloud",
          status: "online",
          location: "US-West-2",
          lastSeen: new Date().toISOString(),
        },
        {
          id: "res_003",
          name: "Docker Cluster",
          type: "container",
          status: "warning",
          location: "EU-Central-1",
          lastSeen: new Date().toISOString(),
        },
      ];

      setAvailableResources(mockResources);

      // Set default resource if none selected
      if (!currentResource && mockResources.length > 0) {
        setCurrentResource(mockResources[0]);
        localStorage.setItem("selectedResourceId", mockResources[0].id);
      }
    } catch (err) {
      setError("Failed to load resources");
    } finally {
      setIsLoading(false);
    }
  };

  const switchResource = (resourceId: string) => {
    const resource = availableResources.find((r) => r.id === resourceId);
    if (resource) {
      setCurrentResource(resource);
      localStorage.setItem("selectedResourceId", resourceId);

      // Emit custom event to notify components about resource change
      window.dispatchEvent(
        new CustomEvent("resourceChanged", {
          detail: { resourceId, resource },
        })
      );
    }
  };

  // Load saved resource from localStorage
  useEffect(() => {
    const savedResourceId = localStorage.getItem("selectedResourceId");
    if (savedResourceId && availableResources.length > 0) {
      const savedResource = availableResources.find((r) => r.id === savedResourceId);
      if (savedResource) {
        setCurrentResource(savedResource);
      }
    }
  }, [availableResources]);

  return (
    <ResourceContext.Provider
      value={{
        currentResource,
        availableResources,
        switchResource,
        isLoading,
        error,
      }}
    >
      {children}
    </ResourceContext.Provider>
  );
}
