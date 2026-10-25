"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  LANES,
  LANE_META,
  STATUSES,
  STATUS_META,
  dotColor,
  isHandLabeled,
  isRejected,
  isVerified,
  laneOf,
  reasonLine,
} from "../lib/types";
import type { Candidate, Lane, Status } from "../lib/types";

type Props = {
  rows: Candidate[] | undefined;
  selectedId: string | null;
  onSelect: (id: string) => void;
  filter: Status[];
  onFilter: (s: Status[]) => void;
  extra?: ReactNode;
  reranked?: boolean;
  /** Candidates whose status just changed live; their rows flash briefly. */
  changedIds?: string[];
  /** Which list is showing; `rows` holds only that lane. */
  lane: Lane;
  onLane: (l: Lane) => void;
  /** Rows per lane after filters, for the tab labels (undefined while loading). */
  counts: Record<Lane, number | undefined>;
  /** The collapsed "Rejected in review" section of the undocumented tab is open (its map dots show). */
  rejectedOpen: boolean;
  onRejectedOpen: (open: boolean) => void;
};

export function LaneBadge({ lane }: { lane: Lane }) {
  return <span className={`lane-badge ${lane}`}>{LANE_META[lane].badge}</span>;
}

/** "Verified in review" and/or "Hand-labeled"; nothing for rejected or unreviewed candidates. */
export function ReviewBadges({ c }: { c: Candidate }) {
  if (isRejected(c)) return null;
  const r = c.review;
  return (
    <>
      {r && isVerified(c) && (
        <span className="review-badge verified" title={[r.reason, r.reviewedBy, r.reviewedAt].filter(Boolean).join(" · ")}>
          Verified in review
        </span>
      )}
      {isHandLabeled(c) && (
        <span className="review-badge hand" title="A person hand-labeled this symbol on the map">
          Hand-labeled
        </span>
      )}
    </>
  );
}

