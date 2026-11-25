export type RouteVariant = {
  route_id: string;
  route_number: string;
  agency_id: string | null;
  direction_id: number | null;
  headsign: string | null;
  shape_id: string | null;
  trip_count: number;
  sample_trip_id: string;
  origin_stop: string | null;
  destination_stop: string | null;
};

export async function fetchRouteVariants(
  apiBaseUrl: string,
  number: string,
): Promise<RouteVariant[]> {
  const response = await fetch(
    `${apiBaseUrl}/api/routes?number=${encodeURIComponent(number)}`,
  );
  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.detail ?? "Could not find this route.");
  }

  return [...(payload as RouteVariant[])].sort(
    (a, b) => b.trip_count - a.trip_count,
  );
}
