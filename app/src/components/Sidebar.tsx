"use client";

import Link from "next/link";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { STATUSES, STATUS_META, dotColor, reasonLine } from "../lib/types";
import type { Candidate, Status } from "../lib/types";

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
};

export default function Sidebar({ rows, selectedId, onSelect, filter, onFilter, extra, reranked, changedIds }: Props) {
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

  return (
    <aside className="sidebar">
      <header className="sidebar-head">
        <h1>
          Dowser{" "}
          <Link href="/field" className="link-btn small">
            Field View →
          </Link>
        </h1>
        <p className="muted">
          Candidate undocumented wells, Kern County.{" "}
          {rows ? `${rows.length} shown` : "Loading…"}
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
            No candidates{filter.length ? " match this filter" : " yet"}.
            {!filter.length && (
              <>
                {" "}
                Run <code>npx convex run seed:seedFakeCandidates</code>.
              </>
            )}
          </li>
        )}
        {rows?.map((c) => (
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
              } ${changedIds?.includes(c.id) ? "flash" : ""}`}
              onClick={() => onSelect(c.id)}
            >
              <span className="rank">
                {c.rank}
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
                {reasonLine(c) && <span className="reason">{reasonLine(c)}</span>}
              </span>
              <span className="score">{c.rankScore.toFixed(2)}</span>
              {c.status !== "candidate" && (
                <span className="badge" style={{ ["--c" as string]: STATUS_META[c.status].color }}>
                  {STATUS_META[c.status].label}
                </span>
              )}
            </button>
          </li>
        ))}
      </ol>
    </aside>
  );
}
