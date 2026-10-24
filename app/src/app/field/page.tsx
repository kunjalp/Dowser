"use client";

import { useMutation, useQuery } from "convex/react";
import Link from "next/link";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import MapView from "../../components/MapView";
import { api } from "../../lib/convexApi";
import { haptics, hapticsStatus } from "../../lib/haptics";
import FieldTabs from "./FieldTabs";
import { STATUS_META, dotColor, isFake, reasonLine } from "../../lib/types";
import type { Candidate, Reading, Status } from "../../lib/types";

type Outcome = "confirmed_leaking" | "confirmed_not_leaking" | "no_well" | "mislocated";
const OUTCOMES: Record<Outcome, string> = {
  confirmed_leaking: "Leaking",
  confirmed_not_leaking: "Not leaking",
  no_well: "No well here",
  mislocated: "Wrong spot",
};

/** Seconds a tapped decision waits before it is saved, so a mis-tap can be undone. */
const UNDO_SECS = 4;
/** Within this many meters the app treats you as at the site. */
const ARRIVED_M = 50;
/** Beyond this the direction arrow is noise; show only "N km away". */
const FAR_M = 5000;

type Pos = { lat: number; lon: number; acc?: number };

const fmtM = (m?: number) =>
  m === undefined ? "n/a" : m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;

const toRad = (d: number) => (d * Math.PI) / 180;

/** Great-circle distance in meters. */
function distM(a: Pos, b: Pos): number {
  const R = 6371000;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Compass bearing in degrees (0 = north) you would walk from a toward b. */
function bearing(a: Pos, b: Pos): number {
  const y = Math.sin(toRad(b.lon - a.lon)) * Math.cos(toRad(b.lat));
  const x =
    Math.cos(toRad(a.lat)) * Math.sin(toRad(b.lat)) -
    Math.sin(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.cos(toRad(b.lon - a.lon));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}
const compass = (deg: number) => ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(deg / 45) % 8];

/** How far away and which way, in a form that stays readable from 300 km down to the pad. */
function awayText(d: number, deg: number): string {
  if (d >= FAR_M) return `${Math.round(d / 1000)} km away`;
  if (d < ARRIVED_M) return "You're here";
  return `${fmtM(d)} ${compass(deg)}`;
}

/** The one fact worth reading at a glance: closest person-related risk first. */
function urgentFact(c: Candidate): string {
  if (c.distToHomeM !== undefined && c.distToHomeM <= 500) return `${fmtM(c.distToHomeM)} from a home`;
  if (c.distToSchoolM !== undefined && c.distToSchoolM <= 1000) return `${fmtM(c.distToSchoolM)} from a school`;
  if (c.distToWaterM !== undefined && c.distToWaterM <= 500) return `${fmtM(c.distToWaterM)} from water`;
  return reasonLine(c).split(" · ")[0] ?? "";
}

function getPosition(): Promise<Pos | undefined> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) return resolve(undefined);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy }),
      () => resolve(undefined),
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 15000 },
    );
  });
}

