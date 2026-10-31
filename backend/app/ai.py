import logging

from google import genai
from google.genai import types
from pydantic import BaseModel

from .config import settings
from .schemas import DriverStep

log = logging.getLogger(__name__)
CHUNK = 60

PROMPT = """You write turn-by-turn instructions for a Perth bus driver.
For each input item, rewrite its "instruction" as a short imperative sentence (max 12 words).
Rules:
- Keep the road name and the turn direction exactly as given; never add roads, landmarks or facts.
- Keep roundabout exit numbers.
- Return one output per input id, same ids.
Input:
"""


class Rewrite(BaseModel):
    id: int
    instruction: str


def _faithful(step: DriverStep, text: str) -> bool:
    t = text.lower()
    if step.road and step.road.lower() not in t:
        return False
    if step.modifier in ("left", "right", "slight left", "slight right", "sharp left", "sharp right"):
        if step.modifier.split()[-1] not in t:
            return False
    return True


def reword(steps: list[DriverStep]) -> list[DriverStep]:
    """Rewrite maneuver instructions with Gemini; falls back to the deterministic text on any problem."""
    if not settings.gemini_api_key:
        return steps
    client = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=4)),
    )
    targets = [s for s in steps if s.type != "stop"]
    by_id = {s.step: s for s in steps}

    for i in range(0, len(targets), CHUNK):
        chunk = targets[i : i + CHUNK]
        payload = [
            {"id": s.step, "instruction": s.instruction, "road": s.road, "distance_m": s.distance_m}
            for s in chunk
        ]
        try:
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=PROMPT + str(payload),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=list[Rewrite],
                    temperature=0,
                ),
            )
        except Exception as e:  # network, quota, bad key
            log.warning("Gemini call failed, using plain instructions: %s", e)
            return steps
        for r in resp.parsed or []:
            step = by_id.get(r.id)
            if step and step.type != "stop" and _faithful(step, r.instruction):
                step.instruction = r.instruction.strip()
    return steps
