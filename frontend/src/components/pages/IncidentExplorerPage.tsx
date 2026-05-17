"use client";

import { useState, useEffect } from "react";
import { Search, Filter, ChevronRight, MessageSquare } from "lucide-react";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { Incident } from "@/lib/api";

const SEVERITY_FILTERS = ["all", "critical", "warning", "info"] as const;
const SERVICE_FILTERS = ["all", "payments", "auth", "inventory", "notifications", "search"] as const;

interface IncidentExplorerPageProps {
  onOpenChat?: (incidentId?: string) => void;
}

export function IncidentExplorerPage({ onOpenChat }: IncidentExplorerPageProps = {}) {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<(typeof SEVERITY_FILTERS)[number]>("all");
  const [serviceFilter, setServiceFilter] = useState<(typeof SERVICE_FILTERS)[number]>("all");
  const [selected, setSelected] = useState<Incident | null>(null);

  useEffect(() => {
    async function fetchIncidents() {
      try {
        const res = await fetch(`/api/incidents?severity=${severityFilter}`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            setIncidents(data);
          }
        }
      } catch (error) {
        console.error("Failed to fetch incidents:", error);
      }
    }
    fetchIncidents();
  }, [severityFilter]);

  const [runbooks, setRunbooks] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    async function searchRunbooks() {
      if (search.length < 3) {
        setRunbooks([]);
        return;
      }
      setSearching(true);
      try {
        const res = await fetch(`/api/runbooks?query=${encodeURIComponent(search)}`);
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data)) {
            setRunbooks(data);
          }
        }
      } catch (error) {
        console.error("Failed to search runbooks:", error);
      } finally {
        setSearching(false);
      }
    }
    const timer = setTimeout(searchRunbooks, 500);
    return () => clearTimeout(timer);
  }, [search]);

  const filtered = incidents.filter((inc) => {
    const matchSearch =
      !search ||
      inc.title.toLowerCase().includes(search.toLowerCase()) ||
      inc.service.toLowerCase().includes(search.toLowerCase());
    const matchService = serviceFilter === "all" || inc.service === serviceFilter;
    return matchSearch && matchService;
  });

  return (
    <div className="flex h-full">
      {/* List panel */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-white/5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-xl font-bold text-white">Incident Explorer</h1>
              <p className="text-xs text-gray-500 mt-1">{filtered.length} incidents matching filters</p>
            </div>
            {onOpenChat && (
              <button
                onClick={() => {
                  const firstIncident = incidents[0];
                  const id = firstIncident?.incident_id || "";
                  onOpenChat(id);
                }}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-indigo-300 bg-indigo-600/20 border border-indigo-500/25 hover:bg-indigo-600/30 transition-all"
              >
                <MessageSquare className="w-3.5 h-3.5" />
                Triage with AI
              </button>
            )}
          </div>

          {/* Search */}
          <div className="relative mb-3">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search incidents..."
              className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-white/5 border border-white/8 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/20"
            />
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2 flex-wrap">
            <Filter className="w-3.5 h-3.5 text-gray-500" />
            <div className="flex gap-1">
              {SEVERITY_FILTERS.map((f) => (
                <button
                  key={f}
                  onClick={() => setSeverityFilter(f)}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-[11px] font-medium capitalize transition-all",
                    severityFilter === f
                      ? "bg-indigo-600/25 text-indigo-300 border border-indigo-500/35"
                      : "text-gray-500 hover:text-gray-300 glass border"
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
            <div className="w-px h-4 bg-white/10" />
            <div className="flex gap-1 flex-wrap">
              {SERVICE_FILTERS.map((s) => (
                <button
                  key={s}
                  onClick={() => setServiceFilter(s)}
                  className={cn(
                    "px-2.5 py-1 rounded-md text-[11px] font-mono transition-all",
                    serviceFilter === s
                      ? "bg-indigo-600/25 text-indigo-300 border border-indigo-500/35"
                      : "text-gray-500 hover:text-gray-300 glass border"
                  )}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Incident list */}
        <div className="flex-1 overflow-y-auto">
          {filtered.map((incident) => (
            <div
              key={incident.incident_id}
              onClick={() => setSelected(incident)}
              className={cn(
                "px-6 py-4 border-b border-white/4 cursor-pointer transition-all",
                selected?.incident_id === incident.incident_id
                  ? "bg-indigo-600/10 border-l-2 border-l-indigo-500"
                  : "hover:bg-white/2"
              )}
            >
              <div className="flex items-start gap-3">
                <div className={cn(
                  "w-2 h-2 rounded-full mt-1.5 flex-shrink-0",
                  incident.severity === "critical" && "bg-red-400 pulse-critical",
                  incident.severity === "warning" && "bg-amber-400",
                  incident.severity === "info" && "bg-blue-400",
                )} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2">
                      <span className={cn(
                        "text-[10px] font-medium px-2 py-0.5 rounded-full border",
                        incident.severity === "critical" && "severity-critical",
                        incident.severity === "warning" && "severity-warning",
                        incident.severity === "info" && "severity-info",
                      )}>
                        {incident.severity.toUpperCase()}
                      </span>
                      <span className="text-[10px] text-gray-500 font-mono">{incident.service}</span>
                      <span className="text-[10px] text-gray-600">·</span>
                      <span className="text-[10px] text-gray-600">{formatRelativeTime(incident.timestamp)}</span>
                    </div>
                    {onOpenChat && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenChat(incident.incident_id);
                        }}
                        className="flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-medium text-indigo-300 bg-indigo-500/10 border border-indigo-500/20 hover:bg-indigo-500/20 transition-all"
                      >
                        <MessageSquare className="w-3 h-3" />
                        Engage Agent
                      </button>
                    )}
                  </div>
                  <p className="text-sm text-gray-200 font-medium truncate">{incident.title}</p>
                  <p className="text-[10px] text-gray-500 mt-0.5 font-mono">{incident.incident_id}</p>
                </div>
                <ChevronRight className="w-4 h-4 text-gray-600 flex-shrink-0 mt-0.5" />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Detail panel */}
      {selected && (
        <div className="w-[360px] flex-shrink-0 border-l border-white/5 overflow-y-auto">
          <div className="p-6 space-y-5">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className={cn(
                  "text-[10px] font-medium px-2 py-0.5 rounded-full border",
                  selected.severity === "critical" && "severity-critical",
                  selected.severity === "warning" && "severity-warning",
                  selected.severity === "info" && "severity-info",
                )}>
                  {selected.severity.toUpperCase()}
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full border border-white/10 text-gray-400">{selected.status}</span>
              </div>
              <h2 className="text-base font-bold text-white">{selected.title}</h2>
              <p className="text-xs text-gray-500 mt-1 font-mono">{selected.incident_id}</p>
            </div>

            <div className="space-y-3">
              {[
                { label: "Service", value: selected.service },
                { label: "Severity", value: selected.severity },
                { label: "Status", value: selected.status },
                { label: "Created", value: new Date(selected.timestamp).toLocaleString() },
                { label: "Triggered By", value: selected.triggered_by_deployment_id || "Unknown" },
              ].map(({ label, value }) => (
                <div key={label} className="flex items-start justify-between gap-4">
                  <span className="text-xs text-gray-500">{label}</span>
                  <span className="text-xs text-gray-200 font-mono text-right truncate">{value}</span>
                </div>
              ))}
            </div>

            <div className="space-y-2">
              <button
                onClick={() => onOpenChat?.(selected.incident_id)}
                className="w-full px-4 py-2.5 rounded-lg text-sm font-medium bg-indigo-600/25 hover:bg-indigo-600/35 text-indigo-300 border border-indigo-500/30 transition-all"
              >
                Triage with AI Agent
              </button>
              <button className="w-full px-4 py-2.5 rounded-lg text-sm font-medium glass border hover:border-white/15 text-gray-400 hover:text-gray-200 transition-all">
                Create Post-Mortem
              </button>
            </div>

            {/* Runbook Recommendations */}
            {runbooks.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Runbook Recommendations</h3>
                <div className="space-y-3">
                  {runbooks.map((rb, i) => (
                    <div key={i} className="p-3 rounded-lg bg-white/5 border border-white/8 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-mono text-indigo-400">{rb.id}</span>
                        <span className="text-[10px] text-gray-600">Score: {rb.score?.toFixed(2)}</span>
                      </div>
                      <p className="text-xs text-gray-300 font-medium">{rb.title}</p>
                      <p className="text-[11px] text-gray-500 line-clamp-3">{rb.content}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Placeholder timeline */}
            <div>
              <h3 className="text-xs font-semibold text-gray-400 mb-3 uppercase tracking-wider">Timeline</h3>
              <div className="space-y-3">
                {[
                  { time: "12 min ago", label: "Incident created", type: "incident" },
                  { time: "13 min ago", label: "Error rate spike detected (18.4%)", type: "metric" },
                  { time: "15 min ago", label: "Deployment v2.3.7 — FAILED", type: "deployment" },
                ].map((event, i) => (
                  <div key={i} className="flex gap-3">
                    <div className="flex flex-col items-center gap-1">
                      <div className={cn(
                        "w-2 h-2 rounded-full mt-0.5",
                        event.type === "incident" ? "bg-red-400" :
                        event.type === "metric" ? "bg-amber-400" : "bg-indigo-400"
                      )} />
                      {i < 2 && <div className="w-px flex-1 bg-white/8 min-h-[16px]" />}
                    </div>
                    <div className="pb-3">
                      <p className="text-xs text-gray-300">{event.label}</p>
                      <p className="text-[10px] text-gray-600 mt-0.5">{event.time}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
