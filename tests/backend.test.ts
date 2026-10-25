import { convexTest } from "convex-test";
import { describe, expect, test, beforeEach } from "vitest";
import schema from "../convex/schema";
import { internal, api } from "../convex/_generated/api";

const modules = import.meta.glob("../convex/**/*.ts");
const TOKEN = "test-token";

function setup() {
  process.env.INGEST_TOKEN = TOKEN;
  return convexTest(schema, modules);
}
const post = (t: ReturnType<typeof setup>, body: unknown, token: string | null = TOKEN) =>
  t.fetch("/ingest/reading", {
    method: "POST",
    headers: token ? { "X-Dowser-Token": token, "Content-Type": "application/json" } : {},
    body: JSON.stringify(body),
  });

describe("seed + ranking", () => {
  test("seeds 50 fake candidates, idempotently, and clears them", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, {});
    await t.mutation(internal.seed.seedFakeCandidates, {});
    let rows = await t.query(api.candidates.ranked, { limit: 2000 });
    expect(rows).toHaveLength(50);
    expect(rows.every((r: any) => r.id.startsWith("fake-"))).toBe(true);
    // Kern bbox from the loader
    expect(rows.every((r: any) => r.lon > -120.19 && r.lon < -117.63 && r.lat > 34.79 && r.lat < 35.8)).toBe(true);
    // sorted by score desc, ranks 1..n
    const scores = rows.map((r: any) => r.rankScore);
    expect([...scores].sort((a, b) => b - a)).toEqual(scores);
    expect(rows[0].rank).toBe(1);
    expect((await t.mutation(internal.seed.clearFake, {})).removed).toBe(50);
    rows = await t.query(api.candidates.ranked, {});
    expect(rows).toHaveLength(0);
  });

  test("custom weights re-rank without writing", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 30 });
    const byWater = await t.query(api.candidates.ranked, {
      weights: { confidence: 0, undocumented: 0, people: 0, water: 1, field: 0 },
    });
    const w = byWater.map((r: any) => r.scoreParts.water);
    expect([...w].sort((a, b) => b - a)).toEqual(w);
    const stored = await t.query(api.candidates.ranked, {});
    expect(stored.map((r: any) => r.score)).not.toEqual(byWater.map((r: any) => r.score)); // stored untouched
  });

  test("lanes rank undocumented candidates and idle wells separately", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 3 }); // source "model"
    const base = {
      lat: 35.4, lon: -119.05, editionsSeen: [], status: "candidate" as const, evidenceImages: [],
      quadName: "Oildale", scoreParts: { confidence: 1, undocumented: 0, people: 1, water: 1, field: 0 },
    };
    await t.mutation(internal.candidates.upsertBatch, {
      candidates: [
        { ...base, id: "idle-0402900001", score: 0.99, source: "calgem_idle", wellStatus: "Idle", operator: "Op", apiNumber: "0402900001" },
        { ...base, id: "idle-0402900002", score: 0.5, source: "calgem_idle", wellStatus: "Idle", apiNumber: "0402900002" },
        { ...base, id: "old-no-source", score: 0.01 }, // records from before `source` existed
      ],
    });
    const idle = await t.query(api.candidates.ranked, { lane: "idle" });
    expect(idle.map((r: any) => [r.id, r.rank])).toEqual([["idle-0402900001", 1], ["idle-0402900002", 2]]);
    const undoc = await t.query(api.candidates.ranked, { lane: "undocumented" });
    expect(undoc).toHaveLength(4);
    expect(undoc.some((r: any) => r.source === "calgem_idle")).toBe(false);
    expect(undoc.map((r: any) => r.id)).toContain("old-no-source");
    expect(undoc[0].rank).toBe(1);
    expect(await t.query(api.candidates.ranked, {})).toHaveLength(6); // no lane = both (Field View)
  });

  test("without a lane, a queued well is never cut by the limit", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 30 });
    const statuses = ["queued", "candidate"] as const; // Field View's call shape, no lane
    const full = await t.query(api.candidates.ranked, { statuses: [...statuses], limit: 2000 });
    const last = full.filter((r: any) => r.status === "candidate").at(-1);
    await t.mutation(api.candidates.setStatus, { id: last.id, status: "queued" });
    const queuedIds = full.filter((r: any) => r.status === "queued").map((r: any) => r.id).concat(last.id);
    expect(queuedIds.length).toBeLessThan(8); // the seed queues a few; the limit below still has room

    const rows = await t.query(api.candidates.ranked, { statuses: [...statuses], limit: 8 });
    expect(rows).toHaveLength(8);
    for (const id of queuedIds) expect(rows.map((r: any) => r.id)).toContain(id);
    expect(rows.at(-1)).toMatchObject({ id: last.id, rank: last.rank }); // keeps its true rank
    const ranks = rows.map((r: any) => r.rank);
    expect([...ranks].sort((a, b) => a - b)).toEqual(ranks);
    // the rest of the limit is the best-ranked unqueued rows
    const rest = rows.filter((r: any) => r.status !== "queued").map((r: any) => r.id);
    expect(rest).toEqual(full.filter((r: any) => r.status !== "queued").slice(0, rest.length).map((r: any) => r.id));
    // with a lane it is a plain top N
    const laned = await t.query(api.candidates.ranked, { statuses: [...statuses], lane: "undocumented", limit: 8 });
    expect(laned.map((r: any) => r.id)).not.toContain(last.id);
  });
});

