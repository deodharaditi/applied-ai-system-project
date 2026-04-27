"""VibeMatcher AI — Eval Harness.

Runs 5 predefined queries through MusicAgent and prints a pass/fail summary.
Exit code 0 if all pass, 1 if any fail.
"""

import logging
import sys
from pathlib import Path

# Silence the "vibematcher" console handler during eval runs — file log still writes.
logging.getLogger("vibematcher").handlers = []
_silent = logging.NullHandler()
logging.getLogger("vibematcher").addHandler(_silent)

# Path bootstrap so we can import from src/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.agent import MusicAgent  # noqa: E402

# ── Test definitions ──────────────────────────────────────────────────────────

TESTS = [
    {
        "name": "Clear study request",
        "query": "I want something chill to study to, not too upbeat",
        "clarification_response": None,
        "checks": {
            "not_guardrail": lambda r: not r["guardrail_hit"],
            "has_recommendations": lambda r: len(r["recommendations"]) >= 1,
            "has_confidence": lambda r: r["confidence"] is not None,
        },
    },
    {
        "name": "Ambiguous gym request (with clarification)",
        "query": "something for the gym",
        "clarification_response": "upbeat pop, I'm doing cardio",
        "checks": {
            "not_guardrail": lambda r: not r["guardrail_hit"],
            "has_recommendations": lambda r: len(r["recommendations"]) >= 1,
            "has_confidence": lambda r: r["confidence"] is not None,
        },
    },
    {
        "name": "Ghost profile — contradictory genre/mood",
        "query": "I want classical music that is aggressive and really intense",
        "clarification_response": None,
        "checks": {
            "not_guardrail": lambda r: not r["guardrail_hit"],
            "has_recommendations": lambda r: len(r["recommendations"]) >= 1,
            "has_confidence": lambda r: r["confidence"] is not None,
        },
    },
    {
        "name": "Off-topic input — guardrail must fire",
        "query": "what's the weather like today?",
        "clarification_response": None,
        "checks": {
            "guardrail_hit": lambda r: r["guardrail_hit"] is True,
        },
    },
    {
        "name": "High-energy hype request",
        "query": "give me the most energetic hype songs you have",
        "clarification_response": None,
        "checks": {
            "not_guardrail": lambda r: not r["guardrail_hit"],
            "has_recommendations": lambda r: len(r["recommendations"]) >= 1,
            "has_confidence": lambda r: r["confidence"] is not None,
        },
    },
]

# ── Runner ────────────────────────────────────────────────────────────────────

def run_eval() -> bool:
    agent = MusicAgent()
    results = []

    for i, test in enumerate(TESTS, 1):
        print(f"\n{'─' * 60}")
        print(f"Test {i}/{len(TESTS)}: {test['name']}")
        print(f"  Query: \"{test['query']}\"")
        if test["clarification_response"]:
            print(f"  Clarification: \"{test['clarification_response']}\"")

        try:
            result = agent.run(
                query=test["query"],
                clarification_response=test["clarification_response"],
            )
        except Exception as exc:
            print(f"  ERROR: {exc}")
            results.append((test["name"], False, {"exception": str(exc)}))
            continue

        failures = {}
        for check_name, check_fn in test["checks"].items():
            try:
                passed = check_fn(result)
            except Exception as exc:
                passed = False
                failures[check_name] = f"check raised {exc}"
            if not passed:
                failures[check_name] = f"got {result.get(check_name.replace('not_', '').replace('has_', ''))!r}"

        all_passed = len(failures) == 0
        results.append((test["name"], all_passed, failures))

        status = "PASS" if all_passed else "FAIL"
        print(f"  Status: {status}")
        if not all_passed:
            for check, reason in failures.items():
                print(f"    ✗ {check}: {reason}")
        else:
            print(f"    confidence={result['confidence']}  recs={len(result['recommendations'])}  guardrail={result['guardrail_hit']}")

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(1 for _, ok, _ in results if ok)
    total  = len(results)

    print(f"\n{'═' * 60}")
    print(f"Eval Summary: {passed}/{total} tests passed")
    print(f"{'═' * 60}")
    for name, ok, _ in results:
        mark = "✓" if ok else "✗"
        print(f"  {mark}  {name}")

    return passed == total


if __name__ == "__main__":
    ok = run_eval()
    sys.exit(0 if ok else 1)
