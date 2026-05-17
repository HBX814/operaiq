"use client";

import { useState, useEffect } from "react";
import {
  AlertTriangle, CheckCircle, Rocket, Clock,
  RefreshCw, MessageSquare
} from "lucide-react";
import { cn, formatRelativeTime } from "@/lib/utils";
import type { Incident, MetricPoint, Deployment } from "@/lib/api";
import { KPICard } from "@/components/KPICard";
import { MetricsChart } from "@/components/MetricsChart";
import { IncidentFeed } from "@/components/IncidentFeed";

interface KpiStats {
  activeIncidents: number;
  deploymentsToday: number;
  errorRate: string;
  p99Latency: string;
}

interface DashboardPageProps {
  onOpenChat: (incidentId?: string) => void;
}

export function DashboardPage({ onOpenChat }: DashboardPageProps) {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [metrics, setMetrics] = useState<MetricPoint[]>([]);
  const [kpi, setKpi] = useState<KpiStats>({
    activeIncidents: 0,
    deploymentsToday: 0,
    errorRate: "0.00%",
    p99Latency: "0ms"
  });
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [refreshing, setRefreshing] = useState(false);

  const fetchIncidents = async () => {
    try {
      const res = await fetch("/api/incidents");
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) {
        setIncidents(data);
      }
    } catch (e) {
      console.error("Failed to fetch incidents", e);
    }
  };

  const fetchDeployments = async () => {
    try {
      const res = await fetch("/api/deployments");
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) {
        setDeployments(data);
      }
    } catch (e) {
      console.error("Failed to fetch deployments", e);
    }
  };

  const fetchMetrics = async () => {
    try {
      const res = await fetch("/api/metrics?service=payments&metric_type=error_rate");
      if (!res.ok) return;
      const data = await res.json();
      if (Array.isArray(data)) {
        setMetrics(data);
      }
    } catch (e) {
      console.error("Failed to fetch metrics", e);
    }
  };

  const fetchKPIs = async () => {
    try {
      const res = await fetch("/api/kpi");
      if (!res.ok) return;
      const data = await res.json();
      if (data && typeof data === 'object') {
        setKpi(data);
      }
    } catch (e) {
      console.error("Failed to fetch KPIs", e);
    }
  };

  const fetchAll = async () => {
    setRefreshing(true);
    try {
      await Promise.all([
        fetchIncidents(),
        fetchDeployments(),
        fetchMetrics(),
        fetchKPIs()
      ]);
      setLastRefresh(new Date());
    } catch (error) {
      console.error("Failed to fetch dashboard data:", error);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Live Operations Board</h1>
          <p className="text-xs text-gray-500 mt-1">
            Last updated {formatRelativeTime(lastRefresh.toISOString())}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchAll}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-gray-400 hover:text-gray-200 glass border hover:border-white/15 transition-all disabled:opacity-50"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", refreshing && "animate-spin")} />
            {refreshing ? "Refreshing..." : "Refresh"}
          </button>
          <button
            onClick={() => onOpenChat()}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-indigo-300 bg-indigo-600/20 border border-indigo-500/25 hover:bg-indigo-600/30 transition-all"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            Ask Trae AI
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <KPICard
          label="Critical Incidents"
          value={kpi.activeIncidents}
          subtext="Require immediate action"
          trend={kpi.activeIncidents > 0 ? "up" : "neutral"}
          color="bg-red-500/15 border border-red-500/20 text-red-400"
          icon={AlertTriangle}
        />
        <KPICard
          label="Error Rate — payments"
          value={kpi.errorRate}
          subtext="Last 2 hours"
          trend={parseFloat(kpi.errorRate) > 1 ? "up" : "neutral"}
          color="bg-amber-500/15 border border-amber-500/20 text-amber-400"
          icon={Clock}
        />
        <KPICard
          label="P99 Latency — payments"
          value={kpi.p99Latency}
          subtext="Last 2 hours"
          trend="neutral"
          color="bg-green-500/15 border border-green-500/20 text-green-400"
          icon={CheckCircle}
        />
        <KPICard
          label="Deployments (24h)"
          value={kpi.deploymentsToday}
          subtext="Across all services"
          trend="neutral"
          color="bg-indigo-500/15 border border-indigo-500/20 text-indigo-400"
          icon={Rocket}
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-5 gap-4">
        {/* Incident feed (3/5) */}
        <div className="col-span-3">
          <IncidentFeed 
            incidents={incidents} 
            onEngageAgent={(id) => onOpenChat(id)} 
          />
        </div>

        {/* Right column (2/5) */}
        <div className="col-span-2 space-y-4">
          <MetricsChart data={metrics} title="Error Rate — payments" />

          {/* Recent deployments */}
          <div className="glass rounded-xl border">
            <div className="px-4 py-3 border-b border-white/5">
              <h3 className="text-sm font-semibold text-white">Recent Deployments</h3>
            </div>
            <div className="p-4 space-y-3">
              {deployments.map((dep) => (
                <div key={dep.deployment_id} className="flex items-center gap-3">
                  <div className={cn(
                    "w-2 h-2 rounded-full flex-shrink-0",
                    dep.status === "success" ? "bg-green-400" : "bg-red-400"
                  )} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs text-gray-300 truncate">
                      <span className="font-mono text-gray-500">{dep.service}</span>
                      {" "}<span className="text-gray-400">{dep.version}</span>
                    </p>
                    <p className="text-[10px] text-gray-600">{formatRelativeTime(dep.timestamp)}</p>
                  </div>
                  <span className={cn(
                    "text-[10px] font-medium",
                    dep.status === "success" ? "text-green-400" : "text-red-400"
                  )}>
                    {dep.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
