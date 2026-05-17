import React from "react";
import { ExternalLink } from "lucide-react";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { Incident } from "@/lib/api";

interface IncidentFeedProps {
  incidents: Incident[];
  onEngageAgent?: (incidentId: string) => void;
}

export function IncidentFeed({ incidents, onEngageAgent }: IncidentFeedProps) {
  return (
    <div className="glass rounded-xl border">
      <div className="px-5 py-4 border-b border-white/5 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-white flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-red-400 pulse-critical" />
          Live Incident Feed
        </h2>
        <span className="text-[10px] text-gray-500">{incidents.length} active</span>
      </div>
      <div className="divide-y divide-white/4 max-h-[600px] overflow-y-auto">
        {incidents.map((incident) => (
          <div key={incident.incident_id} className="px-5 py-4 hover:bg-white/2 transition-colors flex items-start gap-4 group">
            <div className={cn(
              "w-2 h-2 rounded-full mt-1.5 flex-shrink-0",
              incident.severity === "critical" && "bg-red-400 pulse-critical",
              incident.severity === "warning" && "bg-amber-400",
              incident.severity === "info" && "bg-blue-400",
            )} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className={cn(
                  "text-[10px] font-medium px-2 py-0.5 rounded-full border",
                  incident.severity === "critical" && "severity-critical",
                  incident.severity === "warning" && "severity-warning",
                  incident.severity === "info" && "severity-info",
                )}>
                  {incident.severity.toUpperCase()}
                </span>
                <span className="text-[10px] text-gray-500 font-mono">{incident.service}</span>
              </div>
              <p className="text-sm text-gray-200 font-medium truncate">{incident.title}</p>
              <p className="text-[11px] text-gray-500 mt-0.5">{formatRelativeTime(incident.timestamp)}</p>
            </div>
            
            <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
              {onEngageAgent && (
                <button
                  onClick={() => onEngageAgent(incident.incident_id)}
                  className="px-3 py-1.5 text-[10px] font-medium bg-indigo-600 hover:bg-indigo-500 text-white rounded-md transition-colors"
                >
                  Engage Agent
                </button>
              )}
              <button className="text-gray-600 hover:text-indigo-400 transition-colors p-1">
                <ExternalLink className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
