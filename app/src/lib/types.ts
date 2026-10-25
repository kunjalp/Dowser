/** Mirrors the Master Plan candidate record (section 5). Keep in sync with convex/schema.ts. */
export type Status =
  | "candidate"
  | "queued"
  | "confirmed_leaking"
  | "confirmed_not_leaking"
  | "no_well"
  | "mislocated";

export type ScoreParts = {
  confidence: number;
  undocumented: number;
  people: number;
  water: number;
  field: number;
};

export type Candidate = {
  _id: string;
  id: string;
  lat: number;
  lon: number;
  score: number;
  scoreParts: ScoreParts;
  editionsSeen: number[];
  nearestDocumentedId?: string;
  nearestDocumentedDistM?: number;
  distToHomeM?: number;
  distToSchoolM?: number;
  distToWaterM?: number;
  buildingsNear250m?: number;
  status: Status;
  brief?: string;
  evidenceImages: { year: number; url: string }[];
  quadName: string;
  detectionId?: string;
  source?: "model" | "ground_truth" | "calgem_idle";
  /** CalGEM record fields, idle lane only */
  wellStatus?: string;
  operator?: string;
  apiNumber?: string;
  /** added by candidates:ranked */
  rank: number;
  rankScore: number;
};

export type Reading = {
  _id: string;
  deviceId: string;
  value: number;
  raw: number;
  receivedAt: number;
  candidateId?: string;
  isReplay: boolean;
};

export const STATUSES: Status[] = [
  "candidate",
  "queued",
  "confirmed_leaking",
  "confirmed_not_leaking",
  "no_well",
  "mislocated",
];

/** Status colors (Master Plan: red for leaking, gray for no well, ...). */
export const STATUS_META: Record<Status, { label: string; color: string }> = {
  candidate: { label: "Candidate", color: "#8a507e" },
  queued: { label: "Queued", color: "#5933b2" },
  confirmed_leaking: { label: "Confirmed leaking", color: "#d12d2d" },
  confirmed_not_leaking: { label: "Not leaking", color: "#1a7f4b" },
  no_well: { label: "No well", color: "#575757" },
  mislocated: { label: "Mislocated", color: "#4a2a96" },
};

/** Candidate dots are colored by score along this single-hue ramp (low, mid, high). */
export const SCORE_RAMP = ["#9068c2", "#5933b2", "#4a2a96"] as const;

export function scoreColor(score: number): string {
  const t = Math.min(1, Math.max(0, score));
  const [a, b, c] = SCORE_RAMP;
  const lerp = (x: string, y: string, u: number) => {
    const p = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
    const [r1, g1, b1] = p(x);
    const [r2, g2, b2] = p(y);
    const m = (s: number, e: number) => Math.round(s + (e - s) * u);
    return `rgb(${m(r1, r2)},${m(g1, g2)},${m(b1, b2)})`;
  };
  return t < 0.5 ? lerp(a, b, t / 0.5) : lerp(b, c, (t - 0.5) / 0.5);
}

/**
 * Two separate lists. "undocumented" = map symbols with no state record (every source except
 * calgem_idle); "idle" = wells the state lists as Idle, near homes or schools.
 */
export type Lane = "undocumented" | "idle";
export const LANES: Lane[] = ["undocumented", "idle"];

export const IDLE_COLOR = "#2bb3a8";

export const LANE_META: Record<Lane, { tab: string; badge: string; color: string }> = {
  undocumented: { tab: "Not in state records", badge: "Not in state records", color: SCORE_RAMP[1] },
  idle: { tab: "Known to state: idle", badge: "In state records · Idle", color: IDLE_COLOR },
};

export const laneOf = (c: Pick<Candidate, "source">): Lane => (c.source === "calgem_idle" ? "idle" : "undocumented");

/** What color a candidate shows in the list: score ramp (teal for idle wells) while unresolved, status color after. */
export function dotColor(c: Pick<Candidate, "status" | "score" | "source">): string {
  if (c.status !== "candidate") return STATUS_META[c.status].color;
  return laneOf(c) === "idle" ? IDLE_COLOR : scoreColor(c.score);
}

export const PART_LABELS: Record<keyof ScoreParts, string> = {
  confidence: "Map confidence",
  undocumented: "Not in records",
  people: "Near people",
  water: "Near water",
  field: "Field confirmation",
};

const fmtDist = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`);

/** True for the seeded placeholder candidates (ids "fake-001"...). Real ones never start with "fake-". */
export const isFake = (c: Pick<Candidate, "id">) => c.id.startsWith("fake-");

/**
 * One plain-language line on why this candidate ranks where it does. Built only from fields
 * the record actually has; anything missing is skipped, never guessed.
 */
export function reasonLine(c: Candidate): string {
  const bits: string[] = [];
  // Idle wells ARE the state record, so the "no record nearby" fact never applies to them.
  if (c.nearestDocumentedDistM !== undefined && laneOf(c) !== "idle") {
    bits.push(
      c.nearestDocumentedDistM >= 100
        ? `No CalGEM record within ${fmtDist(c.nearestDocumentedDistM)}`
        : `CalGEM well ${fmtDist(c.nearestDocumentedDistM)} away`,
    );
  }
  if (c.distToHomeM !== undefined && c.distToHomeM <= 500) bits.push(`${fmtDist(c.distToHomeM)} from a home`);
  if (c.distToSchoolM !== undefined && c.distToSchoolM <= 1000) bits.push(`${fmtDist(c.distToSchoolM)} from a school`);
  if (c.distToWaterM !== undefined && c.distToWaterM <= 500) bits.push(`${fmtDist(c.distToWaterM)} from water`);
  if (c.editionsSeen.length > 1) bits.push(`on ${c.editionsSeen.length} map editions`);
  return bits.slice(0, 3).join(" · ");
}
