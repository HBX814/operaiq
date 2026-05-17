import React from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, type TooltipProps } from "recharts";
import { Activity } from "lucide-react";
import type { MetricPoint } from "@/lib/api";

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload?.length) {
    return (
      <div className="glass border border-white/10 rounded-lg px-3 py-2 text-xs">
        <p className="text-gray-400">{new Date(label).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</p>
        <p className="text-indigo-300 font-semibold">{payload[0].value.toFixed(2)}%</p>
      </div>
    );
  }
  return null;
};

interface MetricsChartProps {
  data: MetricPoint[];
  title: string;
}

export function MetricsChart({ data, title }: MetricsChartProps) {
  return (
    <div className="glass rounded-xl border p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Activity className="w-4 h-4 text-indigo-400" />
          {title}
        </h3>
        <span className="text-xs font-mono text-red-400">
          {data.length > 0 ? `${data[data.length - 1].value.toFixed(2)}%` : "0.00%"}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={120}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="errorGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="timestamp" hide />
          <YAxis hide domain={["auto", "auto"]} />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke="#6366f1"
            strokeWidth={2}
            fill="url(#errorGrad)"
          />
        </AreaChart>
      </ResponsiveContainer>
      <p className="text-[10px] text-gray-600 mt-2">Last 2 hours · 5-min intervals</p>
    </div>
  );
}
