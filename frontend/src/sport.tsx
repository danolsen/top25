import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { Season, Sport, Week } from "./types";

type LeaveGuard = () => string | null;

type SportValue = {
  sport: Sport;
  pinned: Sport | null;
  setSport: (sport: Sport) => void;
  pinSport: (sport: Sport | null) => void;
  setLeaveGuard: (guard: LeaveGuard | null) => void;
  leaveGuard: () => string | null;
};

const SportContext = createContext<SportValue | null>(null);

function storedSport(): Sport {
  return localStorage.getItem("top25-sport") === "mens_football" ? "mens_football" : "mens_basketball";
}

export function SportProvider({ children }: { children: React.ReactNode }) {
  const [sport, setSportState] = useState<Sport>(storedSport);
  const [pinned, setPinned] = useState<Sport | null>(null);
  const leaveGuardRef = useRef<LeaveGuard | null>(null);

  const setSport = useCallback((next: Sport) => {
    localStorage.setItem("top25-sport", next);
    setSportState(next);
  }, []);

  const pinSport = useCallback((next: Sport | null) => {
    setPinned(next);
    if (next) {
      localStorage.setItem("top25-sport", next);
      setSportState(next);
    }
  }, []);

  const setLeaveGuard = useCallback((guard: LeaveGuard | null) => {
    leaveGuardRef.current = guard;
  }, []);

  const leaveGuard = useCallback(() => leaveGuardRef.current?.() ?? null, []);

  const value = useMemo<SportValue>(
    () => ({ sport, pinned, setSport, pinSport, setLeaveGuard, leaveGuard }),
    [sport, pinned, setSport, pinSport, setLeaveGuard, leaveGuard],
  );
  return <SportContext.Provider value={value}>{children}</SportContext.Provider>;
}

export function useSport(): SportValue {
  const value = useContext(SportContext);
  if (!value) throw new Error("Sport is unavailable");
  return value;
}

export function usePinnedSport(sport: Sport | null) {
  const { pinSport } = useSport();
  useEffect(() => {
    pinSport(sport);
    return () => pinSport(null);
  }, [sport, pinSport]);
}

export function useSportLeaveGuard(guard: LeaveGuard) {
  const { setLeaveGuard } = useSport();
  const guardRef = useRef(guard);
  guardRef.current = guard;
  useEffect(() => {
    setLeaveGuard(() => guardRef.current());
    return () => setLeaveGuard(null);
  }, [setLeaveGuard]);
}

export async function pathForSport(pathname: string, sport: Sport): Promise<string | null> {
  if (/^\/admin\/weeks\/\d+/.test(pathname)) return "/admin/seasons";
  if (/^\/leagues\/\d+/.test(pathname)) return "/leagues";
  const ranking = /^\/weeks\/\d+\/?$/.test(pathname);
  const poll = /^\/weeks\/\d+\/results\/?$/.test(pathname);
  if (!ranking && !poll) return null;
  const weeks = await weeksForSport(sport);
  if (poll) {
    const published = [...weeks].reverse().find((week) => week.status === "published");
    return published ? `/weeks/${published.id}/results` : "/home";
  }
  const latest = weeks[weeks.length - 1];
  if (!latest) return "/home";
  return latest.status === "published" ? `/weeks/${latest.id}/results` : `/weeks/${latest.id}`;
}

async function weeksForSport(sport: Sport): Promise<Week[]> {
  const seasons = await api<Season[]>(`/api/seasons?sport=${sport}`);
  const season = seasons.find((row) => row.status === "active") ?? seasons[0];
  if (!season) return [];
  return api<Week[]>(`/api/seasons/${season.id}/weeks`);
}
