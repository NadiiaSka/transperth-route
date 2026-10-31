import math

import httpx

from .config import settings
from .schemas import (
    Leg,
    Maneuver,
    MatchCoordinate,
    MatchTracepoint,
    PatternStop,
    ShapeMatchDiagnostics,
    ShapeMatchSegment,
)


def _coords(stops: list[PatternStop]) -> str:
    return ";".join(f"{s.lon:.6f},{s.lat:.6f}" for s in stops)


def get_legs(stops: list[PatternStop]) -> list[Leg]:
    """Road-level maneuvers between consecutive stops, from OSRM."""
    if len(stops) < 2:
        return []
    resp = httpx.get(
        f"{settings.osrm_url}/route/v1/driving/{_coords(stops)}",
        params={"steps": "true", "overview": "false", "continue_straight": "true"},
        timeout=30,
    )
    data = resp.json()
    if resp.status_code != 200 or data.get("code") != "Ok":
        raise RuntimeError(f"OSRM error: {data.get('code')} {data.get('message', '')}")

    legs = []
    for i, leg in enumerate(data["routes"][0]["legs"]):
        steps = [
            Maneuver(
                type=s["maneuver"]["type"],
                modifier=s["maneuver"].get("modifier"),
                road=s.get("name") or None,
                roundabout_exit=s["maneuver"].get("exit"),
                distance_m=round(s["distance"]),
            )
            for s in leg["steps"]
            # "arrive" markers carry no driving action between stops.
            if s["maneuver"]["type"] != "arrive"
        ]
        legs.append(
            Leg(
                from_stop=stops[i].stop_name,
                to_stop=stops[i + 1].stop_name,
                from_sequence=stops[i].sequence,
                to_sequence=stops[i + 1].sequence,
                distance_m=round(leg["distance"]),
                steps=steps,
            )
        )
    return legs


def match_shape(shape: list[tuple[float, float]]) -> list[Maneuver]:
    """Get road maneuvers while following the GTFS route geometry."""
    if len(shape) < 2:
        return []
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in shape)
    resp = httpx.get(
        f"{settings.osrm_url}/match/v1/driving/{coords}",
        params={"steps": "true", "overview": "false", "gaps": "ignore"},
        timeout=60,
    )
    data = resp.json()
    if resp.status_code != 200 or data.get("code") != "Ok":
        raise RuntimeError(f"OSRM match error: {data.get('code')} {data.get('message', '')}")

    return [
        Maneuver(
            type=step["maneuver"]["type"],
            modifier=step["maneuver"].get("modifier"),
            road=step.get("name") or None,
            roundabout_exit=step["maneuver"].get("exit"),
            distance_m=round(step["distance"]),
        )
        for matching in data["matchings"]
        for leg in matching["legs"]
        for step in leg["steps"]
        if step["maneuver"]["type"] != "arrive"
    ]


def _distance_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def _distance_to_shape(point: tuple[float, float], shape: list[tuple[float, float]]) -> float:
    lat, lon = point
    lon_scale = 111_320 * math.cos(math.radians(lat))
    nearest = math.inf
    for start, end in zip(shape, shape[1:]):
        ax, ay = (start[1] - lon) * lon_scale, (start[0] - lat) * 111_320
        bx, by = (end[1] - lon) * lon_scale, (end[0] - lat) * 111_320
        dx, dy = bx - ax, by - ay
        length_squared = dx * dx + dy * dy
        fraction = 0 if length_squared == 0 else max(0, min(1, -(ax * dx + ay * dy) / length_squared))
        nearest = min(nearest, math.hypot(ax + fraction * dx, ay + fraction * dy))
    return nearest


