"use client";

import { useMutation, useQuery } from "convex/react";
import { useRef, useState } from "react";
import { api } from "../lib/convexApi";
import { PART_LABELS, STATUSES, STATUS_META, dotColor } from "../lib/types";
import type { Candidate, Reading, ScoreParts, Status } from "../lib/types";

const fmtM = (m?: number) =>
  m === undefined ? "n/a" : m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;

function ScoreBars({ parts, handLabeled }: { parts: ScoreParts; handLabeled?: boolean }) {
  return (
    <div className="parts">
      {(Object.keys(PART_LABELS) as (keyof ScoreParts)[]).map((k) => (
        <div key={k} className="part">
          <span className="part-label">
            {PART_LABELS[k]}
            {k === "confidence" && handLabeled && (
              <em className="tag" title="Hand-labeled symbol. Its detection confidence is fixed at 1.0, so this bar is not a model score; it also reflects how many map editions show the symbol.">
                hand-labeled
              </em>
            )}
          </span>
          <span className="bar">
            <span style={{ width: `${Math.round(parts[k] * 100)}%` }} />
          </span>
          <span className="part-val">{parts[k].toFixed(2)}</span>
        </div>
      ))}
    </div>
  );
}

export function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return <div className="muted small">Waiting for readings…</div>;
  const w = 300;
  const h = 64;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const pts = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / (max - min || 1)) * (h - 6) - 3}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="spark" role="img" aria-label="Recent sensor readings">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

function Evidence({ images }: { images: Candidate["evidenceImages"] }) {
  const [failed, setFailed] = useState<Record<string, boolean>>({});
  if (images.length === 0) return <div className="muted small">No evidence crops yet.</div>;
  return (
    <div className="evidence">
      {[...images]
        .sort((a, b) => a.year - b.year)
        .map((im) => (
          <figure key={`${im.year}-${im.url}`}>
            {failed[im.url] ? (
              <div className="ph">no image yet</div>
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={im.url} alt={`Symbol on the ${im.year} map`} onError={() => setFailed((f) => ({ ...f, [im.url]: true }))} />
            )}
            <figcaption>{im.year}</figcaption>
          </figure>
        ))}
    </div>
  );
}

export default function DetailPanel({
  candidate,
  onClose,
}: {
  candidate: Candidate | null;
  onClose: () => void;
}) {
  const last = useRef<Candidate | null>(null);
  if (candidate) last.current = candidate;
  const c = candidate ?? last.current; // keep content while the panel slides out

  const readings = useQuery(
    api.readings.recent,
    candidate ? { candidateId: candidate.id, limit: 60 } : "skip",
  ) as Reading[] | undefined;
  const setStatus = useMutation(api.candidates.setStatus);

  const chrono = readings ? [...readings].reverse() : [];
  const anyReplay = chrono.some((r) => r.isReplay);

  return (
    <aside className={`detail ${candidate ? "open" : ""}`} aria-hidden={!candidate}>
      {c && (
        <>
          <header className="detail-head">
            <div>
              <h2>
                <span className="dot" style={{ background: dotColor(c) }} /> {c.id}
              </h2>
              <p className="muted">
                {c.quadName} quad · rank {c.rank} · {c.lat.toFixed(4)}, {c.lon.toFixed(4)}
              </p>
            </div>
            <button className="icon-btn" onClick={onClose} aria-label="Close details">
              ✕
            </button>
          </header>

          <div className="detail-body">
            <div className="badge big" style={{ ["--c" as string]: STATUS_META[c.status].color }}>
              {STATUS_META[c.status].label}
            </div>

            <section>
              <h3>Score {c.score.toFixed(2)}</h3>
              <ScoreBars parts={c.scoreParts} handLabeled={c.source === "ground_truth"} />
              <p className="muted small">Candidate undocumented well, not a verified well.</p>
            </section>

            <section>
              <h3>Nearby</h3>
              <dl className="facts">
                <dt>Nearest documented well</dt>
                <dd>
                  {fmtM(c.nearestDocumentedDistM)}
                  {c.nearestDocumentedId ? ` (${c.nearestDocumentedId})` : ""}
                </dd>
                <dt>Nearest home</dt>
                <dd>{fmtM(c.distToHomeM)}</dd>
                <dt>Nearest school</dt>
                <dd>{fmtM(c.distToSchoolM)}</dd>
                <dt>Nearest water</dt>
                <dd>{fmtM(c.distToWaterM)}</dd>
                <dt>Buildings within 250 m</dt>
                <dd>{c.buildingsNear250m ?? "n/a"}</dd>
                <dt>Map editions seen</dt>
                <dd>{c.editionsSeen.length ? [...c.editionsSeen].sort().join(", ") : "n/a"}</dd>
              </dl>
            </section>

            <section>
              <h3>Evidence</h3>
              <Evidence images={c.evidenceImages} />
            </section>

            <section>
              <h3>Brief</h3>
              <p className="brief">{c.brief ?? <span className="muted">No brief yet.</span>}</p>
            </section>

            <section>
              <h3>Field readings</h3>
              {anyReplay && <div className="sim">Simulated sensor data</div>}
              <Sparkline values={chrono.map((r) => r.value)} />
              <p className="muted small">
                {chrono.length} readings{chrono.length ? ` · latest ${chrono[chrono.length - 1].value.toFixed(1)}` : ""}
              </p>
            </section>

            <section>
              <h3>Set status</h3>
              <div className="actions">
                {STATUSES.filter((s) => s !== c.status).map((s: Status) => (
                  <button
                    key={s}
                    className="action"
                    style={{ ["--c" as string]: STATUS_META[s].color }}
                    onClick={() => setStatus({ id: c.id, status: s, source: "analyst" })}
                  >
                    {s === "candidate" ? "Reset to candidate" : STATUS_META[s].label}
                  </button>
                ))}
              </div>
            </section>
          </div>
        </>
      )}
    </aside>
  );
}
