'use client';

import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import type { Map as MLMap, GeoJSONSource } from 'maplibre-gl';
import type { Listing } from '../types';

type Props = {
  listings: Listing[];
  hoveredId: string | null;
  selectedId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
};

// V14: style URL is a module constant. Never accept from env or props
// (T-03-12: prevents tile-URL tampering / malicious style JSON).
const STYLE_URL = 'https://tiles.openfreemap.org/styles/positron';

export function MapView({
  listings,
  hoveredId,
  selectedId,
  onHover,
  onSelect,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MLMap | null>(null);
  const lastHoveredRef = useRef<string | null>(null);
  const lastSelectedRef = useRef<string | null>(null);

  // Mount map once. Pitfall 1: maplibre touches window — must be inside useEffect.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      center: [-122.4, 37.77],
      zoom: 9,
    });

    map.on('load', () => {
      map.addSource('listings', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
        cluster: true,
        clusterRadius: 50,
        clusterMaxZoom: 14,
        // promoteId required so setFeatureState({source, id}) targets feature.id
        // rather than auto-assigned ids; without this, hover highlight breaks.
        promoteId: 'id',
      });

      map.addLayer({
        id: 'clusters',
        type: 'circle',
        source: 'listings',
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': [
            'step',
            ['get', 'point_count'],
            '#a3a3a3',
            10,
            '#71717a',
            50,
            '#3f3f46',
          ],
          'circle-radius': [
            'step',
            ['get', 'point_count'],
            18,
            10,
            24,
            50,
            30,
          ],
        },
      });

      map.addLayer({
        id: 'cluster-count',
        type: 'symbol',
        source: 'listings',
        filter: ['has', 'point_count'],
        layout: {
          'text-field': '{point_count_abbreviated}',
          'text-size': 12,
        },
        paint: { 'text-color': '#fff' },
      });

      map.addLayer({
        id: 'price-pins',
        type: 'symbol',
        source: 'listings',
        filter: ['!', ['has', 'point_count']],
        layout: {
          'text-field': ['get', 'priceLabel'],
          'text-size': 12,
          'text-font': ['Noto Sans Bold'],
          'text-padding': 4,
          'text-allow-overlap': false,
        },
        paint: {
          'text-color': '#fff',
          'text-halo-color': '#18181b',
          // Larger halo when hovered or selected — feature-state drives visible
          // highlight without re-setting source data (Pitfall 8).
          'text-halo-width': [
            'case',
            ['boolean', ['feature-state', 'hovered'], false],
            8,
            ['boolean', ['feature-state', 'selected'], false],
            8,
            4,
          ],
          'text-halo-blur': 0,
        },
      });

      // Cluster click → expand.
      map.on('click', 'clusters', async (e) => {
        const f = e.features?.[0];
        if (!f) return;
        const clusterId = f.properties!.cluster_id as number;
        const src = map.getSource('listings') as GeoJSONSource;
        try {
          const zoom = await src.getClusterExpansionZoom(clusterId);
          const coords = (f.geometry as GeoJSON.Point).coordinates as [
            number,
            number,
          ];
          map.easeTo({ center: coords, zoom });
        } catch {
          /* non-fatal */
        }
      });

      // Pin click → onSelect.
      map.on('click', 'price-pins', (e) => {
        const id = e.features?.[0]?.properties?.id as string | undefined;
        if (id) onSelect(id);
      });

      // Pin hover: emit upward. The setFeatureState side-effect lives in the
      // dedicated effect below so hover state is authoritative from props.
      map.on('mouseenter', 'price-pins', (e) => {
        map.getCanvas().style.cursor = 'pointer';
        const id = e.features?.[0]?.properties?.id as string | undefined;
        if (id) onHover(id);
      });
      map.on('mouseleave', 'price-pins', () => {
        map.getCanvas().style.cursor = '';
        onHover(null);
      });
    });

    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update source data + fitBounds when listings change.
  // Pitfall 8: deps are [listings] ONLY — never [listings, hoveredId].
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const features = listings
      .filter((l) => l.data.lat != null && l.data.lng != null)
      .map((l) => ({
        type: 'Feature' as const,
        id: l.id,
        geometry: {
          type: 'Point' as const,
          coordinates: [l.data.lng as number, l.data.lat as number],
        },
        properties: {
          id: l.id,
          priceLabel:
            l.data.price != null ? `$${l.data.price.toLocaleString()}` : '—',
          address: l.data.address,
        },
      }));

    const apply = () => {
      const src = map.getSource('listings') as GeoJSONSource | undefined;
      if (!src) return;
      src.setData({ type: 'FeatureCollection', features });
      if (features.length > 0) {
        const first = features[0].geometry.coordinates as [number, number];
        const bounds = new maplibregl.LngLatBounds(first, first);
        for (const f of features) {
          bounds.extend(f.geometry.coordinates as [number, number]);
        }
        map.fitBounds(bounds, { padding: 60, duration: 600, maxZoom: 13 });
      }
    };

    if (map.isStyleLoaded()) {
      apply();
    } else {
      map.once('load', apply);
    }
  }, [listings]);

  // Hover/select feature-state sync. Maintain refs to clear the previous id.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const prev = lastHoveredRef.current;
      if (prev !== null && prev !== hoveredId) {
        try {
          map.setFeatureState(
            { source: 'listings', id: prev },
            { hovered: false }
          );
        } catch {
          /* feature may not be in source yet */
        }
      }
      if (hoveredId !== null) {
        try {
          map.setFeatureState(
            { source: 'listings', id: hoveredId },
            { hovered: true }
          );
        } catch {
          /* feature may not be in source yet */
        }
      }
      lastHoveredRef.current = hoveredId;
    };
    if (map.isStyleLoaded()) apply();
    else map.once('load', apply);
  }, [hoveredId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const prev = lastSelectedRef.current;
      if (prev !== null && prev !== selectedId) {
        try {
          map.setFeatureState(
            { source: 'listings', id: prev },
            { selected: false }
          );
        } catch {
          /* feature may not be in source yet */
        }
      }
      if (selectedId !== null) {
        try {
          map.setFeatureState(
            { source: 'listings', id: selectedId },
            { selected: true }
          );
        } catch {
          /* feature may not be in source yet */
        }
      }
      lastSelectedRef.current = selectedId;
    };
    if (map.isStyleLoaded()) apply();
    else map.once('load', apply);
  }, [selectedId]);

  return (
    <div
      ref={containerRef}
      role="region"
      aria-label="Listings map"
      style={{ width: '100%', height: '100%', minHeight: 480 }}
    />
  );
}
