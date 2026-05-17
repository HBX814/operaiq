"use client";

import { useState } from "react";
import { IncidentExplorerPage } from "@/components/pages/IncidentExplorerPage";
import { AgentChatDrawer } from "@/components/AgentChatDrawer";

export default function IncidentsPage() {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <>
      <IncidentExplorerPage onOpenChat={() => setChatOpen(true)} />
      <AgentChatDrawer open={chatOpen} onClose={() => setChatOpen(false)} />
    </>
  );
}
