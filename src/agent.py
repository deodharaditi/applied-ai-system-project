"""VibeMatcher AI — Conversational Music Recommender Agent.

Multi-step pipeline:
  guardrail → parse intent → clarify (≤1 question) → build profile
  → tool call → RAG inject → explain → self-critique
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import anthropic
from dotenv import load_dotenv

# ── Path bootstrap ────────────────────────────────────────────────────────────
# Works whether the file is run directly or imported by eval/run_eval.py
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.recommender import load_songs, recommend_songs  # noqa: E402

load_dotenv()

# ── Directories ───────────────────────────────────────────────────────────────
_DATA = _ROOT / "data"
_LOGS = _ROOT / "logs"
_LOGS.mkdir(exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
# Named logger so eval harness can control console output independently
log = logging.getLogger("vibematcher")
log.setLevel(logging.DEBUG)
if not log.handlers:
    _fh = logging.FileHandler(str(_LOGS / "agent.log"), encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    _sh = logging.StreamHandler(sys.stdout)
    _sh.setFormatter(logging.Formatter("%(message)s"))
    log.addHandler(_fh)
    log.addHandler(_sh)
    log.propagate = False

# ── Load catalog once at import time ─────────────────────────────────────────
_SONGS: list[dict] = load_songs(str(_DATA / "songs.csv"))

with open(_DATA / "song_descriptions.json", encoding="utf-8") as _f:
    _DESCRIPTIONS: dict[str, str] = json.load(_f)

_VALID_GENRES = sorted({s["genre"] for s in _SONGS})
_VALID_MOODS  = sorted({s["mood"]  for s in _SONGS})

# ── Tool schema ───────────────────────────────────────────────────────────────
_TOOLS = [
    {
        "name": "recommend_songs",
        "description": (
            "Score every song in the 20-song VibeMatcher catalog against a user "
            "preference profile and return the top-k results with scores and "
            "per-feature explanations. Call this once you have enough information "
            "to populate the required fields."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "genre": {
                    "type": "string",
                    "description": f"Favorite genre. Valid values: {_VALID_GENRES}",
                },
                "mood": {
                    "type": "string",
                    "description": f"Listening mood. Valid values: {_VALID_MOODS}",
                },
                "target_energy": {
                    "type": "number",
                    "description": "Energy 0.0 (very calm) to 1.0 (maximum)",
                },
                "target_valence": {
                    "type": "number",
                    "description": "Emotional tone 0.0 (dark/sad) to 1.0 (bright/happy)",
                },
                "target_tempo_bpm": {
                    "type": "number",
                    "description": "Desired tempo in BPM (60–168)",
                },
                "target_acousticness": {
                    "type": "number",
                    "description": "0.0 = fully electronic, 1.0 = fully acoustic",
                },
                "target_speechiness": {
                    "type": "number",
                    "description": "0.0 = instrumental/sung, 1.0 = spoken/rap. Default 0.05.",
                },
                "target_instrumentalness": {
                    "type": "number",
                    "description": "0.0 = vocal track, 1.0 = purely instrumental. Default 0.05.",
                },
                "target_popularity": {
                    "type": "integer",
                    "description": "Desired popularity 0–100. Default 50.",
                },
                "target_release_decade": {
                    "type": "integer",
                    "description": "Preferred era: 1970, 1980, 1990, 2000, 2010, or 2020.",
                },
                "prefers_explicit": {
                    "type": "integer",
                    "description": "1 = explicit OK, 0 = prefer clean. Default 0.",
                },
                "k": {
                    "type": "integer",
                    "description": "Number of recommendations (default 3).",
                },
                "artist_penalty": {
                    "type": "number",
                    "description": "Diversity penalty per repeated artist (default 0.0).",
                },
                "genre_penalty": {
                    "type": "number",
                    "description": "Diversity penalty per repeated genre (default 0.0).",
                },
            },
            "required": [
                "genre", "mood", "target_energy", "target_valence",
                "target_tempo_bpm", "target_acousticness",
            ],
        },
    }
]

# ── System prompt (cached) ────────────────────────────────────────────────────
# cache_control here enables prompt caching on Haiku 4.5 once the prefix
# exceeds the 4096-token minimum. The marker is architecturally correct and
# will activate automatically as the prompt grows.
_SYSTEM = [
    {
        "type": "text",
        "text": f"""You are VibeMatcher, a friendly music recommendation assistant.
Catalog: 20 songs. Genres: {_VALID_GENRES}. Moods: {_VALID_MOODS}.

## Workflow — follow every step in order:

STEP 1 — GUARDRAIL
If the query is not about music at all, respond with ONLY this line (no other text):
  GUARDRAIL: I can only help with music recommendations. Try: "I want something chill to study to" or "suggest upbeat songs for a workout."

STEP 2 — CLARIFY (optional, at most once)
If you genuinely cannot determine the genre OR mood from the query, ask ONE focused question.
If you can make a reasonable inference, skip directly to STEP 3.

