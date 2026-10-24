"use client";

import { useMutation, useQuery } from "convex/react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { Sparkline } from "../../components/DetailPanel";
import { api } from "../../lib/convexApi";
import { STATUS_META, dotColor } from "../../lib/types";
import type { Candidate, Reading, Status } from "../../lib/types";

type Outcome = "confirmed_leaking" | "confirmed_not_leaking" | "no_well" | "mislocated";
const OUTCOMES: { key: Outcome; label: string }[] = [
  { key: "confirmed_leaking", label: "Leaking" },
  { key: "confirmed_not_leaking", label: "Not leaking" },
  { key: "no_well", label: "No well here" },
  { key: "mislocated", label: "Wrong spot" },
];

const fmtM = (m?: number) =>
  m === undefined ? "n/a" : m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;

function getPosition(): Promise<{ lat: number; lon: number } | undefined> {
  return new Promise((resolve) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) return resolve(undefined);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => resolve(undefined),
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 15000 },
    );
  });
}

export default function FieldView() {
  const [paired, setPaired] = useState<Candidate | null>(null);
  const [query, setQuery] = useState("");
  const [done, setDone] = useState<string | null>(null);

  const rows = useQuery(api.candidates.ranked, {
    statuses: ["queued", "candidate"] as Status[],
    limit: 200,
  }) as Candidate[] | undefined;
  const pairMut = useMutation(api.pairing.set);
  const clearMut = useMutation(api.pairing.clear);

  // Queued first, then by rank; filter by what the person types.
  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all = (rows ?? []).filter(
      (c) => !q || c.id.toLowerCase().includes(q) || c.quadName.toLowerCase().includes(q),
    );
    return [...all].sort((a, b) => Number(b.status === "queued") - Number(a.status === "queued") || a.rank - b.rank);
  }, [rows, query]);

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
        <Link href="/" className="link-btn">
          Command Map
        </Link>
      </header>
      {done && <div className="field-toast">{done}</div>}
      {paired ? (
        <Paired
          candidate={rows?.find((r) => r.id === paired.id) ?? paired}
          onBack={unpair}
          onLogged={(msg) => {
            setDone(msg);
            void unpair();
          }}
        />
      ) : (
        <>
          <p className="muted">Pick the candidate you are standing at. Your sensor readings attach to it automatically.</p>
          <input
            className="field-search"
            placeholder="Search id or quad (e.g. Lost Hills)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <ul className="field-list">
            {rows === undefined && <li className="muted">Loading…</li>}
            {rows && list.length === 0 && <li className="muted">No open candidates match.</li>}
            {list.map((c) => (
              <li key={c._id}>
                <button className="field-row" onClick={() => pair(c)}>
                  <span className="dot" style={{ background: dotColor(c) }} />
                  <span className="field-row-main">
                    <strong>{c.id}</strong>
                    <span className="muted small">
                      {c.quadName} · rank {c.rank}
                    </span>
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
    </main>
  );
}

function Paired({
  candidate: c,
  onBack,
  onLogged,
}: {
  candidate: Candidate;
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

  return (
    <section className="field-paired">
      <button className="link-btn" onClick={onBack}>
        ← Pick a different candidate
      </button>
      <h2>
        <span className="dot" style={{ background: dotColor(c) }} /> {c.id}
      </h2>
      <p className="muted small">
        {c.quadName} quad · {fmtM(c.distToHomeM)} to nearest home · {fmtM(c.distToWaterM)} to water
      </p>

      <div className={`reading-card ${leaking ? "leak" : ""}`}>
        <div className="reading-top">
          <span className={`live-dot ${live ? "on" : ""}`} />
          <span className="small">
            {latest ? (live ? "Sensor live" : `Last reading ${age}s ago`) : "Waiting for the sensor…"}
          </span>
          {anyReplay && <span className="sim">Simulated</span>}
        </div>
        <div className="reading-value">{latest ? latest.value.toFixed(0) : "–"}</div>
        <Sparkline values={chrono.map((r) => r.value)} />
        {rule && (
          <p className="small muted">
            {leaking
              ? "Confirmed leaking."
              : `${Math.min(hot, rule.count)} of ${rule.count} high readings (≥ ${rule.threshold}) in the last ${
                  rule.windowMs / 1000
                } s. At ${rule.count} it confirms automatically.`}
          </p>
        )}
      </div>

      <div className="field-actions">
        {OUTCOMES.map((o) => (
          <button
            key={o.key}
            className="field-btn"
            style={{ ["--c" as string]: STATUS_META[o.key].color }}
            disabled={busy || photoState === "uploading"}
            onClick={() => log(o.key, o.label)}
          >
            {o.label}
          </button>
        ))}
      </div>

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