describe("status changes", () => {
  test("setStatus logs an event, and a confirmed leak jumps to #1", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 20 });
    const before = await t.query(api.candidates.ranked, {});
    const last = before[before.length - 1];
    expect(last.rank).toBe(20);

    const r = await t.mutation(api.candidates.setStatus, { id: last.id, status: "confirmed_leaking", source: "field" });
    expect(r.changed).toBe(true);
    const after = await t.query(api.candidates.ranked, {});
    expect(after[0].id).toBe(last.id);
    expect(after[0].scoreParts.field).toBe(1);

    const events = await t.query(api.candidates.eventsFor, { id: last.id });
    expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({ from: expect.stringMatching(/candidate|queued/), to: "confirmed_leaking", source: "field" });

    // no-op when unchanged: no duplicate event
    expect((await t.mutation(api.candidates.setStatus, { id: last.id, status: "confirmed_leaking" })).changed).toBe(false);
    expect(await t.query(api.candidates.eventsFor, { id: last.id })).toHaveLength(1);

    // leaving confirmed_leaking resets the field part
    await t.mutation(api.candidates.setStatus, { id: last.id, status: "mislocated" });
    expect((await t.query(api.candidates.get, { id: last.id }))!.scoreParts.field).toBe(0);
  });

  test("unknown candidate throws", async () => {
    const t = setup();
    await expect(t.mutation(api.candidates.setStatus, { id: "nope", status: "queued" })).rejects.toThrow(/Unknown candidate/);
  });

  test("logFinding stores the check and updates status; unknown candidate stores nothing", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 5 });
    await t.mutation(api.fieldChecks.logFinding, { candidateId: "fake-003", outcome: "no_well", note: "just a pipe" });
    expect((await t.query(api.candidates.get, { id: "fake-003" }))!.status).toBe("no_well");
    expect(await t.query(api.fieldChecks.forCandidate, { candidateId: "fake-003" })).toHaveLength(1);

    await expect(t.mutation(api.fieldChecks.logFinding, { candidateId: "ghost", outcome: "no_well" })).rejects.toThrow();
    expect(await t.query(api.fieldChecks.forCandidate, { candidateId: "ghost" })).toHaveLength(0);
  });
});

