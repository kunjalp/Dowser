import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";

/** Called by the HTTP ingest action in http.ts after validation. */
export const ingest = internalMutation({
  args: {
    deviceId: v.string(),
    ts: v.number(),
    raw: v.number(),
    corrected: v.number(),
    wellId: v.optional(v.string()),
    lat: v.optional(v.number()),
    lon: v.optional(v.number()),
    locationSource: v.string(),
    isReplay: v.boolean(),
  },
  handler: async (ctx, args) => {
    const receivedAt = Date.now();
    const readingId = `${args.deviceId}-${receivedAt}-${Math.random().toString(36).slice(2, 8)}`;
    await ctx.db.insert("readings", { readingId, receivedAt, ...args });
    // FR-8.3 / FR-8.4 (auto-confirm after 3 readings above threshold in 30 s)
    // hooks in here on Saturday; this endpoint only stores readings.
    return { readingId, receivedAt };
  },
});

/** Live feed for the map's readings chart (FR-9.4). Newest first. */
export const recent = query({
  args: { wellId: v.optional(v.string()), limit: v.optional(v.number()) },
  handler: async (ctx, { wellId, limit }) => {
    const n = Math.min(limit ?? 100, 500);
    if (wellId !== undefined) {
      return await ctx.db
        .query("readings")
        .withIndex("by_well_receivedAt", (q) => q.eq("wellId", wellId))
        .order("desc")
        .take(n);
    }
    return await ctx.db.query("readings").withIndex("by_receivedAt").order("desc").take(n);
  },
});
