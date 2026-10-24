import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

/**
 * Dowser data model (PRD 5.2).
 * Convex adds _id and _creationTime to every document automatically.
 */

const bounds = v.object({
  minLon: v.number(),
  minLat: v.number(),
  maxLon: v.number(),
  maxLat: v.number(),
});

export default defineSchema({
  // Written by the ingestion script (FR-1.3). One row per map tile.
  tiles: defineTable({
    tileId: v.string(),
    sheetName: v.string(),
    mapYear: v.number(),
    // Affine pixel -> world transform [a, b, c, d, e, f] (rasterio order),
    // in the sheet's own CRS. Never reuse one sheet's transform for another.
    transform: v.array(v.number()),
    crs: v.string(), // e.g. "EPSG:26911"
    widthPx: v.number(),
    heightPx: v.number(),
    bounds,
  })
    .index("by_tileId", ["tileId"])
    .index("by_mapYear", ["mapYear"]),

  // Written by the detector pipeline (FR-2.4, FR-3.1).
  detections: defineTable({
    detectionId: v.string(),
    tileId: v.string(),
    box: v.object({ x: v.number(), y: v.number(), w: v.number(), h: v.number() }),
    className: v.string(),
    confidence: v.number(),
    lat: v.number(),
    lon: v.number(),
    // FR-2.7: lets the pipeline run from hand-labeled ground truth.
    source: v.union(v.literal("model"), v.literal("ground_truth")),
  })
    .index("by_detectionId", ["detectionId"])
    .index("by_tileId", ["tileId"]),

  // Written by the CalGEM loader / Apify Actor (FR-4.1, FR-A4).
  documentedWells: defineTable({
    apiNumber: v.string(), // string: API numbers have leading zeros
    lat: v.optional(v.number()), // absent when CalGEM has no usable coordinates
    lon: v.optional(v.number()),
    status: v.string(),
    // FR-4.5: "uncertain" wells are excluded from the match and counted.
    locationQuality: v.union(v.literal("good"), v.literal("uncertain")),
    wellType: v.optional(v.string()),
    operator: v.optional(v.string()),
  })
    .index("by_apiNumber", ["apiNumber"])
    .index("by_locationQuality", ["locationQuality"]),

  // Written by cross-check and ranking (FR-4.3, FR-5.x, FR-8.3).
  candidates: defineTable({
    candidateId: v.string(),
    detectionId: v.string(),
    lat: v.number(),
    lon: v.number(),
    nearestDocumentedM: v.number(),
    nearestSchoolM: v.optional(v.number()),
    buildingsNear: v.number(),
    mapConfidence: v.number(), // C in the score formula, 0..1
    mapYears: v.optional(v.array(v.number())),
    fieldStatus: v.union(v.literal("candidate"), v.literal("field-confirmed leak")),
    proximityRisk: v.optional(v.number()), // P, 0..1
    score: v.number(),
    rank: v.optional(v.number()),
  })
    .index("by_candidateId", ["candidateId"])
    .index("by_detectionId", ["detectionId"])
    .index("by_score", ["score"])
    .index("by_fieldStatus", ["fieldStatus"]),

  // Written by the ESP32 or the replay script via the HTTP ingest (FR-7.3).
  readings: defineTable({
    readingId: v.string(),
    deviceId: v.string(),
    ts: v.number(), // device-reported ms since epoch (or server time if the device had no clock)
    receivedAt: v.number(), // server ms since epoch; used for the 5 s latency check
    raw: v.number(),
    corrected: v.number(), // baseline-corrected
    wellId: v.optional(v.string()), // candidateId the reading is pinned to
    lat: v.optional(v.number()),
    lon: v.optional(v.number()),
    locationSource: v.string(), // "selected_well" | "phone" | "none"
    isReplay: v.boolean(),
  })
    .index("by_readingId", ["readingId"])
    .index("by_receivedAt", ["receivedAt"])
    .index("by_well_receivedAt", ["wellId", "receivedAt"]),

  // Written by the Claude brief generator (FR-6.1, FR-6.3).
  briefs: defineTable({
    candidateId: v.string(),
    text: v.string(),
    generatedAt: v.number(),
    inputHash: v.string(), // regenerate only when candidate fields change
  }).index("by_candidateId", ["candidateId"]),
});
