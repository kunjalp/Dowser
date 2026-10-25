import { internalMutation, internalQuery, mutation, query } from "./_generated/server";
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
  if (args.status === "queued" && isRejected(c)) {
    throw new Error(`${args.id} was rejected in review (not a well symbol) and cannot be queued for a field check`);
  }

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
/** Sources in the undocumented lane that --prune may delete. */
const UNDOCUMENTED_SOURCES = ["model", "ground_truth"] as const;

const isRejected = (c: Pick<Doc<"candidates">, "review">) => c.review?.verdict === "rejected";

/** Which list: "undocumented" = every source except calgem_idle (records without a source
 * included); "idle" = CalGEM idle wells near people. */
const laneValidator = v.union(v.literal("undocumented"), v.literal("idle"));

/**
 * Ranked list for the sidebar and map. A confirmed leak always ranks above every
 * unconfirmed candidate. Pass `weights` (priority sliders) to re-rank live without
 * writing anything; omit it to use the stored default-weight score.
 * Pass `lane` to rank one list on its own (ranks start at 1); omit it for both together.
 * Undocumented lane: candidates rejected in review come last with rank 0 (not counted in the
 * ranks). Without a lane (Field View) they are left out entirely.
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
    if (!lane) docs = docs.filter((d) => !isRejected(d));
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
    if (lane === "undocumented") {
      const kept = rows.filter((r) => !isRejected(r)).map((r, i) => ({ ...r, rank: i + 1 }));
      const rejected = rows.filter(isRejected).map((r) => ({ ...r, rank: 0 }));
      return [...kept, ...rejected].slice(0, cap);
    }
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
 * `resetStatus: true` lets the load's status win over a decided one; each reset is logged.
 */
export const upsertBatch = internalMutation({
  args: { candidates: v.array(v.object(candidateFields)), resetStatus: v.optional(v.boolean()) },
  handler: async (ctx, { candidates, resetStatus }) => {
    let inserted = 0;
    let replaced = 0;
    let keptDecisions = 0;
    let reset = 0;
    for (const c of candidates) {
      const existing = await ctx.db
        .query("candidates")
        .withIndex("by_candidate_id", (q) => q.eq("id", c.id))
        .unique();
      if (existing) {
        const next = { ...c };
        // Re-running the loader must never undo a human or field decision. Keep the
        // existing status and field-confirmation part, and recompute the score from them.
        // With resetStatus the load's status and field part win instead, and the change is logged.
        if (existing.status !== c.status && resetStatus) {
          await ctx.db.insert("statusEvents", {
            candidateId: c.id,
            from: existing.status,
            to: c.status,
            source: "pipeline",
            note: "Reset by pipeline load",
            createdAt: Date.now(),
          });
          reset++;
        } else if (existing.status !== "candidate") {
          next.status = existing.status;
          next.scoreParts = { ...c.scoreParts, field: existing.scoreParts.field };
          next.score = weightedScore(next.scoreParts);
          keptDecisions++;
        }
        // Keep a generated brief unless the new load carries one. Rejected candidates get none.
        if (next.brief === undefined && existing.brief !== undefined && !isRejected(next)) next.brief = existing.brief;
        await ctx.db.replace(existing._id, next);
        replaced++;
      } else {
        await ctx.db.insert("candidates", c);
        inserted++;
      }
    }
    return { inserted, replaced, keptDecisions, reset };
  },
});

/** For load_candidates.py --prune: every undocumented-lane candidate from a detection source. */
export const undocumentedIds = internalQuery({
  args: {},
  handler: async (ctx) => {
    const out: { id: string; source: string; status: Status }[] = [];
    for (const source of UNDOCUMENTED_SOURCES) {
      const docs = await ctx.db
        .query("candidates")
        .withIndex("by_source", (q) => q.eq("source", source))
        .take(2000);
      out.push(...docs.map((d) => ({ id: d.id, source, status: d.status })));
    }
    return out;
  },
});

/** For load_candidates.py --prune. Deletes only model/ground_truth candidates; anything else is refused. */
export const deleteUndocumented = internalMutation({
  args: { ids: v.array(v.string()) },
  handler: async (ctx, { ids }) => {
    let deleted = 0;
    const refused: string[] = [];
    for (const id of ids) {
      const c = await ctx.db
        .query("candidates")
        .withIndex("by_candidate_id", (q) => q.eq("id", id))
        .unique();
      if (!c) continue;
      if (!(UNDOCUMENTED_SOURCES as readonly (string | undefined)[]).includes(c.source)) {
        refused.push(id);
        continue;
      }
      await ctx.db.delete(c._id);
      deleted++;
    }
    return { deleted, refused };
  },
});
