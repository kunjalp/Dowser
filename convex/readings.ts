import { internalMutation, query } from "./_generated/server";
import { v } from "convex/values";
import { locationSourceValidator } from "./constants";
import { PAIRING_TTL_MS } from "./pairing";

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
    // Auto-confirm after 3 readings above threshold in 30 s is a should-have (P1);
    // it hooks in here. For now readings are only stored.
    return { id, receivedAt, candidateId: candidateId ?? null };
  },
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
