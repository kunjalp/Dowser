import { internalMutation, mutation, query } from "./_generated/server";
import type { MutationCtx } from "./_generated/server";
import type { Doc } from "./_generated/dataModel";
import { v } from "convex/values";
import type { Infer } from "convex/values";
import { candidateFields } from "./schema";
import {
  scorePartsValidator,
  statusSourceValidator,
  statusValidator,
} from "./constants";
import { weightedScore } from "./scoring";

type Status = Infer<typeof statusValidator>;
type StatusSource = Infer<typeof statusSourceValidator>;

/**
 * Change a candidate's status and log a statusEvent. Shared by setStatus and logFinding.
 * Entering confirmed_leaking sets scoreParts.field to 1; leaving it resets to 0.
 */
export async function applyStatus(
  ctx: MutationCtx,
  args: { id: string; status: Status; source: StatusSource; note?: string },
) {
  const c = await ctx.db
    .query("candidates")
    .withIndex("by_candidate_id", (q) => q.eq("id", args.id))
    .unique();
  if (!c) throw new Error(`Unknown candidate: ${args.id}`);
  if (c.status === args.status) return { changed: false as const };

  const field =
    args.status === "confirmed_leaking" ? 1 : c.status === "confirmed_leaking" ? 0 : c.scoreParts.field;
  const scoreParts = { ...c.scoreParts, field };

  await ctx.db.patch(c._id, { status: args.status, scoreParts, score: weightedScore(scoreParts) });
  await ctx.db.insert("statusEvents", {
    candidateId: args.id,
    from: c.status,
    to: args.status,
    source: args.source,
    note: args.note,
    createdAt: Date.now(),
  });
  return { changed: true as const };
}

const IDLE_SOURCE = "calgem_idle";

/** Which list: "undocumented" = every source except calgem_idle (records without a source
 * included); "idle" = CalGEM idle wells near people. */
const laneValidator = v.union(v.literal("undocumented"), v.literal("idle"));

/**
 * Ranked list for the sidebar and map. A confirmed leak always ranks above every
 * unconfirmed candidate. Pass `weights` (priority sliders) to re-rank live without
 * writing anything; omit it to use the stored default-weight score.
 * Pass `lane` to rank one list on its own (ranks start at 1); omit it for both together.
 * Returns at most 2000 candidates.
 */
export const ranked = query({
  args: {
    statuses: v.optional(v.array(statusValidator)),
    weights: v.optional(scorePartsValidator),
    limit: v.optional(v.number()),
    lane: v.optional(laneValidator),
  },
  handler: async (ctx, { statuses, weights, limit, lane }) => {
    let docs: Doc<"candidates">[];
    if (lane === "idle") {
      docs = await ctx.db
        .query("candidates")
        .withIndex("by_source", (q) => q.eq("source", IDLE_SOURCE))
        .take(2000);
    } else if (lane === "undocumented") {
      // Both sides of "calgem_idle" in the index; missing source sorts first, so it is included.
      const before = await ctx.db
        .query("candidates")
        .withIndex("by_source", (q) => q.lt("source", IDLE_SOURCE))
        .take(2000);
      const after = await ctx.db
        .query("candidates")
        .withIndex("by_source", (q) => q.gt("source", IDLE_SOURCE))
        .take(2000 - before.length);
      docs = [...before, ...after];
    } else {
      docs = await ctx.db.query("candidates").take(2000);
      // Field View (no lane) must see every queued well, even past the 2000-row scan.
      const seen = new Set(docs.map((d) => d._id));
      const queued = await ctx.db
        .query("candidates")
        .withIndex("by_status", (q) => q.eq("status", "queued"))
        .take(2000);
      docs.push(...queued.filter((d) => !seen.has(d._id)));
    }
    if (statuses) docs = docs.filter((d) => statuses.includes(d.status));
    const rows = docs.map((d) => ({
      ...d,
      rankScore: weights ? weightedScore(d.scoreParts, weights) : d.score,
    }));
    rows.sort(
      (a, b) =>
        Number(b.status === "confirmed_leaking") - Number(a.status === "confirmed_leaking") ||
        b.rankScore - a.rankScore,
    );
    const cap = Math.min(limit ?? 500, 2000);
    const all = rows.map((r, i) => ({ ...r, rank: i + 1 }));
    if (lane) return all.slice(0, cap);
    // No lane (Field View): every queued row is kept, and the limit is filled with the best of
    // the rest, so a queued well can never fall outside the top N. Ranks stay the true ranks.
    const queued = all.filter((r) => r.status === "queued");
    const rest = all.filter((r) => r.status !== "queued").slice(0, Math.max(0, cap - queued.length));
    return [...queued, ...rest].sort((a, b) => a.rank - b.rank);
  },
});

export const get = query({
  args: { id: v.string() },
  handler: async (ctx, { id }) =>
    await ctx.db
      .query("candidates")
      .withIndex("by_candidate_id", (q) => q.eq("id", id))
      .unique(),
});

/** Status buttons in the Command Map and Field View. */
export const setStatus = mutation({
  args: {
    id: v.string(),
    status: statusValidator,
    source: v.optional(statusSourceValidator),
    note: v.optional(v.string()),
  },
  handler: async (ctx, { id, status, source, note }) =>
    await applyStatus(ctx, { id, status, source: source ?? "analyst", note }),
});

/** Status change history for one candidate, newest first. */
export const eventsFor = query({
  args: { id: v.string() },
  handler: async (ctx, { id }) =>
    await ctx.db
      .query("statusEvents")
      .withIndex("by_candidateId", (q) => q.eq("candidateId", id))
      .order("desc")
      .take(100),
});

/**
 * Pipeline loader: insert or replace candidates by `id`. Internal, so run it with
 *   npx convex run candidates:upsertBatch '{"candidates":[...]}'
 * For big loads prefer: npx convex import --table candidates --replace file.jsonl
 */
export const upsertBatch = internalMutation({
  args: { candidates: v.array(v.object(candidateFields)) },
  handler: async (ctx, { candidates }) => {
    let inserted = 0;
    let replaced = 0;
    let keptDecisions = 0;
    for (const c of candidates) {
      const existing = await ctx.db
        .query("candidates")
        .withIndex("by_candidate_id", (q) => q.eq("id", c.id))
        .unique();
      if (existing) {
        const next = { ...c };
        // Re-running the loader must never undo a human or field decision. Keep the
        // existing status and field-confirmation part, and recompute the score from them.
        if (existing.status !== "candidate") {
          next.status = existing.status;
          next.scoreParts = { ...c.scoreParts, field: existing.scoreParts.field };
          next.score = weightedScore(next.scoreParts);
          keptDecisions++;
        }
        // Keep a generated brief unless the new load carries one.
        if (next.brief === undefined && existing.brief !== undefined) next.brief = existing.brief;
        await ctx.db.replace(existing._id, next);
        replaced++;
      } else {
        await ctx.db.insert("candidates", c);
        inserted++;
      }
    }
    return { inserted, replaced, keptDecisions };
  },
});
