"use client";

import { useEffect, useRef, useState } from "react";
import { X, Send, Bot, User, Wrench, Loader2, ChevronDown } from "lucide-react";
import { cn, generateSessionId } from "@/lib/utils";
import { createAgentWebSocket, type AgentMessage } from "@/lib/websocket";
import { ToolCallCard } from "./ToolCallCard";
import { CONFIG } from "@/lib/config";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: Array<{ tool: string; input?: Record<string, unknown> }>;
  timestamp: Date;
  requiresApproval?: boolean;
  approvalPayload?: any;
  isError?: boolean;
}

interface AgentChatDrawerProps {
  open: boolean;
  onClose: () => void;
  incidentId?: string | null;
}

const QUICK_PROMPTS = [
  "What are the active critical incidents?",
  "Analyze the payments service error rate",
  "Find runbooks for auth failures",
  "Create a post-mortem for the latest incident",
];

export function AgentChatDrawer({ open, onClose, incidentId }: AgentChatDrawerProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [sessionId] = useState(() => generateSessionId());
  const [pendingApproval, setPendingApproval] = useState<{
    sessionId: string;
    action: Record<string, unknown>;
  } | null>(null);
  const wsRef = useRef<ReturnType<typeof createAgentWebSocket> | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  // Focus input when opened
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [open]);

  // If incidentId is provided, trigger triage via SSE
  useEffect(() => {
    if (open && incidentId) {
      triggerTriage(incidentId);
    }
  }, [open, incidentId]);

  const triggerTriage = async (id: string) => {
    setIsThinking(true);
    const assistantId = crypto.randomUUID();
    
    // Add initial assistant message
    setMessages(prev => [...prev, {
      id: assistantId,
      role: "assistant",
      content: "",
      timestamp: new Date()
    }]);

    try {
      const agentsUrl = process.env.NEXT_PUBLIC_AGENTS_WS_URL || "http://localhost:8081";
      const httpUrl = agentsUrl.replace("ws://", "http://").replace("wss://", "https://");
      
      const response = await fetch(`${httpUrl}/triage`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify({ incident_id: id, session_id: sessionId }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let toolCalls: Array<{ tool: string; input?: Record<string, unknown> }> = [];

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));
              
              if (event.type === "text") {
                setMessages(prev => prev.map(m => 
                  m.id === assistantId ? { ...m, content: m.content + event.content } : m
                ));
              } else if (event.type === "tool_call") {
                toolCalls = [...toolCalls, { tool: event.tool, input: event.input }];
                setMessages(prev => prev.map(m => 
                  m.id === assistantId ? { ...m, toolCalls: [...toolCalls] } : m
                ));
              } else if (event.type === "done") {
                setIsThinking(false);
              }
            } catch (e) {
              console.error("Failed to parse SSE event", e);
            }
          }
        }
      }
    } catch (error) {
      console.error("Triage failed", error);
      setIsThinking(false);
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: "assistant",
        content: "⚠️ Failed to connect to agent service for triage.",
        timestamp: new Date()
      }]);
    }
  };

  const handleSend = async (overrideText?: string) => {
    const textToSend = overrideText || input;
    if (!textToSend.trim() || isThinking) return;
    const userMessage = textToSend.trim();
    if (!overrideText) setInput("");
    setMessages(prev => [...prev, {
      id: crypto.randomUUID(),
      role: "user",
      content: userMessage,
      timestamp: new Date()
    }]);
    setIsThinking(true);

    try {
      const response = await fetch(`${CONFIG.AGENTS_URL}/triage`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "text/event-stream",
        },
        body: JSON.stringify({
          incident_id: incidentId || "general",
          user_query: userMessage,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(`Agent returned ${response.status}: ${await response.text()}`);
      }

      const contentType = response.headers.get("content-type") || "";

      if (contentType.includes("text/event-stream")) {
        const reader = response.body!.getReader();
        const decoder = new TextDecoder();
        let agentMessage = "";
        let currentAssistantId = crypto.randomUUID();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          for (const line of chunk.split("\n")) {
            if (!line.startsWith("data: ")) continue;
            try {
              const event = JSON.parse(line.slice(6));
              if (event.type === "text") {
                agentMessage += event.content;
                setMessages(prev => {
                  const msgs = [...prev];
                  const lastMsg = msgs[msgs.length - 1];
                  if (lastMsg && lastMsg.role === "assistant" && lastMsg.id === currentAssistantId) {
                    msgs[msgs.length - 1] = {
                      ...lastMsg,
                      content: agentMessage,
                    };
                  } else {
                    msgs.push({
                      id: currentAssistantId,
                      role: "assistant",
                      content: agentMessage,
                      timestamp: new Date(),
                    });
                  }
                  return msgs;
                });
              } else if (event.type === "tool_call") {
                setMessages(prev => {
                  const msgs = [...prev];
                  const lastMsg = msgs[msgs.length - 1];
                  const toolCall = { tool: event.tool, input: event.input };
                  if (lastMsg && lastMsg.role === "assistant" && lastMsg.id === currentAssistantId) {
                    msgs[msgs.length - 1] = {
                      ...lastMsg,
                      toolCalls: [...(lastMsg.toolCalls || []), toolCall],
                    };
                  } else {
                    msgs.push({
                      id: currentAssistantId,
                      role: "assistant",
                      content: "",
                      toolCalls: [toolCall],
                      timestamp: new Date(),
                    });
                  }
                  return msgs;
                });
              } else if (event.type === "done") {
                break;
              } else if (event.type === "awaiting_approval") {
                setMessages(prev => [...prev, {
                  id: crypto.randomUUID(),
                  role: "assistant",
                  content: event.action?.description || "Approval required before continuing.",
                  timestamp: new Date(),
                  requiresApproval: true,
                  approvalPayload: event,
                }]);
              }
            } catch { /* skip malformed lines */ }
          }
        }
      } else {
        const data = await response.json();
        setMessages(prev => [...prev, {
          id: crypto.randomUUID(),
          role: "assistant",
          content: data.summary || data.message || JSON.stringify(data),
          timestamp: new Date(),
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Error: ${err instanceof Error ? err.message : "Could not reach agent service. Check deployment."}`,
        timestamp: new Date(),
        isError: true,
      }]);
    } finally {
      setIsThinking(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend();
  };

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
          onClick={onClose}
        />
      )}

      <div
        className={cn(
          "fixed right-0 top-0 h-full w-full sm:w-[420px] z-50 flex flex-col",
          "glass border-l border-white/8 shadow-2xl",
          "transition-transform duration-300 ease-in-out",
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center">
              <Bot className="w-4 h-4 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">OperaIQ AI</h2>
              <p className="text-[10px] text-gray-500">Powered by Gemini 2.0 Flash</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-md hover:bg-white/8 flex items-center justify-center text-gray-500 hover:text-gray-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="space-y-4">
              <div className="text-center pt-6">
                <div className="w-12 h-12 rounded-2xl bg-indigo-500/15 border border-indigo-500/25 flex items-center justify-center mx-auto mb-3">
                  <Bot className="w-6 h-6 text-indigo-400" />
                </div>
                <p className="text-sm font-medium text-gray-200">OperaIQ Production AI</p>
                <p className="text-xs text-gray-500 mt-1">
                  I can triage incidents, run rollbacks, and generate post-mortems.
                </p>
              </div>

              {/* Quick prompts */}
              <div className="space-y-2">
                <p className="text-[10px] text-gray-600 uppercase tracking-wider px-1">Try asking</p>
                {QUICK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => handleSend(prompt)}
                      className="w-full text-left px-3 py-2.5 rounded-lg text-xs text-gray-400 hover:text-indigo-300 hover:bg-indigo-500/5 border border-white/4 hover:border-indigo-500/20 transition-all"
                    >
                      {prompt}
                    </button>
                  ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "message-enter",
                msg.role === "user" ? "flex justify-end" : "flex justify-start"
              )}
            >
              {msg.role === "assistant" && (
                <div className="w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center flex-shrink-0 mr-2 mt-0.5">
                  <Bot className="w-3 h-3 text-indigo-400" />
                </div>
              )}

              <div className={cn("max-w-[85%] space-y-2")}>
                {/* Tool calls */}
                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div className="space-y-1">
                    {msg.toolCalls.map((tc, i) => (
                      <ToolCallCard
                        key={i}
                        toolName={tc.tool}
                        input={tc.input}
                        status="success"
                      />
                    ))}
                  </div>
                )}

                {/* Message content */}
                {msg.content && (
                  <div
                    className={cn(
                      "px-3.5 py-2.5 rounded-xl text-sm leading-relaxed",
                      msg.role === "user"
                        ? "bg-indigo-600/25 border border-indigo-500/25 text-gray-100 rounded-tr-sm"
                        : "glass border border-white/6 text-gray-200 rounded-tl-sm"
                    )}
                  >
                    <pre className="whitespace-pre-wrap font-sans">{msg.content}</pre>
                  </div>
                )}

                <p className="text-[10px] text-gray-600 px-1">
                  {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>

              {msg.role === "user" && (
                <div className="w-6 h-6 rounded-full bg-gray-600 flex items-center justify-center flex-shrink-0 ml-2 mt-0.5">
                  <User className="w-3 h-3 text-gray-300" />
                </div>
              )}
            </div>
          ))}

          {/* Thinking indicator */}
          {isThinking && (
            <div className="flex items-start gap-2 message-enter">
              <div className="w-6 h-6 rounded-full bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center flex-shrink-0">
                <Bot className="w-3 h-3 text-indigo-400" />
              </div>
              <div className="px-3.5 py-3 rounded-xl rounded-tl-sm glass border border-white/6">
                <div className="thinking-dots flex gap-1 items-center">
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                  <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
                </div>
              </div>
            </div>
          )}

          {/* Human-in-the-loop approval card */}
          {pendingApproval && (
            <div className="mx-2 p-3 rounded-xl border border-amber-500/40 bg-amber-500/10 space-y-2">
              <p className="text-xs font-semibold text-amber-400">⚠️ Action Required — Operator Approval</p>
              <pre className="text-[10px] text-gray-300 whitespace-pre-wrap">
                {JSON.stringify(pendingApproval.action, null, 2)}
              </pre>
              <div className="flex gap-2">
                <button
                  onClick={async () => {
                    const agentsUrl =
                      process.env.NEXT_PUBLIC_AGENTS_WS_URL?.replace(/^ws/, "http") ??
                      "http://localhost:8081";
                    await fetch(`${agentsUrl}/remediate/approve`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ session_id: pendingApproval.sessionId, approved: true }),
                    });
                    setPendingApproval(null);
                  }}
                  className="flex-1 py-1.5 rounded-lg bg-green-600 hover:bg-green-500 text-white text-xs font-medium transition-colors"
                >
                  ✓ Approve
                </button>
                <button
                  onClick={async () => {
                    const agentsUrl =
                      process.env.NEXT_PUBLIC_AGENTS_WS_URL?.replace(/^ws/, "http") ??
                      "http://localhost:8081";
                    await fetch(`${agentsUrl}/remediate/deny`, {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ session_id: pendingApproval.sessionId, approved: false }),
                    });
                    setPendingApproval(null);
                  }}
                  className="flex-1 py-1.5 rounded-lg bg-red-700 hover:bg-red-600 text-white text-xs font-medium transition-colors"
                >
                  ✗ Deny
                </button>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="px-4 pb-4 pt-2 border-t border-white/5">
          <form onSubmit={handleSubmit} className="relative">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about incidents, metrics, runbooks..."
              className="w-full px-4 py-3 pr-12 rounded-xl bg-white/5 border border-white/8 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-indigo-500/40 focus:ring-1 focus:ring-indigo-500/20 transition-all"
              disabled={isThinking}
            />
            <button
              type="submit"
              disabled={!input.trim() || isThinking}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center transition-all"
            >
              {isThinking ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin text-white" />
              ) : (
                <Send className="w-3.5 h-3.5 text-white" />
              )}
            </button>
          </form>
          <p className="text-[10px] text-gray-600 mt-2 text-center">
            AI may make mistakes. Always verify before triggering rollbacks.
          </p>
        </div>
      </div>
    </>
  );
}
