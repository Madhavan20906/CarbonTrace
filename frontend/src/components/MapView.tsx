import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

export interface MapPolygon { id: string | number; ring: number[][]; color: string; label?: string; onClick?: () => void }
export interface MapPoint { id: string | number; lat: number; lon: number; radius: number; color: string; label?: string; onClick?: () => void }
export interface Draft { points: [number, number][]; enabled: boolean; onAdd: (p: [number, number]) => void }

interface Props {
  polygons?: MapPolygon[];
  points?: MapPoint[];
  draft?: Draft;
  height?: number;
  fit?: boolean;
  label: string;
}

const TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

export default function MapView({ polygons = [], points = [], draft, height = 420, fit = true, label }: Props) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const shapes = useRef<L.LayerGroup | null>(null);
  const drawing = useRef<L.LayerGroup | null>(null);
  const draftRef = useRef(draft);
  draftRef.current = draft;

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { zoomControl: true, attributionControl: true }).setView([15, 40], 2);
    L.tileLayer(TILES, { maxZoom: 18, attribution: "Imagery © Esri, Maxar, Earthstar Geographics" }).addTo(m);
    shapes.current = L.layerGroup().addTo(m);
    drawing.current = L.layerGroup().addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => {
      const d = draftRef.current;
      if (d?.enabled) d.onAdd([e.latlng.lng, e.latlng.lat]);
    });
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current, g = shapes.current;
    if (!m || !g) return;
    g.clearLayers();
    const bounds: L.LatLngBounds[] = [];
    for (const p of polygons) {
      const latlngs = p.ring.map(([lon, lat]) => [lat, lon] as [number, number]);
      const poly = L.polygon(latlngs, { color: p.color, weight: 2, fillOpacity: 0.28 }).addTo(g);
      if (p.label) poly.bindTooltip(p.label, { sticky: true });
      if (p.onClick) poly.on("click", p.onClick);
      bounds.push(poly.getBounds());
    }
    for (const p of points) {
      const c = L.circleMarker([p.lat, p.lon], { radius: p.radius, color: "#fff", weight: 2, fillColor: p.color, fillOpacity: 0.92 }).addTo(g);
      if (p.label) c.bindTooltip(p.label, { sticky: true });
      if (p.onClick) c.on("click", p.onClick);
      bounds.push(L.latLngBounds([[p.lat, p.lon], [p.lat, p.lon]]));
    }
    if (fit && bounds.length) {
      const all = bounds.reduce((a, b) => a.extend(b));
      m.fitBounds(all, { padding: [40, 40], maxZoom: polygons.length ? 15 : 6 });
    }
  }, [polygons, points, fit]);

  useEffect(() => {
    const g = drawing.current;
    if (!g) return;
    g.clearLayers();
    if (!draft || draft.points.length === 0) return;
    const ll = draft.points.map(([lon, lat]) => [lat, lon] as [number, number]);
    if (ll.length >= 3) L.polygon(ll, { color: "#ff7a1a", weight: 2, fillOpacity: 0.2, dashArray: "6 4" }).addTo(g);
    else L.polyline(ll, { color: "#ff7a1a", weight: 2, dashArray: "6 4" }).addTo(g);
    ll.forEach((p, i) => L.circleMarker(p, { radius: i === 0 ? 6 : 4, color: "#fff", weight: 2, fillColor: "#ff7a1a", fillOpacity: 1 }).addTo(g));
  }, [draft]);

  return (
    <div className="map-frame" style={{ height }}>
      <div ref={el} className="map" role="application" aria-label={label} style={{ height: "100%" }} />
    </div>
  );
}
