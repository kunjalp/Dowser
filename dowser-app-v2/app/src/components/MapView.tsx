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

type Props = {
  rows: Candidate[];
  selectedId: string | null;
  onSelect: (id: string) => void;
};

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

export default function MapView({ rows, selectedId, onSelect }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const readyRef = useRef(false);
  const rowsRef = useRef(rows);
  const selectRef = useRef(onSelect);
  const [histOn, setHistOn] = useState(false);
  const [opacity, setOpacity] = useState(70);
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
          .forEach((s) => statusMatch.push(s, STATUS_META[s].color));
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
            "circle-opacity": 0.95,
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

        map.on("click", "candidates", (e) => {
          const id = e.features?.[0]?.properties?.id;
          if (typeof id === "string") selectRef.current(id);
        });
        map.on("mouseenter", "candidates", () => (map.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "candidates", () => (map.getCanvas().style.cursor = ""));
        readyRef.current = true;
      });
    })();

    return () => {
      cancelled = true;
      readyRef.current = false;
      created?.remove();
      mapRef.current = null;
    };
  }, []);

  // Push live data into the map whenever the query result changes.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    (map.getSource("candidates") as GeoJSONSource | undefined)?.setData(toGeoJSON(rows));
  }, [rows]);

  // Highlight and fly to the selected candidate.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !readyRef.current) return;
    map.setFilter("candidates-selected", ["==", ["get", "id"], selectedId ?? ""]);
    const c = selectedId ? rowsRef.current.find((r) => r.id === selectedId) : undefined;
    if (c) map.easeTo({ center: [c.lon, c.lat], zoom: Math.max(map.getZoom(), 11), duration: 600 });
  }, [selectedId]);

  return (
    <div className="map">
      <div ref={el} className="map-canvas" />

      <div className="map-control" aria-label="Historical map overlay">
        <label className="toggle disabled" title="The historical overlay arrives Saturday (from Ryann's converted sheets)">
          <input type="checkbox" checked={histOn} disabled onChange={(e) => setHistOn(e.target.checked)} />
          <span>Historical map overlay</span>
          <em>coming soon</em>
        </label>
        <input
          type="range"
          min={0}
          max={100}
          value={opacity}
          disabled
          onChange={(e) => setOpacity(Number(e.target.value))}
          aria-label="Overlay opacity"
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
        {(Object.keys(STATUS_META) as (keyof typeof STATUS_META)[])
          .filter((s) => s !== "candidate")
          .map((s) => (
            <div key={s} className="legend-row">
              <span className="dot" style={{ background: STATUS_META[s].color }} />
              {STATUS_META[s].label}
            </div>
          ))}
      </div>
    </div>
  );
}
