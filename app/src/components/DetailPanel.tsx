"use client";

import { useMutation, useQuery } from "convex/react";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/convexApi";
import { LaneBadge, ReviewBadges } from "./Sidebar";
import { PART_LABELS, STATUSES, STATUS_META, dotColor, isRejected, laneOf } from "../lib/types";
import type { Candidate, Reading, ScoreParts, Status } from "../lib/types";

type StatusEvent = { _id: string; from: Status; to: Status; source: string; note?: string; createdAt: number };

const SOURCE_LABEL: Record<string, string> = { field: "Field check", analyst: "Analyst", auto: "Auto-confirmed", pipeline: "Pipeline" };

function ago(ts: number, now: number): string {
  const s = Math.max(0, Math.round((now - ts) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

const fmtM = (m?: number) =>
  m === undefined ? "n/a" : m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;

function ScoreBars({ parts, handLabeled, hide = [] }: { parts: ScoreParts; handLabeled?: boolean; hide?: (keyof ScoreParts)[] }) {
  return (
    <div className="parts">
      {(Object.keys(PART_LABELS) as (keyof ScoreParts)[]).filter((k) => !hide.includes(k)).map((k) => (
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

export function Sparkline({ values, sim }: { values: number[]; sim?: boolean }) {
  if (values.length < 2) return <div className="muted small">Waiting for readings…</div>;
  const w = 300;
  const h = 64;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const pts = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / (max - min || 1)) * (h - 6) - 3}`)
    .join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className={`spark ${sim ? "sim-data" : ""}`} role="img" aria-label="Recent sensor readings">
      <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

function StateRecord({ c }: { c: Candidate }) {
  return (
    <>
      <dl className="facts">
        <dt>Status</dt>
        <dd>{c.wellStatus ?? "n/a"}</dd>
        <dt>Operator</dt>
        <dd>{c.operator ?? "n/a"}</dd>
        <dt>API number</dt>
        <dd>{c.apiNumber ?? "n/a"}</dd>
      </dl>
      <p className="muted small">The state knows about this well. It is listed as idle (not producing, not plugged).</p>
    </>
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
            <figcaption>
              {im.year}
              {/\/gt_[^/]*$/.test(im.url) ? " · hand label" : ""}
            </figcaption>
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
  const events = useQuery(api.candidates.eventsFor, candidate ? { id: candidate.id } : "skip") as StatusEvent[] | undefined;
  const setStatus = useMutation(api.candidates.setStatus);
  const [tipOff, setTipOff] = useState(false); // Esc hides the confidence tooltip (WCAG 1.4.13)
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(t);
  }, []);

  // A newly selected candidate starts at the top (brief first), not where the last one was scrolled.
  const bodyRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (candidate) bodyRef.current?.scrollTo({ top: 0 });
  }, [candidate?.id]);

  const chrono = readings ? [...readings].reverse() : [];
  const anyReplay = chrono.some((r) => r.isReplay);
  // Open the sensor block by itself while readings are arriving (last 10 minutes).
  const recentReadings = chrono.length > 0 && now - chrono[chrono.length - 1].receivedAt < 10 * 60 * 1000;
  const idle = c ? laneOf(c) === "idle" : false;
  // Rejected in review: evidence and facts stay for the record; no brief, rank, confidence or queueing.
  const rejected = c ? isRejected(c) : false;

  return (
    <aside className={`detail ${candidate ? "open" : ""}`} aria-hidden={!candidate}>
      {c && (
        <>
          <header className="detail-head">
            <div>
              <h2>
                <span className="dot" style={{ background: dotColor(c) }} /> {c.id}
              </h2>
              <div className="detail-badges">
                <LaneBadge lane={laneOf(c)} />
                <ReviewBadges c={c} />
              </div>
              {rejected && <p className="reject-note">Rejected in review: {c.review!.reason}</p>}
              <p className="muted">
                {c.quadName} quad · {rejected ? "not ranked" : `rank ${c.rank}`} · {c.lat.toFixed(4)},{" "}
                {c.lon.toFixed(4)}
              </p>
            </div>
            <button className="icon-btn" onClick={onClose} aria-label="Close details">
              ✕
            </button>
          </header>

          <div className="detail-body" ref={bodyRef}>
            <div className="detail-top">
              <div className="detail-top-pills">
                <div className="badge big" style={{ ["--c" as string]: STATUS_META[c.status].color }}>
                  {STATUS_META[c.status].label}
                  {c.status === "candidate" ? ` · ${c.score.toFixed(2)}` : ""}
                </div>
                {/* idle wells are state records, not detected symbols: no map confidence */}
                {!idle && !rejected && (
                  <span
                    className={`conf-pill ${tipOff ? "tip-off" : ""}`}
                    tabIndex={0}
                    aria-describedby="conf-tip"
                    onKeyDown={(e) => e.key === "Escape" && setTipOff(true)}
                    onBlur={() => setTipOff(false)}
                    onMouseLeave={() => setTipOff(false)}
                  >
                    Map confidence {Math.round(c.scoreParts.confidence * 100)}%
                    <span id="conf-tip" role="tooltip" className="conf-tip">
                      Combines detector confidence with how many map editions show the symbol.
                    </span>
                  </span>
                )}
              </div>
              {c.status === "candidate" && !rejected && (
                <button
                  className="action queue-btn"
                  style={{ ["--c" as string]: STATUS_META.queued.color }}
                  onClick={() => setStatus({ id: c.id, status: "queued", source: "analyst" })}
                >
                  Queue for field check
                </button>
              )}
            </div>

            {!rejected && (
              <section>
                <h3>Brief</h3>
                <p className="brief">{c.brief ?? <span className="muted">No brief yet.</span>}</p>
              </section>
            )}

            {idle ? (
              <section>
                <h3>State record</h3>
                <StateRecord c={c} />
              </section>
            ) : (
              <section>
                <h3>Evidence</h3>
                <Evidence images={c.evidenceImages} />
              </section>
            )}

            <section>
              <h3>Score {c.score.toFixed(2)}</h3>
              <ScoreBars
                parts={c.scoreParts}
                handLabeled={c.source === "ground_truth"}
                hide={idle ? ["undocumented"] : []}
              />
              <p className="muted small">
                {idle
                  ? "Ranked by how close it is to people and water. No leak has been verified."
                  : "Candidate undocumented well, not a verified well."}
              </p>
            </section>

            <section>
              <h3>Nearby</h3>
              <dl className="facts">
                {!idle && (
                  <>
                    <dt>Nearest documented well</dt>
                    <dd>
                      {fmtM(c.nearestDocumentedDistM)}
                      {c.nearestDocumentedId ? ` (${c.nearestDocumentedId})` : ""}
                    </dd>
                  </>
                )}
                <dt>Nearest home</dt>
                <dd>{fmtM(c.distToHomeM)}</dd>
                <dt>Nearest school</dt>
                <dd>{fmtM(c.distToSchoolM)}</dd>
                <dt>Nearest water</dt>
                <dd>{fmtM(c.distToWaterM)}</dd>
                <dt>Buildings within 250 m</dt>
                <dd>{c.buildingsNear250m ?? "n/a"}</dd>
                {!idle && (
                  <>
                    <dt>Map editions seen</dt>
                    <dd>{c.editionsSeen.length ? [...c.editionsSeen].sort().join(", ") : "n/a"}</dd>
                  </>
                )}
              </dl>
            </section>

            <details className="fold" open={recentReadings}>
              <summary>
                Live sensor
                <span className="fold-meta">
                  {chrono.length
                    ? `${chrono.length} readings · latest ${chrono[chrono.length - 1].value.toFixed(0)}`
                    : "no readings"}
                </span>
              </summary>
              {anyReplay && <div className="sim">Simulated sensor data</div>}
              <Sparkline values={chrono.map((r) => r.value)} sim={anyReplay} />
            </details>

            {events && events.length > 0 && (
              <details className="fold">
                <summary>
                  Activity<span className="fold-meta">{events.length}</span>
                </summary>
                <ul className="timeline">
                  {events.map((e) => (
                    <li key={e._id}>
                      <span className="tl-dot" style={{ background: STATUS_META[e.to].color }} />
                      <span>
                        <span className="tl-main">
                          {STATUS_META[e.from].label} → {STATUS_META[e.to].label}
                        </span>
                        <span className="tl-sub">
                          {" "}
                          · {SOURCE_LABEL[e.source] ?? e.source} · {ago(e.createdAt, now)}
                          {e.note ? ` · ${e.note}` : ""}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            <section>
              <h3>Set status</h3>
              <div className="actions">
                {STATUSES.filter((s) => s !== c.status && !(rejected && s === "queued")).map((s: Status) => (
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
