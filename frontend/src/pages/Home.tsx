import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { SeasonSelect, useSeasons } from "../components/ui";
import { ordinal, sportLabel, when } from "../format";
import { useSport } from "../sport";
import type { HistoryRow, Standing, Week } from "../types";

export function Home() {
  const { user } = useAuth();
  const { sport } = useSport();
  const { seasons, seasonId, setSeasonId, season } = useSeasons(sport);
  const [weeks, setWeeks] = useState<Week[]>([]);
  const [standings, setStandings] = useState<Standing[]>([]);
  const [history, setHistory] = useState<HistoryRow[]>([]);

  useEffect(() => {
    if (!seasonId) return;
    api<Week[]>(`/api/seasons/${seasonId}/weeks`).then(setWeeks).catch(() => setWeeks([]));
    api<Standing[]>(`/api/standings/global?season_id=${seasonId}`).then(setStandings).catch(() => setStandings([]));
    api<HistoryRow[]>(`/api/standings/me/history?season_id=${seasonId}`).then(setHistory).catch(() => setHistory([]));
  }, [seasonId]);

  const current = weeks[weeks.length - 1];
  const mine = standings.find((row) => row.user_id === user?.id);
  const latest = history[history.length - 1];

  return (
    <section className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <p className="muted">{sportLabel(sport)}</p>
          <h1 style={{ margin: 0 }}>{season?.name ?? "No season yet"}</h1>
        </div>
        <SeasonSelect seasons={seasons} seasonId={seasonId} onChange={setSeasonId} />
      </div>
      {current ? (
        <div className="panel stack">
          <h2>Week {current.number}</h2>
          <p>Deadline {when(current.deadline_at)} · {current.status}</p>
          <div className="row">
            {current.status === "published" ? (
              <Link className="btn primary" to={`/weeks/${current.id}/results`}>See the poll</Link>
            ) : (
              <Link className="btn primary" to={`/weeks/${current.id}`}>Make picks</Link>
            )}
            <Link className="btn" to="/rankings">Current Top 25</Link>
            <Link className="btn" to="/standings">Standings</Link>
          </div>
        </div>
      ) : (
        <p className="muted">The next week has not been opened.</p>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <div className="panel">
          <h2>Your rank</h2>
          {mine ? (
            <p style={{ fontSize: "2rem", margin: 0 }}>{ordinal(mine.rank)} <span className="muted" style={{ fontSize: "1rem" }}>{mine.points} pts</span></p>
          ) : <p className="muted">Submit a ballot and wait for the poll to see a rank.</p>}
          {latest?.previous_rank && latest.rank && (
            <p className={latest.rank < latest.previous_rank ? "good" : latest.rank > latest.previous_rank ? "danger" : "muted"}>
              {latest.rank < latest.previous_rank ? "Up" : latest.rank > latest.previous_rank ? "Down" : "Steady"} from {ordinal(latest.previous_rank)}
            </p>
          )}
        </div>
        <div className="panel">
          <h2>Top of the board</h2>
          <ol>
            {standings.slice(0, 5).map((row) => (
              <li key={row.user_id}>{row.display_name} · {row.points}</li>
            ))}
          </ol>
          {!standings.length && <p className="muted">No scores yet.</p>}
        </div>
      </div>
    </section>
  );
}
