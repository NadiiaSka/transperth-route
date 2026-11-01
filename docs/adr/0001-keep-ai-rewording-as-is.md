# ADR 0001: Keep AI rewording as-is

- **Status:** Accepted
- **Date:** 2026-11-01

AI rewording (`backend/app/ai.py`) is frozen: do not audit or change it unless
explicitly asked. It may paraphrase or drop anchors like "At the traffic
lights" — accepted. When checking reported direction issues, verify the
deterministic instruction (`instr` field), not the reworded text.
