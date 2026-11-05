import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { SortableRanks } from "../components/SortableRanks";
import { SeasonSelect, TeamMark, useSeasons } from "../components/ui";
import { officialRanks, shownRank, sportLabel, when } from "../format";
import { usePinnedSport, useSport, useSportLeaveGuard } from "../sport";
import type { AdminUser, Audit, Poll, School, SchoolImport, Season, Team, Week } from "../types";

type Slot = { team: Team; tied?: boolean };

function slotKey(slots: Slot[]) {
  return slots.map((slot) => `${slot.team.id}:${slot.tied ? "t" : ""}`).join(",");
}

function keepTies(previous: Slot[], teams: Team[]): Slot[] {
  return teams.map((team, index) => {
    const oldIndex = previous.findIndex((slot) => slot.team.id === team.id);
    const aboveId = index > 0 ? teams[index - 1].id : null;
    const oldAboveId = oldIndex > 0 ? previous[oldIndex - 1]?.team.id : null;
    const tied = oldIndex > 0 && Boolean(previous[oldIndex]?.tied) && aboveId === oldAboveId;
    return { team, tied };
  });
}

function localDateTime(value: string) {
  const date = new Date(value);
  const pad = (part: number) => String(part).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function AdminSeasons() {
  const { user } = useAuth();
  const { sport } = useSport();
  const { seasons, seasonId, setSeasonId, season, reload } = useSeasons(sport);
  const [weeks, setWeeks] = useState<Week[]>([]);
  const [name, setName] = useState("");
  const [deadline, setDeadline] = useState("");
  const [error, setError] = useState("");

  function loadWeeks(id: number) {
    api<Week[]>(`/api/seasons/${id}/weeks`).then(setWeeks).catch((reason: Error) => setError(reason.message));
  }
  useEffect(() => { if (seasonId) loadWeeks(seasonId); }, [seasonId]);

  async function createSeason(event: React.FormEvent) {
    event.preventDefault();
    try {
      const created = await api<Season>("/api/seasons", { method: "POST", body: JSON.stringify({ sport, name, status: "active" }) });
      setName("");
      setSeasonId(created.id);
      reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create the season");
    }
  }

  async function addWeek(event: React.FormEvent) {
    event.preventDefault();
    if (!seasonId) return;
    try {
      await api("/api/seasons/" + seasonId + "/weeks", { method: "POST", body: JSON.stringify({ deadline_at: new Date(deadline).toISOString() }) });
      setDeadline("");
      loadWeeks(seasonId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not open the week");
    }
  }

  async function setStatus(status: Season["status"]) {
    if (!season) return;
    try {
      await api(`/api/seasons/${season.id}`, { method: "PATCH", body: JSON.stringify({ status }) });
      window.location.reload();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update the season");
    }
  }

  return (
    <section className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>{sportLabel(sport)} weeks</h1>
        <SeasonSelect seasons={seasons} seasonId={seasonId} onChange={setSeasonId} />
      </div>
      {error && <p className="danger">{error}</p>}
      {user?.role === "super_admin" && (
        <form className="panel row controls" onSubmit={(event) => void createSeason(event)}>
          <label className="field" style={{ flex: 1 }}>New season<input value={name} onChange={(event) => setName(event.target.value)} required /></label>
          <button className="btn primary" type="submit">Create active season</button>
          {season && season.status !== "archived" && <button className="btn" type="button" onClick={() => void setStatus("archived")}>Archive</button>}
          {season && season.status !== "active" && <button className="btn" type="button" onClick={() => void setStatus("active")}>Make active</button>}
        </form>
      )}
      <form className="panel row controls" onSubmit={(event) => void addWeek(event)}>
        <label className="field" style={{ flex: 1 }}>Deadline<input type="datetime-local" value={deadline} onChange={(event) => setDeadline(event.target.value)} required /></label>
        <button className="btn primary" type="submit">Open week</button>
      </form>
      <div className="stack">
        {weeks.map((week) => (
          <div key={week.id} className="panel row" style={{ justifyContent: "space-between" }}>
            <div>
              <strong>Week {week.number}</strong>
              <div className="muted">{when(week.deadline_at)} · {week.status}{week.scores_stale ? " · scores need a rerun" : ""}</div>
            </div>
            <Link className="btn" to={`/admin/weeks/${week.id}`}>Enter poll</Link>
          </div>
        ))}
      </div>
    </section>
  );
}

export function AdminPublish() {
  const { user } = useAuth();
  const { weekId } = useParams();
  const [poll, setPoll] = useState<Poll | null>(null);
  const [ranked, setRanked] = useState<Slot[]>([]);
  const [also, setAlso] = useState<Slot[]>([]);
  const [pool, setPool] = useState<Team[]>([]);
  const [query, setQuery] = useState("");
  const [audit, setAudit] = useState<Audit[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [deadlineDraft, setDeadlineDraft] = useState("");
  const [baseline, setBaseline] = useState("");
  const [prefillNotice, setPrefillNotice] = useState(false);
  const superAdmin = user?.role === "super_admin";

  function remember(rankedSlots: Slot[], alsoSlots: Slot[]) {
    setRanked(rankedSlots);
    setAlso(alsoSlots);
    setBaseline(`${slotKey(rankedSlots)}|${slotKey(alsoSlots)}`);
  }

  useEffect(() => {
    if (!weekId) return;
    api<Poll>(`/api/weeks/${weekId}/prefill`).then((view) => {
      setPoll(view);
      setPrefillNotice(view.source === "previous");
      setDeadlineDraft(localDateTime(view.week.deadline_at));
      const rankedRows = view.entries.filter((entry) => entry.placement === "ranked");
      const alsoRows = view.entries.filter((entry) => entry.placement === "also_receiving");
      remember(
        rankedRows.map((entry, index) => ({
          team: entry.team,
          tied: index > 0 && entry.rank != null && entry.rank === rankedRows[index - 1].rank,
        })),
        alsoRows.map((entry) => ({ team: entry.team })),
      );
      return api<Team[]>(`/api/teams?sport=${view.week.sport}&include_inactive=true`);
    }).then((teams) => { if (teams) setPool(teams); }).catch((reason: Error) => setError(reason.message));
    if (superAdmin) api<Audit[]>(`/api/admin/audit?week_id=${weekId}`).then(setAudit).catch(() => setAudit([]));
  }, [weekId, superAdmin]);

  usePinnedSport(poll?.week.sport ?? null);
  useSportLeaveGuard(() => {
    if (!poll) return null;
    const sameLists = `${slotKey(ranked)}|${slotKey(also)}` === baseline;
    const sameDeadline = deadlineDraft === localDateTime(poll.week.deadline_at);
    return sameLists && sameDeadline ? null : "Changes you have not saved will be lost.";
  });

  function payload() {
    return {
      entries: [
        ...officialRanks(ranked.map((slot) => Boolean(slot.tied))).map((rank, index) => ({ team_id: ranked[index].team.id, placement: "ranked", rank, votes: 0, first_place_votes: 0 })),
        ...also.map((slot) => ({ team_id: slot.team.id, placement: "also_receiving", rank: null, votes: 0, first_place_votes: 0 })),
      ],
    };
  }

  async function send(path: "official" | "publish" | "rescore", method: "PUT" | "POST") {
    setError("");
    try {
      const body = path === "rescore" ? undefined : JSON.stringify(payload());
      const next = await api<Poll>(`/api/weeks/${weekId}/${path}`, { method, body });
      setPoll(next);
      setPrefillNotice(false);
      setBaseline(`${slotKey(ranked)}|${slotKey(also)}`);
      setMessage(path === "publish" ? "Published and scored." : path === "rescore" ? "Scores rerun." : "Saved.");
      if (superAdmin) setAudit(await api<Audit[]>(`/api/admin/audit?week_id=${weekId}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save the poll");
    }
  }

  useEffect(() => {
    if (poll) setDeadlineDraft(localDateTime(poll.week.deadline_at));
  }, [poll]);

  async function moveDeadline(value: string) {
    if (!poll) return;
    setError("");
    try {
      const week = await api<Week>(`/api/weeks/${weekId}`, { method: "PATCH", body: JSON.stringify({ deadline_at: new Date(value).toISOString() }) });
      setPoll({ ...poll, week });
      setDeadlineDraft(localDateTime(week.deadline_at));
      setMessage("Deadline updated.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update the deadline");
    }
  }

  if (!poll) return <p className="muted">{error || "Loading poll…"}</p>;
  const locked = poll.published && !superAdmin;
  const used = new Set([...ranked, ...also].map((slot) => slot.team.id));
  const available = pool.filter((team) => !used.has(team.id) && team.name.toLowerCase().includes(query.toLowerCase()));
  const deadlinePassed = new Date(poll.week.deadline_at).getTime() <= Date.now();

  return (
    <section className="stack">
      <div>
        <p className="muted">{sportLabel(poll.week.sport)} · {poll.week.season_name}</p>
        <h1 style={{ margin: 0 }}>Week {poll.week.number} poll</h1>
        <p>Deadline {when(poll.week.deadline_at)}</p>
      </div>
      {prefillNotice && <div className="banner">This top 25 was loaded from the previous week.</div>}
      {!poll.published && (
        <form className="panel row controls" onSubmit={(event) => { event.preventDefault(); void moveDeadline(deadlineDraft); }}>
          <label className="field" style={{ flex: 1 }}>Change deadline
            <input type="datetime-local" value={deadlineDraft} onChange={(event) => setDeadlineDraft(event.target.value)} required />
          </label>
          <button className="btn" type="submit">Update deadline</button>
          {superAdmin && <button className="btn" type="button" onClick={() => void moveDeadline(new Date(Date.now() - 60_000).toISOString())}>Close the week</button>}
        </form>
      )}
      {poll.scores_stale && <div className="banner">The published poll changed. Rerun scoring so the standings match.</div>}
      {error && <p className="danger">{error}</p>}
      {message && <p className="good">{message}</p>}
      <h2 className="section-title">Top 25</h2>
      <p className="muted">Tie gives a team the same rank as the one above it. A shared rank shows a T.</p>
      <div className={locked ? "stack" : "poll-layout"}>
        <div className="stack">
          <SortableRanks
            teams={ranked.map((slot) => slot.team)}
            disabled={locked}
            rankLabel={(_team, index) => {
              const ranks = officialRanks(ranked.map((slot) => Boolean(slot.tied)));
              return shownRank(ranks[index], ranks.filter((rank) => rank === ranks[index]).length > 1);
            }}
            onChange={(teams) => {
              setPrefillNotice(false);
              setRanked(keepTies(ranked, teams));
            }}
            extra={locked ? undefined : (team) => {
              const index = ranked.findIndex((slot) => slot.team.id === team.id);
              if (index <= 0) return null;
              const tied = Boolean(ranked[index]?.tied);
              return (
                <button
                  className="btn"
                  type="button"
                  aria-pressed={tied}
                  aria-label={tied ? `Untie ${team.name}` : `Tie ${team.name} with the team above`}
                  onClick={() => {
                    setPrefillNotice(false);
                    setRanked(ranked.map((slot, slotIndex) => (slotIndex === index ? { ...slot, tied: !slot.tied } : slot)));
                  }}
                >
                  {tied ? "Untie" : "Tie"}
                </button>
              );
            }}
          />
          {!ranked.length && <p className="muted">Add teams from the list.</p>}
        </div>
        {!locked && (
          <div className="panel stack team-picker">
            <label className="field">Add a team
              <input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search schools" />
            </label>
            <div className="stack team-results" style={{ maxHeight: 480, overflowX: "hidden", overflowY: "auto" }}>
              {available.slice(0, 30).map((team) => (
                <div key={team.id} className="team-result">
                  <button
                    className="btn"
                    type="button"
                    disabled={ranked.length >= 25}
                    onClick={() => { setPrefillNotice(false); setRanked([...ranked, { team }]); }}
                    style={{ justifyContent: "flex-start", display: "flex", gap: "0.5rem", borderLeft: `6px solid ${team.primary_color}` }}
                  >
                    <TeamMark team={team} />
                    <span className="team-line">{team.name}</span>
                  </button>
                  <button className="btn" type="button" onClick={() => { setPrefillNotice(false); setAlso([...also, { team }]); }} aria-label={`Add ${team.name} to also receiving`}>Also</button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      <h2 className="section-title">Also receiving</h2>
      <div className="stack">
        {also.map((slot) => (
          <div key={slot.team.id} className="rank-row also-row" style={{ "--team": slot.team.primary_color } as React.CSSProperties}>
            <TeamMark team={slot.team} />
            <strong className="team-line">{slot.team.name}</strong>
            {!locked && <button className="btn" type="button" onClick={() => { setPrefillNotice(false); setAlso(also.filter((item) => item.team.id !== slot.team.id)); }}>Remove</button>}
          </div>
        ))}
      </div>
      <div className="action-bar">
        {!poll.published && <button className="btn" type="button" onClick={() => void send("official", "PUT")}>Save draft</button>}
        {!poll.published && <button className="btn primary" type="button" disabled={!deadlinePassed || ranked.length !== 25} onClick={() => void send("publish", "POST")}>Publish</button>}
        {poll.published && superAdmin && <button className="btn" type="button" onClick={() => void send("official", "PUT")}>Save correction</button>}
        {poll.published && superAdmin && <button className="btn primary" type="button" onClick={() => void send("rescore", "POST")}>Rerun scoring</button>}
        {!deadlinePassed && !poll.published && <span className="muted">You can publish after the deadline.</span>}
      </div>
      {superAdmin && audit.length > 0 && (
        <div className="panel">
          <h2>Audit</h2>
          <ul>{audit.map((item) => <li key={item.id}>{when(item.created_at)} · {item.actor_name} · {item.action}</li>)}</ul>
        </div>
      )}
    </section>
  );
}

function importSummary(result: SchoolImport): string {
  if (result.created === 0 && result.updated === 0) {
    return "No changes. Those schools were already loaded.";
  }
  const parts: string[] = [];
  if (result.created) parts.push(result.created === 1 ? "Added 1 school." : `Added ${result.created} schools.`);
  if (result.updated) parts.push(result.updated === 1 ? "Updated 1 school." : `Updated ${result.updated} schools.`);
  return parts.join(" ");
}

export function AdminTeams() {
  const [schools, setSchools] = useState<School[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [importing, setImporting] = useState(false);
  const [form, setForm] = useState({ name: "", abbreviation: "", mascot: "", primary_color: "#003087", secondary_color: "#FFFFFF", logo_url: "", football: true, basketball: true });

  function load() {
    api<School[]>("/api/schools").then(setSchools).catch((reason: Error) => setError(reason.message));
  }
  useEffect(load, []);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    const sports = [form.football ? "mens_football" : "", form.basketball ? "mens_basketball" : ""].filter(Boolean);
    try {
      await api("/api/schools", {
        method: "POST",
        body: JSON.stringify({
          name: form.name,
          abbreviation: form.abbreviation,
          mascot: form.mascot,
          primary_color: form.primary_color,
          secondary_color: form.secondary_color,
          logo_url: form.logo_url || null,
          sports,
        }),
      });
      setForm({ ...form, name: "", abbreviation: "", mascot: "", logo_url: "" });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not add the school");
    }
  }

  async function saveSchool(school: School, sports: string[]) {
    try {
      await api(`/api/schools/${school.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: school.name,
          abbreviation: school.abbreviation,
          mascot: school.mascot,
          primary_color: school.primary_color,
          secondary_color: school.secondary_color,
          logo_url: school.logo_url ?? "",
          sports,
        }),
      });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save the school");
    }
  }

  async function importFile(file: File) {
    const body = new FormData();
    body.set("file", file);
    setImporting(true);
    setError("");
    setNotice("");
    try {
      const result = await api<SchoolImport>("/api/schools/import", { method: "POST", body });
      setNotice(importSummary(result));
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load the file");
    } finally {
      setImporting(false);
    }
  }

  async function upload(schoolId: number, file: File) {
    const body = new FormData();
    body.set("file", file);
    try {
      await api(`/api/schools/${schoolId}/logo`, { method: "POST", body });
      load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not upload the logo");
    }
  }

  return (
    <section className="stack">
      <h1>Teams</h1>
      <p>One school can play football, basketball, or both. The lists stay separate.</p>
      {error && <p className="danger">{error}</p>}
      {notice && <p className="good">{notice}</p>}
      <div className="panel stack">
        <p>Load several schools from a CSV file. Download the template and replace the example row. A row matches a school by name or abbreviation and updates that school instead of adding a second one. Football and basketball follow the yes or no in the file. Leave the logo URL blank to keep the current logo.</p>
        <div className="row">
          <a className="btn" href="/api/schools/import-template" download="teams-template.csv">Download template</a>
          <label className="btn primary">
            {importing ? "Loading…" : "Upload CSV"}
            <input
              type="file"
              accept=".csv,text/csv"
              hidden
              disabled={importing}
              onChange={(event) => {
                const file = event.target.files?.[0];
                event.target.value = "";
                if (file) void importFile(file);
              }}
            />
          </label>
        </div>
      </div>
      <form className="panel stack" onSubmit={(event) => void create(event)}>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="field">School<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>
          <label className="field">Abbreviation<input value={form.abbreviation} onChange={(event) => setForm({ ...form, abbreviation: event.target.value })} required /></label>
          <label className="field">Mascot<input value={form.mascot} onChange={(event) => setForm({ ...form, mascot: event.target.value })} required /></label>
          <label className="field">Logo URL<input value={form.logo_url} onChange={(event) => setForm({ ...form, logo_url: event.target.value })} /></label>
          <label className="field">Primary<input type="color" value={form.primary_color} onChange={(event) => setForm({ ...form, primary_color: event.target.value })} /></label>
          <label className="field">Secondary<input type="color" value={form.secondary_color} onChange={(event) => setForm({ ...form, secondary_color: event.target.value })} /></label>
        </div>
        <label><input type="checkbox" checked={form.football} onChange={(event) => setForm({ ...form, football: event.target.checked })} /> Football</label>
        <label><input type="checkbox" checked={form.basketball} onChange={(event) => setForm({ ...form, basketball: event.target.checked })} /> Basketball</label>
        <button className="btn primary" type="submit">Add school</button>
      </form>
      {schools.map((school) => (
        <SchoolEditor key={school.id} school={school} onSave={saveSchool} onUpload={upload} />
      ))}
    </section>
  );
}

function sportsFor(school: School) {
  return {
    football: school.teams.some((team) => team.sport === "mens_football" && team.active),
    basketball: school.teams.some((team) => team.sport === "mens_basketball" && team.active),
  };
}

function SchoolEditor({
  school,
  onSave,
  onUpload,
}: {
  school: School;
  onSave: (school: School, sports: string[]) => Promise<void>;
  onUpload: (schoolId: number, file: File) => Promise<void>;
}) {
  const [draft, setDraft] = useState(school);
  const [sports, setSports] = useState(() => sportsFor(school));
  useEffect(() => {
    setDraft(school);
    setSports(sportsFor(school));
  }, [school]);
  return (
    <form className="panel stack" onSubmit={(event) => { event.preventDefault(); const next = [sports.football ? "mens_football" : "", sports.basketball ? "mens_basketball" : ""].filter(Boolean); void onSave(draft, next); }}>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="field">School<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
        <label className="field">Abbreviation<input value={draft.abbreviation} onChange={(event) => setDraft({ ...draft, abbreviation: event.target.value })} /></label>
        <label className="field">Mascot<input value={draft.mascot} onChange={(event) => setDraft({ ...draft, mascot: event.target.value })} /></label>
        <label className="field">Logo URL<input value={draft.logo_url ?? ""} onChange={(event) => setDraft({ ...draft, logo_url: event.target.value })} /></label>
        <label className="field">Primary<input type="color" value={draft.primary_color} onChange={(event) => setDraft({ ...draft, primary_color: event.target.value })} /></label>
        <label className="field">Secondary<input type="color" value={draft.secondary_color} onChange={(event) => setDraft({ ...draft, secondary_color: event.target.value })} /></label>
      </div>
      <label><input type="checkbox" checked={sports.football} onChange={(event) => setSports({ ...sports, football: event.target.checked })} /> Football</label>
      <label><input type="checkbox" checked={sports.basketball} onChange={(event) => setSports({ ...sports, basketball: event.target.checked })} /> Basketball</label>
      <div className="row">
        <button className="btn" type="submit">Save</button>
        <label className="btn">Upload logo
          <input type="file" accept="image/png,image/jpeg,image/webp,image/gif" hidden onChange={(event) => { const file = event.target.files?.[0]; if (file) void onUpload(school.id, file); }} />
        </label>
        {draft.logo_file_url && <span className="muted">Uploaded backup ready</span>}
      </div>
    </form>
  );
}

export function AdminUsers() {
  const [query, setQuery] = useState("");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState("");
  function load(term: string) {
    api<AdminUser[]>(`/api/admin/users?q=${encodeURIComponent(term)}`).then(setUsers).catch((reason: Error) => setError(reason.message));
  }
  useEffect(() => { load(""); }, []);

  async function setRole(userId: number, role: "user" | "admin") {
    try {
      await api(`/api/admin/users/${userId}/role`, { method: "POST", body: JSON.stringify({ role }) });
      load(query);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not change the role");
    }
  }

  return (
    <section className="stack">
      <h1>Players</h1>
      {error && <p className="danger">{error}</p>}
      <form className="row" onSubmit={(event) => { event.preventDefault(); load(query); }}>
        <input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name or email" />
        <button className="btn" type="submit">Search</button>
      </form>
      <table className="table">
        <thead><tr><th>Name</th><th>Email</th><th>Role</th><th></th></tr></thead>
        <tbody>
          {users.map((person) => (
            <tr key={person.id}>
              <td>{person.display_name}</td>
              <td>{person.email}</td>
              <td>{person.role}</td>
              <td>
                {person.role !== "super_admin" && (
                  person.role === "admin"
                    ? <button className="btn" type="button" onClick={() => void setRole(person.id, "user")}>Remove admin</button>
                    : <button className="btn" type="button" onClick={() => void setRole(person.id, "admin")}>Make admin</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <a href="/api/docs">Open the API reference</a>
    </section>
  );
}
