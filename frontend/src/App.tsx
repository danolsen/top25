import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth";
import { Layout } from "./components/Layout";
import { AdminPublish, AdminSeasons, AdminTeams, AdminUsers } from "./pages/Admin";
import { Ballot } from "./pages/Ballot";
import { Home } from "./pages/Home";
import { Join, LeagueDetail, Leagues, SchoolLeagues } from "./pages/Leagues";
import { Profile } from "./pages/Profile";
import { Results } from "./pages/Results";
import { Rankings } from "./pages/Rankings";
import { History, Standings } from "./pages/Standings";
import { Disclaimer, Landing, Login, Magic, Register, Reset, Rules, Setup } from "./pages/public";

function RequireUser({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RequireName({ children }: { children: React.ReactNode }) {
  const { user, ready } = useAuth();
  if (!ready) return <p className="muted">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (!user.display_name_set) return <Navigate to="/setup" replace />;
  return children;
}

function RequireAdmin({ children, superOnly = false }: { children: React.ReactNode; superOnly?: boolean }) {
  const { user } = useAuth();
  const allowed = superOnly ? user?.role === "super_admin" : user?.role === "admin" || user?.role === "super_admin";
  if (!allowed) return <Navigate to="/home" replace />;
  return children;
}

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/magic" element={<Magic />} />
        <Route path="/reset" element={<Reset />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="/disclaimer" element={<Disclaimer />} />
        <Route path="/setup" element={<RequireUser><Setup /></RequireUser>} />
        <Route path="/home" element={<RequireName><Home /></RequireName>} />
        <Route path="/weeks/:weekId" element={<RequireName><Ballot /></RequireName>} />
        <Route path="/weeks/:weekId/results" element={<RequireName><Results /></RequireName>} />
        <Route path="/rankings" element={<RequireName><Rankings /></RequireName>} />
        <Route path="/standings" element={<RequireName><Standings /></RequireName>} />
        <Route path="/history" element={<RequireName><History /></RequireName>} />
        <Route path="/leagues" element={<RequireName><Leagues /></RequireName>} />
        <Route path="/leagues/:leagueId" element={<RequireName><LeagueDetail /></RequireName>} />
        <Route path="/join" element={<RequireName><Join /></RequireName>} />
        <Route path="/join/:code" element={<RequireName><Join /></RequireName>} />
        <Route path="/schools" element={<RequireName><SchoolLeagues /></RequireName>} />
        <Route path="/profile" element={<RequireName><Profile /></RequireName>} />
        <Route path="/admin/seasons" element={<RequireName><RequireAdmin><AdminSeasons /></RequireAdmin></RequireName>} />
        <Route path="/admin/weeks/:weekId" element={<RequireName><RequireAdmin><AdminPublish /></RequireAdmin></RequireName>} />
        <Route path="/admin/teams" element={<RequireName><RequireAdmin superOnly><AdminTeams /></RequireAdmin></RequireName>} />
        <Route path="/admin/users" element={<RequireName><RequireAdmin superOnly><AdminUsers /></RequireAdmin></RequireName>} />
      </Route>
    </Routes>
  );
}
