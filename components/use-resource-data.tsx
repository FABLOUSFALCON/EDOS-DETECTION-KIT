"use client";

import { useResource } from "./resource-context";
import { useEffect, useState } from "react";

export function useResourceData<T>(fetcher: (resourceId: string) => Promise<T>, dependencies: any[] = []) {
  const { currentResource } = useResource();
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!currentResource) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const result = await fetcher(currentResource.id);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch data");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [currentResource?.id, ...dependencies]);

  // Listen for resource changes
  useEffect(() => {
    const handleResourceChange = () => {
      setData(null); // Clear old data when switching resources
    };

    window.addEventListener("resourceChanged", handleResourceChange);
    return () => window.removeEventListener("resourceChanged", handleResourceChange);
  }, []);

  return {
    data,
    loading,
    error,
    resourceId: currentResource?.id,
    resourceName: currentResource?.name,
  };
}