describe("ingest endpoint", () => {
  test("health needs no token", async () => {
    const t = setup();
    const res = await t.fetch("/health", { method: "GET" });
    expect(res.status).toBe(200);
    expect((await res.json()).ok).toBe(true);
  });

  test("rejects missing/wrong token and bad bodies", async () => {
    const t = setup();
    expect((await post(t, { deviceId: "d", value: 1 }, null)).status).toBe(401);
    expect((await post(t, { deviceId: "d", value: 1 }, "wrong")).status).toBe(401);
    expect((await post(t, { value: 1 })).status).toBe(400);
    expect((await post(t, { deviceId: "d" })).status).toBe(400);
    expect((await post(t, { deviceId: "d", value: "x" })).status).toBe(400);
    expect((await post(t, { deviceId: "d", value: 1, lat: 200 })).status).toBe(400);
    expect((await post(t, { deviceId: "d", value: 1, locationSource: "moon" })).status).toBe(400);
    expect(await t.query(api.readings.recent, {})).toHaveLength(0);
  });

  test("stores a minimal reading (value only), defaults raw, no pairing -> none", async () => {
    const t = setup();
    const res = await post(t, { deviceId: "esp32-1", value: 12.5 });
    expect(res.status).toBe(201);
    const [r] = await t.query(api.readings.recent, {});
    expect(r).toMatchObject({ deviceId: "esp32-1", value: 12.5, raw: 12.5, locationSource: "none", isReplay: false });
    expect(r.candidateId).toBeUndefined();
  });

  test("accepts legacy field names", async () => {
    const t = setup();
    const res = await post(t, { deviceId: "d", corrected: 7, raw: 500, ts: Date.now(), wellId: "fake-001" });
    expect(res.status).toBe(201);
    const [r] = await t.query(api.readings.recent, {});
    expect(r).toMatchObject({ value: 7, raw: 500, candidateId: "fake-001", locationSource: "candidate" });
  });

  test("implausible device timestamp falls back to server time", async () => {
    const t = setup();
    await post(t, { deviceId: "d", value: 1, timestamp: 1000 }); // 1970
    const [r] = await t.query(api.readings.recent, {});
    expect(Math.abs(r.timestamp - r.receivedAt)).toBeLessThan(5000);
  });

  test("phone pairing attaches candidate + phone location; device-specific beats 'any'; clear stops it", async () => {
    const t = setup();
    await t.mutation(api.pairing.set, { candidateId: "fake-010", lat: 35.4, lon: -119.0 });
    await post(t, { deviceId: "esp32-1", value: 30, isReplay: true });
    let [r] = await t.query(api.readings.recent, {});
    expect(r).toMatchObject({ candidateId: "fake-010", lat: 35.4, lon: -119.0, locationSource: "phone", isReplay: true });

    await t.mutation(api.pairing.set, { deviceId: "esp32-1", candidateId: "fake-020" });
    await post(t, { deviceId: "esp32-1", value: 31 });
    [r] = await t.query(api.readings.recent, {});
    expect(r).toMatchObject({ candidateId: "fake-020", locationSource: "candidate" });

    await t.mutation(api.pairing.clear, { deviceId: "esp32-1" });
    await t.mutation(api.pairing.clear, {});
    await post(t, { deviceId: "esp32-1", value: 2 });
    [r] = await t.query(api.readings.recent, {});
    expect(r.candidateId).toBeUndefined();

    // per-candidate feed
    expect(await t.query(api.readings.recent, { candidateId: "fake-010" })).toHaveLength(1);
  });

  test("an explicit candidateId from the device wins over the pairing", async () => {
    const t = setup();
    await t.mutation(api.pairing.set, { candidateId: "fake-010" });
    await post(t, { deviceId: "d", value: 5, candidateId: "fake-099" });
    const [r] = await t.query(api.readings.recent, {});
    expect(r.candidateId).toBe("fake-099");
  });
});

