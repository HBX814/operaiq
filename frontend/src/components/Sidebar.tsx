"use client";

import { LayoutDashboard, AlertTriangle, FileText, MessageSquare, Settings, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Page } from "@/app/dashboard/page";

const navItems = [
  { id: "dashboard" as Page, label: "Operations Board", icon: LayoutDashboard },
  { id: "incidents" as Page, label: "Incident Explorer", icon: AlertTriangle },
  { id: "postmortems" as Page, label: "Post-Mortems", icon: FileText },
];

interface SidebarProps {
  activePage: Page;
  onNavigate: (page: Page) => void;
  onOpenChat: () => void;
}

export function Sidebar({ activePage, onNavigate, onOpenChat }: SidebarProps) {
  return (
    <aside className="w-60 flex-shrink-0 flex flex-col h-full glass border-r border-white/5">
      {/* Logo */}
      <div className="p-5 border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
            <Activity className="w-4 h-4 text-indigo-400" />
          </div>
          <div>
            <span className="font-semibold text-white text-sm">OperaIQ</span>
            <p className="text-[10px] text-gray-500 leading-none mt-0.5">Production Intelligence</p>
          </div>
        </div>
      </div>

      {/* Live status indicator */}
      <div className="mx-4 mt-4 mb-2 px-3 py-2 rounded-lg bg-green-500/5 border border-green-500/15 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 pulse-critical" />
        <span className="text-[11px] text-green-400 font-medium">Systems Operational</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2 space-y-1">
        {navItems.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => onNavigate(id)}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
              activePage === id
                ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/25"
                : "text-gray-400 hover:text-gray-200 hover:bg-white/5"
            )}
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            {label}
          </button>
        ))}
      </nav>

      {/* Chat button */}
      <div className="p-3 border-t border-white/5">
        <button
          onClick={onOpenChat}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/25 transition-all duration-200 group"
        >
          <MessageSquare className="w-4 h-4 group-hover:scale-110 transition-transform" />
          Ask OperaIQ AI
          <span className="ml-auto text-[10px] text-indigo-500 font-mono">⌘K</span>
        </button>
      </div>

      {/* Bottom user area */}
      <div className="p-3 pt-0">
        <button className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-gray-500 hover:text-gray-300 hover:bg-white/5 transition-all duration-200">
          <Settings className="w-4 h-4" />
          Settings
        </button>
        <div className="mt-3 px-3 py-2 rounded-lg flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-indigo-500 flex items-center justify-center text-[10px] font-bold text-white flex-shrink-0">
            HB
          </div>
          <div className="min-w-0">
            <p className="text-[11px] text-gray-300 font-medium truncate">Harsh Bhati</p>
            <p className="text-[10px] text-gray-600 truncate">operator</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