STEP 3 — PROFILE
Map the user's words to catalog values. Use these defaults when details are vague:
  study / focus / coding / work  → genre=lofi, mood=focused, energy=0.40, tempo=80, acousticness=0.75, instrumentalness=0.85
  workout / gym / cardio         → mood=intense, energy=0.90, tempo=132, acousticness=0.10, valence=0.75
  chill / relax / wind down      → mood=chill, energy=0.35, tempo=80, valence=0.60, acousticness=0.60
  party / dance / club           → mood=happy, energy=0.90, tempo=128, valence=0.82, acousticness=0.10
  sad / breakup / cry            → mood=sad, valence=0.28, energy=0.38, tempo=75, acousticness=0.85
  hype / pump up / energetic     → mood=intense, energy=0.95, valence=0.80, tempo=135, acousticness=0.05

STEP 4 — CALL TOOL
Call recommend_songs with the profile you built. Do not name any songs before calling it.

STEP 5 — EXPLAIN
Write warm, plain-English explanations. Reference the song descriptions provided in the
tool result. Highlight the 1–2 strongest matching features per song.

Format your song list like this:
  #1  <Title> — <Artist>  [<genre>]  <score>/9.50

Then a short paragraph starting "Why these songs:" explaining the top picks.

STEP 6 — SELF-CRITIQUE
Close with exactly these two lines (no extra text between them):
  Confidence: <0.0–1.0>
  Note: <catalog limitations or caveats, or "Catalog coverage is good for this request." if none>

Confidence guide: 0.90+ = strong genre+mood match; 0.70–0.89 = partial match; below 0.70 = limited catalog coverage.

## Tone examples:
BAD:  "The algorithm found optimal feature proximity."
GOOD: "Focus Flow is built exactly for this — quiet, instrumental, zero distractions."

BAD:  "Here are your results."
GOOD: "Here's what I found:"

