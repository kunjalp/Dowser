"use client";

import { useQuery } from "convex/react";
import { useMemo, useState } from "react";
import DetailPanel from "../components/DetailPanel";
import MapView from "../components/MapView";
import PrioritySliders, { DEFAULT_WEIGHTS } from "../components/PrioritySliders";
import Sidebar from "../components/Sidebar";
import { api } from "../lib/convexApi";
import { isFake } from "../lib/types";
import type { Candidate, ScoreParts, Status } from "../lib/types";

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

  const anyFake = !!rows?.some(isFake);

  const selected = useMemo(() => rows?.find((r) => r.id === selectedId) ?? null, [rows, selectedId]);

  return (
    <main className="shell">
      <Sidebar
        rows={rows}
        selectedId={selectedId}
        onSelect={setSelectedId}
        filter={filter}
        onFilter={setFilter}
        extra={<PrioritySliders weights={weights} onChange={setWeights} />}
        reranked={customWeights}
      />
      <section className="map-wrap">
        {anyFake && (
          <div className="demo-banner" role="status">
            <strong>Demo data</strong> · simulated candidates
          </div>
        )}
        <MapView rows={rows ?? []} selectedId={selectedId} onSelect={setSelectedId} />
        <DetailPanel candidate={selected} onClose={() => setSelectedId(null)} />
      </section>
    </main>
  );
}
