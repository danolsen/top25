export const DISCLAIMER =
  "Independent fan game. Not affiliated with, endorsed by, or associated with the NCAA or The Associated Press. AP Top 25 is a trademark of its owner. We do not represent either organization.";

export function sportLabel(sport: string): string {
  return sport === "mens_football" ? "Football" : "Basketball";
}

export function ordinal(value: number): string {
  const teen = value % 100;
  if (teen >= 11 && teen <= 13) return `${value}th`;
  switch (value % 10) {
    case 1:
      return `${value}st`;
    case 2:
      return `${value}nd`;
    case 3:
      return `${value}rd`;
    default:
      return `${value}th`;
  }
}

export function officialRanks(tiedWithAbove: boolean[]): number[] {
  const ranks: number[] = [];
  tiedWithAbove.forEach((tied, index) => {
    ranks.push(index > 0 && tied ? ranks[index - 1] : index + 1);
  });
  return ranks;
}

export function shownRank(rank: number, tied: boolean): string {
  return tied ? `T${rank}` : String(rank);
}

export function when(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}
