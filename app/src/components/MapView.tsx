"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { GeoJSONSource, Map as MapLibreMap } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import { SCORE_RAMP, STATUS_META } from "../lib/types";
import type { Candidate } from "../lib/types";

// Satellite basemap: Esri World Imagery (no key). Swap via NEXT_PUBLIC_BASEMAP_URL.
const BASEMAP_URL =
  process.env.NEXT_PUBLIC_BASEMAP_URL ||
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";
const BASEMAP_ATTRIBUTION =
  process.env.NEXT_PUBLIC_BASEMAP_ATTRIBUTION ||
  "Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community";

const KERN_CENTER: [number, number] = [-119.35, 35.38];

type Sheet = { id: string; name: string; year: number; url: string; corners: [number, number][] };

type Props = {
  rows: Candidate[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  /** Phone layout: no layer panel, legend or zoom slider; pinch to zoom. */
  compact?: boolean;
  /** The phone's own position, drawn as a blue dot when given. */
  here?: { lat: number; lon: number };
  /** Bump `n` to play a short expanding-ring pulse on candidate `id` (a live status change). */
  pulse?: { id: string; n: number } | null;
};

const hereGeoJSON = (h?: { lat: number; lon: number }) => ({
  type: "FeatureCollection" as const,
  features: h
    ? [{ type: "Feature" as const, geometry: { type: "Point" as const, coordinates: [h.lon, h.lat] }, properties: {} }]
    : [],
});

function toGeoJSON(rows: Candidate[]) {
  return {
    type: "FeatureCollection" as const,
    features: rows.map((c) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [c.lon, c.lat] },
      properties: { id: c.id, score: c.rankScore, status: c.status },
    })),
  };
}

