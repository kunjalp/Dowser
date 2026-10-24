/**
 * Transparent weighted score from scoreParts (Master Plan section 5/6).
 * Weights are PLACEHOLDERS until tuned on Saturday. They are normalized, so
 * the slider values the frontend sends can be any non-negative numbers.
 */
export type ScoreParts = {
  confidence: number;
  undocumented: number;
  people: number;
  water: number;
  field: number;
};

export const DEFAULT_WEIGHTS: ScoreParts = {
  confidence: 0.2,
  undocumented: 0.2,
  people: 0.3,
  water: 0.1,
  field: 0.2,
};

const clamp01 = (x: number) => (Number.isFinite(x) ? Math.min(1, Math.max(0, x)) : 0);

export function weightedScore(parts: ScoreParts, weights: ScoreParts = DEFAULT_WEIGHTS): number {
  const keys = Object.keys(DEFAULT_WEIGHTS) as (keyof ScoreParts)[];
  let total = 0;
  let sum = 0;
  for (const k of keys) {
    const w = Math.max(0, weights[k]);
    total += w;
    sum += w * clamp01(parts[k]);
  }
  return total > 0 ? sum / total : 0;
}
