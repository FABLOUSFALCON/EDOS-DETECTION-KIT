"use client";

import React from "react";
import { ChevronDown, Server, Cloud, Box, Network, AlertTriangle } from "lucide-react";
import { useResource } from "./resource-context";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from "./ui/dropdown-menu";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";

const getResourceIcon = (type: string) => {
  switch (type) {
    case "server":
      return <Server className="h-4 w-4" />;
    case "cloud":
      return <Cloud className="h-4 w-4" />;
    case "container":
      return <Box className="h-4 w-4" />;
    case "network":
      return <Network className="h-4 w-4" />;
    default:
      return <Server className="h-4 w-4" />;
  }
};

const getStatusColor = (status: string) => {
  switch (status) {
    case "online":
      return "bg-green-500";
    case "warning":
      return "bg-yellow-500";
    case "offline":
      return "bg-red-500";
    default:
      return "bg-gray-500";
  }
};

const getStatusBadgeVariant = (status: string) => {
  switch (status) {
    case "online":
      return "success";
    case "warning":
      return "warning";
    case "offline":
      return "destructive";
    default:
      return "secondary";
  }
};

export function ResourceSwitcher() {
  const { currentResource, availableResources, switchResource, isLoading } = useResource();

  if (isLoading) {
    return (
      <div className="flex items-center space-x-2">
        <div className="w-4 h-4 bg-gray-600 animate-pulse rounded"></div>
        <div className="w-32 h-6 bg-gray-600 animate-pulse rounded"></div>
      </div>
    );
  }

  if (!currentResource) {
    return (
      <div className="flex items-center space-x-2 text-gray-400">
        <AlertTriangle className="h-4 w-4" />
        <span>No resources available</span>
      </div>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="flex items-center space-x-2 text-left h-auto p-2 hover:bg-gray-800">
          <div className="flex items-center space-x-2">
            {getResourceIcon(currentResource.type)}
            <div className="flex flex-col">
              <div className="flex items-center space-x-2">
                <span className="font-medium text-white">{currentResource.name}</span>
                <div className={`w-2 h-2 rounded-full ${getStatusColor(currentResource.status)}`} />
              </div>
              <span className="text-xs text-gray-400">{currentResource.location}</span>
            </div>
          </div>
          <ChevronDown className="h-4 w-4 text-gray-400" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-64 bg-gray-900 border-gray-700">
        <div className="p-2">
          <p className="text-xs text-gray-400 mb-2">Switch Resource</p>
        </div>
        <DropdownMenuSeparator className="bg-gray-700" />
        {availableResources.map((resource) => (
          <DropdownMenuItem
            key={resource.id}
            onClick={() => switchResource(resource.id)}
            className="flex items-center space-x-3 p-3 hover:bg-gray-800 cursor-pointer"
          >
            <div className="flex items-center space-x-2">
              {getResourceIcon(resource.type)}
              <div className="flex flex-col flex-1">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-white">{resource.name}</span>
                  <Badge variant={getStatusBadgeVariant(resource.status) as any} className="text-xs">
                    {resource.status}
                  </Badge>
                </div>
                <div className="flex items-center space-x-2">
                  <span className="text-xs text-gray-400">{resource.location}</span>
                  <span className="text-xs text-gray-500">• {resource.type}</span>
                </div>
              </div>
            </div>
            {currentResource.id === resource.id && <div className="w-2 h-2 bg-green-500 rounded-full" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator className="bg-gray-700" />
        <DropdownMenuItem className="p-3 text-gray-400 hover:bg-gray-800">
          <div className="flex items-center space-x-2">
            <span className="text-sm">Manage Resources</span>
            <span className="text-xs bg-gray-700 px-2 py-1 rounded">Coming Soon</span>
          </div>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