export default function MapView({ rows, selectedId, onSelect, compact, here, pulse }: Props) {
  const hereRef = useRef(here);
  const centeredRef = useRef(false);
  hereRef.current = here;
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const readyRef = useRef(false);
  const rowsRef = useRef(rows);
  const selectRef = useRef(onSelect);
  const [histOn, setHistOn] = useState(false);
  const [opacity, setOpacity] = useState(70);
  const [sheets, setSheets] = useState<Sheet[]>([]);
  const [sheetSel, setSheetSel] = useState<string>("all");
  const [mapReady, setMapReady] = useState(false);
  const [zoom, setZoom] = useState(8.4);
  // CalGEM documented wells: "none" = file not published yet, "off"/"on" = available.
  const [wellsOn, setWellsOn] = useState(true);
  const [wellsAvail, setWellsAvail] = useState<"checking" | "yes" | "no">("checking");
  const wellsData = useRef<unknown>(null);
  rowsRef.current = rows;
  selectRef.current = onSelect;

  // Create the map once.
  useEffect(() => {
    let cancelled = false;
    let created: MapLibreMap | null = null;

    (async () => {
      const maplibregl = await import("maplibre-gl");
      if (cancelled || !el.current) return;
      // See scripts/copy-maplibre-worker.mjs: the bundler breaks MapLibre's default worker lookup.
      maplibregl.setWorkerUrl(new URL("/maplibre/maplibre-gl-worker.mjs", window.location.href).href);

      const map: MapLibreMap = new maplibregl.Map({
        container: el.current,
        center: KERN_CENTER,
        zoom: 8.4,
        attributionControl: { compact: true },
        style: {
          version: 8,
          sources: {
            satellite: {
              type: "raster",
              tiles: [BASEMAP_URL],
              tileSize: 256,
              maxzoom: 19,
              attribution: BASEMAP_ATTRIBUTION,
            },
          },
          layers: [{ id: "satellite", type: "raster", source: "satellite" }],
        },
      });
      created = map;
      mapRef.current = map;
      map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

      map.on("load", () => {
        map.addSource("candidates", { type: "geojson", data: toGeoJSON(rowsRef.current) });

        const statusMatch: unknown[] = ["match", ["get", "status"]];
        (Object.keys(STATUS_META) as (keyof typeof STATUS_META)[])
          .filter((s) => s !== "candidate")
          .forEach((s) =>
            // Not-leaking is drawn as a hollow ring (see the ring layer below), so its fill is clear.
            statusMatch.push(s, s === "confirmed_not_leaking" ? "rgba(0,0,0,0)" : STATUS_META[s].color),
          );
        statusMatch.push([
          "interpolate",
          ["linear"],
          ["get", "score"],
          0,
          SCORE_RAMP[0],
          0.5,
          SCORE_RAMP[1],
          1,
          SCORE_RAMP[2],
        ]);

        map.addLayer({
          id: "candidates-halo",
          type: "circle",
          source: "candidates",
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 8, 13, 17],
            "circle-color": "#0b0f14",
            "circle-opacity": 0.55,
            "circle-blur": 0,
          },
        });
        map.addLayer({
          id: "candidates",
          type: "circle",
          source: "candidates",
          paint: {
            "circle-color": statusMatch as never,
            "circle-radius": [
              "interpolate", ["linear"], ["zoom"],
              7, ["case", ["==", ["get", "status"], "confirmed_leaking"], 7, 4],
              13, ["case", ["==", ["get", "status"], "confirmed_leaking"], 14, 9],
            ],
            "circle-stroke-color": "#0b0f14",
            "circle-stroke-width": 1.5,
            "circle-opacity": ["match", ["get", "status"], ["no_well", "mislocated"], 0.55, 0.95],
          },
        });
        // Status symbols that colour alone can't carry on satellite imagery:
        // queued = white ring, leaking = wide red ring, not leaking = hollow green ring.
        const radius = (a: number, b: number) => ["interpolate", ["linear"], ["zoom"], 7, a, 13, b] as never;
        map.addLayer({
          id: "candidates-queued",
          type: "circle",
          source: "candidates",
          filter: ["==", ["get", "status"], "queued"],
          paint: {
            "circle-radius": radius(8, 14),
            "circle-color": "rgba(0,0,0,0)",
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2,
          },
        });
        map.addLayer({
          id: "candidates-leaking-ring",
          type: "circle",
          source: "candidates",
          filter: ["==", ["get", "status"], "confirmed_leaking"],
          paint: {
            "circle-radius": radius(12, 24),
            "circle-color": "rgba(0,0,0,0)",
            "circle-stroke-color": STATUS_META.confirmed_leaking.color,
            "circle-stroke-width": 2,
            "circle-stroke-opacity": 0.55,
          },
        });
        map.addLayer({
          id: "candidates-notleaking-ring",
          type: "circle",
          source: "candidates",
          filter: ["==", ["get", "status"], "confirmed_not_leaking"],
          paint: {
            "circle-radius": radius(4.5, 9.5),
            "circle-color": "rgba(0,0,0,0)",
            "circle-stroke-color": STATUS_META.confirmed_not_leaking.color,
            "circle-stroke-width": 2.5,
          },
        });
        map.addSource("pulse", { type: "geojson", data: hereGeoJSON(undefined) });
        map.addLayer({
          id: "pulse",
          type: "circle",
          source: "pulse",
          paint: {
            "circle-radius": 0,
            "circle-color": "rgba(0,0,0,0)",
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 3,
            "circle-stroke-opacity": 0,
          },
        });

        map.addLayer({
          id: "candidates-selected",
          type: "circle",
          source: "candidates",
          filter: ["==", ["get", "id"], ""],
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 7, 9, 13, 17],
            "circle-color": "rgba(0,0,0,0)",
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 2.5,
          },
        });

        map.addSource("here", { type: "geojson", data: hereGeoJSON(hereRef.current) });
        map.addLayer({
          id: "here-halo",
          type: "circle",
          source: "here",
          paint: { "circle-radius": 16, "circle-color": "#7b8ce7", "circle-opacity": 0.25 },
        });
        map.addLayer({
          id: "here",
          type: "circle",
          source: "here",
          paint: { "circle-radius": 6, "circle-color": "#7b8ce7", "circle-stroke-color": "#ffffff", "circle-stroke-width": 2.5 },
        });

        map.on("click", "candidates", (e) => {
          const id = e.features?.[0]?.properties?.id;
          if (typeof id === "string") selectRef.current(id);
        });
        map.on("mouseenter", "candidates", () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "candidates", () => (map.getCanvas().style.cursor = ""));
        readyRef.current = true;
        setMapReady(true);
        map.on("zoom", () => setZoom(map.getZoom()));
      });
    })();

    return () => {
      cancelled = true;
      readyRef.current = false;
      setMapReady(false);
      created?.remove();
      mapRef.current = null;
    };
  }, []);

  // Documented wells (CalGEM): one compact file, loaded once, drawn as hollow rings under the candidates.
  useEffect(() => {
    let alive = true;
    fetch("/calgem/wells.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((d) => {
        if (!alive) return;
        wellsData.current = d;
        setWellsAvail("yes");
      })
      .catch(() => alive && setWellsAvail("no"));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || wellsAvail !== "yes") return;
    if (!map.getSource("calgem")) {
      map.addSource("calgem", { type: "geojson", data: wellsData.current as never });
      // Zoomed out: a soft density glow. Zoomed in: individual rings. Never a solid white mass.
      map.addLayer(
        {
          id: "calgem-heat",
          type: "heatmap",
          source: "calgem",
          maxzoom: 12.5,
          paint: {
            "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 7, 9, 11, 30],
            "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 7, 0.12, 11, 0.4],
            "heatmap-color": [
              "interpolate", ["linear"], ["heatmap-density"],
              0, "rgba(255,255,255,0)",
              0.2, "rgba(255,255,255,0.08)",
              0.6, "rgba(255,255,255,0.2)",
              1, "rgba(255,255,255,0.38)",
            ],
            "heatmap-opacity": ["interpolate", ["linear"], ["zoom"], 10.5, 0.9, 12.5, 0],
          },
        },
        "candidates-halo",
      );
      map.addLayer(
        {
          id: "calgem-wells",
          type: "circle",
          source: "calgem",
          minzoom: 11.5,
          paint: {
            "circle-color": "rgba(0,0,0,0)",
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 11.5, 1.3, 14, 3, 17, 6],
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 11.5, 0.5, 14, 1, 17, 1.4],
            "circle-stroke-opacity": ["interpolate", ["linear"], ["zoom"], 11.5, 0.35, 14, 0.7, 16, 0.9],
          },
        },
        "candidates-halo",
      );
    }
    for (const id of ["calgem-heat", "calgem-wells"]) map.setLayoutProperty(id, "visibility", wellsOn ? "visible" : "none");
  }, [wellsAvail, wellsOn, mapReady]);

  // Historical sheets: public/historical/manifest.json is written by pipeline/geotiff_to_overlay.py.
  useEffect(() => {
    let alive = true;
    fetch("/historical/manifest.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : []))
      .then((m) => alive && Array.isArray(m) && setSheets(m as Sheet[]))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // Add each sheet as an image layer under the candidate dots; show/hide and fade on demand.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    for (const sh of sheets) {
      const id = `hist-${sh.id}`;
      if (!map.getSource(id)) {
        map.addSource(id, {
          type: "image",
          url: sh.url,
          coordinates: sh.corners as [[number, number], [number, number], [number, number], [number, number]],
        });
        map.addLayer(
          { id, type: "raster", source: id, layout: { visibility: "none" }, paint: { "raster-opacity": 0.7, "raster-fade-duration": 0 } },
          map.getLayer("calgem-heat") ? "calgem-heat" : "candidates-halo",
        );
      }
      const show = histOn && (sheetSel === "all" || sheetSel === sh.id);
      map.setLayoutProperty(id, "visibility", show ? "visible" : "none");
      map.setPaintProperty(id, "raster-opacity", opacity / 100);
    }
  }, [sheets, histOn, sheetSel, opacity, mapReady]);

  // Jump to the sheet(s) when the overlay is switched on or the sheet changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !histOn) return;
    const shown = sheets.filter((s) => sheetSel === "all" || s.id === sheetSel);
    if (!shown.length) return;
    const lons = shown.flatMap((s) => s.corners.map((c) => c[0]));
    const lats = shown.flatMap((s) => s.corners.map((c) => c[1]));
    map.fitBounds(
      [[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
      { padding: 60, duration: 700 },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [histOn, sheetSel, mapReady]);

  // Push live data into the map whenever the query result changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    (map.getSource("candidates") as GeoJSONSource | undefined)?.setData(toGeoJSON(rows));
  }, [rows]);

  // Phone position: keep the blue dot current; on the first fix near the candidates, move there.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    (map.getSource("here") as GeoJSONSource | undefined)?.setData(hereGeoJSON(here));
    if (!compact || !here || centeredRef.current || selectedId) return;
    centeredRef.current = true;
    const near = rowsRef.current.some((r) => Math.abs(r.lat - here.lat) < 1 && Math.abs(r.lon - here.lon) < 1.2);
    if (near) map.jumpTo({ center: [here.lon, here.lat], zoom: 13 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [here, mapReady, compact]);

  // Live status change: two expanding rings in the new status colour, ~2.4 s.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady || !pulse) return;
    const c = rowsRef.current.find((r) => r.id === pulse.id);
    const src = map.getSource("pulse") as GeoJSONSource | undefined;
    if (!c || !src) return;
    src.setData(hereGeoJSON({ lat: c.lat, lon: c.lon }));
    map.setPaintProperty("pulse", "circle-stroke-color", STATUS_META[c.status].color);
    const start = performance.now();
    const DUR = 2400;
    let raf = 0;
    const tick = (t: number) => {
      const k = (t - start) / DUR;
      if (k >= 1) {
        map.setPaintProperty("pulse", "circle-stroke-opacity", 0);
        return;
      }
      const phase = (k * 2) % 1;
      map.setPaintProperty("pulse", "circle-radius", 10 + phase * 40);
      map.setPaintProperty("pulse", "circle-stroke-opacity", 0.9 * (1 - phase));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pulse?.n, mapReady]);

  // Highlight and fly to the selected candidate.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    map.setFilter("candidates-selected", ["==", ["get", "id"], selectedId ?? ""]);
    const c = selectedId ? rowsRef.current.find((r) => r.id === selectedId) : undefined;
    if (c) map.easeTo({ center: [c.lon, c.lat], zoom: Math.max(map.getZoom(), 11), duration: 600 });
  }, [selectedId]);

  return (
    <div className={`map ${selectedId ? "panel-open" : ""}`}>
      <div ref={el} className="map-canvas" />

      {compact && here && (
        <button
          className="map-me"
          onClick={() => mapRef.current?.easeTo({ center: [here.lon, here.lat], zoom: 14, duration: 600 })}
        >
          Me
        </button>
      )}

      {!compact && (
        <>
      <div className="map-control" aria-label="Map layers">
        <label className={`toggle ${wellsAvail === "yes" ? "" : "disabled"}`} title="Wells already in the state's CalGEM records: a density glow zoomed out, individual rings zoomed in.">
          <input
            type="checkbox"
            checked={wellsAvail === "yes" && wellsOn}
            disabled={wellsAvail !== "yes"}
            onChange={(e) => setWellsOn(e.target.checked)}
          />
          <span>Documented wells (CalGEM)</span>
          {wellsAvail === "no" && <em>not loaded</em>}
        </label>
        {sheets.length === 0 ? (
          <label className="toggle disabled" title="Add a converted sheet with pipeline/geotiff_to_overlay.py">
            <input type="checkbox" checked={false} disabled readOnly />
            <span>Historical map overlay</span>
            <em>no sheets yet</em>
          </label>
        ) : (
          <>
            <label className="toggle">
              <input type="checkbox" checked={histOn} onChange={(e) => setHistOn(e.target.checked)} />
              <span>Historical map overlay</span>
              {histOn && sheetSel !== "all" && (
                <em>{sheets.find((s) => s.id === sheetSel)?.year}</em>
              )}
            </label>
            {sheets.length > 1 && (
              <select
                className="sheet-select"
                value={sheetSel}
                onChange={(e) => setSheetSel(e.target.value)}
                aria-label="Which historical sheet"
              >
                <option value="all">All sheets</option>
                {sheets.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} · {s.year}
                  </option>
                ))}
              </select>
            )}
            <input
              type="range"
              min={0}
              max={100}
              value={opacity}
              disabled={!histOn}
              onChange={(e) => setOpacity(Number(e.target.value))}
              aria-label="Overlay opacity"
            />
          </>
        )}
      </div>

      <div className="zoom-slider" aria-label="Zoom">
        <input
          type="range"
          min={6}
          max={18}
          step={0.05}
          value={Math.min(18, Math.max(6, zoom))}
          onChange={(e) => mapRef.current?.setZoom(Number(e.target.value))}
          aria-label="Zoom level"
          title="Drag to zoom"
        />
      </div>

      <div className="legend" aria-label="Legend">
        <div className="legend-title">Candidate score</div>
        <div
          className="ramp"
          style={{ background: `linear-gradient(90deg, ${SCORE_RAMP.join(",")})` }}
        />
        <div className="ramp-labels">
          <span>low</span>
          <span>high</span>
        </div>
        {wellsAvail === "yes" && wellsOn && (
          <div className="legend-row">
            <span className="dot ring" />
            In CalGEM records
          </div>
        )}
        {(Object.keys(STATUS_META) as (keyof typeof STATUS_META)[])
          .filter((s) => s !== "candidate")
          .map((s) => (
            <div key={s} className="legend-row">
              {s === "queued" ? (
                <span className="dot ring" />
              ) : s === "confirmed_not_leaking" ? (
                <span className="dot ring" style={{ borderColor: STATUS_META[s].color }} />
              ) : (
                <span
                  className="dot"
                  style={{ background: STATUS_META[s].color, opacity: s === "no_well" || s === "mislocated" ? 0.55 : 1 }}
                />
              )}
              {STATUS_META[s].label}
            </div>
          ))}
      </div>
        </>
      )}
    </div>
  );
}
