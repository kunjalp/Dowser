"use client";

import type { ScoreParts } from "../lib/types";

export const DEFAULT_WEIGHTS: ScoreParts = {
  confidence: 0.2,
  undocumented: 0.2,
  people: 0.3,
  water: 0.1,
  field: 0.2,
};

const SLIDERS: { key: keyof ScoreParts; label: string; hint: string }[] = [
  { key: "people", label: "People nearby", hint: "Homes, schools" },
  { key: "water", label: "Water nearby", hint: "Streams, aquifers" },
  { key: "undocumented", label: "Missing from records", hint: "Not in CalGEM" },
  { key: "confidence", label: "Map confidence", hint: "Detector certainty" },
];

type Props = { weights: ScoreParts; onChange: (w: ScoreParts) => void };

export default function PrioritySliders({ weights, onChange }: Props) {
  const isDefault = (Object.keys(DEFAULT_WEIGHTS) as (keyof ScoreParts)[]).every(
    (k) => weights[k] === DEFAULT_WEIGHTS[k],
  );
  return (
    <section className="priority" aria-label="Priority sliders">
      <div className="priority-head">
        <span>What matters most?</span>
        <button className="link-btn" disabled={isDefault} onClick={() => onChange(DEFAULT_WEIGHTS)}>
          Reset
        </button>
      </div>
      {SLIDERS.map((s) => (
        <label key={s.key} className="slider" title={s.hint}>
          <span className="slider-label">{s.label}</span>
          <input
            type="range"
            min={0}
            max={100}
            value={Math.round(weights[s.key] * 100)}
            onChange={(e) => onChange({ ...weights, [s.key]: Number(e.target.value) / 100 })}
          />
          <span className="slider-val">{Math.round(weights[s.key] * 100)}</span>
        </label>
      ))}
    </section>
  );
}
