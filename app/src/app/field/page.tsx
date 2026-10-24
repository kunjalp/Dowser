"use client";

import { useMutation, useQuery } from "convex/react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Sparkline } from "../../components/DetailPanel";
import MapView from "../../components/MapView";
import { api } from "../../lib/convexApi";
import { STATUS_META, dotColor, isFake, reasonLine } from "../../lib/types";
import type { Candidate, Reading, Status } from "../../lib/types";

type Outcome = "confirmed_leaking" | "confirmed_not_leaking" | "no_well" | "mislocated";
const OUTCOMES: { key: Outcome; label: string }[] = [
  { key: "confirmed_leaking", label: "Leaking" },
  { key: "confirmed_not_leaking", label: "Not leaking" },
  { key: "no_well", label: "No well here" },
  { key: "mislocated", label: "Wrong spot" },
];

/** Seconds a tapped decision waits before it is saved, so a mis-tap can be undone. */
const UNDO_SECS = 4;

type Pos = { lat: number; lon: number };

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

/** Compass direction (N, NE, ...) you would walk from a toward b. */
function compass(a: Pos, b: Pos): string {
  const y = Math.sin(toRad(b.lon - a.lon)) * Math.cos(toRad(b.lat));
  const x =
    Math.cos(toRad(a.lat)) * Math.sin(toRad(b.lat)) -
    Math.sin(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.cos(toRad(b.lon - a.lon));
  const deg = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.round(deg / 45) % 8];
}

function getPosition(): Promise<Pos | undefined> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) return resolve(undefined);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
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
      (p) => setHere({ lat: p.coords.latitude, lon: p.coords.longitude }),
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

type Mode = "near" | "queued" | "rank";
const MODES: { key: Mode; label: string }[] = [
  { key: "near", label: "Nearest" },
  { key: "queued", label: "Queued" },
  { key: "rank", label: "Top ranked" },
];