describe("auto-confirm", () => {
  const hot = (id: string, value = 1500) => ({ deviceId: "esp32-1", value, candidateId: id });

  test("three hot readings in the window confirm a leak and move it to #1", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 5 });
    const r1 = await post(t, hot("fake-003"));
    const r2 = await post(t, hot("fake-003"));
    expect((await r2.json()).autoConfirmed).toBe(false);
    const r3 = await post(t, hot("fake-003"));
    expect((await r3.json()).autoConfirmed).toBe(true);
    expect(r1.status).toBe(201);
    const rows = await t.query(api.candidates.ranked, {});
    expect(rows[0].id).toBe("fake-003");
    expect(rows[0].status).toBe("confirmed_leaking");
    const events = await t.query(api.candidates.eventsFor, { id: "fake-003" });
    expect(events.some((e: any) => e.source === "auto")).toBe(true);
  });

  test("low readings and unknown candidates do not confirm or break ingest", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 5 });
    for (let i = 0; i < 4; i++) await post(t, hot("fake-002", 200));
    expect((await t.query(api.candidates.get, { id: "fake-002" }))?.status).not.toBe("confirmed_leaking");
    for (let i = 0; i < 3; i++) {
      const r = await post(t, hot("does-not-exist"));
      expect(r.status).toBe(201);
    }
  });

  test("a human decision is never overridden by auto-confirm", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 5 });
    await t.mutation(api.candidates.setStatus, { id: "fake-004", status: "no_well", source: "analyst" });
    for (let i = 0; i < 4; i++) await post(t, hot("fake-004"));
    expect((await t.query(api.candidates.get, { id: "fake-004" }))?.status).toBe("no_well");
  });
});

describe("upsertBatch (pipeline loader)", () => {
  test("re-running the loader keeps status, field part and brief of decided candidates", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 3 });
    const fresh = async (id: string) => {
      const c: any = await t.query(api.candidates.get, { id });
      const { _id, _creationTime, rank, rankScore, ...rest } = c;
      return { ...rest, scoreParts: { ...rest.scoreParts, field: 0 }, status: "candidate", brief: undefined };
    };
    // fake-001 gets a field confirmation and a brief; fake-002 stays an open candidate
    await t.mutation(api.candidates.setStatus, { id: "fake-001", status: "confirmed_leaking", source: "field" });
    const a: any = await fresh("fake-001");
    const b: any = await fresh("fake-002");
    const res = await t.mutation(internal.candidates.upsertBatch, { candidates: [a, b] });
    expect(res).toEqual({ inserted: 0, replaced: 2, keptDecisions: 1, reset: 0 });
    const kept: any = await t.query(api.candidates.get, { id: "fake-001" });
    expect(kept.status).toBe("confirmed_leaking");
    expect(kept.scoreParts.field).toBe(1);
    const open: any = await t.query(api.candidates.get, { id: "fake-002" });
    expect(open.status).toBe("candidate");
    expect(open.brief).toBeTruthy(); // seeded placeholder brief is kept when the load has none
  });
});

