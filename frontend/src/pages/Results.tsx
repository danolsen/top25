import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { TeamMark } from "../components/ui";
import { shownRank, sportLabel } from "../format";
import { usePinnedSport } from "../sport";
import type { PollEntry, Results as ResultsView } from "../types";

export function Results() {
  const { weekId } = useParams();
  const [data, setData] = useState<ResultsView | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!weekId) return;
    let cancel = false;
    setData(null);
    setError("");
    api<ResultsView>(`/api/weeks/${weekId}/results`).then((view) => { if (!cancel) setData(view); }).catch((reason: Error) => { if (!cancel) setError(reason.message); });
    return () => { cancel = true; };
  }, [weekId]);
  usePinnedSport(data?.week.sport ?? null);
  if (!data) return <p className="muted">{error || "Loading results…"}</p>;
  const ranked = data.entries.filter((entry) => entry.placement === "ranked");
  const also = data.entries.filter((entry) => entry.placement === "also_receiving");
  return (
    <section className="stack">
      <div>
        <p className="muted">{sportLabel(data.week.sport)} · {data.week.season_name}</p>
        <h1 style={{ margin: 0 }}>Week {data.week.number} poll</h1>
        <p><Link to={`/rankings?week=${data.week.id}`}>Rankings and week-to-week change</Link></p>
        {data.score && (
          <p>{data.score.total_points} points · {data.score.proximity_points} proximity · {data.score.bubble_points} bubble · {data.score.exact_count} exact</p>
        )}
      </div>
      <EntryTable title="Top 25" entries={ranked} showRank />
      <EntryTable title="Also receiving" entries={also} showRank={false} />
    </section>
  );
}

function EntryTable({ title, entries, showRank }: { title: string; entries: PollEntry[]; showRank: boolean }) {
  return (
    <div className="panel">
      <h2>{title}</h2>
      <table className="table">
        <thead>
          <tr>
            {showRank && <th>Rank</th>}
            <th>Team</th>
            <th>Your rank</th>
            <th>Your points</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.team.id}>
              {showRank && <td>{entry.rank == null ? "—" : shownRank(entry.rank, entries.filter((other) => other.rank === entry.rank).length > 1)}</td>}
              <td>
                <span className="row"><TeamMark team={entry.team} />{entry.team.name}</span>
              </td>
              <td>{entry.user_rank ?? "—"}</td>
              <td>{entry.points ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
