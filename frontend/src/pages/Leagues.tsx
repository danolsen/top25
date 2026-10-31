import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { SeasonSelect, useSeasons } from "../components/ui";
import { ordinal, sportLabel } from "../format";
import { usePinnedSport, useSport, useSportLeaveGuard } from "../sport";
import type { HistoryRow, League, SchoolLeague, Standing } from "../types";
import { StandingTable } from "./Standings";

export function Leagues() {
  const { sport, setSport } = useSport();
  const { seasons, seasonId, setSeasonId } = useSeasons(sport);
  const [leagues, setLeagues] = useState<League[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  function load(id: number) {
    api<League[]>(`/api/leagues?season_id=${id}`).then(setLeagues).catch((reason: Error) => setError(reason.message));
  }
  useEffect(() => { if (seasonId) load(seasonId); }, [seasonId]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (!seasonId) return;
    try {
      const league = await api<League>("/api/leagues", { method: "POST", body: JSON.stringify({ season_id: seasonId, name }) });
      setName("");
      setSport(league.sport);
      load(seasonId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create the league");
    }
  }

  return (
    <section className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>{sportLabel(sport)} leagues</h1>
        <SeasonSelect seasons={seasons} seasonId={seasonId} onChange={setSeasonId} />
      </div>
      {error && <p className="danger">{error}</p>}
      <form className="panel row controls" onSubmit={(event) => void create(event)}>
        <label className="field" style={{ flex: 1 }}>New private league
          <input value={name} onChange={(event) => setName(event.target.value)} maxLength={40} required />
        </label>
        <button className="btn primary" type="submit">Create</button>
      </form>
      <div className="row">
        <Link className="btn" to="/join">Join with a code</Link>
        <Link className="btn" to="/schools">School leagues</Link>
      </div>
      <div className="stack">
        {leagues.map((league) => (
          <Link key={league.id} className="panel" to={`/leagues/${league.id}`}>
            <strong>{league.name}</strong>
            <div className="muted">{league.kind === "school" ? "School league" : "Private league"}{league.kicked ? " · removed" : ""}</div>
          </Link>
        ))}
        {!leagues.length && <p className="muted">You have not joined a league in this season.</p>}
      </div>
    </section>
  );
}

export function Join() {
  const { code: routeCode } = useParams();
  const navigate = useNavigate();
  const { setSport } = useSport();
  const [code, setCode] = useState(routeCode ?? "");
  const [error, setError] = useState("");
  useEffect(() => { if (routeCode) setCode(routeCode); }, [routeCode]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      const league = await api<League>("/api/leagues/join", { method: "POST", body: JSON.stringify({ code }) });
      setSport(league.sport);
      navigate(`/leagues/${league.id}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not join");
    }
  }

  return (
    <form className="panel stack" style={{ maxWidth: 460 }} onSubmit={(event) => void submit(event)}>
      <h1>Join a private league</h1>
      <p>Enter the code from the commissioner, or open the link they sent you.</p>
      {error && <p className="danger">{error}</p>}
      <label className="field">Join code<input value={code} onChange={(event) => setCode(event.target.value)} required /></label>
      <button className="btn primary" type="submit">Join league</button>
    </form>
  );
}

export function LeagueDetail() {
  const { leagueId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [league, setLeague] = useState<League | null>(null);
  const [standings, setStandings] = useState<Standing[]>([]);
  const [history, setHistory] = useState<HistoryRow[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function load() {
    if (!leagueId) return;
    api<League>(`/api/leagues/${leagueId}`).then((row) => { setLeague(row); setName(row.name); }).catch((reason: Error) => setError(reason.message));
    api<Standing[]>(`/api/leagues/${leagueId}/standings`).then(setStandings).catch(() => setStandings([]));
    api<HistoryRow[]>(`/api/leagues/${leagueId}/history`).then(setHistory).catch(() => setHistory([]));
  }
  useEffect(load, [leagueId]);
  usePinnedSport(league?.sport ?? null);
  useSportLeaveGuard(() => (league && name !== league.name ? "The new name has not been saved." : null));

  async function act(path: string, body?: unknown) {
    setError("");
    try {
      const next = await api<League>(`/api/leagues/${leagueId}/${path}`, { method: "POST", body: body ? JSON.stringify(body) : undefined });
      setLeague(next);
      setNotice("Saved.");
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update the league");
    }
  }

  if (!league) return <p className="muted">{error || "Loading league…"}</p>;
  const link = league.join_code ? `${window.location.origin}/join/${league.join_code}` : "";
  return (
    <section className="stack">
      <div>
        <p className="muted">{league.season_name} · {sportLabel(league.sport)}</p>
        <h1 style={{ margin: 0 }}>{league.name}</h1>
      </div>
      {league.kicked && <div className="banner">The commissioner has removed you from this league.</div>}
      {error && <p className="danger">{error}</p>}
      {notice && <p className="good">{notice}</p>}
      {league.is_owner && (
        <div className="panel stack">
          <h2>Commissioner</h2>
          <p>Share this link or the code. They are the same secret.</p>
          <p><strong>{league.join_code}</strong></p>
          <p className="muted">{link}</p>
          <div className="row">
            <button className="btn" type="button" onClick={() => void navigator.clipboard.writeText(link)}>Copy link</button>
            <button className="btn" type="button" onClick={() => void act("rotate-code")}>New code</button>
          </div>
          <form className="row" onSubmit={(event) => { event.preventDefault(); void api<League>(`/api/leagues/${league.id}`, { method: "PATCH", body: JSON.stringify({ name }) }).then(setLeague); }}>
            <label className="field" style={{ flex: 1 }}>Rename<input value={name} onChange={(event) => setName(event.target.value)} maxLength={40} required /></label>
            <button className="btn" type="submit">Rename</button>
          </form>
        </div>
      )}
      {!league.kicked && <StandingTable rows={standings} me={user?.id} />}
      {!league.kicked && history.length > 0 && (
        <div className="panel">
          <h2>Your rank in this league</h2>
          <ul>{history.map((row) => <li key={row.week_id}>Week {row.week_number}: {row.rank ? ordinal(row.rank) : "—"}</li>)}</ul>
        </div>
      )}
      {league.members && (
        <div className="panel stack">
          <h2>Players</h2>
          {league.members.map((member) => (
            <div key={member.user_id} className="row" style={{ justifyContent: "space-between" }}>
              <span>{member.display_name}{member.is_owner ? " · commissioner" : ""}{member.kicked ? " · removed" : ""}</span>
              {league.is_owner && member.user_id !== user?.id && (
                <span className="row">
                  {member.kicked ? (
                    <button className="btn" type="button" onClick={() => void act("restore", { user_id: member.user_id })}>Allow back</button>
                  ) : (
                    <>
                      <button className="btn danger" type="button" onClick={() => { if (window.confirm(`Remove ${member.display_name} from the league?`)) void act("kick", { user_id: member.user_id }); }}>Remove</button>
                      <button className="btn" type="button" onClick={() => { if (window.confirm(`Hand this league to ${member.display_name}? You stay in as a player.`)) void act("transfer", { user_id: member.user_id }); }}>Hand off</button>
                    </>
                  )}
                </span>
              )}
            </div>
          ))}
          {!league.is_owner && (
            <button className="btn" type="button" onClick={() => void api(`/api/leagues/${league.id}/leave`, { method: "POST" }).then(() => navigate("/leagues"))}>Leave league</button>
          )}
        </div>
      )}
    </section>
  );
}

export function SchoolLeagues() {
  const { sport } = useSport();
  const { seasons, seasonId, setSeasonId } = useSeasons(sport);
  const [rows, setRows] = useState<SchoolLeague[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  function load(id: number) {
    api<SchoolLeague[]>(`/api/school-leagues?season_id=${id}`).then(setRows).catch((reason: Error) => setError(reason.message));
  }
  useEffect(() => { if (seasonId) load(seasonId); }, [seasonId]);

  async function toggle(row: SchoolLeague) {
    if (!seasonId) return;
    try {
      if (row.joined && row.league_id) await api(`/api/school-leagues/${row.league_id}/leave`, { method: "POST" });
      else await api("/api/school-leagues/join", { method: "POST", body: JSON.stringify({ season_id: seasonId, team_id: row.team.id }) });
      load(seasonId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update membership");
    }
  }

  const shown = rows.filter((row) => row.team.name.toLowerCase().includes(query.toLowerCase()));
  return (
    <section className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>School leagues</h1>
        <SeasonSelect seasons={seasons} seasonId={seasonId} onChange={setSeasonId} />
      </div>
      <p>Join any school for this season. You can be in more than one.</p>
      {error && <p className="danger">{error}</p>}
      <input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search schools" />
      <div className="stack">
        {shown.map((row) => (
          <div key={row.team.id} className="panel row" style={{ justifyContent: "space-between", borderLeft: `6px solid ${row.team.primary_color}` }}>
            <span>{row.team.name} <span className="muted">{row.team.mascot}</span></span>
            <span className="row">
              {row.joined && row.league_id && <Link to={`/leagues/${row.league_id}`}>Standings</Link>}
              <button className="btn" type="button" onClick={() => void toggle(row)}>{row.joined ? "Leave" : "Join"}</button>
            </span>
          </div>
        ))}
      </div>
    </section>
  );
}
