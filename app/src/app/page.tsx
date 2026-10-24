"use client";

import { useQuery } from "convex/react";
import { useEffect, useMemo, useRef, useState } from "react";
import DetailPanel from "../components/DetailPanel";
import MapView from "../components/MapView";
import PrioritySliders, { DEFAULT_WEIGHTS } from "../components/PrioritySliders";
import MapFilters, { DEFAULT_FILTERS, applyFilters } from "../components/MapFilters";
import type { MapFilterState } from "../components/MapFilters";
import Sidebar from "../components/Sidebar";
import { api } from "../lib/convexApi";
import { STATUS_META, isFake } from "../lib/types";
import type { Candidate, ScoreParts, Status } from "../lib/types";

// Always-on disclosure: the demo's sensor reading comes from a knob, not real gas.
function SimInputPill() {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      btnRef.current?.focus();
    };
    const onDown = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [open]);

  return (
    <div className="sim-input" ref={wrapRef}>
      <button
        ref={btnRef}
        type="button"
        className="sim-input-btn"
        aria-expanded={open}
        aria-controls="sim-input-pop"
        onClick={() => setOpen((o) => !o)}
      >
        Simulated sensor input
      </button>
      <div id="sim-input-pop" className="sim-input-pop" role="region" aria-label="About the simulated sensor" hidden={!open}>
        Flammable gas isn&apos;t allowed at the venue, so a knob on the handheld simulates the sensor reading. The
        firmware, data path and live map updates are the same as with a real methane sensor.
      </div>
    </div>
  );
}

export default function CommandMap() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<Status[]>([]); // empty = all statuses

  const [weights, setWeights] = useState<ScoreParts>(DEFAULT_WEIGHTS);
  const customWeights = (Object.keys(DEFAULT_WEIGHTS) as (keyof ScoreParts)[]).some(
    (k) => weights[k] !== DEFAULT_WEIGHTS[k],
  );
  const allZero = Object.values(weights).every((w) => w === 0);

  // Live from Convex: re-renders on any status change or new candidate.
  // Custom weights re-rank on the server without writing anything.
  const rows = useQuery(api.candidates.ranked, {
    statuses: filter.length ? filter : undefined,
    weights: customWeights && !allZero ? weights : undefined,
    limit: 1000,
  }) as Candidate[] | undefined;

  const [mf, setMf] = useState<MapFilterState>(DEFAULT_FILTERS);
  const shown = useMemo(() => (rows ? applyFilters(rows, mf) : undefined), [rows, mf]);

  const anyFake = !!rows?.some(isFake);

  // Live changes: when Convex pushes a new status for a candidate (field check, auto-confirm,
  // analyst), flash its row, pulse its map dot, and show a toast. The first load is not a change.
  const prevStatus = useRef<Map<string, Status> | null>(null);
  const [changed, setChanged] = useState<string[]>([]);
  const [toast, setToast] = useState<{ id: string; to: Status; rank: number } | null>(null);
  const [pulse, setPulse] = useState<{ id: string; n: number } | null>(null);
  useEffect(() => {
    if (!rows) return;
    const prev = prevStatus.current;
    prevStatus.current = new Map(rows.map((r) => [r.id, r.status]));
    if (!prev) return;
    const moved = rows.filter((r) => prev.has(r.id) && prev.get(r.id) !== r.status);
    if (moved.length === 0) return;
    // Most important change wins the toast: leaking first, then best rank.
    const top = [...moved].sort(
      (a, b) =>
        Number(b.status === "confirmed_leaking") - Number(a.status === "confirmed_leaking") || a.rank - b.rank,
    )[0];
    setChanged(moved.map((r) => r.id));
    setToast({ id: top.id, to: top.status, rank: top.rank });
    setPulse((p) => ({ id: top.id, n: (p?.n ?? 0) + 1 }));
    const t1 = setTimeout(() => setChanged([]), 3200);
    const t2 = setTimeout(() => setToast(null), 9000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [rows]);

  const selected = useMemo(() => shown?.find((r) => r.id === selectedId) ?? null, [shown, selectedId]);

  return (
    <main className="shell">
      <Sidebar
        rows={shown}
        selectedId={selectedId}
        onSelect={setSelectedId}
        filter={filter}
        onFilter={setFilter}
        extra={
          <>
            <MapFilters value={mf} onChange={setMf} />
            <PrioritySliders weights={weights} onChange={setWeights} />
          </>
        }
        reranked={customWeights}
        changedIds={changed}
      />
      <section className="map-wrap">
        {anyFake && (
          <div className="demo-banner" role="status">
            <strong>Simulated sensor data</strong> / not field readings
          </div>
        )}
        <SimInputPill />
        {toast && (
          <button
            className={`live-toast ${toast.to === "confirmed_leaking" ? "leak" : ""}`}
            onClick={() => {
              setSelectedId(toast.id);
              setToast(null);
            }}
          >
            <strong>{toast.id}</strong> {STATUS_META[toast.to].label.toLowerCase()}
            {toast.rank === 1 ? " · now #1" : ` · rank ${toast.rank}`}
            <span className="live-toast-go">Show</span>
          </button>
        )}
        <MapView rows={shown ?? []} selectedId={selectedId} onSelect={setSelectedId} pulse={pulse} />
        <DetailPanel candidate={selected} onClose={() => setSelectedId(null)} />
      </section>
    </main>
  );
}
