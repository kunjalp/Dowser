import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";
import {
  locationSourceValidator,
  outcomeValidator,
  scorePartsValidator,
  statusSourceValidator,
  statusValidator,
} from "./constants";

/**
 * Dowser data model, conformed to Master Plan section 5 (the single source of truth).
 * Convex adds _id and _creationTime to every document automatically.
 */

/** Candidate record (pipeline -> Convex -> app). Field names are the agreed contract. */
export const candidateFields = {
  id: v.string(), // stable string id, e.g. "kern-0042" (fake ones start with "fake-")
  lat: v.number(),
  lon: v.number(),
  score: v.number(), // weighted score from scoreParts with the default weights
  scoreParts: scorePartsValidator,
  editionsSeen: v.array(v.number()), // map years the symbol appears on, e.g. [1947, 1962]
  nearestDocumentedId: v.optional(v.string()), // documentedWells.apiNumber
  nearestDocumentedDistM: v.optional(v.number()),
  distToHomeM: v.optional(v.number()),
  distToSchoolM: v.optional(v.number()),
  distToWaterM: v.optional(v.number()),
  buildingsNear250m: v.optional(v.number()),
  status: statusValidator,
  brief: v.optional(v.string()),
  evidenceImages: v.array(v.object({ year: v.number(), url: v.string() })),
  quadName: v.string(),
  detectionId: v.optional(v.string()),
  // "calgem_idle" = a well the state already lists as Idle (pipeline/idle_wells.py), not a detection.
  source: v.optional(v.union(v.literal("model"), v.literal("ground_truth"), v.literal("calgem_idle"))),
  wellStatus: v.optional(v.string()), // CalGEM status, idle lane only
  operator: v.optional(v.string()), // CalGEM operator, idle lane only
  apiNumber: v.optional(v.string()), // CalGEM API number, idle lane only
};

export default defineSchema({
  // Written by the ingestion script. One row per map tile.
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
    bounds: v.object({
      minLon: v.number(),
      minLat: v.number(),
      maxLon: v.number(),
      maxLat: v.number(),
    }),
  })
    .index("by_tileId", ["tileId"])
    .index("by_mapYear", ["mapYear"]),

  // Written by the detector pipeline.
  detections: defineTable({
    detectionId: v.string(),
    tileId: v.string(),
    mapYear: v.number(),
    box: v.object({ x: v.number(), y: v.number(), w: v.number(), h: v.number() }),
    className: v.string(),
    confidence: v.number(),
    lat: v.number(),
    lon: v.number(),
    cropUrl: v.optional(v.string()), // small symbol crop
    source: v.union(v.literal("model"), v.literal("ground_truth")),
  })
    .index("by_detectionId", ["detectionId"])
    .index("by_tileId", ["tileId"]),

  // Loaded from CalGEM (158k rows for Kern). Shape matches pipeline/load_calgem.py output.
  documentedWells: defineTable({
    apiNumber: v.string(), // 10-digit string; keep leading zeros
    lat: v.optional(v.number()), // absent when CalGEM has no usable coordinates
    lon: v.optional(v.number()),
    status: v.string(), // CalGEM WellStatus: Active, Idle, Plugged, Canceled, ...
    locationQuality: v.union(v.literal("good"), v.literal("uncertain")),
    wellType: v.optional(v.string()),
    operator: v.optional(v.string()),
  })
    .index("by_apiNumber", ["apiNumber"])
    .index("by_locationQuality", ["locationQuality"]),

  candidates: defineTable(candidateFields)
    .index("by_candidate_id", ["id"])
    .index("by_score", ["score"])
    .index("by_status", ["status"])
    .index("by_source", ["source"]),

  // Sensor -> Convex. candidateId is attached by the phone pairing (see pairings).
  readings: defineTable({
    deviceId: v.string(),
    value: v.number(), // relative, baseline-corrected
    raw: v.number(),
    timestamp: v.number(), // device ms since epoch, or server time if the device clock is bad
    receivedAt: v.number(), // server ms; used for the sensor-to-map latency check
    candidateId: v.optional(v.string()),
    lat: v.optional(v.number()),
    lon: v.optional(v.number()),
    locationSource: locationSourceValidator,
    isReplay: v.boolean(),
  })
    .index("by_receivedAt", ["receivedAt"])
    .index("by_candidate_receivedAt", ["candidateId", "receivedAt"]),

  // The verifier's logged finding from the Field View.
  fieldChecks: defineTable({
    candidateId: v.string(),
    outcome: outcomeValidator,
    note: v.optional(v.string()),
    photoId: v.optional(v.id("_storage")),
    deviceId: v.optional(v.string()),
    lat: v.optional(v.number()),
    lon: v.optional(v.number()),
    createdAt: v.number(),
  }).index("by_candidateId", ["candidateId"]),

  // Every status change is logged here.
  statusEvents: defineTable({
    candidateId: v.string(),
    from: statusValidator,
    to: statusValidator,
    source: statusSourceValidator,
    note: v.optional(v.string()),
    createdAt: v.number(),
  })
    .index("by_candidateId", ["candidateId"])
    .index("by_createdAt", ["createdAt"]),

  // Which candidate a handheld is currently pointed at. Set by the phone.
  // deviceId "any" pairs whatever device posts next.
  pairings: defineTable({
    deviceId: v.string(),
    candidateId: v.string(),
    lat: v.optional(v.number()), // phone location
    lon: v.optional(v.number()),
    updatedAt: v.number(),
  }).index("by_deviceId", ["deviceId"]),

  // Claude briefs: top ~50, 80-120 words, four parts. Regenerate only when inputHash changes.
  briefs: defineTable({
    candidateId: v.string(),
    text: v.string(),
    generatedAt: v.number(),
    inputHash: v.string(),
  }).index("by_candidateId", ["candidateId"]),
});
