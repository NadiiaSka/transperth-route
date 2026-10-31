import { useEffect, useRef } from "react";
import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import mapWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import "maplibre-gl/dist/maplibre-gl.css";

type RouteMapProps = {
  coordinates: [number, number][];
};

const EMPTY_ROUTE: Parameters<GeoJSONSource["setData"]>[0] = {
  type: "FeatureCollection",
  features: [],
};

function endpointElement(label: "START" | "END", position: "start" | "end") {
  const element = document.createElement("div");
  element.className = `route-endpoint route-endpoint-${position}`;
  element.setAttribute("aria-label", `Route ${label.toLowerCase()}`);

  const labelElement = document.createElement("span");
  labelElement.className = "route-endpoint-label";
  labelElement.textContent = label;

  const dot = document.createElement("span");
  dot.className = "route-endpoint-dot";
  element.append(labelElement, dot);
  return element;
}

function drawRoute(
  map: MapLibreMap,
  coordinates: [number, number][],
  markers: Marker[],
) {
  const source = map.getSource("route-line") as GeoJSONSource | undefined;
  if (!source) return;

  markers.forEach((marker) => marker.remove());
  markers.length = 0;

  if (coordinates.length < 2) {
    source.setData(EMPTY_ROUTE);
    return;
  }

  const routeCoordinates = coordinates.map(([lat, lon]) => [lon, lat]);
  source.setData({
    type: "Feature",
    properties: {},
    geometry: { type: "LineString", coordinates: routeCoordinates },
  });

  markers.push(
    new maplibregl.Marker({
      element: endpointElement("START", "start"),
      anchor: "bottom",
    })
      .setLngLat(routeCoordinates[0] as [number, number])
      .addTo(map),
    new maplibregl.Marker({
      element: endpointElement("END", "end"),
      anchor: "bottom",
    })
      .setLngLat(
        routeCoordinates[routeCoordinates.length - 1] as [number, number],
      )
      .addTo(map),
  );

  const bounds = new maplibregl.LngLatBounds();
  routeCoordinates.forEach((coordinate) =>
    bounds.extend(coordinate as [number, number]),
  );
  map.fitBounds(bounds, {
    padding: { top: 54, right: 54, bottom: 54, left: 54 },
    maxZoom: 13.5,
    duration: 450,
  });
}

export function RouteMap({ coordinates }: RouteMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const mapLoadedRef = useRef(false);
  const coordinatesRef = useRef(coordinates);
  const markersRef = useRef<Marker[]>([]);

  useEffect(() => {
    coordinatesRef.current = coordinates;
  }, [coordinates]);

  useEffect(() => {
    if (!containerRef.current) return;

    maplibregl.setWorkerUrl(mapWorkerUrl);
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: {
        version: 8,
        sources: {
          openstreetmap: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
            maxzoom: 19,
          },
        },
        layers: [
          {
            id: "openstreetmap-tiles",
            type: "raster",
            source: "openstreetmap",
          },
        ],
      },
      center: [115.86, -31.95],
      zoom: 10,
      attributionControl: { compact: true },
    });

    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      "top-right",
    );
    map.on("load", () => {
      map.addSource("route-line", { type: "geojson", data: EMPTY_ROUTE });
      map.addLayer({
        id: "route-line-casing",
        type: "line",
        source: "route-line",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: {
          "line-color": "#ffffff",
          "line-width": 9,
          "line-opacity": 0.9,
        },
      });
      map.addLayer({
        id: "route-line",
        type: "line",
        source: "route-line",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#173bb8", "line-width": 5 },
      });
      mapLoadedRef.current = true;
      drawRoute(map, coordinatesRef.current, markersRef.current);
    });

    mapRef.current = map;
    return () => {
      mapLoadedRef.current = false;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (map && mapLoadedRef.current) {
      drawRoute(map, coordinates, markersRef.current);
    }
  }, [coordinates]);

  return (
    <div
      className="route-map"
      ref={containerRef}
      aria-label="Selected bus route map"
    />
  );
}
