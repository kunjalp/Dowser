import { httpRouter } from "convex/server";
import { httpAction } from "./_generated/server";
import { internal } from "./_generated/api";

const http = httpRouter();

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

// Constant-time string compare so the token check does not leak length/prefix.
function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

const isNum = (x: unknown): x is number => typeof x === "number" && Number.isFinite(x);

/**
 * POST /ingest/reading   (FR-7.3)
 * Header: X-Dowser-Token: <INGEST_TOKEN>   (NFR-5: scoped ingest credential)
 * Body:   { deviceId, raw, corrected, ts?, wellId?, lat?, lon?, locationSource?, isReplay? }
 *
 * ts is optional because an ESP32 without NTP has no wall clock; the server
 * always records receivedAt, which is what the sensor-to-map latency check uses.
 */
http.route({
  path: "/ingest/reading",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    const expected = process.env.INGEST_TOKEN;
    if (!expected) return json({ error: "server_not_configured" }, 500);
    const given = request.headers.get("X-Dowser-Token") ?? "";
    if (!safeEqual(given, expected)) return json({ error: "unauthorized" }, 401);

    let body: Record<string, unknown>;
    try {
      body = await request.json();
    } catch {
      return json({ error: "invalid_json" }, 400);
    }

    const { deviceId, raw, corrected, ts, wellId, lat, lon, locationSource, isReplay } = body;

    if (typeof deviceId !== "string" || deviceId.length === 0 || deviceId.length > 64)
      return json({ error: "invalid_deviceId" }, 400);
    if (!isNum(raw)) return json({ error: "invalid_raw" }, 400);
    if (!isNum(corrected)) return json({ error: "invalid_corrected" }, 400);
    if (ts !== undefined && !isNum(ts)) return json({ error: "invalid_ts" }, 400);
    if (wellId !== undefined && (typeof wellId !== "string" || wellId.length > 64))
      return json({ error: "invalid_wellId" }, 400);
    if (lat !== undefined && (!isNum(lat) || lat < -90 || lat > 90))
      return json({ error: "invalid_lat" }, 400);
    if (lon !== undefined && (!isNum(lon) || lon < -180 || lon > 180))
      return json({ error: "invalid_lon" }, 400);
    if (isReplay !== undefined && typeof isReplay !== "boolean")
      return json({ error: "invalid_isReplay" }, 400);

    // Device clocks drift or start at 1970; fall back to server time if implausible.
    const now = Date.now();
    const tsOk = isNum(ts) && Math.abs(ts - now) < 24 * 60 * 60 * 1000;

    const source =
      typeof locationSource === "string"
        ? locationSource
        : wellId !== undefined
          ? "selected_well"
          : lat !== undefined && lon !== undefined
            ? "phone"
            : "none";

    const result = await ctx.runMutation(internal.readings.ingest, {
      deviceId,
      ts: tsOk ? (ts as number) : now,
      raw,
      corrected,
      wellId: wellId as string | undefined,
      lat: lat as number | undefined,
      lon: lon as number | undefined,
      locationSource: source,
      isReplay: isReplay === true,
    });

    return json({ ok: true, ...result }, 201);
  }),
});

// Cheap reachability check the ESP32 / hotspot test can hit first (section 8.4).
http.route({
  path: "/health",
  method: "GET",
  handler: httpAction(async () => json({ ok: true, now: Date.now() })),
});

export default http;
