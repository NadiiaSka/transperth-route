import httpx

from .config import settings
from .schemas import Leg, Maneuver, PatternStop


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
