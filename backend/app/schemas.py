from pydantic import BaseModel


class RouteVariant(BaseModel):
    route_id: str
    route_number: str
    agency_id: str | None
    direction_id: int | None
    headsign: str | None
    shape_id: str | None
    trip_count: int
    sample_trip_id: str
    origin_stop: str | None
    destination_stop: str | None


class PatternStop(BaseModel):
    sequence: int
    stop_id: str
    stop_code: str | None
    stop_name: str
    lat: float
    lon: float
    arrival_time: str | None


class Maneuver(BaseModel):
    type: str
    modifier: str | None
    road: str | None
    roundabout_exit: int | None
    distance_m: int
    # L/R computed from approach vs departure geometry at roundabouts
    roundabout_turn: str | None = None


class Leg(BaseModel):
    from_stop: str
    to_stop: str
    from_sequence: int
    to_sequence: int
    distance_m: int
    steps: list[Maneuver]


class DriverStep(BaseModel):
    step: int
    type: str
    turn: str | None = None
    instruction: str
    maneuver: str | None = None
    modifier: str | None = None
    road: str | None = None
    roundabout_exit: int | None = None
    distance_m: int = 0
    cumulative_m: int = 0
    # True when a traffic-signal node sits at this turn; the UI tags the
    # street/landmark column rather than wording it into the instruction.
    traffic_signal: bool = False


class RoutePattern(BaseModel):
    variant: RouteVariant
    stops: list[PatternStop]
    # [lat, lon] pairs along the road geometry
    shape: list[tuple[float, float]]


class MatchCoordinate(BaseModel):
    lat: float
    lon: float


class MatchTracepoint(BaseModel):
    input_index: int
    input: MatchCoordinate
    snapped: MatchCoordinate | None
    snap_distance_m: float | None
    matching_index: int | None
    waypoint_index: int | None


class ShapeMatchSegment(BaseModel):
    confidence: float
    distance_m: float
    p95_geometry_deviation_m: float | None
    max_geometry_deviation_m: float | None
    streets: list[str]
    geometry: list[MatchCoordinate]


class ShapeMatchDiagnostics(BaseModel):
    input_point_count: int
    matched_point_count: int
    unmatched_point_count: int
    matching_count: int
    gtfs_length_m: float
    matched_length_m: float
    length_ratio: float | None
    mean_snap_distance_m: float | None
    p95_snap_distance_m: float | None
    p95_geometry_deviation_m: float | None
    max_geometry_deviation_m: float | None
    tracepoints: list[MatchTracepoint]
    matchings: list[ShapeMatchSegment]