/** Live phone position; undefined until the first fix (or if location is denied). */
function useHere(): Pos | undefined {
  const [here, setHere] = useState<Pos | undefined>();
  useEffect(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) return;
    const id = navigator.geolocation.watchPosition(
      (p) => setHere({ lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy }),
      () => {},
      { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, []);
  return here;
}

/** True inside the iOS app wrapper (Capacitor), false in a normal browser. */
function useInApp(): boolean {
  const [inApp, setInApp] = useState(false);
  useEffect(() => {
    const w = window as unknown as { Capacitor?: { isNativePlatform?: () => boolean } };
    const ua = navigator.userAgent;
    // iOS browsers always carry "Safari/" in the UA; the app's web view does not.
    setInApp(!!w.Capacitor?.isNativePlatform?.() || (/iPhone|iPad/.test(ua) && !/Safari\//.test(ua)));
  }, []);
  return inApp;
}

type Sort = "queue" | "near" | "rank";
const SORTS: { key: Sort; label: string; hint: string }[] = [
  { key: "queue", label: "Queued first", hint: "Work list on top, then nearest" },
  { key: "near", label: "Nearest", hint: "Closest to you, any status" },
  { key: "rank", label: "Top ranked", hint: "Highest priority first" },
];

export default function FieldView() {
  const [paired, setPaired] = useState<Candidate | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<Sort>("queue");
  const [sheet, setSheet] = useState(false);
  const [sheetClosing, setSheetClosing] = useState(false);
  const [view, setView] = useState<"list" | "map">("list");
  const [mapSel, setMapSel] = useState<string | null>(null);
  const [done, setDone] = useState<{ msg: string; id: number } | null>(null);
  const here = useHere();
  const inApp = useInApp();
  const [outdoor, setOutdoor] = useState(false);
  useEffect(() => {
    try {
      setOutdoor(localStorage.getItem("dowser.outdoor") === "1");
    } catch {
      /* storage blocked: stay in the default look */
    }
  }, []);
  function toggleOutdoor() {
    const next = !outdoor;
    setOutdoor(next);
    try {
      localStorage.setItem("dowser.outdoor", next ? "1" : "0");
    } catch {
      /* not persisted, still applies this session */
    }
  }

  const rows = useQuery(api.candidates.ranked, {
    statuses: ["queued", "candidate"] as Status[],
    limit: 200,
  }) as Candidate[] | undefined;
  // The map shows every status (confirmed ones included); only fetched while the map tab is open.
  const allRows = useQuery(api.candidates.ranked, view === "map" ? { limit: 1000 } : "skip") as
    | Candidate[]
    | undefined;
  const mapPick = allRows?.find((r) => r.id === mapSel) ?? null;
  const toastId = useRef(0);
  const pairMut = useMutation(api.pairing.set);
  const clearMut = useMutation(api.pairing.clear);

  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    type Item = { c: Candidate; d?: number; deg?: number };
    const items: Item[] = (rows ?? [])
      .filter((c) => !q || c.id.toLowerCase().includes(q) || c.quadName.toLowerCase().includes(q))
      .map((c) => ({ c, d: here ? distM(here, c) : undefined, deg: here ? bearing(here, c) : undefined }));
    const byRank = (a: Item, b: Item) => a.c.rank - b.c.rank;
    const byDist = (a: Item, b: Item) => (a.d !== undefined && b.d !== undefined ? a.d - b.d : byRank(a, b));
    const queuedFirst = (a: Item, b: Item) =>
      Number(b.c.status === "queued") - Number(a.c.status === "queued") || byDist(a, b);
    return items.sort(sort === "rank" ? byRank : sort === "near" ? byDist : queuedFirst);
  }, [rows, query, sort, here]);

  const nearest = list.reduce<number | undefined>(
    (m, it) => (it.d === undefined ? m : m === undefined ? it.d : Math.min(m, it.d)),
    undefined,
  );
  const farAway = nearest !== undefined && nearest > 100000;
  const queuedCount = list.filter((it) => it.c.status === "queued").length;

  // iOS only fires :active (the shared press style) when some touch listener exists on the document.
  useEffect(() => {
    const noop = () => {};
    document.addEventListener("touchstart", noop, { passive: true });
    return () => document.removeEventListener("touchstart", noop);
  }, []);

  // Sort sheet: slides out before it unmounts, whatever closed it (Done, backdrop, Escape).
  function closeSheet() {
    if (sheetClosing) return;
    setSheetClosing(true);
    window.setTimeout(finishClose, 260); // fallback if animationend never fires
  }
  function finishClose() {
    setSheet(false);
    setSheetClosing(false);
  }
  useEffect(() => {
    if (!sheet) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeSheet();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sheet, sheetClosing]);

  async function pair(c: Candidate) {
    setDone(null);
    setPaired(c);
    const pos = await getPosition();
    await pairMut({ candidateId: c.id, lat: pos?.lat, lon: pos?.lon });
  }
  async function unpair() {
    setPaired(null);
    await clearMut({});
  }

  return (
    <main className={`field ${outdoor ? "outdoor" : ""}`}>
      <header className="field-head">
        <h1>Dowser · Field</h1>
        <span className="field-gps">
          {here ? `GPS ±${Math.round(here.acc ?? 0)} m` : "Locating…"}
        </span>
        {inApp && <span className="field-gps">{hapticsStatus()}</span>}
        <button
          className={`pc-sun ${outdoor ? "on" : ""}`}
          onClick={toggleOutdoor}
          aria-pressed={outdoor}
          aria-label="Outdoor mode"
          title="Outdoor mode: higher contrast for sunlight"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </svg>
        </button>
        {!inApp && (
          <Link href="/" className="link-btn">
            Command Map
          </Link>
        )}
      </header>
      {done && <FieldToast key={done.id} message={done.msg} onGone={() => setDone((d) => (d && d.id === done.id ? null : d))} />}
      {paired ? (
        <Paired
          candidate={rows?.find((r) => r.id === paired.id) ?? paired}
          gone={rows !== undefined && !rows.some((r) => r.id === paired.id)}
          here={here}
          onBack={unpair}
          onLogged={(msg) => {
            setDone({ msg, id: ++toastId.current });
            void unpair();
          }}
        />
      ) : (
        <>
          {view === "map" ? (
            <>
              <div className="field-map">
                <MapView rows={allRows ?? []} selectedId={mapSel} onSelect={setMapSel} compact here={here} />
              </div>
              {mapPick ? (
                <div className="map-card">
                  <div className="map-card-top">
                    <strong>
                      {mapPick.quadName} · {mapPick.id}
                    </strong>
                    <span className="badge" style={{ ["--c" as string]: STATUS_META[mapPick.status].color }}>
                      {STATUS_META[mapPick.status].label}
                      {mapPick.status === "candidate" ? ` · ${mapPick.score.toFixed(2)}` : ""}
                    </span>
                  </div>
                  <p className="muted small">
                    {here ? `${awayText(distM(here, mapPick), bearing(here, mapPick))} · ` : ""}
                    {urgentFact(mapPick)}
                  </p>
                  <div className="map-card-actions">
                    {(mapPick.status === "candidate" || mapPick.status === "queued") && (
                      <button className="field-btn" onClick={() => pair(mapPick)}>
                        Check this one
                      </button>
                    )}
                    <a
                      className="field-nav"
                      href={`https://maps.apple.com/?daddr=${mapPick.lat},${mapPick.lon}&dirflg=d&q=${encodeURIComponent(mapPick.id)}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span>Navigate</span>
                    </a>
                  </div>
                </div>
              ) : (
                <p className="muted small field-hint">Tap a dot to see it. The blue dot is you.</p>
              )}
            </>
          ) : (
            <>
              {farAway && (
                <p className="field-far" role="status">
                  Nearest candidate is {Math.round((nearest ?? 0) / 1000)} km from you. Distances become useful once
                  you are in the field.
                </p>
              )}
              <p className="field-section">
                {sort === "queue" ? `Queued (${queuedCount}) then nearby` : sort === "near" ? "Nearest first" : "Top ranked"}
              </p>
              <ul className="field-list">
                {rows === undefined && <li className="muted">Loading…</li>}
                {rows && list.length === 0 && <li className="muted">No open candidates match.</li>}
                {list.map(({ c, d, deg }) => {
                  const arrived = d !== undefined && d < ARRIVED_M;
                  return (
                    <li key={c._id}>
                      <button className={`field-row ${arrived ? "here" : ""}`} onClick={() => pair(c)}>
                        <span className="dot" style={{ background: dotColor(c) }} />
                        <span className="field-row-main">
                          <strong className="field-dist">
                            {d !== undefined && deg !== undefined ? (
                              <>
                                {d >= ARRIVED_M && d < FAR_M && (
                                  <span className="field-arrow" style={{ transform: `rotate(${deg}deg)` }} aria-hidden>
                                    ↑
                                  </span>
                                )}
                                {awayText(d, deg)}
                              </>
                            ) : (
                              `#${c.rank}`
                            )}
                          </strong>
                          <span className="muted small">
                            {c.quadName} · {c.id}
                            {isFake(c) && <em className="tag sim">Sim</em>}
                          </span>
                          {urgentFact(c) && <span className="reason">{urgentFact(c)}</span>}
                        </span>
                        {c.status === "queued" && (
                          <span className="badge" style={{ ["--c" as string]: STATUS_META.queued.color }}>
                            Queued
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </>
          )}

          <FieldTabs view={view} onView={setView} onSort={() => setSheet(true)} />

          {sheet && (
            <div className={`sheet-backdrop ${sheetClosing ? "closing" : ""}`} onClick={closeSheet}>
              <div
                className={`sheet ${sheetClosing ? "closing" : ""}`}
                role="dialog"
                aria-modal="true"
                aria-label="Sort and filter"
                onClick={(e) => e.stopPropagation()}
                onAnimationEnd={(e) => {
                  if (sheetClosing && e.target === e.currentTarget) finishClose();
                }}
              >
                <h3>Sort</h3>
                {SORTS.map((s) => (
                  <button
                    key={s.key}
                    className={`sheet-opt ${sort === s.key ? "on" : ""}`}
                    onClick={() => {
                      if (sort !== s.key) haptics.tick();
                      setSort(s.key);
                    }}
                    aria-pressed={sort === s.key}
                  >
                    <strong>{s.label}</strong>
                    <span className="muted small">{s.hint}</span>
                  </button>
                ))}
                <input
                  className="field-search"
                  placeholder="Filter by quad (e.g. Lost Hills)"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <button className="field-btn" onClick={closeSheet}>
                  Done
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </main>
  );
}

/** Slides in from the top edge, rests ~3.5 s, slides back out; removed only after the exit animation. */
function FieldToast({ message, onGone }: { message: string; onGone: () => void }) {
  const [leaving, setLeaving] = useState(false);
  const goneRef = useRef(onGone);
  goneRef.current = onGone;
  useEffect(() => {
    const t = window.setTimeout(() => setLeaving(true), 3500);
    return () => window.clearTimeout(t);
  }, []);
  useEffect(() => {
    if (!leaving) return;
    const t = window.setTimeout(() => goneRef.current(), 220); // fallback if animationend never fires
    return () => window.clearTimeout(t);
  }, [leaving]);
  return (
    <div className={`field-toast ${leaving ? "leaving" : ""}`} role="status" onAnimationEnd={() => leaving && goneRef.current()}>
      {message}
    </div>
  );
}

function FieldEvidence({ images }: { images: Candidate["evidenceImages"] }) {
  const [failed, setFailed] = useState<Record<string, boolean>>({});
  const [big, setBig] = useState<string | null>(null);
  if (images.length === 0) return null;
  const sorted = [...images].sort((a, b) => a.year - b.year);
  const shown = sorted.length > 2 ? [sorted[0], sorted[sorted.length - 1]] : sorted;
  return (
    <div className="field-evidence">
      <h3>What you are looking for</h3>
      <div className="field-evidence-row">
        {shown.map((im) => (
          <figure key={`${im.year}-${im.url}`}>
            {failed[im.url] ? (
              <div className="ph">no image yet</div>
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={im.url}
                alt={`Symbol on the ${im.year} map`}
                onClick={() => setBig(big === im.url ? null : im.url)}
                onError={() => setFailed((f) => ({ ...f, [im.url]: true }))}
              />
            )}
            <figcaption>{im.year} map</figcaption>
          </figure>
        ))}
      </div>
      {big && (
        // eslint-disable-next-line @next/next/no-img-element
        <img className="field-evidence-big" src={big} alt="Enlarged map crop" onClick={() => setBig(null)} />
      )}
    </div>
  );
}

/** Smooth reading trace: fading area, dashed auto-confirm line, dot on the latest value. No axes. */
function FieldSpark({ values, threshold }: { values: number[]; threshold: number }) {
  const gid = useId();
  if (values.length < 2) return <div className="pc-spark-empty">Waiting for readings…</div>;
  const w = 300;
  const h = 72;
  const pad = 6;
  const max = Math.max(...values, threshold * 1.15, 1);
  const y = (v: number) => h - pad - (v / max) * (h - pad * 2);
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, y(v)] as const);
  // Catmull-Rom to cubic Bezier: a smooth curve through every reading, clamped so it never overshoots the box.
  const clamp = (n: number) => Math.min(h, Math.max(0, n));
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] ?? pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] ?? p2;
    d += ` C${p1[0] + (p2[0] - p0[0]) / 6},${clamp(p1[1] + (p2[1] - p0[1]) / 6)} ${p2[0] - (p3[0] - p1[0]) / 6},${clamp(p2[1] - (p3[1] - p1[1]) / 6)} ${p2[0]},${p2[1]}`;
  }
  const last = pts[pts.length - 1];
  const over = values[values.length - 1] >= threshold;
  const ty = y(threshold);
  return (
    <div className={`pc-spark ${over ? "over" : ""}`}>
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" role="img" aria-label="Recent sensor readings">
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="currentColor" stopOpacity="0.28" />
            <stop offset="1" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={`${d} L${w},${h} L0,${h} Z`} fill={`url(#${gid})`} />
        <line x1="0" x2={w} y1={ty} y2={ty} className="pc-spark-th" vectorEffect="non-scaling-stroke" />
        <path d={d} fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      </svg>
      <span className="pc-spark-dot" style={{ top: `${(last[1] / h) * 100}%` }} />
    </div>
  );
}

function Paired({
  candidate: c,
  gone,
  here,
  onBack,
  onLogged,
}: {
  candidate: Candidate;
  /** True once the candidate has left the queued/candidate list (the sensor auto-confirmed it, or someone changed it). */
  gone: boolean;
  here: Pos | undefined;
  onBack: () => void;
  onLogged: (msg: string) => void;
}) {
  const readings = useQuery(api.readings.recent, { candidateId: c.id, limit: 40 }) as Reading[] | undefined;
  const rule = useQuery(api.readings.autoConfirmRule, {}) as
    | { threshold: number; count: number; windowMs: number }
    | undefined;
  const logFinding = useMutation(api.fieldChecks.logFinding);
  const genUrl = useMutation(api.fieldChecks.generateUploadUrl);

  const [note, setNote] = useState("");
  const [photoId, setPhotoId] = useState<string | null>(null);
  const [photoState, setPhotoState] = useState<"none" | "uploading" | "ready" | "error">("none");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [pending, setPending] = useState<{ outcome: Outcome; label: string } | null>(null);
  const [secs, setSecs] = useState(0);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [simInfo, setSimInfo] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const chrono = readings ? [...readings].reverse() : [];
  const latest = chrono[chrono.length - 1];
  const age = latest ? Math.round((now - latest.receivedAt) / 1000) : undefined;
  const live = age !== undefined && age <= 10;
  const hot =
    rule && readings
      ? readings.filter((r) => r.value >= rule.threshold && now - r.receivedAt <= rule.windowMs).length
      : 0;
  const anyReplay = chrono.some((r) => r.isReplay);
  // The list only returns queued/candidate, so an auto-confirmed well drops out of it. Treat "gone while the
  // readings meet the auto-confirm rule" as confirmed leaking so the screen keeps the well and says so.
  const hotAtLatest =
    rule && readings && latest
      ? readings.filter((r) => r.value >= rule.threshold && latest.receivedAt - r.receivedAt <= rule.windowMs).length
      : 0;
  const autoConfirmed = gone && !!rule && hotAtLatest >= rule.count;
  const leaking = c.status === "confirmed_leaking" || autoConfirmed;
  const warned = useRef(false);
  useEffect(() => {
    if (leaking && !warned.current) {
      warned.current = true;
      haptics.warning();
    }
  }, [leaking]);

  // One warning buzz when the latest reading first crosses the trigger (below to above). Shares the
  // `warned` latch so the auto-confirm buzz above does not fire a second time.
  const prevAbove = useRef<boolean | null>(null);
  const latestVal = latest?.value;
  useEffect(() => {
    if (latestVal === undefined || !rule) return;
    const above = latestVal >= rule.threshold;
    if (prevAbove.current === false && above && !warned.current) {
      warned.current = true;
      haptics.warning();
    }
    prevAbove.current = above;
  }, [latestVal, rule]);

  // Keep the screen on while this screen is open; the lock drops when the tab hides, so re-request on return.
  useEffect(() => {
    let lock: WakeLockSentinel | null = null;
    let dead = false;
    const request = async () => {
      try {
        if (!("wakeLock" in navigator) || document.visibilityState !== "visible") return;
        const l = await navigator.wakeLock.request("screen");
        if (dead) void l.release().catch(() => {});
        else lock = l;
      } catch {
        /* denied or unsupported: nothing to do */
      }
    };
    void request();
    const onVis = () => {
      if (document.visibilityState === "visible") void request();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => {
      dead = true;
      document.removeEventListener("visibilitychange", onVis);
      void lock?.release().catch(() => {});
    };
  }, []);

  useEffect(() => {
    if (!simInfo) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSimInfo(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [simInfo]);

  // Gauge geometry: the trigger line sits at 2/3 of the bar unless the reading goes past it.
  const val = latest?.value ?? 0;
  const th = rule?.threshold ?? 1200;
  const top = Math.max(th * 1.5, val * 1.1, 1);
  const fillPct = Math.min(100, (val / top) * 100);
  const markPct = Math.min(100, (th / top) * 100);

  const target: Pos = { lat: c.lat, lon: c.lon };
  const dist = here ? distM(here, target) : undefined;
  const arrived = dist !== undefined && dist < ARRIVED_M;
  const weakGps = here?.acc !== undefined && here.acc > 25;

  async function onPhoto(file: File | undefined) {
    if (!file) return;
    setPhotoState("uploading");
    try {
      const url = await genUrl({});
      const res = await fetch(url, { method: "POST", headers: { "Content-Type": file.type || "image/jpeg" }, body: file });
      if (!res.ok) throw new Error(`upload ${res.status}`);
      const { storageId } = (await res.json()) as { storageId: string };
      setPhotoId(storageId);
      setPhotoState("ready");
    } catch {
      haptics.error();
      setPhotoState("error");
    }
  }

  async function log(outcome: Outcome, label: string) {
    setBusy(true);
    setError(null);
    try {
      const pos = await getPosition();
      await logFinding({
        candidateId: c.id,
        outcome,
        note: note.trim() || undefined,
        photoId: (photoId ?? undefined) as never,
        lat: pos?.lat,
        lon: pos?.lon,
      });
      haptics.success();
      onLogged(`${c.id}: logged "${label}".`);
    } catch (e) {
      haptics.error();
      setError(e instanceof Error ? e.message : "Could not save. Try again.");
      setBusy(false);
    }
  }

  // A tapped decision counts down, then saves; Undo cancels it before anything is written.
  function choose(outcome: Outcome) {
    haptics.light();
    setError(null);
    setPending({ outcome, label: OUTCOMES[outcome] });
    setSecs(UNDO_SECS);
  }
  useEffect(() => {
    if (!pending) return;
    if (secs <= 0) {
      const p = pending;
      setPending(null);
      void log(p.outcome, p.label);
      return;
    }
    const t = setTimeout(() => setSecs((s) => s - 1), 1000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending, secs]);

  const decideDisabled = busy || photoState === "uploading";
  const btn = (o: Outcome) => (
    <button
      key={o}
      className={`field-btn out-${o}`}
      style={{ ["--c" as string]: STATUS_META[o].color }}
      disabled={decideDisabled}
      onClick={() => choose(o)}
    >
      {OUTCOMES[o]}
    </button>
  );

  const stateWord = leaking ? "Confirmed leaking" : val >= th && latest ? "High" : "Below trigger";
  const stateKind = leaking ? "leak" : val >= th && latest ? "high" : "ok";
  const hasDetails = note.trim() !== "" || photoState !== "none";

  return (
    <section className="field-paired">
      <header className="pc-head">
        <button className="pc-back" onClick={onBack} aria-label="Back to candidates">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 5l-7 7 7 7" />
          </svg>
        </button>
        <h2 className="pc-title">
          <span className="dot" style={{ background: dotColor(c) }} />
          <span className="pc-name">{c.quadName}</span>
          <span className="pc-id">{c.id}</span>
        </h2>
        <span className="pc-chip" title="Distance to the nearest home">
          {fmtM(c.distToHomeM)} to home
        </span>
      </header>

      {arrived ? (
        <div className="pc-where here" role="status">
          <strong>You&apos;re here</strong>
          <span>{weakGps ? `GPS ±${Math.round(here?.acc ?? 0)} m, look for the pad` : "Readings are attached to this site"}</span>
        </div>
      ) : (
        <div className="pc-where">
          <span className="pc-away">{here && dist !== undefined ? awayText(dist, bearing(here, target)).replace(/(?<! away)$/, " away") : "Location off"}</span>
          <a
            className="pc-nav"
            href={`https://maps.apple.com/?daddr=${c.lat},${c.lon}&dirflg=d&q=${encodeURIComponent(c.id)}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            Navigate
          </a>
        </div>
      )}

      <div className={`pc-reading ${stateKind} ${anyReplay ? "sim-data" : ""}`}>
        <div className="pc-reading-top">
          <span className={`pc-state ${stateKind}`} role={leaking ? "alert" : undefined}>
            {latest ? stateWord : gone ? "Status changed" : "Waiting for sensor"}
          </span>
          <button className="pc-sim" onClick={() => setSimInfo(true)} aria-haspopup="dialog">
            Simulated sensor input
          </button>
          <span className="pc-live" title={latest ? (live ? "Sensor live" : `Last reading ${age}s ago`) : "No readings yet"}>
            <span className={`live-dot ${live ? "on" : ""}`} />
            {latest ? (live ? "Live" : `${age}s ago`) : ""}
          </span>
        </div>
        <div className="pc-value">{latest ? latest.value.toFixed(0) : "–"}</div>
        <div className="pc-gauge" role="meter" aria-label="Reading against trigger" aria-valuenow={val} aria-valuemin={0} aria-valuemax={Math.round(top)}>
          <span className={`pc-gauge-fill ${val >= th ? "hi" : ""}`} style={{ width: `${fillPct}%` }} />
          <span className="pc-gauge-mark" style={{ left: `${markPct}%` }} />
        </div>
        <div className="pc-gauge-legend">
          <span>0</span>
          <span>trigger {th}</span>
        </div>
        <FieldSpark values={chrono.map((r) => r.value)} threshold={th} />
        {rule && latest && !leaking && !gone && val >= th && (
          <p className="pc-hint">
            {hot >= rule.count ? "Confirming…" : `${rule.count - hot} more in ${rule.windowMs / 1000} s confirms it.`}
          </p>
        )}
      </div>

      {simInfo && (
        <div className="sheet-backdrop" onClick={() => setSimInfo(false)}>
          <div className="sheet" role="dialog" aria-modal="true" aria-label="About the simulated sensor" onClick={(e) => e.stopPropagation()}>
            <h3>Simulated sensor input</h3>
            <p className="pc-sim-copy">
              Flammable gas isn&apos;t allowed at this venue, so a knob stands in for the sensor reading. Everything after the
              reading is the real system.
            </p>
            <button className="pc-sim-done" onClick={() => setSimInfo(false)}>
              Got it
            </button>
          </div>
        </div>
      )}

      <FieldEvidence images={c.evidenceImages} />

      <button
        className="pc-details-toggle"
        aria-expanded={detailsOpen}
        aria-controls="pc-details"
        onClick={() => setDetailsOpen((o) => !o)}
      >
        <span>Add details</span>
        {hasDetails && <span className="pc-details-dot" role="img" aria-label="Has note or photo" />}
        <svg className="pc-chev" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      <div id="pc-details" className="sheet-backdrop pc-details-backdrop" hidden={!detailsOpen} onClick={() => setDetailsOpen(false)}>
      <div className="sheet pc-details-sheet" role="dialog" aria-label="Note and photo" onClick={(e) => e.stopPropagation()}>
        <h3>Note and photo</h3>
        <textarea
          className="field-note"
          placeholder="Optional note (smell, staining, access…)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={2}
        />
        <button className="field-photo" onClick={() => fileRef.current?.click()} disabled={photoState === "uploading"}>
          {photoState === "uploading"
            ? "Uploading photo…"
            : photoState === "ready"
              ? "Photo attached ✓ (tap to replace)"
              : photoState === "error"
                ? "Photo failed, tap to retry"
                : "Add photo"}
        </button>
        <button className="pc-sim-done" onClick={() => setDetailsOpen(false)}>
          Done
        </button>
      </div>
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => onPhoto(e.target.files?.[0])}
      />
      {error && <p className="field-error">{error}</p>}

      <div className="field-decide">
        {pending ? (
          <div className="undo-bar" role="status">
            <span>
              Marking <strong>{pending.label}</strong> in {secs}s
            </span>
            <button
              onClick={() => {
                haptics.light();
                setPending(null);
              }}
            >
              Undo
            </button>
          </div>
        ) : (
          <>
            {btn("confirmed_leaking")}
            {btn("confirmed_not_leaking")}
            <div className="field-decide-row">
              {btn("no_well")}
              {btn("mislocated")}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
