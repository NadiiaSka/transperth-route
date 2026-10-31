import logging

from google import genai
from google.genai import types
from pydantic import BaseModel

from .config import settings
from .schemas import DriverStep

log = logging.getLogger(__name__)
CHUNK = 60

PROMPT = """You write concise spoken turn-by-turn instructions for a Perth bus driver.
For each input item, rewrite its "instruction" as a natural navigation cue.
Rules:
- Preserve the street name, left/right direction, and roundabout exit number exactly.
- Preserve end-of-road and fork guidance.
- Do not add turns, traffic lights, landmarks, or facts.
- Return one output per input id, same ids.
Input:
"""


class Rewrite(BaseModel):
    id: int
    instruction: str


def _faithful(step: DriverStep, text: str) -> bool:
    t = text.lower()
    if step.turn:
        direction = "left" if step.turn == "L" else "right"
        if direction not in t:
            return False
    if step.roundabout_exit and str(step.roundabout_exit) not in t:
        return False
    if step.road and step.road.lower() not in t:
        return False
    if step.maneuver == "end of road" and "end" not in t:
        return False
    if "1st" in step.instruction.lower() and "1st" not in t:
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
    targets = steps
    by_id = {s.step: s for s in steps}

    for i in range(0, len(targets), CHUNK):
        chunk = targets[i : i + CHUNK]
        payload = [
            {
                "id": s.step,
                "instruction": s.instruction,
                "road": s.road,
                "maneuver": s.maneuver,
                "turn": s.turn,
                "roundabout_exit": s.roundabout_exit,
            }
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
            if step and _faithful(step, r.instruction):
                step.instruction = r.instruction.strip()
    return steps
