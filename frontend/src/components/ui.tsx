import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Season, Sport, Team } from "../types";

export function TeamMark({ team }: { team: Team }) {
  const [src, setSrc] = useState(team.logo_url || team.logo_file_url || "");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setSrc(team.logo_url || team.logo_file_url || "");
    setFailed(false);
  }, [team.logo_url, team.logo_file_url]);

  if (!src || failed) {
    return (
      <span className="team-mark" style={{ background: team.primary_color, color: team.secondary_color }}>
        {team.abbreviation.slice(0, 4)}
      </span>
    );
  }
  return (
    <span className="team-mark" style={{ background: team.primary_color }}>
      <img
        src={src}
        alt=""
        onError={() => {
          if (team.logo_url && team.logo_file_url && src === team.logo_url) setSrc(team.logo_file_url);
          else setFailed(true);
        }}
      />
    </span>
  );
}

export function Modal({
  title,
  children,
  confirmLabel,
  cancelLabel = "Keep editing",
  onConfirm,
  onClose,
}: {
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <div className="modal-back" role="presentation" onClick={onClose}>
      <div className="panel modal stack" role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}>
        <h2>{title}</h2>
        <div>{children}</div>
        <div className="row">
          <button className="btn primary" type="button" onClick={onConfirm}>{confirmLabel}</button>
          <button className="btn" type="button" onClick={onClose}>{cancelLabel}</button>
        </div>
      </div>
    </div>
  );
}

export function useSeasons(sport: Sport) {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [seasonId, setSeasonId] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => setVersion((value) => value + 1), []);
  useEffect(() => {
    let cancel = false;
    api<Season[]>(`/api/seasons?sport=${sport}`)
      .then((rows) => {
        if (cancel) return;
        setSeasons(rows);
        setSeasonId((current) => current && rows.some((row) => row.id === current) ? current : (rows.find((row) => row.status === "active") ?? rows[0])?.id ?? null);
      })
      .catch((reason: Error) => setError(reason.message));
    return () => {
      cancel = true;
    };
  }, [sport, version]);
  return { seasons, seasonId, setSeasonId, reload, error, season: seasons.find((row) => row.id === seasonId) ?? null };
}

export function SeasonSelect({
  seasons,
  seasonId,
  onChange,
}: {
  seasons: Season[];
  seasonId: number | null;
  onChange: (id: number) => void;
}) {
  if (!seasons.length) return <p className="muted">No seasons for this sport yet.</p>;
  return (
    <label className="field">
      <span>Season</span>
      <select value={seasonId ?? ""} onChange={(event) => onChange(Number(event.target.value))}>
        {seasons.map((season) => (
          <option key={season.id} value={season.id}>{season.name} · {season.status}</option>
        ))}
      </select>
    </label>
  );
}
