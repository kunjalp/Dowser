import { internalMutation } from "./_generated/server";
import { v } from "convex/values";
import { weightedScore } from "./scoring";

/**
 * FAKE candidates so the frontend can build before real detections exist
 * (Master Plan: 50 fake candidates in Convex by Fri 10 PM).
 * Locations are scattered around real Kern oil-field areas but are NOT wells.
 * Every id starts with "fake-" so clearFake can remove them cleanly.
 *
 *   npx convex run seed:seedFakeCandidates          (50, idempotent)
 *   npx convex run seed:seedFakeCandidates '{"count":120}'
 *   npx convex run seed:clearFake
 */

const AREAS = [
  { lat: 35.43, lon: -118.99, quad: "Oildale", r: 0.05 }, // Kern River area
  { lat: 35.22, lon: -119.45, quad: "Taft", r: 0.12 }, // Midway-Sunset area
  { lat: 35.48, lon: -119.72, quad: "Lost Hills", r: 0.06 }, // Belridge area
  { lat: 35.3, lon: -119.5, quad: "Tupman", r: 0.05 }, // Elk Hills area
  { lat: 35.18, lon: -119.4, quad: "Fellows", r: 0.05 }, // Buena Vista area
  { lat: 35.35, lon: -119.65, quad: "McKittrick", r: 0.05 }, // Cymric area
  { lat: 35.6, lon: -119.05, quad: "Famoso", r: 0.05 }, // Poso Creek area
];
const EDITIONS = [1947, 1962, 1978, 1992];

// Small deterministic PRNG so reseeding gives the same data.
function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const round = (x: number, d = 3) => Math.round(x * 10 ** d) / 10 ** d;

export const seedFakeCandidates = internalMutation({
  args: { count: v.optional(v.number()) },
  handler: async (ctx, { count }) => {
    const n = Math.max(1, Math.min(Math.floor(count ?? 50), 500));

    // Idempotent: drop earlier fakes first.
    const all = await ctx.db.query("candidates").take(2000);
    for (const c of all) if (c.id.startsWith("fake-")) await ctx.db.delete(c._id);

    const rnd = mulberry32(529);
    for (let i = 1; i <= n; i++) {
      const area = AREAS[Math.floor(rnd() * AREAS.length)];
      const lat = round(area.lat + (rnd() - 0.5) * 2 * area.r, 5);
      const lon = round(area.lon + (rnd() - 0.5) * 2 * area.r, 5);

      const nearestDocumentedDistM = Math.round(100 + rnd() * 1100);
      const distToHomeM = Math.round(50 + rnd() * rnd() * 3000);
      const distToSchoolM = Math.round(200 + rnd() * 5800);
      const distToWaterM = Math.round(30 + rnd() * 2470);
      const editionsSeen = EDITIONS.filter(() => rnd() < 0.55);
      if (editionsSeen.length === 0) editionsSeen.push(EDITIONS[Math.floor(rnd() * 4)]);

      const scoreParts = {
        confidence: round(0.4 + rnd() * 0.55),
        undocumented: round(clamp01(nearestDocumentedDistM / 600)),
        people: round(0.5 * clamp01(1 - distToSchoolM / 3000) + 0.5 * clamp01(1 - distToHomeM / 1500)),
        water: round(clamp01(1 - distToWaterM / 2000)),
        field: 0,
      };
      const id = `fake-${String(i).padStart(3, "0")}`;

      await ctx.db.insert("candidates", {
        id,
        lat,
        lon,
        score: round(weightedScore(scoreParts), 4),
        scoreParts,
        editionsSeen,
        nearestDocumentedDistM,
        distToHomeM,
        distToSchoolM,
        distToWaterM,
        buildingsNear250m: Math.floor(rnd() * 40),
        status: i % 11 === 0 ? "queued" : "candidate",
        brief: "FAKE DATA: placeholder brief. Real briefs are generated from real candidates.",
        evidenceImages: editionsSeen.map((year) => ({ year, url: `/evidence/fake/${id}-${year}.png` })),
        quadName: area.quad,
        detectionId: `fake-det-${String(i).padStart(3, "0")}`,
        source: "model",
      });
    }
    return { seeded: n };
  },
});

export const clearFake = internalMutation({
  args: {},
  handler: async (ctx) => {
    const all = await ctx.db.query("candidates").take(2000);
    let removed = 0;
    for (const c of all) {
      if (c.id.startsWith("fake-")) {
        await ctx.db.delete(c._id);
        removed++;
      }
    }
    return { removed };
  },
});
