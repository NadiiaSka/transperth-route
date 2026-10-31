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


class Leg(BaseModel):
    from_stop: str
    to_stop: str
    from_sequence: int
    to_sequence: int
    distance_m: int
    steps: list[Maneuver]


class DriverStep(BaseModel):
    step: int
    type: str  # "stop" | "depart" | "maneuver"
    instruction: str
    maneuver: str | None = None
    modifier: str | None = None
    road: str | None = None
    distance_m: int = 0
    cumulative_m: int = 0
    stop_sequence: int | None = None
    stop_code: str | None = None
    stop_name: str | None = None


class RoutePattern(BaseModel):
    variant: RouteVariant
    stops: list[PatternStop]
    # [lat, lon] pairs along the road geometry
    shape: list[tuple[float, float]]
