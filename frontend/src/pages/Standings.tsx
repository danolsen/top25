import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import { SeasonSelect, useSeasons } from "../components/ui";
import { ordinal, sportLabel } from "../format";
import { useSport } from "../sport";
import type { HistoryRow, Standing } from "../types";

export function Standings() {
  const { user } = useAuth();
  const { sport } = useSport();
  const { seasons, seasonId, setSeasonId } = useSeasons(sport);
  const [rows, setRows] = useState<Standing[]>([]);
  useEffect(() => {
    if (!seasonId) return;
    api<Standing[]>(`/api/standings/global?season_id=${seasonId}`).then(setRows).catch(() => setRows([]));
  }, [seasonId]);
  return (
    <section className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>{sportLabel(sport)} standings</h1>
        <SeasonSelect seasons={seasons} seasonId={seasonId} onChange={setSeasonId} />
      </div>
      <StandingTable rows={rows} me={user?.id} />
      <Link to="/history">Your week-by-week rank</Link>
    </section>
  );
}

export function History() {
  const { sport } = useSport();
  const { seasons, seasonId, setSeasonId } = useSeasons(sport);
  const [rows, setRows] = useState<HistoryRow[]>([]);
  useEffect(() => {
    if (!seasonId) return;
    api<HistoryRow[]>(`/api/standings/me/history?season_id=${seasonId}`).then(setRows).catch(() => setRows([]));
  }, [seasonId]);
  const max = Math.max(250, ...rows.map((row) => row.week_points ?? 0));
  return (
    <section className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0 }}>Season trend</h1>
        <SeasonSelect seasons={seasons} seasonId={seasonId} onChange={setSeasonId} />
      </div>
      <div className="bars">
        {rows.map((row) => (
          <div key={row.week_id}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <span>Week {row.week_number}</span>
              <span>{row.rank ? ordinal(row.rank) : "—"} · {row.week_points ?? 0} pts</span>
            </div>
            <div className="bar"><span style={{ width: `${((row.week_points ?? 0) / max) * 100}%` }} /></div>
          </div>
        ))}
      </div>
      <table className="table">
        <thead><tr><th>Week</th><th>Rank</th><th>Move</th><th>Week</th><th>Total</th></tr></thead>
        <tbody>
          {rows.map((row) => {
            const move = row.rank && row.previous_rank ? row.previous_rank - row.rank : null;
            return (
              <tr key={row.week_id}>
                <td><Link to={`/weeks/${row.week_id}/results`}>{row.week_number}</Link></td>
                <td>{row.rank ? ordinal(row.rank) : "—"}</td>
                <td className={move === null ? "muted" : move > 0 ? "good" : move < 0 ? "danger" : "muted"}>
                  {move === null ? "—" : move > 0 ? `Up ${move}` : move < 0 ? `Down ${Math.abs(move)}` : "Steady"}
                </td>
                <td>{row.week_points ?? "—"}</td>
                <td>{row.cumulative_points}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

export function StandingTable({ rows, me }: { rows: Standing[]; me?: number }) {
  if (!rows.length) return <p className="muted">No scores in this season yet.</p>;
  return (
    <table className="table">
      <thead><tr><th>Rank</th><th>Player</th><th>Points</th><th>Last week</th><th>Exact</th></tr></thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.user_id} style={{ fontWeight: row.user_id === me ? 650 : 400 }}>
            <td>{row.rank}</td>
            <td>
              {row.display_name}
              {row.tiebreak && <div className="muted">Tiebreak: {row.tiebreak}</div>}
            </td>
            <td>{row.points}</td>
            <td>{row.last_week_points}</td>
            <td>{row.exact_count}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
