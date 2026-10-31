import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import type { Team } from "../types";
import { TeamMark } from "./ui";

export function SortableRanks({
  teams,
  onChange,
  disabled,
  extra,
}: {
  teams: Team[];
  onChange: (teams: Team[]) => void;
  disabled?: boolean;
  extra?: (team: Team) => React.ReactNode;
}) {
  const [activeId, setActiveId] = useState<number | null>(null);
  const [overId, setOverId] = useState<number | null>(null);
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 120, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );
  const active = teams.find((team) => team.id === activeId) ?? null;

  function move(from: number, to: number) {
    if (disabled || to < 0 || to >= teams.length) return;
    onChange(arrayMove(teams, from, to));
  }

  function onDragEnd(event: DragEndEvent) {
    setActiveId(null);
    setOverId(null);
    const { active: dragged, over } = event;
    if (!over || dragged.id === over.id) return;
    const from = teams.findIndex((team) => team.id === dragged.id);
    const to = teams.findIndex((team) => team.id === over.id);
    if (from >= 0 && to >= 0) move(from, to);
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={(event: DragStartEvent) => setActiveId(Number(event.active.id))}
      onDragOver={(event) => setOverId(event.over ? Number(event.over.id) : null)}
      onDragEnd={onDragEnd}
      onDragCancel={() => { setActiveId(null); setOverId(null); }}
    >
      <SortableContext items={teams.map((team) => team.id)} strategy={verticalListSortingStrategy}>
        <ol className="rank-list">
          {teams.map((team, index) => (
            <SortableRow
              key={team.id}
              team={team}
              rank={index + 1}
              disabled={disabled}
              over={overId === team.id && activeId !== team.id}
              onUp={() => move(index, index - 1)}
              onDown={() => move(index, index + 1)}
              onRemove={() => onChange(teams.filter((item) => item.id !== team.id))}
              extra={extra?.(team)}
            />
          ))}
        </ol>
      </SortableContext>
      <DragOverlay>
        {active ? (
          <div className="rank-row drag-card" style={{ "--team": active.primary_color } as React.CSSProperties}>
            <TeamMark team={active} />
            <strong>{active.name}</strong>
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

function SortableRow({
  team,
  rank,
  disabled,
  over,
  onUp,
  onDown,
  onRemove,
  extra,
}: {
  team: Team;
  rank: number;
  disabled?: boolean;
  over: boolean;
  onUp: () => void;
  onDown: () => void;
  onRemove: () => void;
  extra?: React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: team.id, disabled });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.45 : 1,
    "--team": team.primary_color,
  } as React.CSSProperties;
  return (
    <li ref={setNodeRef} style={style} className={over ? "rank-row is-over" : "rank-row"}>
      <button className="handle" type="button" aria-label={`Drag ${team.name}`} {...attributes} {...listeners} disabled={disabled}>
        ::
      </button>
      <strong>{rank}</strong>
      <span className="rank-identity" title={`${team.name} ${team.mascot}`}>
        <TeamMark team={team} />
        <span className="team-line">
          <strong>{team.name}</strong>
          <span className="muted"> {team.mascot}</span>
        </span>
      </span>
      <span className="row row-actions">
        {extra}
        <button className="btn" type="button" onClick={onUp} disabled={disabled} aria-label="Move up">Up</button>
        <button className="btn" type="button" onClick={onDown} disabled={disabled} aria-label="Move down">Down</button>
        <button className="btn" type="button" onClick={onRemove} disabled={disabled}>Remove</button>
      </span>
    </li>
  );
}