export default function Sidebar({
  rows,
  selectedId,
  onSelect,
  filter,
  onFilter,
  extra,
  reranked,
  changedIds,
  lane,
  onLane,
  counts,
  rejectedOpen,
  onRejectedOpen,
}: Props) {
  // Rank movement since the previous ordering, shown briefly after sliders move.
  const prevRanks = useRef<Map<string, number>>(new Map());
  const [moves, setMoves] = useState<Map<string, number>>(new Map());
  useEffect(() => {
    if (!rows) return;
    const m = new Map<string, number>();
    for (const r of rows) {
      const before = prevRanks.current.get(r.id);
      if (before !== undefined && before !== r.rank) m.set(r.id, before - r.rank);
    }
    prevRanks.current = new Map(rows.map((r) => [r.id, r.rank]));
    setMoves(m);
    if (m.size === 0) return;
    const t = setTimeout(() => setMoves(new Map()), 1800);
    return () => clearTimeout(t);
  }, [rows]);

  // Slide rows to their new position when the live ordering changes (a field reading moved a well).
  const liRefs = useRef(new Map<string, HTMLLIElement>());
  const prevTops = useRef(new Map<string, number>());
  useLayoutEffect(() => {
    const reduce = typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const next = new Map<string, number>();
    liRefs.current.forEach((el, id) => next.set(id, el.offsetTop));
    if (!reduce) {
      liRefs.current.forEach((el, id) => {
        const before = prevTops.current.get(id);
        const after = next.get(id);
        if (before === undefined || after === undefined || before === after) return;
        el.style.transition = "none";
        el.style.transform = `translateY(${before - after}px)`;
        void el.offsetHeight; // flush so the next change animates
        el.style.transition = "transform 420ms ease";
        el.style.transform = "";
      });
    }
    prevTops.current = next;
  }, [rows]);

  const toggle = (s: Status) =>
    onFilter(filter.includes(s) ? filter.filter((x) => x !== s) : [...filter, s]);

  // Undocumented tab: reviewed candidates on top, rejected ones in a collapsed section below.
  const split = lane === "undocumented";
  const main = rows ? (split ? rows.filter((r) => !isRejected(r)) : rows) : undefined;
  const rejected = rows && split ? rows.filter(isRejected) : [];

  const row = (c: Candidate) => {
    const rej = isRejected(c);
    const why = rej ? c.review!.reason : reasonLine(c);
    return (
      <li
        key={c._id}
        ref={(el) => {
          if (el) liRefs.current.set(c.id, el);
          else liRefs.current.delete(c.id);
        }}
      >
        <button
          className={`row ${c.id === selectedId ? "sel" : ""} ${
            c.status === "confirmed_leaking" ? "leak" : ""
          } ${changedIds?.includes(c.id) ? "flash" : ""} ${rej ? "rejected" : ""}`}
          onClick={() => onSelect(c.id)}
        >
          <span className="rank">
            {rej ? "–" : c.rank}
            {moves.get(c.id) ? (
              <em className={moves.get(c.id)! > 0 ? "up" : "down"}>
                {moves.get(c.id)! > 0 ? "▲" : "▼"}
                {Math.abs(moves.get(c.id)!)}
              </em>
            ) : null}
          </span>
          <span className="dot" style={{ background: dotColor(c) }} />
          <span className="row-main">
            <span className="row-title" title={`${c.quadName} · ${c.id}`}>
              <span className="row-quad">{c.quadName}</span>
              <span className="row-id">{c.id.length > 8 ? `…${c.id.slice(-6)}` : c.id}</span>
            </span>
            <span className="bar">
              <span style={{ width: `${Math.round(c.rankScore * 100)}%`, background: dotColor(c) }} />
            </span>
            {why && <span className="reason">{why}</span>}
          </span>
          <span className="score">{c.rankScore.toFixed(2)}</span>
          <span className="row-badges">
            {!rej && <LaneBadge lane={laneOf(c)} />}
            <ReviewBadges c={c} />
            {c.status !== "candidate" && (
              <span className="badge" style={{ ["--c" as string]: STATUS_META[c.status].color }}>
                {STATUS_META[c.status].label}
              </span>
            )}
          </span>
        </button>
      </li>
    );
  };

  return (
    <aside className="sidebar">
      <header className="sidebar-head">
        <h1>
          Dowser{" "}
          <Link href="/field" className="link-btn small">
            Field View →
          </Link>
        </h1>
        <div className="lane-tabs" role="tablist" aria-label="Which wells">
          {LANES.map((l) => (
            <button
              key={l}
              role="tab"
              aria-selected={lane === l}
              className={`lane-tab ${l} ${lane === l ? "on" : ""}`}
              onClick={() => onLane(l)}
            >
              {LANE_META[l].tab} <span className="lane-n">({counts[l] ?? "…"})</span>
            </button>
          ))}
        </div>
        <p className="muted">
          {lane === "idle"
            ? "Idle wells in state records within 250 m of a home or school, Kern County."
            : "Candidate undocumented wells, Kern County."}{" "}
          {main ? `${main.length} shown` : "Loading…"}
        </p>
        <div className="chips" role="group" aria-label="Filter by status">
          {STATUSES.map((s) => (
            <button
              key={s}
              className={`chip ${filter.includes(s) ? "on" : ""}`}
              style={{ ["--c" as string]: STATUS_META[s].color }}
              onClick={() => toggle(s)}
              aria-pressed={filter.includes(s)}
            >
              {STATUS_META[s].label}
            </button>
          ))}
        </div>
        {extra}
        {reranked && <p className="muted small rerank-note">Ranked by your priorities (saved scores unchanged).</p>}
      </header>

      <ol className="list">
        {rows?.length === 0 && (
          <li className="empty">
            {lane === "idle" ? "No idle wells" : "No candidates"}
            {filter.length ? " match this filter" : " yet"}.
            {!filter.length && (
              <>
                {" "}
                Run{" "}
                <code>{lane === "idle" ? "python pipeline/idle_wells.py" : "npx convex run seed:seedFakeCandidates"}</code>.
              </>
            )}
          </li>
        )}
        {split && main && main.length > 0 && (
          <li className="list-head">
            {main.every(isVerified) ? "Verified" : "Candidates"} ({main.length})
          </li>
        )}
        {main?.map(row)}
        {rejected.length > 0 && (
          <li className="rejected-sec">
            <details open={rejectedOpen} onToggle={(e) => onRejectedOpen(e.currentTarget.open)}>
              <summary>
                Rejected in review ({rejected.length})
                <span className="rejected-hint">not well symbols · not ranked</span>
              </summary>
              <ol className="rejected-list">{rejected.map(row)}</ol>
            </details>
          </li>
        )}
      </ol>
    </aside>
  );
}
