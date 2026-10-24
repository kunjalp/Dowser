import { internalAction, internalMutation, internalQuery } from "./_generated/server";
import { internal } from "./_generated/api";
import { v } from "convex/values";
import { SYSTEM_PROMPT, inputHash, userPrompt, validateBrief } from "./briefPrompt";
import type { BriefInput } from "./briefPrompt";

const DEFAULT_MODEL = "claude-sonnet-5-5";
const OPEN_STATUSES = new Set(["candidate", "queued", "confirmed_leaking"]);

/** Highest-ranked candidates that still need a brief decision (open ones only). */
export const topCandidates = internalQuery({
  args: { limit: v.number(), id: v.optional(v.string()) },
  handler: async (ctx, { limit, id }) => {
    if (id !== undefined) {
      const one = await ctx.db
        .query("candidates")
        .withIndex("by_candidate_id", (q) => q.eq("id", id))
        .unique();
      return one ? [one] : [];
    }
    const rows = await ctx.db.query("candidates").withIndex("by_score").order("desc").take(limit * 3);
    return rows.filter((r) => OPEN_STATUSES.has(r.status)).slice(0, limit);
  },
});

export const existing = internalQuery({
  args: { candidateId: v.string() },
  handler: async (ctx, { candidateId }) =>
    await ctx.db
      .query("briefs")
      .withIndex("by_candidateId", (q) => q.eq("candidateId", candidateId))
      .unique(),
});

export const save = internalMutation({
  args: { candidateId: v.string(), text: v.string(), inputHash: v.string() },
  handler: async (ctx, { candidateId, text, inputHash }) => {
    const row = await ctx.db
      .query("briefs")
      .withIndex("by_candidateId", (q) => q.eq("candidateId", candidateId))
      .unique();
    const doc = { candidateId, text, inputHash, generatedAt: Date.now() };
    if (row) await ctx.db.replace(row._id, doc);
    else await ctx.db.insert("briefs", doc);
    const cand = await ctx.db
      .query("candidates")
      .withIndex("by_candidate_id", (q) => q.eq("id", candidateId))
      .unique();
    if (cand) await ctx.db.patch(cand._id, { brief: text });
  },
});

type ClaudeReply = { text: string; stop: string; blocks: string };

async function askClaude(apiKey: string, model: string, input: BriefInput, feedback?: string): Promise<ClaudeReply> {
  const messages: { role: "user"; content: string }[] = [
    { role: "user", content: userPrompt(input) + (feedback ? `\n\nYour previous attempt was rejected: ${feedback}. Write the brief as plain text now.` : "") },
  ];
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "content-type": "application/json", "x-api-key": apiKey, "anthropic-version": "2023-06-01" },
    // Generous max_tokens: models that think first can spend the budget before writing any text.
    body: JSON.stringify({ model, max_tokens: 2000, system: SYSTEM_PROMPT, messages }),
  });
  if (!res.ok) throw new Error(`Anthropic API ${res.status}: ${(await res.text()).slice(0, 300)}`);
  const json = (await res.json()) as { content?: { type: string; text?: string }[]; stop_reason?: string };
  const blocks = json.content ?? [];
  return {
    text: blocks.filter((b) => b.type === "text").map((b) => b.text ?? "").join("").trim(),
    stop: json.stop_reason ?? "unknown",
    blocks: blocks.map((b) => b.type).join(",") || "none",
  };
}

/** One attempt: ask, then validate. An empty reply reports why (stop reason, block types). */
async function attempt(apiKey: string, model: string, c: BriefInput, feedback?: string) {
  const r = await askClaude(apiKey, model, c, feedback);
  const problem = r.text ? validateBrief(r.text, c) : `empty response (stop_reason=${r.stop}, blocks=${r.blocks})`;
  return { text: r.text, problem };
}

/**
 * Write Claude briefs for the top candidates. Internal on purpose (it spends API credit), run with:
 *   npx convex run briefs:generate '{"limit":50}' --prod
 * Options: id (one candidate), force (regenerate even if inputs are unchanged).
 * Skips candidates whose inputs have not changed since their last brief.
 */
export const generate = internalAction({
  args: { limit: v.optional(v.number()), id: v.optional(v.string()), force: v.optional(v.boolean()) },
  handler: async (ctx, { limit, id, force }) => {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) throw new Error("ANTHROPIC_API_KEY is not set. Run: npx convex env set ANTHROPIC_API_KEY <key> [--prod]");
    const model = process.env.ANTHROPIC_MODEL || DEFAULT_MODEL;

    const cands = await ctx.runQuery(internal.briefs.topCandidates, { limit: limit ?? 50, id });
    const result = { generated: 0, skipped: 0, failed: [] as { id: string; reason: string }[] };

    for (const c of cands) {
      const hash = inputHash(c);
      const prev = await ctx.runQuery(internal.briefs.existing, { candidateId: c.id });
      if (!force && prev && prev.inputHash === hash) {
        result.skipped++;
        continue;
      }
      try {
        let { text, problem } = await attempt(apiKey, model, c);
        if (problem) ({ text, problem } = await attempt(apiKey, model, c, problem));
        if (problem) {
          result.failed.push({ id: c.id, reason: problem });
          continue;
        }
        // Seeded placeholder candidates are labelled so a brief can never pass for real analysis.
        const final = c.id.startsWith("fake-") ? `FAKE DATA: ${text}` : text;
        await ctx.runMutation(internal.briefs.save, { candidateId: c.id, text: final, inputHash: hash });
        result.generated++;
      } catch (e) {
        result.failed.push({ id: c.id, reason: e instanceof Error ? e.message : String(e) });
      }
    }
    return result;
  },
});
