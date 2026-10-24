"use client";

import type { Candidate } from "../lib/types";

export type MapFilterState = {
  min: number; // 0..100, rank score percent
  max: number;
  nearHomes: boolean;
  nearSchools: boolean;
  fieldConfirmed: boolean;
};

export const NEAR_HOME_M = 500;
export const NEAR_SCHOOL_M = 1000;
export const DEFAULT_FILTERS: MapFilterState = { min: 0, max: 100, nearHomes: false, nearSchools: false, fieldConfirmed: false };

export const filtersActive = (f: MapFilterState) =>
  f.min > 0 || f.max < 100 || f.nearHomes || f.nearSchools || f.fieldConfirmed;

export function applyFilters(rows: Candidate[], f: MapFilterState): Candidate[] {
  if (!filtersActive(f)) return rows;
  return rows.filter((c) => {
    const pct = c.rankScore * 100;
    if (pct < f.min || pct > f.max) return false;
    if (f.nearHomes && !(c.distToHomeM != null && c.distToHomeM <= NEAR_HOME_M)) return false;
    if (f.nearSchools && !(c.distToSchoolM != null && c.distToSchoolM <= NEAR_SCHOOL_M)) return false;
    if (f.fieldConfirmed && c.status !== "confirmed_leaking" && c.status !== "confirmed_not_leaking") return false;
    return true;
  });
}

export default function MapFilters({ value, onChange }: { value: MapFilterState; onChange: (v: MapFilterState) => void }) {
  const set = (p: Partial<MapFilterState>) => onChange({ ...value, ...p });
  const toggle = (k: "nearHomes" | "nearSchools" | "fieldConfirmed", label: string) => (
    <button
      type="button"
      className={`mf-toggle ${value[k] ? "on" : ""}`}
      aria-pressed={value[k]}
      onClick={() => set({ [k]: !value[k] })}
    >
      {label}
    </button>
  );
  return (
    <div className="map-filters">
      <div className="mf-head">
        <h3>Filters</h3>
        {filtersActive(value) && (
          <button type="button" className="link-btn" onClick={() => onChange(DEFAULT_FILTERS)}>
            Reset
          </button>
        )}
      </div>
      <div className="mf-range">
        <label>
          <span>Score from {value.min}%</span>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={value.min}
            onChange={(e) => set({ min: Math.min(Number(e.target.value), value.max) })}
          />
        </label>
        <label>
          <span>to {value.max}%</span>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={value.max}
            onChange={(e) => set({ max: Math.max(Number(e.target.value), value.min) })}
          />
        </label>
      </div>
      <div className="mf-toggles">
        {toggle("nearHomes", `Near homes ≤${NEAR_HOME_M} m`)}
        {toggle("nearSchools", `Near schools ≤${NEAR_SCHOOL_M / 1000} km`)}
        {toggle("fieldConfirmed", "Field-confirmed")}
      </div>
    </div>
  );
}
