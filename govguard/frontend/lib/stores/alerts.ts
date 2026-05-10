"use client";
import { create } from "zustand";

export interface Alert {
  id: string;
  type: "ALERT" | "KPI_UPDATE" | "COMPLIANCE_CHANGE" | "FRAUD_FLAG";
  severity: "critical" | "warning" | "info";
  payload: Record<string, unknown>;
  ts: string;
  read: boolean;
}

interface AlertStore {
  alerts: Alert[];
  unreadCount: number;
  addAlert: (alert: Omit<Alert, "read">) => void;
  markRead: (id: string) => void;
  markAllRead: () => void;
}

export const useAlertStore = create<AlertStore>((set, get) => ({
  alerts: [],
  unreadCount: 0,
  addAlert: (alert) => {
    set((state) => ({
      alerts: [{ ...alert, read: false }, ...state.alerts].slice(0, 100),
      unreadCount: state.unreadCount + 1,
    }));
  },
  markRead: (id) =>
    set((state) => ({
      alerts: state.alerts.map((a) => (a.id === id ? { ...a, read: true } : a)),
      unreadCount: Math.max(0, state.unreadCount - 1),
    })),
  markAllRead: () =>
    set((state) => ({
      alerts: state.alerts.map((a) => ({ ...a, read: true })),
      unreadCount: 0,
    })),
}));