export default function FieldView() {
  const [paired, setPaired] = useState<Candidate | null>(null);
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<Mode>("near");
  const [view, setView] = useState<"list" | "map">("list");
  const [mapSel, setMapSel] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
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
  const pairMut = useMutation(api.pairing.set);
  const clearMut = useMutation(api.pairing.clear);

  // Distance and direction from the phone; the list order follows the chosen mode.
  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    const items = (rows ?? [])
      .filter((c) => !q || c.id.toLowerCase().includes(q) || c.quadName.toLowerCase().includes(q))
      .filter((c) => mode !== "queued" || c.status === "queued")
      .map((c) => ({
        c,
        d: here ? distM(here, c) : undefined,
        dir: here ? compass(here, c) : undefined,
      }));
    const byRank = (a: (typeof items)[number], b: (typeof items)[number]) =>
      Number(b.c.status === "queued") - Number(a.c.status === "queued") || a.c.rank - b.c.rank;
    const byDist = (a: (typeof items)[number], b: (typeof items)[number]) =>
      a.d !== undefined && b.d !== undefined ? a.d - b.d : byRank(a, b);
    return items.sort(mode === "rank" ? byRank : byDist);
  }, [rows, query, mode, here]);

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
        {!inApp && (
          <Link href="/" className="link-btn">
            Command Map
          </Link>
        )}
      </header>
      {done && <div className="field-toast">{done}</div>}
      {paired ? (
        <Paired
          candidate={rows?.find((r) => r.id === paired.id) ?? paired}
          here={here}
          onBack={unpair}
          onLogged={(msg) => {
            setDone(msg);
            void unpair();
          }}
        />
      ) : (
        <>
          <div className="chips" role="group" aria-label="View">
            {(["list", "map"] as const).map((v) => (
              <button
                key={v}
                className={`chip ${view === v ? "on" : ""}`}
                onClick={() => setView(v)}
                aria-pressed={view === v}
              >
                {v === "list" ? "List" : "Map"}
              </button>
            ))}
          </div>
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
                    </span>
                  </div>
                  <p className="muted small">
                    {here ? `${fmtM(distM(here, mapPick))} ${compass(here, mapPick)} · ` : ""}
                    {reasonLine(mapPick)}
                  </p>
                  <div className="map-card-actions">
                    {(mapPick.status === "candidate" || mapPick.status === "queued") && (
                      <button className="field-btn" style={{ ["--c" as string]: "#f59e0b" }} onClick={() => pair(mapPick)}>
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
          <div className="chips" role="group" aria-label="Sort and filter">
            {MODES.map((m) => (
              <button
                key={m.key}
                className={`chip ${mode === m.key ? "on" : ""}`}
                onClick={() => setMode(m.key)}
                aria-pressed={mode === m.key}
              >
                {m.label}
              </button>
            ))}
          </div>
          <p className="muted small field-hint">
            {mode === "near" && !here
              ? "Finding your location… showing top ranked until we have it."
              : mode === "rank"
                ? "Highest priority first."
                : here
                  ? "Closest to you first. Tap the one you are standing at."
                  : "Queued candidates first."}
          </p>
          <input
            className="field-search"
            placeholder="Filter by quad (e.g. Lost Hills)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <ul className="field-list">
            {rows === undefined && <li className="muted">Loading…</li>}
            {rows && list.length === 0 && <li className="muted">No open candidates match.</li>}
            {list.map(({ c, d, dir }) => (
              <li key={c._id}>
                <button className="field-row" onClick={() => pair(c)}>
                  <span className="dot" style={{ background: dotColor(c) }} />
                  <span className="field-row-main">
                    <strong className="field-dist">{d !== undefined ? `${fmtM(d)} ${dir}` : `#${c.rank}`}</strong>
                    <span className="muted small">
                      {c.quadName} · {c.id}
                      {isFake(c) ? " · sim" : ""}
                    </span>
                    {reasonLine(c) && <span className="reason">{reasonLine(c)}</span>}
                  </span>
                  {c.status === "queued" && (
                    <span className="badge" style={{ ["--c" as string]: STATUS_META.queued.color }}>
                      Queued
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
            </>
          )}
        </>
      )}
    </main>
  );
}

function Paired({
  candidate: c,
  here,
  onBack,
  onLogged,
}: {
  candidate: Candidate;
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
  const leaking = c.status === "confirmed_leaking";

  // Gauge geometry: the trigger line sits at 2/3 of the bar unless the reading goes past it.
  const val = latest?.value ?? 0;
  const th = rule?.threshold ?? 1000;
  const top = Math.max(th * 1.5, val * 1.1, 1);
  const fillPct = Math.min(100, (val / top) * 100);
  const markPct = Math.min(100, (th / top) * 100);
  const gaugeText = leaking
    ? "Confirmed leaking."
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
  const toTarget = here ? `${fmtM(distM(here, target))} ${compass(here, target)}` : null;

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
      onLogged(`${c.id}: logged "${label}".`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save. Try again.");
      setBusy(false);
    }
  }

  // A tapped decision counts down, then saves; Undo cancels it before anything is written.
  function choose(outcome: Outcome, label: string) {
    setError(null);
    setPending({ outcome, label });
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

      <a
        className="field-nav"
        href={`https://maps.apple.com/?daddr=${c.lat},${c.lon}&dirflg=d&q=${encodeURIComponent(c.id)}`}
        target="_blank"
        rel="noopener noreferrer"
      >
        <span>Navigate</span>
        <span className="field-nav-dist">{toTarget ?? "in Maps"}</span>
      </a>

      <div className={`reading-card ${leaking ? "leak" : ""}`}>
        <div className="reading-top">
          <span className={`live-dot ${live ? "on" : ""}`} />
          <span className="small">
            {latest ? (live ? "Sensor live" : `Last reading ${age}s ago`) : "Waiting for the sensor…"}
          </span>
          {anyReplay && <span className="sim">Simulated</span>}
        </div>
        <div className="reading-value">{latest ? latest.value.toFixed(0) : "–"}</div>
        <div className="gauge" role="meter" aria-valuenow={val} aria-valuemin={0} aria-valuemax={Math.round(top)}>
          <span className={`gauge-fill ${val >= th ? "hi" : ""}`} style={{ width: `${fillPct}%` }} />
          <span className="gauge-mark" style={{ left: `${markPct}%` }} />
        </div>
        <div className="gauge-legend">
          <span>0</span>
          <span>trigger {th}</span>
        </div>
        <Sparkline values={chrono.map((r) => r.value)} />
        {gaugeText && <p className="small muted">{gaugeText}</p>}
      </div>

      {pending ? (
        <div className="undo-bar" role="status">
          <span>
            Marking <strong>{pending.label}</strong> in {secs}s
          </span>
          <button onClick={() => setPending(null)}>Undo</button>
        </div>
      ) : (
        <div className="field-actions">
          {OUTCOMES.map((o) => (
            <button
              key={o.key}
              className="field-btn"
              style={{ ["--c" as string]: STATUS_META[o.key].color }}
              disabled={busy || photoState === "uploading"}
              onClick={() => choose(o.key, o.label)}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}

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
    </section>
  );
}