describe("human review (verified / rejected)", () => {
  const base = {
    lat: 35.4, lon: -119.05, editionsSeen: [1954], status: "candidate" as const, evidenceImages: [],
    quadName: "Oildale", scoreParts: { confidence: 0.5, undocumented: 0.5, people: 0.5, water: 0.5, field: 0 },
  };
  const rejected = { verdict: "rejected" as const, reason: "Not an oil/gas well symbol", reviewedBy: "r" };
  const verified = { verdict: "verified" as const, reason: "Well symbol", reviewedBy: "r", reviewedAt: "2026-10-24" };
  const load = (t: ReturnType<typeof setup>) =>
    t.mutation(internal.candidates.upsertBatch, {
      candidates: [
        { ...base, id: "cand-rej-high", score: 0.9, source: "model", review: rejected },
        { ...base, id: "cand-ok", score: 0.3, source: "model", review: verified, handLabeled: true },
        { ...base, id: "cand-gt", score: 0.2, source: "ground_truth", review: verified, handLabeled: true },
        { ...base, id: "cand-rej-low", score: 0.1, source: "model", review: rejected },
        { ...base, id: "idle-1", score: 0.95, source: "calgem_idle", review: rejected },
      ],
    });

  test("undocumented lane: rejected last and unranked; no lane leaves them out; idle unchanged", async () => {
    const t = setup();
    await load(t);
    const undoc = await t.query(api.candidates.ranked, { lane: "undocumented" });
    expect(undoc.map((r: any) => [r.id, r.rank])).toEqual([
      ["cand-ok", 1], ["cand-gt", 2], ["cand-rej-high", 0], ["cand-rej-low", 0],
    ]);
    const field = await t.query(api.candidates.ranked, {});
    expect(field.map((r: any) => r.id)).toEqual(["cand-ok", "cand-gt"]);
    expect(field.map((r: any) => r.rank)).toEqual([1, 2]);
    const idle = await t.query(api.candidates.ranked, { lane: "idle" });
    expect(idle.map((r: any) => [r.id, r.rank])).toEqual([["idle-1", 1]]); // the idle lane ignores review
  });

  test("a rejected candidate cannot be queued; other statuses still work", async () => {
    const t = setup();
    await load(t);
    await expect(
      t.mutation(api.candidates.setStatus, { id: "cand-rej-high", status: "queued" }),
    ).rejects.toThrow(/rejected in review/);
    expect((await t.query(api.candidates.get, { id: "cand-rej-high" }))!.status).toBe("candidate");
    await t.mutation(api.candidates.setStatus, { id: "cand-rej-high", status: "no_well" });
    expect((await t.query(api.candidates.get, { id: "cand-rej-high" }))!.status).toBe("no_well");
    await t.mutation(api.candidates.setStatus, { id: "cand-ok", status: "queued" });
    expect((await t.query(api.candidates.get, { id: "cand-ok" }))!.status).toBe("queued");
  });

  test("resetStatus puts decided candidates back to candidate and logs it; rejected loses its old brief", async () => {
    const t = setup();
    await t.mutation(internal.candidates.upsertBatch, {
      candidates: [
        { ...base, id: "cand-a", score: 0.5, source: "model", brief: "old brief" },
        { ...base, id: "cand-b", score: 0.4, source: "model", brief: "kept brief" },
      ],
    });
    await t.mutation(api.candidates.setStatus, { id: "cand-a", status: "confirmed_leaking", source: "field" });
    await t.mutation(api.candidates.setStatus, { id: "cand-b", status: "queued" });
    const res = await t.mutation(internal.candidates.upsertBatch, {
      resetStatus: true,
      candidates: [
        { ...base, id: "cand-a", score: 0.5, source: "model", review: rejected },
        { ...base, id: "cand-b", score: 0.4, source: "model", review: verified },
      ],
    });
    expect(res).toEqual({ inserted: 0, replaced: 2, keptDecisions: 0, reset: 2 });
    const a: any = await t.query(api.candidates.get, { id: "cand-a" });
    expect(a.status).toBe("candidate");
    expect(a.scoreParts.field).toBe(0);
    expect(a.brief).toBeUndefined();
    const b: any = await t.query(api.candidates.get, { id: "cand-b" });
    expect(b.status).toBe("candidate");
    expect(b.brief).toBe("kept brief");
    const events: any[] = await t.query(api.candidates.eventsFor, { id: "cand-a" });
    expect(events[0]).toMatchObject({ from: "confirmed_leaking", to: "candidate", source: "pipeline" });
  });

  test("prune helpers list and delete only model/ground_truth candidates", async () => {
    const t = setup();
    await load(t);
    await t.mutation(internal.candidates.upsertBatch, { candidates: [{ ...base, id: "no-source", score: 0.1 }] });
    const ids = await t.query(internal.candidates.undocumentedIds, {});
    expect(ids.map((r) => r.id).sort()).toEqual(["cand-gt", "cand-ok", "cand-rej-high", "cand-rej-low"]);
    const res = await t.mutation(internal.candidates.deleteUndocumented, {
      ids: ["cand-rej-low", "cand-gt", "idle-1", "no-source", "missing"],
    });
    expect(res).toEqual({ deleted: 2, refused: ["idle-1", "no-source"] });
    expect(await t.query(api.candidates.get, { id: "idle-1" })).not.toBeNull();
    expect(await t.query(api.candidates.get, { id: "cand-gt" })).toBeNull();
  });
});

