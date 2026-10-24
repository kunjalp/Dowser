import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";
import { locationSourceValidator } from "./constants";
import { PAIRING_TTL_MS } from "./pairing";
import { applyStatus } from "./candidates";

/**
 * Auto-confirm rule (Master Plan should-have): this many readings at or above the
 * threshold within the window flips a candidate to confirmed_leaking. The threshold is
 * in the same units as `value` (the corrected reading); tune it once Murad has a baseline.
 */
export const AUTO_CONFIRM = { threshold: 1200, count: 8, windowMs: 10_000 } as const;

/** Called by the HTTP ingest action in http.ts after validation. */
export const ingest = internalMutation({
  args: {
    deviceId: v.string(),
    value: v.number(),
    raw: v.number(),
    timestamp: v.number(),
    candidateId: v.optional(v.string()),
    lat: v.optional(v.number()),
    lon: v.optional(v.number()),
    locationSource: v.optional(locationSourceValidator),
    isReplay: v.boolean(),
  },
  handler: async (ctx, args) => {
    const receivedAt = Date.now();
    let { candidateId, lat, lon, locationSource } = args;

    // Attach the phone's pairing when the device did not say where it is.
    if (candidateId === undefined) {
      for (const key of [args.deviceId, "any"]) {
        const p = await ctx.db
          .query("pairings")
          .withIndex("by_deviceId", (q) => q.eq("deviceId", key))
          .unique();
        if (p && receivedAt - p.updatedAt < PAIRING_TTL_MS) {
          candidateId = p.candidateId;
          lat = lat ?? p.lat;
          lon = lon ?? p.lon;
          locationSource = locationSource ?? (p.lat !== undefined ? "phone" : "candidate");
          break;
        }
      }
    }

    const id = await ctx.db.insert("readings", {
      deviceId: args.deviceId,
      value: args.value,
      raw: args.raw,
      timestamp: args.timestamp,
      receivedAt,
      candidateId,
      lat,
      lon,
      locationSource: locationSource ?? (candidateId !== undefined ? "candidate" : "none"),
      isReplay: args.isReplay,
    });

    // Auto-confirm: N hot readings inside the window for a still-open candidate.
    let autoConfirmed = false;
    if (candidateId !== undefined && args.value >= AUTO_CONFIRM.threshold) {
      const cand = await ctx.db
        .query("candidates")
        .withIndex("by_candidate_id", (q) => q.eq("id", candidateId as string))
        .unique();
      if (cand && (cand.status === "candidate" || cand.status === "queued")) {
        const recent = await ctx.db
          .query("readings")
          .withIndex("by_candidate_receivedAt", (q) =>
            q.eq("candidateId", candidateId as string).gte("receivedAt", receivedAt - AUTO_CONFIRM.windowMs),
          )
          .order("desc")
          .take(50);
        const hot = recent.filter((r) => r.value >= AUTO_CONFIRM.threshold).length;
        if (hot >= AUTO_CONFIRM.count) {
          const res = await applyStatus(ctx, {
            id: candidateId,
            status: "confirmed_leaking",
            source: "auto",
            note: `${hot} readings >= ${AUTO_CONFIRM.threshold} within ${AUTO_CONFIRM.windowMs / 1000}s`,
          });
          autoConfirmed = res.changed;
        }
      }
    }
    return { id, receivedAt, candidateId: candidateId ?? null, autoConfirmed };
  },
});

/** The auto-confirm rule, so the UI can show "2 of 3 hot readings" without hardcoding it. */
export const autoConfirmRule = query({
  args: {},
  handler: async () => AUTO_CONFIRM,
});

/** Live readings feed for the chart. Newest first; pass candidateId for one well. */
export const recent = query({
  args: { candidateId: v.optional(v.string()), limit: v.optional(v.number()) },
  handler: async (ctx, { candidateId, limit }) => {
    const n = Math.min(limit ?? 100, 500);
    if (candidateId !== undefined) {
      return await ctx.db
        .query("readings")
        .withIndex("by_candidate_receivedAt", (q) => q.eq("candidateId", candidateId))
        .order("desc")
        .take(n);
    }
    return await ctx.db.query("readings").withIndex("by_receivedAt").order("desc").take(n);
  },
});
