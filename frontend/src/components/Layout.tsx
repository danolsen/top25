import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth, useThemeMode } from "../auth";
import { Modal } from "./ui";
import { DISCLAIMER, sportLabel } from "../format";
import { pathForSport, useSport } from "../sport";
import type { Sport, Theme } from "../types";

function ThemeIcon({ theme }: { theme: Theme }) {
  if (theme === "light") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
    );
  }
  if (theme === "dark") {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M21 14.5A8.5 8.5 0 1 1 9.5 3 7 7 0 0 0 21 14.5z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </svg>
  );
}

const themeOrder: Theme[] = ["system", "light", "dark"];

function storedTheme(): Theme {
  const stored = localStorage.getItem("top25-theme");
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "system";
}

function nextTheme(current: Theme): Theme {
  const index = themeOrder.indexOf(current);
  return themeOrder[(index + 1) % themeOrder.length];
}

const links = [
  ["/home", "Home"],
  ["/rankings", "Rankings"],
  ["/standings", "Standings"],
  ["/leagues", "Leagues"],
  ["/schools", "Schools"],
  ["/rules", "Scoring"],
];

export function Layout() {
  const { user, setUser, logout } = useAuth();
  const { sport, pinned, setSport, pinSport, leaveGuard } = useSport();
  const shown = pinned ?? sport;
  const navigate = useNavigate();
  const location = useLocation();
  const [theme, setTheme] = useState<Theme>(storedTheme);
  const [pendingSport, setPendingSport] = useState<Sport | null>(null);
  const [leaveWarning, setLeaveWarning] = useState("");
  const [switching, setSwitching] = useState(false);
  useThemeMode(theme);
  useEffect(() => {
    if (!user?.theme) return;
    localStorage.setItem("top25-theme", user.theme);
    setTheme(user.theme);
  }, [user?.theme]);

  async function chooseTheme(next: Theme) {
    localStorage.setItem("top25-theme", next);
    setTheme(next);
    if (user?.display_name_set) {
      setUser(await api("/api/me", { method: "PATCH", body: JSON.stringify({ theme: next }) }));
    }
  }

  async function goToSport(next: Sport) {
    setPendingSport(null);
    setSport(next);
    pinSport(null);
    setSwitching(true);
    try {
      const target = await pathForSport(location.pathname, next);
      if (target && target !== location.pathname) navigate(target);
    } catch {
      navigate("/home");
    } finally {
      setSwitching(false);
    }
  }

  function chooseSport(next: Sport) {
    if (next === shown || switching) return;
    const warning = leaveGuard();
    if (warning) {
      setLeaveWarning(warning);
      setPendingSport(next);
      return;
    }
    void goToSport(next);
  }

  return (
    <div className="shell">
      <header className="site-header">
        <div className="topbar">
          <div className="topbar-start">
            <NavLink to="/" className="brand">Top 25</NavLink>
            <div className="sport-switch" role="group" aria-label="Sport">
              {(["mens_basketball", "mens_football"] as const).map((item) => (
                <button key={item} className={item === shown ? "on" : ""} type="button" aria-pressed={item === shown} disabled={switching} onClick={() => chooseSport(item)}>
                  {sportLabel(item)}
                </button>
              ))}
            </div>
          </div>
          <div className="topbar-end">
            <button className="theme-toggle" type="button" aria-label={`${theme} color mode`} onClick={() => void chooseTheme(nextTheme(theme))}>
              <ThemeIcon theme={theme} />
            </button>
            {user ? (
              <>
                <NavLink className="header-link profile-link" to="/profile">{user.display_name}</NavLink>
                <button className="header-link" type="button" onClick={() => void logout().then(() => navigate("/"))}>Log out</button>
              </>
            ) : (
              <NavLink className="btn" to="/login">Log in</NavLink>
            )}
          </div>
          {user?.display_name_set && (
            <nav className="nav">
              {links.map(([to, label]) => (
                <NavLink key={to} to={to}>{label}</NavLink>
              ))}
              {user.role !== "user" && <span className="nav-split" />}
              {user.role !== "user" && <NavLink to="/admin/seasons">Weeks</NavLink>}
              {user.role === "super_admin" && <NavLink to="/admin/teams">Teams</NavLink>}
              {user.role === "super_admin" && <NavLink to="/admin/users">Players</NavLink>}
            </nav>
          )}
        </div>
      </header>
      <main className="page">
        <Outlet />
      </main>
      {pendingSport && (
        <Modal title={`Switch to ${sportLabel(pendingSport)}?`} confirmLabel="Switch sports" onConfirm={() => void goToSport(pendingSport)} onClose={() => setPendingSport(null)}>
          <p>{leaveWarning}</p>
        </Modal>
      )}
      <footer className="site-footer">
        <div className="footer">{DISCLAIMER} <NavLink to="/disclaimer">Details</NavLink></div>
      </footer>
    </div>
  );
}