describe("Claude brief generator", () => {
  const good = (quad: string) =>
    `The ${quad} quadrangle shows a well symbol on the 1962 and 1978 map editions, a repeated mark that suggests a real structure rather than a one-off drawing artifact. ` +
    `The state CalGEM records list no well within 1.1 km, so this site is flagged as undocumented. ` +
    `The nearest home is 336 m away, a school lies 644 m off and surface water is 418 m away, with 7 buildings inside 250 m, which raises the stakes if anything is leaking. ` +
    `This is an unverified candidate only. The next step is to visit the site and take readings with the handheld methane sensor before any plugging decision is made.`;

  const stubFetch = (texts: string[]) => {
    const calls: any[] = [];
    let i = 0;
    (globalThis as any).fetch = async (_url: string, init: any) => {
      calls.push(JSON.parse(init.body));
      const text = texts[Math.min(i++, texts.length - 1)];
      return { ok: true, json: async () => ({ content: [{ type: "text", text }] }), text: async () => "" };
    };
    return calls;
  };

  beforeEach(() => {
    process.env.ANTHROPIC_API_KEY = "test-key";
  });

  test("writes a brief, prefixes fake candidates, and skips unchanged inputs on re-run", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 2 });
    const c: any = await t.query(api.candidates.get, { id: "fake-001" });
    // make the facts match the canned brief text
    await t.run(async (ctx: any) => {
      const row = await ctx.db.query("candidates").withIndex("by_candidate_id", (q: any) => q.eq("id", "fake-001")).unique();
      await ctx.db.patch(row._id, {
        quadName: "Lost Hills", editionsSeen: [1962, 1978], nearestDocumentedDistM: 1123,
        distToHomeM: 336, distToSchoolM: 644, distToWaterM: 418, buildingsNear250m: 7,
      });
    });
    const calls = stubFetch([good("Lost Hills")]);
    const r1: any = await t.action(internal.briefs.generate, { id: "fake-001" });
    expect(r1).toEqual({ generated: 1, skipped: 0, failed: [] });
    expect(calls[0].system).toContain("ONLY the facts provided");
    const after: any = await t.query(api.candidates.get, { id: "fake-001" });
    expect(after.brief.startsWith("FAKE DATA: The Lost Hills")).toBe(true);
    const r2: any = await t.action(internal.briefs.generate, { id: "fake-001" });
    expect(r2.skipped).toBe(1);
    expect(calls.length).toBe(1); // no second API call
    expect(c.id).toBe("fake-001");
  });

  test("rejects a brief that invents a number, retries once, then records the failure", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 1 });
    const bad = good("Lost Hills").replace("336 m", "999 m");
    const calls = stubFetch([bad, bad]);
    const r: any = await t.action(internal.briefs.generate, { id: "fake-001" });
    expect(r.generated).toBe(0);
    expect(r.failed).toHaveLength(1);
    expect(calls.length).toBe(2); // original + one retry
    const unchanged: any = await t.query(api.candidates.get, { id: "fake-001" });
    expect(unchanged.brief).toMatch(/^FAKE DATA: placeholder/);
  });

  test("an empty reply is retried once and then succeeds", async () => {
    const t = setup();
    await t.mutation(internal.seed.seedFakeCandidates, { count: 1 });
    await t.run(async (ctx: any) => {
      const row = await ctx.db.query("candidates").withIndex("by_candidate_id", (q: any) => q.eq("id", "fake-001")).unique();
      await ctx.db.patch(row._id, {
        quadName: "Lost Hills", editionsSeen: [1962, 1978], nearestDocumentedDistM: 1123,
        distToHomeM: 336, distToSchoolM: 644, distToWaterM: 418, buildingsNear250m: 7,
      });
    });
    const calls = stubFetch(["", good("Lost Hills")]);
    const r: any = await t.action(internal.briefs.generate, { id: "fake-001" });
    expect(r).toEqual({ generated: 1, skipped: 0, failed: [] });
    expect(calls.length).toBe(2);
    expect(calls[1].messages[0].content).toContain("empty response");
  });

  test("fails loudly when the API key is missing", async () => {
    const t = setup();
    delete process.env.ANTHROPIC_API_KEY;
    await expect(t.action(internal.briefs.generate, {})).rejects.toThrow(/ANTHROPIC_API_KEY/);
  });
});
