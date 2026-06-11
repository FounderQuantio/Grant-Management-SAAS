"use client";
import { useEffect, useRef } from "react";
import { useAlertStore } from "@/lib/stores/alerts";
import { api } from "@/lib/api";

interface WSToken { ws_token: string; endpoint: string; expires_in: number; }

export function useAlertFeed() {
  const wsRef = useRef<WebSocket | null>(null);
  const addAlert = useAlertStore((s) => s.addAlert);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let retries = 0;
    const MAX_RETRIES = 3;

    async function connect() {
      if (retries >= MAX_RETRIES) return;
      try {
        const { ws_token, endpoint } = await api.get<WSToken>("/api/v1/dashboard/ws-token");
        const sep = endpoint.includes("?") ? "&" : "?";
        const ws = new WebSocket(`${endpoint}${sep}token=${ws_token}`);
        wsRef.current = ws;

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "PING") {
              ws.send(JSON.stringify({ type: "PONG" }));
            } else if (msg.type && msg.severity) {
              addAlert({ ...msg, id: crypto.randomUUID() });
            }
          } catch { /* ignore malformed messages */ }
        };

        ws.onopen = () => { retries = 0; };

        ws.onclose = () => {
          retries++;
          if (retries < MAX_RETRIES) {
            reconnectTimeout = setTimeout(connect, 15000 * retries);
          }
        };

        ws.onerror = () => { ws.close(); };
      } catch {
        retries++;
        if (retries < MAX_RETRIES) {
          reconnectTimeout = setTimeout(connect, 15000 * retries);
        }
      }
    }

    connect();
    return () => {
      clearTimeout(reconnectTimeout);
      if (pingIntervalRef.current) clearInterval(pingIntervalRef.current);
      wsRef.current?.close();
    };
  }, [addAlert]);
}
