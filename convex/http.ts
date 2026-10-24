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
 * POST /ingest/reading
 * Header: X-Dowser-Token: <INGEST_TOKEN>
 * Body (Master Plan section 5):
 *   { deviceId, value, raw?, timestamp?, candidateId?, lat?, lon?, locationSource?, isReplay? }
 *
 *  - value: relative reading above baseline (required)
 *  - raw: raw ADC value; defaults to value if omitted
 *  - timestamp: optional; an ESP32 without NTP has no wall clock. The server always
 *    records receivedAt, which is what the latency check uses.
 *  - candidateId/lat/lon: usually omitted by the device. The phone's pairing supplies them.
 * Older field names are still accepted: corrected -> value, ts -> timestamp, wellId -> candidateId.
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
    if (typeof body !== "object" || body === null) return json({ error: "invalid_json" }, 400);

    const deviceId = body.deviceId;
    const value = body.value ?? body.corrected;
    const raw = body.raw ?? value;
    const timestamp = body.timestamp ?? body.ts;
    const candidateId = body.candidateId ?? body.wellId;
    const { lat, lon, locationSource, isReplay } = body;

    if (typeof deviceId !== "string" || deviceId.length === 0 || deviceId.length > 64)
      return json({ error: "invalid_deviceId" }, 400);
    if (!isNum(value)) return json({ error: "invalid_value" }, 400);
    if (!isNum(raw)) return json({ error: "invalid_raw" }, 400);
    if (timestamp !== undefined && !isNum(timestamp)) return json({ error: "invalid_timestamp" }, 400);
    if (candidateId !== undefined && (typeof candidateId !== "string" || candidateId.length > 64))
      return json({ error: "invalid_candidateId" }, 400);
    if (lat !== undefined && (!isNum(lat) || lat < -90 || lat > 90))
      return json({ error: "invalid_lat" }, 400);
    if (lon !== undefined && (!isNum(lon) || lon < -180 || lon > 180))
      return json({ error: "invalid_lon" }, 400);
    if (
      locationSource !== undefined &&
      locationSource !== "candidate" &&
      locationSource !== "phone" &&
      locationSource !== "none"
    )
      return json({ error: "invalid_locationSource" }, 400);
    if (isReplay !== undefined && typeof isReplay !== "boolean")
      return json({ error: "invalid_isReplay" }, 400);

    // Device clocks drift or start at 1970; fall back to server time if implausible.
    const now = Date.now();
    const tsOk = isNum(timestamp) && Math.abs(timestamp - now) < 24 * 60 * 60 * 1000;

    const result = await ctx.runMutation(internal.readings.ingest, {
      deviceId,
      value,
      raw,
      timestamp: tsOk ? timestamp : now,
      candidateId: candidateId as string | undefined,
      lat: lat as number | undefined,
      lon: lon as number | undefined,
      locationSource: locationSource as "candidate" | "phone" | "none" | undefined,
      isReplay: isReplay === true,
    });

    return json({ ok: true, ...result }, 201);
  }),
});

// Cheap reachability check the ESP32 / hotspot test can hit first (no token needed).
http.route({
  path: "/health",
  method: "GET",
  handler: httpAction(async () => json({ ok: true, now: Date.now() })),
});

export default http;
