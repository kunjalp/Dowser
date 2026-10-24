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
