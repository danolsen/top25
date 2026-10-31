import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { SortableRanks } from "../components/SortableRanks";
import { Modal, TeamMark } from "../components/ui";
import { sportLabel, when } from "../format";
import { usePinnedSport, useSportLeaveGuard } from "../sport";
import type { Ballot as BallotView, Team } from "../types";

export function Ballot() {
  const { weekId } = useParams();
  const [ballot, setBallot] = useState<BallotView | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [picks, setPicks] = useState<Team[]>([]);
  const [query, setQuery] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!weekId) return;
    let cancel = false;
    setBallot(null);
    setPicks([]);
    setError("");
    api<BallotView>(`/api/weeks/${weekId}/ballot`).then((view) => {
      if (cancel) return;
      setBallot(view);
      setPicks(view.picks.map((pick) => pick.team));
      return api<Team[]>(`/api/teams?sport=${view.week.sport}`);
    }).then((rows) => { if (!cancel && rows) setTeams(rows); }).catch((reason: Error) => { if (!cancel) setError(reason.message); });
    return () => { cancel = true; };
  }, [weekId]);

  usePinnedSport(ballot?.week.sport ?? null);
  useSportLeaveGuard(() => {
    if (!ballot) return null;
    const saved = ballot.picks.map((pick) => pick.team.id).join(",");
    const current = picks.map((team) => team.id).join(",");
    return saved === current ? null : "Picks you have not saved will be lost.";
  });

  if (!ballot) return <p className="muted">{error || "Loading ballot…"}</p>;
  const chosen = new Set(picks.map((team) => team.id));
  const available = teams.filter((team) => !chosen.has(team.id) && team.name.toLowerCase().includes(query.toLowerCase()));

  async function persist() {
    const next = await api<BallotView>(`/api/weeks/${weekId}/ballot`, {
      method: "PUT",
      body: JSON.stringify({ picks: picks.map((team, index) => ({ team_id: team.id, rank: index + 1 })) }),
    });
    setBallot(next);
    return next;
  }

  async function save() {
    setBusy(true);
    setError("");
    try {
      await persist();
      setMessage("Saved. These picks will not count until you submit them.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    setConfirming(false);
    setBusy(true);
    setError("");
    try {
      await persist();
      const next = await api<BallotView>(`/api/weeks/${weekId}/ballot/submit`, { method: "POST" });
      setBallot(next);
      setMessage("Submitted. These picks are locked.");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not submit");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="stack">
      <div>
        <p className="muted">{sportLabel(ballot.week.sport)} · {ballot.week.season_name}</p>
        <h1 style={{ margin: 0 }}>Week {ballot.week.number}</h1>
        <p>Deadline {when(ballot.week.deadline_at)}</p>
      </div>
      {ballot.status !== "submitted" && (
        <div className="banner danger">These picks will not be used until you submit them. Save if you are still moving teams around.</div>
      )}
      {ballot.locked_reason && <div className="banner">{ballot.locked_reason}</div>}
      {error && <p className="danger">{error}</p>}
      {message && <p className={ballot.status === "submitted" ? "good" : "danger"}>{message}</p>}
      <div className="ballot-layout grid gap-4 lg:grid-cols-[1.4fr_0.8fr]">
        <div className="order-2 lg:order-1">
          <SortableRanks teams={picks} onChange={setPicks} disabled={!ballot.editable} />
          {!picks.length && <p className="muted">Add teams from the list.</p>}
        </div>
        <div className="panel stack team-picker order-1 lg:order-2">
          <label className="field">Add a team
            <input className="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search schools" />
          </label>
          <div className="stack team-results" style={{ maxHeight: 480, overflowX: "hidden", overflowY: "auto" }}>
            {available.slice(0, 30).map((team) => (
              <button
                key={team.id}
                className="btn"
                type="button"
                disabled={!ballot.editable || picks.length >= 25}
                onClick={() => setPicks([...picks, team])}
                style={{ justifyContent: "flex-start", display: "flex", gap: "0.5rem", borderLeft: `6px solid ${team.primary_color}` }}
              >
                <TeamMark team={team} />
                <span className="team-line">{team.name}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="action-bar">
        <button className="btn" type="button" disabled={!ballot.editable || busy} onClick={() => void save()}>Save</button>
        <button className="btn primary" type="button" disabled={!ballot.editable || picks.length !== 25 || busy} onClick={() => setConfirming(true)}>Submit</button>
        {picks.length !== 25 && ballot.editable && <span className="muted">Add {25 - picks.length} more before you can submit.</span>}
        {ballot.status === "submitted" && <Link to={`/weeks/${ballot.week.id}/results`}>View results</Link>}
      </div>
      {confirming && (
        <Modal title="Submit these picks?" confirmLabel="Submit picks" onConfirm={() => void submit()} onClose={() => setConfirming(false)}>
          <p>You will not be able to change your picks after you submit. Save instead if you are not ready.</p>
        </Modal>
      )}
    </section>
  );
}
