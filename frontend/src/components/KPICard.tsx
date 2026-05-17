import React from "react";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";

export interface KpiCardProps {
  label: string;
  value: string | number;
  subtext: string;
  trend?: "up" | "down" | "neutral";
  color: string;
  icon: React.ElementType;
}

export function KPICard({ label, value, subtext, trend, color, icon: Icon }: KpiCardProps) {
  return (
    <div className="glass glass-hover rounded-xl p-5 border transition-all duration-200">
      <div className="flex items-start justify-between mb-4">
        <div className={cn("w-9 h-9 rounded-lg flex items-center justify-center", color)}>
          <Icon className="w-4 h-4" />
        </div>
        {trend && (
          <div className={cn("flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full",
            trend === "up" ? "text-red-400 bg-red-400/10" : trend === "down" ? "text-green-400 bg-green-400/10" : "text-gray-500 bg-gray-500/10"
          )}>
            {trend === "up" ? <TrendingUp className="w-3 h-3" /> : trend === "down" ? <TrendingDown className="w-3 h-3" /> : null}
            {trend === "up" ? "+24%" : trend === "down" ? "-8%" : "stable"}
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-white mb-1">{value}</div>
      <div className="text-xs text-gray-400">{label}</div>
      <div className="text-[10px] text-gray-600 mt-1">{subtext}</div>
    </div>
  );
}
