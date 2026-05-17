/**
 * useProductionFeed — React hook for live incident + deployment feed
 *
 * Connects to the agents service WebSocket and returns the most recent
 * events, auto-reconnecting on disconnect. Uses exponential backoff.
 *
 * Usage:
 *   const { incidents, deployments, connected } = useProductionFeed();
 */

"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { Incident, Deployment } from "./mcp-client";

// ---------------------------------------------------------------------------
// Types for feed events arriving from the WebSocket
// ---------------------------------------------------------------------------

export interface FeedEvent {
  event_type: "incident" | "deployment" | "metric";
  timestamp: string;
  [key: string]: unknown;
}

export interface ProductionFeedState {
  incidents: Incident[];
  deployments: Deployment[];
  rawEvents: FeedEvent[];
  connected: boolean;
  error: string | null;
  reconnectCount: number;
}

const WS_BASE =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_AGENTS_WS_URL ?? "ws://localhost:8081")
    : "ws://localhost:8081";

const MAX_INCIDENTS = 50;
const MAX_DEPLOYMENTS = 25;
const MAX_RAW_EVENTS = 100;
const MAX_RECONNECT_DELAY_MS = 30_000;

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useProductionFeed(): ProductionFeedState {
  const [state, setState] = useState<ProductionFeedState>({
    incidents: [],
    deployments: [],
    rawEvents: [],
    connected: false,
    error: null,
    reconnectCount: 0,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectCountRef = useRef(0);
  const unmountedRef = useRef(false);

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    const sessionId = `feed-${Date.now()}`;
    const url = `${WS_BASE}/ws/${sessionId}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (unmountedRef.current) return;
        reconnectCountRef.current = 0;
        setState((prev) => ({ ...prev, connected: true, error: null, reconnectCount: 0 }));
        // Ask the agent service for the live feed
        ws.send(JSON.stringify({ message: "subscribe:live-feed" }));
      };

      ws.onmessage = (event) => {
        if (unmountedRef.current) return;
        try {
          const msg = JSON.parse(event.data as string) as Record<string, unknown>;

          // Handle feed events published by generator → pub/sub → agent push
          if (msg.type === "feed_event" && msg.data) {
            const feedEvent = msg.data as FeedEvent;
            setState((prev) => {
              const rawEvents = [feedEvent, ...prev.rawEvents].slice(0, MAX_RAW_EVENTS);

              if (feedEvent.event_type === "incident") {
                const inc = feedEvent as unknown as Incident;
                const incidents = [inc, ...prev.incidents.filter((i) => i.incident_id !== inc.incident_id)].slice(0, MAX_INCIDENTS);
                return { ...prev, incidents, rawEvents };
              }

              if (feedEvent.event_type === "deployment") {
                const dep = feedEvent as unknown as Deployment;
                const deployments = [dep, ...prev.deployments.filter((d) => d.deployment_id !== dep.deployment_id)].slice(0, MAX_DEPLOYMENTS);
                return { ...prev, deployments, rawEvents };
              }

              return { ...prev, rawEvents };
            });
          }
        } catch {
          // Non-fatal parse errors
        }
      };

      ws.onclose = () => {
        if (unmountedRef.current) return;
        setState((prev) => ({ ...prev, connected: false }));
        scheduleReconnect();
      };

      ws.onerror = () => {
        if (unmountedRef.current) return;
        setState((prev) => ({
          ...prev,
          connected: false,
          error: "WebSocket connection error",
        }));
      };
    } catch (err) {
      setState((prev) => ({
        ...prev,
        connected: false,
        error: String(err),
      }));
      scheduleReconnect();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function scheduleReconnect() {
    if (unmountedRef.current) return;
    reconnectCountRef.current += 1;
    const delay = Math.min(
      1_000 * 2 ** (reconnectCountRef.current - 1),
      MAX_RECONNECT_DELAY_MS
    );
    setState((prev) => ({
      ...prev,
      reconnectCount: reconnectCountRef.current,
      error: `Reconnecting in ${Math.round(delay / 1000)}s… (attempt ${reconnectCountRef.current})`,
    }));
    reconnectTimerRef.current = setTimeout(connect, delay);
  }

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return state;
}

// ---------------------------------------------------------------------------
// createAgentWebSocket — imperative factory for the chat drawer
// (re-exported here so consumers only need one import)
// ---------------------------------------------------------------------------

export interface AgentMessage {
  type: "thinking" | "tool_call" | "chunk" | "complete" | "error" | "awaiting_approval";
  content?: string;
  tool?: string;
  input?: Record<string, unknown>;
  result?: unknown;
  session_id?: string;
  message?: string;
  tool_calls?: Array<{ tool: string; input?: Record<string, unknown> }>;
  action?: Record<string, unknown>;
  summary?: string;
}

export function createAgentWebSocket(
  sessionId: string,
  onMessage: (msg: AgentMessage) => void,
  onClose?: () => void
): { send: (message: string) => void; close: () => void } {
  const url = `${WS_BASE}/ws/${sessionId}`;
  const ws = new WebSocket(url);

  ws.onmessage = (event) => {
    try {
      const msg: AgentMessage = JSON.parse(event.data as string);
      onMessage(msg);
    } catch {
      // ignore malformed frames
    }
  };

  ws.onclose = () => onClose?.();

  ws.onerror = () => {
    onMessage({ type: "error", message: "WebSocket connection failed" });
  };

  return {
    send: (message: string) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ message }));
      }
    },
    close: () => ws.close(),
  };
}
