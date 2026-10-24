/**
 * Pure helpers for the Claude brief generator: build the prompt from a candidate's real
 * fields, hash the inputs, and reject any output that adds facts we did not provide.
 */

export type BriefInput = {
  id: string;
  quadName: string;
  editionsSeen: number[];
  nearestDocumentedDistM?: number;
  distToHomeM?: number;
  distToSchoolM?: number;
  distToWaterM?: number;
  buildingsNear250m?: number;
  source?: string;
  lat: number;
  lon: number;
};

export const MIN_WORDS = 70;
export const MAX_WORDS = 135;

const dist = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`);

/** The only facts Claude may use. Every number in the brief must appear here. */
export function factsFor(c: BriefInput): string {
  const lines: string[] = [`Map quadrangle: ${c.quadName}`];
  if (c.editionsSeen.length) {
    const years = [...c.editionsSeen].sort((a, b) => a - b);
    lines.push(`Historical map editions showing a well symbol here: ${years.join(", ")} (${years.length} editions)`);
  }
  if (c.nearestDocumentedDistM !== undefined) {
    lines.push(`Nearest well in the CalGEM state records: ${dist(c.nearestDocumentedDistM)} away`);
  }
  if (c.distToHomeM !== undefined) lines.push(`Nearest home: ${dist(c.distToHomeM)}`);
  if (c.distToSchoolM !== undefined) lines.push(`Nearest school: ${dist(c.distToSchoolM)}`);
  if (c.distToWaterM !== undefined) lines.push(`Nearest surface water: ${dist(c.distToWaterM)}`);
  if (c.buildingsNear250m !== undefined) lines.push(`Buildings within 250 m: ${c.buildingsNear250m}`);
  return lines.join("\n");
}

export const SYSTEM_PROMPT = `You write short field briefs for crews who plug orphaned oil and gas wells.
Write ONE plain-text paragraph of 80 to 120 words, in four parts, in this order:
1. What the map evidence shows and where (name the quadrangle and the map years).
2. Why it is flagged: no matching well in the CalGEM state records within the distance given.
3. Who or what is nearby, using the home, school, water and building facts that are provided.
4. A recommended next step: verify on site with the handheld methane sensor before any plugging decision.
Hard rules:
- Use ONLY the facts provided. Copy numbers exactly as written. Do not add, round, convert or infer any other number.
- Never write coordinates. Never say a well is confirmed or leaking: this is an unverified candidate until a field reading says otherwise.
- No markdown, no bullet points, no headings, no preamble. Calm, specific, professional.`;

export function userPrompt(c: BriefInput): string {
  return `Facts about this candidate site:\n${factsFor(c)}\n\nWrite the brief.`;
}

/** Stable hash of exactly the inputs the brief depends on (status and score are excluded on purpose). */
export function inputHash(c: BriefInput): string {
  const s = JSON.stringify([
    c.quadName,
    [...c.editionsSeen].sort((a, b) => a - b),
    c.nearestDocumentedDistM ?? null,
    c.distToHomeM ?? null,
    c.distToSchoolM ?? null,
    c.distToWaterM ?? null,
    c.buildingsNear250m ?? null,
  ]);
  let h = 0x811c9dc5; // FNV-1a
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(16).padStart(8, "0");
}

const numbersIn = (t: string) => t.match(/\d+(?:\.\d+)?/g) ?? [];

/** Returns null when the brief is acceptable, otherwise the reason it was rejected. */
export function validateBrief(text: string, c: BriefInput): string | null {
  const t = text.trim();
  if (!t) return "empty";
  const words = t.split(/\s+/).length;
  if (words < MIN_WORDS || words > MAX_WORDS) return `length ${words} words (need ${MIN_WORDS}-${MAX_WORDS})`;
  if (/[#*•]|^\s*[-\d]+[.)]\s/m.test(t)) return "contains markdown or list formatting";
  if (/\b(?:confirmed|verified)\s+(?:to be\s+)?(?:a\s+)?leak/i.test(t) || /\b(?:actively|currently)\s+leaking/i.test(t) || /has been confirmed/i.test(t))
    return "claims a confirmed leak";
  const allowed = new Set(numbersIn(factsFor(c)));
  const stray = numbersIn(t).filter((n) => !allowed.has(n));
  if (stray.length) return `numbers not in the facts: ${[...new Set(stray)].join(", ")}`;
  if (new RegExp(`${Math.abs(c.lat).toFixed(2)}|${Math.abs(c.lon).toFixed(2)}`).test(t)) return "contains coordinates";
  return null;
}
