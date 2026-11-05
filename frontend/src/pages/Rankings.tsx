import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { SeasonSelect, TeamMark, useSeasons } from "../components/ui";
import { shownRank, sportLabel } from "../format";
import { useSport } from "../sport";
import type { Ranking, Rankings as RankingsView } from "../types";

export function Rankings() {
  const { sport } = useSport();
  const { seasons, seasonId, setSeasonId, season } = useSeasons(sport);
  const [params, setParams] = useSearchParams();
  const weekParam = Number(params.get("week")) || null;
  const [data, setData] = useState<RankingsView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setError("");
  }, [seasonId]);

  useEffect(() => {
    if (!seasonId) return;
    let cancel = false;
    setError("");
    const query = weekParam ? `?week_id=${weekParam}` : "";
    api<RankingsView>(`/api/seasons/${seasonId}/rankings${query}`)
      .then((view) => {
        if (cancel) return;
        setData(view);
      })
      .catch((reason: Error) => {
        if (cancel) return;
        if (weekParam) {
          setParams({}, { replace: true });
          return;
        }
        setData(null);
        setError(reason.message);
      });
    return () => {
      cancel = true;
    };
  }, [seasonId, weekParam, setParams]);

  function chooseWeek(weekId: number) {
    const latest = data?.weeks[data.weeks.length - 1]?.id;
    setParams(weekId === latest ? {} : { week: String(weekId) }, { replace: true });
  }

  return (
    <section className="stack">
      <div className="row" style={{ justifyContent: "space-between", alignItems: "end" }}>
        <div>
          <p className="muted">{sportLabel(sport)}{season ? ` · ${season.name}` : ""}</p>
          <h1 style={{ margin: 0 }}>Top 25</h1>
        </div>
        <div className="row" style={{ alignItems: "end" }}>
          <SeasonSelect seasons={seasons} seasonId={seasonId} onChange={setSeasonId} />
          {data && data.weeks.length > 1 && (
            <label className="field">
              <span>Week</span>
              <select value={data.week.id} onChange={(event) => chooseWeek(Number(event.target.value))}>
                {data.weeks.map((week) => (
                  <option key={week.id} value={week.id}>
                    Week {week.number}{week.id === data.weeks[data.weeks.length - 1].id ? " · latest" : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </div>
      {!data && <p className="muted">{error || (seasonId ? "Loading rankings…" : "No season yet.")}</p>}
      {data && (
        <>
          <p className="muted">
            {data.previous_week_number == null
              ? `Week ${data.week.number} is the first published poll this season.`
              : `Week ${data.week.number}. Change is from week ${data.previous_week_number}.`}
          </p>
          <div className="panel">
            <table className="table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Team</th>
                  <th>Change</th>
                </tr>
              </thead>
              <tbody>
                {data.entries.map((entry) => {
                  const move = movement(entry, data.previous_week_number != null);
                  const tied = data.entries.filter((other) => other.rank === entry.rank).length > 1;
                  return (
                    <tr key={entry.team.id}>
                      <td className="rank-num">{entry.rank == null ? "—" : shownRank(entry.rank, tied)}</td>
                      <td><span className="row"><TeamMark team={entry.team} />{entry.team.name}</span></td>
                      <td className={`move ${move.tone}`}>{move.text}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!data.entries.length && <p className="muted">This poll has no ranked teams.</p>}
          </div>
          {data.dropped.length > 0 && (
            <div className="panel">
              <h2>Dropped out</h2>
              <ul className="plain-list">
                {data.dropped.map((entry) => (
                  <li key={entry.team.id}>
                    <span className="row">
                      <TeamMark team={entry.team} />
                      {entry.team.name}
                      <span className="muted">was {entry.previous_rank}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function movement(entry: Ranking, comparable: boolean): { text: string; tone: string } {
  if (!comparable || entry.rank == null) return { text: "—", tone: "muted" };
  if (entry.previous_rank == null) return { text: "New", tone: "" };
  if (entry.previous_rank === entry.rank) return { text: "Steady", tone: "muted" };
  if (entry.previous_rank > entry.rank) return { text: `Up ${entry.previous_rank - entry.rank}`, tone: "good" };
  return { text: `Down ${entry.rank - entry.previous_rank}`, tone: "danger" };
}