## Hard rules:
- NEVER invent song titles. Only recommend songs the tool returns.
- Ask AT MOST ONE clarifying question per conversation.
- Always call recommend_songs before naming any songs.
""",
        "cache_control": {"type": "ephemeral"},
    }
]


# ── Tool executor ─────────────────────────────────────────────────────────────

def _run_recommend_tool(tool_input: dict) -> str:
    """Execute recommend_songs() and inject RAG descriptions. Returns JSON string."""
    user_prefs = {
        "genre":                   tool_input["genre"],
        "mood":                    tool_input["mood"],
        "target_energy":           float(tool_input["target_energy"]),
        "target_valence":          float(tool_input["target_valence"]),
        "target_tempo_bpm":        float(tool_input["target_tempo_bpm"]),
        "target_acousticness":     float(tool_input["target_acousticness"]),
        "target_speechiness":      float(tool_input.get("target_speechiness",    0.05)),
        "target_instrumentalness": float(tool_input.get("target_instrumentalness", 0.05)),
        "target_popularity":       int(tool_input.get("target_popularity",     50)),
        "target_release_decade":   int(tool_input.get("target_release_decade", 2010)),
        "target_liveness":         float(tool_input.get("target_liveness",     0.10)),
        "target_loudness":         float(tool_input.get("target_loudness",     0.50)),
        "prefers_explicit":        int(tool_input.get("prefers_explicit",      0)),
    }
    k              = int(tool_input.get("k", 3))
    artist_penalty = float(tool_input.get("artist_penalty", 0.0))
    genre_penalty  = float(tool_input.get("genre_penalty",  0.0))

    results = recommend_songs(
        user_prefs, _SONGS, k=k,
        artist_penalty=artist_penalty,
        genre_penalty=genre_penalty,
    )

    # RAG: inject text descriptions alongside numeric scores
    output = []
    for song, score, reasons in results:
        desc = _DESCRIPTIONS.get(str(song["id"]), "No description available.")
        output.append({
            "id":          song["id"],
            "title":       song["title"],
            "artist":      song["artist"],
            "genre":       song["genre"],
            "score":       score,
            "max_score":   9.50,
            "reasons":     reasons,
            "description": desc,   # RAG context for explanation step
        })
    return json.dumps(output, indent=2)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_text(response) -> str:
    """Pull the first text block from a message response."""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""


def _is_clarifying_question(text: str) -> bool:
    """True when the response is a short question asking the user for more info."""
    stripped = text.strip()
    if len(stripped) > 500:   # full explanations are always longer
        return False
    return "?" in stripped


def _parse_self_critique(text: str) -> tuple[float | None, bool]:
    """Extract (confidence, has_limitation_note) from the final response text."""
    confidence = None
    has_note   = False
    for line in text.splitlines():
        ll = line.strip().lower()
        if ll.startswith("confidence:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
            except (ValueError, IndexError):
                pass
        if ll.startswith("note:"):
            has_note = True
    return confidence, has_note


def _blocked(message: str) -> dict:
    return {
        "reply":           message,
        "confidence":      None,
        "limited":         False,
        "guardrail_hit":   True,
        "recommendations": [],
    }


# ── Agent ─────────────────────────────────────────────────────────────────────

class MusicAgent:
    """Conversational music recommender agent backed by the Claude API."""

    def __init__(self):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set. Copy .env.example → .env and add your key."
            )
        self.client = anthropic.Anthropic(api_key=api_key)

    def run(
        self,
        query: str,
        clarification_response: Optional[str] = None,
    ) -> dict:
        """Run the full agent pipeline on a single query.

        Parameters
        ----------
        query                  : natural language music request
        clarification_response : pre-supplied answer to any clarifying question.
                                 None = interactive (prompts user on stdin).

        Returns
        -------
        dict with keys:
            reply            – final text shown to the user
            confidence       – float 0–1, or None if guardrail hit
            limited          – bool, True if agent flagged catalog limitations
            guardrail_hit    – bool
            recommendations  – list of song dicts from the tool call
        """
        query = query.strip()

        # ── Input guardrail: reject empty queries immediately ─────────────────
        if not query:
            log.warning("[GUARDRAIL] Empty input rejected.")
            return _blocked("Please describe what kind of music you're looking for.")

        log.info("[INPUT] %s", query)

        messages: list[dict] = [{"role": "user", "content": query}]
        recommendations: list[dict] = []
        clarification_asked = False

        # ── Agentic loop ──────────────────────────────────────────────────────
        while True:
            log.info("[STEP] Calling Claude (%d message(s) in context)…", len(messages))

            response = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=_SYSTEM,
                tools=_TOOLS,
                messages=messages,
            )

            log.debug("[STEP] stop_reason=%s", response.stop_reason)

            # ── End turn: guardrail, clarifying Q, or final answer ────────────
            if response.stop_reason == "end_turn":
                text = _extract_text(response)

                # STEP 1 — Guardrail fired by Claude
                if text.startswith("GUARDRAIL:"):
                    msg = text[len("GUARDRAIL:"):].strip()
                    log.warning("[GUARDRAIL] Off-topic query blocked: %s", query)
                    return _blocked(msg)

                # STEP 2 — Clarifying question (at most once)
                if _is_clarifying_question(text) and not clarification_asked:
                    clarification_asked = True
                    log.info("[CLARIFY] Question: %s", text)
                    print(f"\n[Agent] {text}")

                    if clarification_response is not None:
                        # Eval / batch mode — use pre-supplied answer
                        answer = clarification_response
                        log.info("[CLARIFY] Batch answer: %s", answer)
                    elif sys.stdin.isatty():
                        # Interactive terminal — prompt the user
                        answer = input("You: ").strip()
                        log.info("[CLARIFY] User answered: %s", answer)
                    else:
                        # Non-interactive (pipe / test runner) — auto-proceed
                        answer = "Please use your best judgment and proceed."
                        log.info("[CLARIFY] Non-interactive mode; auto-answering.")

                    messages.append({"role": "assistant", "content": text})
                    messages.append({"role": "user",      "content": answer})
                    continue  # loop back for tool call

                # STEP 5+6 — Final explanation + self-critique
                log.info("[EXPLAIN] Final response generated (%d chars).", len(text))
                confidence, limited = _parse_self_critique(text)
                log.info("[RESULT] confidence=%.2f  limited=%s  recs=%d",
                         confidence or 0, limited, len(recommendations))
                return {
                    "reply":           text,
                    "confidence":      confidence,
                    "limited":         limited,
                    "guardrail_hit":   False,
                    "recommendations": recommendations,
                }

            # ── Tool use — STEP 4 ─────────────────────────────────────────────
            if response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    log.info(
                        "[TOOL] recommend_songs(genre=%s, mood=%s, energy=%s, tempo=%s)",
                        block.input.get("genre", "?"),
                        block.input.get("mood",  "?"),
                        block.input.get("target_energy", "?"),
                        block.input.get("target_tempo_bpm", "?"),
                    )

                    result_str    = _run_recommend_tool(block.input)
                    recs          = json.loads(result_str)
                    recommendations = recs

                    log.info("[TOOL] %d result(s) returned:", len(recs))
                    for r in recs:
                        log.info(
                            "  → #%d %-30s  %.3f / 9.50",
                            r["id"], r["title"], r["score"],
                        )

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     result_str,
                    })

                content_dicts = []
                for block in response.content:
                    if block.type == "text":
                        content_dicts.append({"type": "text", "text": block.text})
                    elif block.type == "tool_use":
                        content_dicts.append({
                            "type":  "tool_use",
                            "id":    block.id,
                            "name":  block.name,
                            "input": block.input,
                        })
                messages.append({"role": "assistant", "content": content_dicts})
                messages.append({"role": "user",      "content": tool_results})
                continue

            # Unexpected stop reason
            log.error("[STEP] Unexpected stop_reason=%s — aborting.", response.stop_reason)
            break

        return {
            "reply":           "Something went wrong. Please try again.",
            "confidence":      None,
            "limited":         False,
            "guardrail_hit":   False,
            "recommendations": [],
        }


# ── CLI entry point ───────────────────────────────────────────────────────────

def main():
    agent = MusicAgent()
    print("\nVibeMatcher AI — Conversational Music Recommender")
    print("Type your request, or 'quit' to exit.\n")

    while True:
        try:
            query = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if query.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break
        if not query:
            continue
        result = agent.run(query)
        print(f"\n{result['reply']}\n")


if __name__ == "__main__":
    main()
