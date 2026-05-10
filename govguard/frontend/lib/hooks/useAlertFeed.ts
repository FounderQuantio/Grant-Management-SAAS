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

    async function connect() {
      try {
        const { ws_token, endpoint } = await api.get<WSToken>("/api/v1/dashboard/ws-token");
        const ws = new WebSocket(`${endpoint}?token=${ws_token}`);
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

        ws.onclose = () => {
          reconnectTimeout = setTimeout(connect, 5000);
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        reconnectTimeout = setTimeout(connect, 10000);
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
