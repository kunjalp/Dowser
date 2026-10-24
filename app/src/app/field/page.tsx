"use client";

import { useMutation, useQuery } from "convex/react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Sparkline } from "../../components/DetailPanel";
import MapView from "../../components/MapView";
import { api } from "../../lib/convexApi";
import { haptics, hapticsStatus } from "../../lib/haptics";
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
    <main className="field">
      <header className="field-head">
        <h1>Dowser · Field</h1>
        <span className="field-gps">
          {here ? `GPS ±${Math.round(here.acc ?? 0)} m` : "Locating…"}
        </span>
        {inApp && <span className="field-gps">{hapticsStatus()}</span>}
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

          <nav className="field-tabs" aria-label="Field View">
            <button
              className={`tab ${view === "list" ? "on" : ""}`}
              onClick={() => {
                if (view !== "list") haptics.tick();
                setView("list");
              }}
            >
              List
            </button>
            <button
              className={`tab ${view === "map" ? "on" : ""}`}
              onClick={() => {
                if (view !== "map") haptics.tick();
                setView("map");
              }}
            >
              Map
            </button>
            {view === "list" && (
              <button
                className="tab sort"
                onClick={() => {
                  haptics.light();
                  setSheet(true);
                }}
              >
                Sort
              </button>
            )}
          </nav>

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

  // Gauge geometry: the trigger line sits at 2/3 of the bar unless the reading goes past it.
  const val = latest?.value ?? 0;
  const th = rule?.threshold ?? 1200;
  const top = Math.max(th * 1.5, val * 1.1, 1);
  const fillPct = Math.min(100, (val / top) * 100);
  const markPct = Math.min(100, (th / top) * 100);
  const gaugeText = leaking
    ? "Confirmed leaking."
    : gone
      ? "Status changed elsewhere."
      : !latest
      ? "Waiting for the sensor…"
      : !rule
        ? ""
        : hot >= rule.count
          ? "Confirming…"
          : val >= th
            ? `High reading. ${rule.count - hot} more in ${rule.windowMs / 1000} s confirms it.`
            : "Below the trigger line.";

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

  return (
    <section className="field-paired">
      <button className="link-btn" onClick={onBack}>
        ← Pick a different candidate
      </button>
      <h2>
        <span className="dot" style={{ background: dotColor(c) }} /> {c.quadName} · {c.id}
      </h2>
      <p className="muted small">
        {fmtM(c.distToHomeM)} to nearest home · {fmtM(c.distToWaterM)} to water
      </p>

      {arrived ? (
        <div className="arrive on" role="status">
          <strong>You&apos;re here</strong>
          <span className="small">{weakGps ? `GPS ±${Math.round(here?.acc ?? 0)} m, look for the pad` : "Readings are attached to this site"}</span>
        </div>
      ) : (
        <a
          className="field-nav"
          href={`https://maps.apple.com/?daddr=${c.lat},${c.lon}&dirflg=d&q=${encodeURIComponent(c.id)}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          <span>Navigate</span>
          <span className="field-nav-dist">
            {here && dist !== undefined ? awayText(dist, bearing(here, target)) : "in Maps"}
          </span>
        </a>
      )}

      <div className={`reading-card ${leaking ? "leak" : ""} ${anyReplay ? "sim-data" : ""}`}>
        <div className="reading-top">
          <span className={`live-dot ${live ? "on" : ""}`} />
          <span className="small">
            {latest ? (live ? "Sensor live" : `Last reading ${age}s ago`) : "Waiting for the sensor…"}
          </span>
          {anyReplay && <span className="sim">Simulated</span>}
        </div>
        <div className="reading-value">
          {latest ? latest.value.toFixed(0) : "–"}
          {anyReplay && <em className="tag sim">Sim</em>}
        </div>
        <div className={`gauge ${anyReplay ? "sim-data" : ""}`} role="meter" aria-valuenow={val} aria-valuemin={0} aria-valuemax={Math.round(top)}>
          <span className={`gauge-fill ${val >= th ? "hi" : ""}`} style={{ width: `${fillPct}%` }} />
          <span className="gauge-mark" style={{ left: `${markPct}%` }} />
        </div>
        <div className="gauge-legend">
          <span>0</span>
          <span>trigger {th}</span>
        </div>
        <Sparkline values={chrono.map((r) => r.value)} sim={anyReplay} />
        {gaugeText && latest && (
          <p className={`small ${leaking ? "gauge-confirmed" : "muted"}`} role={leaking ? "alert" : undefined}>
            {gaugeText}
          </p>
        )}
      </div>

      <FieldEvidence images={c.evidenceImages} />

      <textarea
        className="field-note"
        placeholder="Optional note (smell, staining, access…)"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
      />
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => onPhoto(e.target.files?.[0])}
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
