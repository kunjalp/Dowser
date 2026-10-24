import { mutation, query } from "./_generated/server";
import { v } from "convex/values";
import { outcomeValidator } from "./constants";
import { applyStatus } from "./candidates";

/** Step 1 of attaching a photo: the Field View uploads the file to this URL. */
export const generateUploadUrl = mutation({
  args: {},
  handler: async (ctx) => await ctx.storage.generateUploadUrl(),
});

/**
 * Field View "log finding": stores the check AND moves the candidate to the matching
 * status (which logs a statusEvent), so the Command Map updates live. One tap, P0.
 */
export const logFinding = mutation({
  args: {
    candidateId: v.string(),
    outcome: outcomeValidator,
    note: v.optional(v.string()),
    photoId: v.optional(v.id("_storage")),
    deviceId: v.optional(v.string()),
    lat: v.optional(v.number()),
    lon: v.optional(v.number()),
  },
  handler: async (ctx, args) => {
    // Status first: it throws on an unknown candidate, so we never store an orphan check.
    const result = await applyStatus(ctx, {
      id: args.candidateId,
      status: args.outcome,
      source: "field",
      note: args.note,
    });
    const checkId = await ctx.db.insert("fieldChecks", { ...args, createdAt: Date.now() });
    return { checkId, ...result };
  },
});

export const forCandidate = query({
  args: { candidateId: v.string() },
  handler: async (ctx, { candidateId }) =>
    await ctx.db
      .query("fieldChecks")
      .withIndex("by_candidateId", (q) => q.eq("candidateId", candidateId))
      .order("desc")
      .take(50),
});
