import type { components } from "./api-types";

type Schemas = components["schemas"];
type Matches<T extends U, U> = T;

export type Sport = "mens_football" | "mens_basketball";
export type Theme = "light" | "dark" | "system";
export type Role = "user" | "admin" | "super_admin";

export type User = {
  id: number;
  email: string;
  role: Role;
  display_name: string;
  display_name_set: boolean;
  theme: Theme;
  has_password: boolean;
  google_connected: boolean;
};

export type Team = {
  id: number;
  sport: Sport;
  active: boolean;
  school_id: number;
  name: string;
  abbreviation: string;
  mascot: string;
  primary_color: string;
  secondary_color: string;
  logo_url: string | null;
  logo_file_url: string | null;
};

export type Season = { id: number; sport: Sport; name: string; status: "upcoming" | "active" | "archived" };

export type Week = {
  id: number;
  season_id: number;
  season_name: string;
  season_status: string;
  sport: Sport;
  number: number;
  deadline_at: string;
  status: "open" | "locked" | "published";
  scores_stale: boolean;
};

export type Pick = { team: Team; rank: number };

export type Ballot = {
  week: Week;
  status: "none" | "draft" | "submitted";
  submitted_at: string | null;
  editable: boolean;
  locked_reason: string | null;
  picks: Pick[];
};

export type PollEntry = {
  team: Team;
  placement: "ranked" | "also_receiving";
  rank: number | null;
  votes: number;
  first_place_votes: number;
  user_rank: number | null;
  points: number | null;
};

export type Poll = {
  week: Week;
  published: boolean;
  source: "draft" | "previous" | "empty" | "current";
  entries: PollEntry[];
  scores_stale: boolean;
};

export type Score = {
  total_points: number;
  proximity_points: number;
  bubble_points: number;
  exact_count: number;
  distance_sum: number;
  breakdown: {
    proximity: { team_id: number; official_rank: number; user_rank: number | null; distance: number | null; points: number }[];
    bubble: { team_id: number; user_rank: number; points: number }[];
    ignored: { team_id: number; user_rank: number; points: number; reason: string }[];
  };
};

export type Results = { week: Week; entries: PollEntry[]; score: Score | null };

export type Standing = {
  rank: number;
  user_id: number;
  display_name: string;
  points: number;
  last_week_points: number;
  exact_count: number;
  tiebreak: string | null;
};

export type HistoryRow = {
  week_id: number;
  week_number: number;
  week_points: number | null;
  cumulative_points: number;
  rank: number | null;
  previous_rank: number | null;
};

export type Member = { user_id: number; display_name: string; kicked: boolean; is_owner: boolean };

export type League = {
  id: number;
  season_id: number;
  season_name: string;
  sport: Sport;
  kind: "private" | "school";
  name: string;
  owner_id: number | null;
  team_id: number | null;
  join_code: string | null;
  is_owner: boolean;
  kicked: boolean;
  members: Member[] | null;
};

export type SchoolLeague = { team: Team; league_id: number | null; joined: boolean };

export type AdminUser = {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  display_name_set: boolean;
};

export type Audit = {
  id: number;
  actor_id: number;
  actor_name: string;
  action: string;
  week_id: number | null;
  payload: Record<string, unknown>;
  created_at: string;
};

export type SchoolImport = {
  created: number;
  updated: number;
};

export type School = {
  id: number;
  name: string;
  abbreviation: string;
  mascot: string;
  primary_color: string;
  secondary_color: string;
  logo_url: string | null;
  logo_file_url: string | null;
  teams: (Team & { on_published_poll: boolean; on_ballot: boolean })[];
};

export type SchemaCheck = [
  Matches<User, Schemas["UserOut"]>,
  Matches<Team, Schemas["TeamOut"]>,
  Matches<Season, Schemas["SeasonOut"]>,
  Matches<Week, Schemas["WeekOut"]>,
  Matches<Pick, Schemas["PickOut"]>,
  Matches<Ballot, Schemas["BallotOut"]>,
  Matches<PollEntry, Schemas["EntryOut"]>,
  Matches<Poll, Schemas["PollOut"]>,
  Matches<Score, Schemas["ScoreOut"]>,
  Matches<Results, Schemas["ResultsOut"]>,
  Matches<Standing, Schemas["StandingOut"]>,
  Matches<HistoryRow, Schemas["HistoryOut"]>,
  Matches<Member, Schemas["MemberOut"]>,
  Matches<League, Schemas["LeagueOut"]>,
  Matches<SchoolLeague, Schemas["SchoolLeagueOut"]>,
  Matches<AdminUser, Schemas["AdminUserOut"]>,
  Matches<Audit, Schemas["AuditOut"]>,
  Matches<School, Schemas["SchoolOut"]>,
  Matches<SchoolImport, Schemas["SchoolImportOut"]>,
];
