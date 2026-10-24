import { v } from "convex/values";

/** Status values, exactly as locked in Master Plan section 5. */
export const statusValidator = v.union(
  v.literal("candidate"),
  v.literal("queued"),
  v.literal("confirmed_leaking"),
  v.literal("confirmed_not_leaking"),
  v.literal("no_well"),
  v.literal("mislocated"),
);

/** What a verifier can log from the field (a subset of statuses). */
export const outcomeValidator = v.union(
  v.literal("confirmed_leaking"),
  v.literal("confirmed_not_leaking"),
  v.literal("no_well"),
  v.literal("mislocated"),
);

/** scoreParts: each 0..1. `field` is 1 once a leak is confirmed. */
export const scorePartsValidator = v.object({
  confidence: v.number(),
  undocumented: v.number(),
  people: v.number(),
  water: v.number(),
  field: v.number(),
});

/** Who changed a status (statusEvents.source). */
export const statusSourceValidator = v.union(
  v.literal("field"),
  v.literal("analyst"),
  v.literal("auto"),
  v.literal("pipeline"),
);

export const locationSourceValidator = v.union(
  v.literal("candidate"),
  v.literal("phone"),
  v.literal("none"),
);
