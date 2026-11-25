from contextlib import contextmanager

from fastapi import FastAPI

from app import routes


class FixtureConnection:
    def execute(self, query, params):
        if params != {"number": "240"}:
            raise ValueError(f"Unexpected parameters: {params}")
        return self

    def fetchall(self):
        return [
            {
                "route_id": "SWA-SRI-146",
                "route_number": "240",
                "agency_id": "SWA-SRI",
                "direction_id": 1,
                "headsign": "Kelmscott Stn",
                "shape_id": "125949",
                "trip_count": 2,
                "sample_trip_id": "7070970",
                "origin_stop": "Example origin",
                "destination_stop": "Example destination",
            }
        ]


class FixturePool:
    @contextmanager
    def connection(self):
        yield FixtureConnection()


routes.pool = FixturePool()

app = FastAPI()
app.include_router(routes.router)