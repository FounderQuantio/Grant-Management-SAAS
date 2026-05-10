"use client";
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface UserSession {
  id: string;
  tenantId: string;
  role: string;
  displayName: string;
  emailHash: string;
}

interface SessionStore {
  user: UserSession | null;
  setUser: (user: UserSession) => void;
  clearUser: () => void;
  hasRole: (...roles: string[]) => boolean;
}

const ROLE_HIERARCHY: Record<string, number> = {
  system_admin: 7,
  agency_officer: 6,
  compliance_officer: 5,
  finance_manager: 4,
  finance_staff: 3,
  auditor: 2,
  equity_analyst: 1,
};

export const useSessionStore = create<SessionStore>()(
  persist(
    (set, get) => ({
      user: null,
      setUser: (user) => set({ user }),
      clearUser: () => set({ user: null }),
      hasRole: (...roles: string[]) => {
        const user = get().user;
        if (!user) return false;
        const userLevel = ROLE_HIERARCHY[user.role] || 0;
        const requiredLevel = Math.max(...roles.map((r) => ROLE_HIERARCHY[r] || 0));
        return userLevel >= requiredLevel;
      },
    }),
    { name: "govguard-session" }
  )
);
