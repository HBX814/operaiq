"use client";

import { useState } from "react";
import { Sidebar } from "@/components/Sidebar";
import { DashboardPage } from "@/components/pages/DashboardPage";
import { IncidentExplorerPage } from "@/components/pages/IncidentExplorerPage";
import { PostMortemPage } from "@/components/pages/PostMortemPage";
import { AgentChatDrawer } from "@/components/AgentChatDrawer";

export type Page = "dashboard" | "incidents" | "postmortems";

export default function DashboardLayout() {
  const [activePage, setActivePage] = useState<Page>("dashboard");
  const [chatOpen, setChatOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeIncidentId, setActiveIncidentId] = useState<string | null>(null);

  const handleOpenChat = (incidentId?: string) => {
    setActiveIncidentId(incidentId || null);
    setChatOpen(true);
  };

  const renderPage = () => {
    switch (activePage) {
      case "dashboard":
        return <DashboardPage onOpenChat={handleOpenChat} />;
      case "incidents":
        return <IncidentExplorerPage onOpenChat={handleOpenChat} />;
      case "postmortems":
        return <PostMortemPage />;
    }
  };

  return (
    <div className="flex flex-col md:flex-row h-screen overflow-hidden bg-[#0a0a0f]">
      {/* Mobile header */}
      <div className="md:hidden flex items-center justify-between p-4 border-b border-white/5 bg-[#0a0a0f] z-20">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
            <span className="text-indigo-400 font-bold text-xs">OIQ</span>
          </div>
          <span className="font-semibold text-white">OperaIQ</span>
        </div>
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="text-gray-400 hover:text-white"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {mobileMenuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Sidebar - responsive behavior */}
      <div className={`md:block ${mobileMenuOpen ? 'block fixed inset-0 z-40 bg-[#0a0a0f]' : 'hidden'} md:relative md:w-60 flex-shrink-0 h-full`}>
        <Sidebar 
          activePage={activePage} 
          onNavigate={(page) => {
            setActivePage(page);
            setMobileMenuOpen(false);
          }} 
          onOpenChat={() => {
            handleOpenChat();
            setMobileMenuOpen(false);
          }} 
        />
      </div>

      <main className="flex-1 overflow-y-auto z-10 relative">
        {renderPage()}
      </main>
      <AgentChatDrawer 
        open={chatOpen} 
        onClose={() => setChatOpen(false)} 
        incidentId={activeIncidentId}
      />
    </div>
  );
}
