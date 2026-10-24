import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

/** A pairing older than this is ignored by the ingest endpoint. */
export const PAIRING_TTL_MS = 30 * 60 * 1000;

/**
 * The phone says "this handheld is now at candidate X, and I am at lat/lon".
 * Readings that arrive without a candidateId are attached to the pairing.
 * deviceId defaults to "any", which pairs whichever device posts next.
 */
export const set = mutation({
  args: {
    candidateId: v.string(),
    deviceId: v.optional(v.string()),
    lat: v.optional(v.number()),
    lon: v.optional(v.number()),
  },
  handler: async (ctx, { candidateId, deviceId, lat, lon }) => {
    const key = deviceId ?? "any";
    const existing = await ctx.db
      .query("pairings")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", key))
      .unique();
    const doc = { deviceId: key, candidateId, lat, lon, updatedAt: Date.now() };
    if (existing) await ctx.db.replace(existing._id, doc);
    else await ctx.db.insert("pairings", doc);
  },
});

export const clear = mutation({
  args: { deviceId: v.optional(v.string()) },
  handler: async (ctx, { deviceId }) => {
    const existing = await ctx.db
      .query("pairings")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId ?? "any"))
      .unique();
    if (existing) await ctx.db.delete(existing._id);
  },
});

export const current = query({
  args: { deviceId: v.optional(v.string()) },
  handler: async (ctx, { deviceId }) =>
    await ctx.db
      .query("pairings")
      .withIndex("by_deviceId", (q) => q.eq("deviceId", deviceId ?? "any"))
      .unique(),
});