def diagnose_shape_match(shape: list[tuple[float, float]]) -> ShapeMatchDiagnostics:
    """Return OSRM's snaps and compare its matched geometry with the GTFS line."""
    if len(shape) < 2:
        raise ValueError("A route shape needs at least two points")

    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in shape)
    resp = httpx.get(
        f"{settings.osrm_url}/match/v1/driving/{coords}",
        params={
            "steps": "true",
            "overview": "full",
            "geometries": "geojson",
            "gaps": "ignore",
        },
        timeout=60,
    )
    data = resp.json()
    if resp.status_code != 200 or data.get("code") != "Ok":
        raise RuntimeError(f"OSRM match error: {data.get('code')} {data.get('message', '')}")

    tracepoints = []
    snap_distances = []
    for index, (point, matched) in enumerate(zip(shape, data["tracepoints"])):
        snapped = None
        snap_distance = None
        if matched is not None:
            snapped = MatchCoordinate(lat=matched["location"][1], lon=matched["location"][0])
            snap_distance = _distance_m(point, (snapped.lat, snapped.lon))
            snap_distances.append(snap_distance)
        tracepoints.append(
            MatchTracepoint(
                input_index=index,
                input=MatchCoordinate(lat=point[0], lon=point[1]),
                snapped=snapped,
                snap_distance_m=round(snap_distance, 1) if snap_distance is not None else None,
                matching_index=matched.get("matchings_index") if matched is not None else None,
                waypoint_index=matched.get("waypoint_index") if matched is not None else None,
            )
        )

    matchings = []
    matched_geometry = []
    for matching in data["matchings"]:
        geometry = [
            MatchCoordinate(lat=lat, lon=lon)
            for lon, lat in matching["geometry"]["coordinates"]
        ]
        matched_geometry.extend((point.lat, point.lon) for point in geometry)
        segment_deviations = [
            _distance_to_shape((point.lat, point.lon), shape)
            for point in geometry[:: max(1, len(geometry) // 500)]
        ]
        sorted_segment_deviations = sorted(segment_deviations)
        segment_p95_index = max(0, math.ceil(len(sorted_segment_deviations) * 0.95) - 1)
        streets = []
        for leg in matching["legs"]:
            for step in leg["steps"]:
                name = step.get("name")
                if name and (not streets or streets[-1] != name):
                    streets.append(name)
        matchings.append(
            ShapeMatchSegment(
                confidence=matching["confidence"],
                distance_m=round(matching["distance"], 1),
                p95_geometry_deviation_m=round(sorted_segment_deviations[segment_p95_index], 1)
                if sorted_segment_deviations
                else None,
                max_geometry_deviation_m=round(max(segment_deviations), 1)
                if segment_deviations
                else None,
                streets=streets,
                geometry=geometry,
            )
        )

    gtfs_length = sum(_distance_m(a, b) for a, b in zip(shape, shape[1:]))
    matched_length = sum(matching.distance_m for matching in matchings)
    deviations = [
        _distance_to_shape(point, shape)
        for point in matched_geometry[:: max(1, len(matched_geometry) // 500)]
    ]
    sorted_deviations = sorted(deviations)
    p95_index = max(0, math.ceil(len(sorted_deviations) * 0.95) - 1)

    return ShapeMatchDiagnostics(
        input_point_count=len(shape),
        matched_point_count=len(snap_distances),
        unmatched_point_count=len(shape) - len(snap_distances),
        matching_count=len(matchings),
        gtfs_length_m=round(gtfs_length, 1),
        matched_length_m=round(matched_length, 1),
        length_ratio=round(matched_length / gtfs_length, 3) if gtfs_length else None,
        mean_snap_distance_m=round(sum(snap_distances) / len(snap_distances), 1)
        if snap_distances
        else None,
        p95_snap_distance_m=round(
            sorted(snap_distances)[max(0, math.ceil(len(snap_distances) * 0.95) - 1)], 1
        )
        if snap_distances
        else None,
        p95_geometry_deviation_m=round(sorted_deviations[p95_index], 1)
        if sorted_deviations
        else None,
        max_geometry_deviation_m=round(max(deviations), 1) if deviations else None,
        tracepoints=tracepoints,
        matchings=matchings,
    )
