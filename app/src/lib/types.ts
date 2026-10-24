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
  source?: "model" | "ground_truth";
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
  candidate: { label: "Candidate", color: "#f59e0b" },
  queued: { label: "Queued", color: "#38bdf8" },
  confirmed_leaking: { label: "Confirmed leaking", color: "#ef4444" },
  confirmed_not_leaking: { label: "Not leaking", color: "#22c55e" },
  no_well: { label: "No well", color: "#9ca3af" },
  mislocated: { label: "Mislocated", color: "#a78bfa" },
};

/** Candidate dots are colored by score along this ramp (low, mid, high). */
export const SCORE_RAMP = ["#fde047", "#f97316", "#c026d3"] as const;

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

/** What color a candidate shows in the list: score ramp while unresolved, status color after. */
export function dotColor(c: Pick<Candidate, "status" | "score">): string {
  return c.status === "candidate" ? scoreColor(c.score) : STATUS_META[c.status].color;
}

export const PART_LABELS: Record<keyof ScoreParts, string> = {
  confidence: "Map confidence",
  undocumented: "Not in records",
  people: "Near people",
  water: "Near water",
  field: "Field confirmation",
};
