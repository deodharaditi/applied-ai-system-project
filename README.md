# VibeMatcher AI — Conversational Music Recommender Agent

A conversational AI system that turns natural language into personalized music recommendations. Built on top of a content-based recommender engine, it uses the Claude API to understand what a listener actually wants, ask clarifying questions when needed, retrieve song context, and explain its choices in plain English.

This is the final applied AI extension of **VibeMatcher 1.0**, originally built in CodePath AI110 Module 3.

---

## Video Walkthrough

▶️ [Watch on Loom](https://loom.com/share/YOUR_LINK_HERE)

The walkthrough demonstrates an end-to-end run covering three cases: a clear study request (no clarification needed), an ambiguous gym request (clarifying question triggered), and an off-topic input (guardrail fires). It also shows the eval harness running all 5 predefined queries with pass/fail output.

---

## Portfolio Reflection

This project reflects how I think about building AI systems: start with what already works, then extend it carefully. The scoring engine from Module 3 was solid, so I kept it unchanged and wrapped a conversational layer around it rather than rebuilding from scratch. Every new layer — guardrails, clarifying questions, RAG, self-critique — exists because I hit a specific failure mode during testing and needed to close it. That process taught me that reliable AI systems are not built by adding features; they are built by identifying exactly where the system breaks and fixing those boundaries. As an AI engineer, I want to build things that are honest about what they can and cannot do — and the confidence score and catalog limitation notes in this project are a direct expression of that value.

---

## Original Project

**Base:** [Music Recommender Simulation (Module 3)](https://github.com/deodharaditi/ai110-module3show-musicrecommendersimulation-starter)

The original system was a CLI-based content-based recommender. It represented songs and user taste profiles as structured data, scored each song against a user profile using a 13-feature weighted proximity algorithm (max score 9.50), and returned ranked recommendations with per-feature explanations. It supported four scoring modes (balanced, genre-first, vibe-first, discovery) and a diversity penalty to avoid repetitive results. It had no natural language interface — users had to manually write Python dicts to define their preferences.

---

## What This System Adds

This project extends that engine into a full conversational AI system. Instead of writing code to describe your taste, you just say what you want.

| Layer | What it does |
|---|---|
| **Claude Agent** | Understands natural language, asks clarifying questions, builds a UserProfile |
| **Recommender Engine** | Scores all 20 songs using the original weighted proximity algorithm |
| **RAG Retriever** | Fetches per-song text descriptions to enrich Claude's explanation |
| **Self-Critique** | Agent rates its own confidence and flags weak matches |
| **Eval Harness** | Runs 5 predefined test queries and prints a pass/fail summary |
| **Logger** | Records every agent step to `logs/agent.log` |

---

## System Architecture

![System Architecture](assets/architecture.png)

### How data flows

1. User types a natural language query
2. **Input guardrail** rejects off-topic or empty input immediately
3. **Claude Agent** parses the intent — if it needs more information, it asks at most one clarifying question
4. Agent builds a `UserProfile` dict from the conversation
5. `recommend_songs()` is called as a tool — scores all 20 songs, applies diversity penalty
6. **RAG retriever** fetches text descriptions for the top results from `data/song_descriptions.json`
7. Claude generates a plain-English explanation using both the scores and the descriptions
8. **Self-critique** adds a confidence score (0–1) and flags any catalog limitations
9. Final output is printed; all steps are written to `logs/agent.log`
10. **Eval harness** (`eval/run_eval.py`) can run the full pipeline on predefined inputs and grade output

---

## Project Structure

```
applied-ai-system-project/
├── src/
│   ├── agent.py                ← conversational agent (new)
│   └── recommender.py          ← scoring engine (unchanged from Module 3)
├── data/
│   ├── songs.csv               ← 20-song catalog (17 features)
│   └── song_descriptions.json  ← RAG context per song (new)
├── eval/
│   └── run_eval.py             ← test harness (new)
├── logs/                       ← agent.log written here at runtime
├── assets/
│   └── architecture.png        ← system diagram
├── tests/
│   └── test_recommender.py     ← unit tests for scoring engine
├── .env.example                ← API key template
├── requirements.txt
├── model_card.md
└── reflection.md
```

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/deodharaditi/applied-ai-system-project.git
cd applied-ai-system-project
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate      # Mac / Linux
.venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Add your Anthropic API key

```bash
cp .env.example .env
```

Open `.env` and fill in your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at [console.anthropic.com](https://console.anthropic.com).

### 5. Run the conversational agent

```bash
python src/agent.py
```

### 6. Run the eval harness

```bash
python eval/run_eval.py
```

### 7. Run unit tests

```bash
pytest
```

---

## Sample Interactions

### Example 1 — Clear intent, no clarification needed

```
You: I want something chill to study to, not too upbeat

[Agent] Parsing your request...
[Agent] Built profile: genre=lofi, mood=focused, energy=0.35, valence=0.55, tempo=76bpm
[Agent] Scoring 20 songs...
[Agent] Retrieving context for top results...
[Agent] Generating explanation...

 Top Recommendations for You
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#1  Focus Flow — LoRoom  [lofi]  9.12/9.50
#2  Library Rain — Paper Lanterns  [lofi]  7.68/9.50
#3  Midnight Coding — LoRoom  [lofi]  7.61/9.50

 Why these songs:
Focus Flow is a perfect match — it's a lofi instrumental with low energy (0.40)
and a focused, quiet mood built for concentration. Library Rain and Midnight Coding
are also lofi, but their mood label is "chill" rather than "focused," which costs
them the mood bonus.

Confidence: 0.91
Note: Only 3 lofi songs exist in the catalog. A larger library would give
more variety within this genre.
```

---

### Example 2 — Clarifying question triggered

```
You: something for the gym

[Agent] I want to make sure I get this right — do you prefer
        (a) aggressive/metal energy, or (b) upbeat pop/EDM for cardio?

You: upbeat pop, I'm doing cardio

[Agent] Got it. Building your profile...
[Agent] Built profile: genre=pop, mood=intense, energy=0.90, valence=0.80, tempo=132bpm
[Agent] Scoring 20 songs...

 Top Recommendations for You
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#1  Gym Hero — PowerUp  [pop]  8.94/9.50
#2  Neon Rush — Synth Wolves  [edm]  6.21/9.50
#3  Storm Runner — IronVox  [rock]  5.87/9.50

 Why these songs:
Gym Hero is the only pop/intense song in the catalog — it earns both genre and
mood bonuses (3.50 pts combined) and matches your target energy of 0.90 almost
exactly. Neon Rush ranks second because EDM energy is nearly identical to pop
energy even though the genre doesn't match.

Confidence: 0.88
Note: Only 1 pop/intense song in catalog. Results may be repetitive with larger k.
```

---

### Example 3 — Off-topic input rejected by guardrail

```
You: what's the weather like today?

[Agent] I can only help with music recommendations.
        Try something like: "I want something chill to wind down with" or
        "suggest upbeat songs for a workout."
```

---

## Design Decisions

**Why Claude as the agent layer?**
Parsing "something for the gym" into `{genre: pop, mood: intense, energy: 0.90}` is a natural language understanding problem. Claude handles this far more robustly than regex or keyword matching, and it can ask follow-up questions when intent is ambiguous — something a rule-based parser cannot do.

**Why keep `recommender.py` unchanged?**
The scoring engine is already well-tested and correct. Wrapping it as a Claude tool rather than rewriting it means the recommendation logic is deterministic and inspectable — the AI handles language understanding, but the actual scoring is pure Python math with no hallucination risk.

**Why RAG over song descriptions instead of embedding search?**
With only 20 songs, a full vector database (Chroma, Pinecone) would be architectural overkill. A JSON file with text descriptions is simpler, auditable, and achieves the same goal: giving Claude richer context than raw numbers when generating explanations.

**Why `claude-haiku-4-5` and not a larger model?**
Haiku is fast and cheap — a full agent run costs fractions of a cent. For a structured task like parsing a music preference and formatting an explanation, a smaller model is sufficient and makes the system practical to run in a classroom or demo setting.

**Trade-offs:**
- The 20-song catalog limits recommendation variety — this is a known limitation inherited from Module 3
- Clarifying questions add a turn of latency for ambiguous queries, but the system skips them when intent is already clear
- RAG descriptions were written manually — a production system would generate them from audio features automatically

---

## Testing Summary

**Unit tests (`pytest`):** 4 tests covering scoring correctness, genre mismatch gap, BPM clamping, and explanation string format. All pass after adding the new agent layer — `recommender.py` was not modified.

**Eval harness (`eval/run_eval.py`):** 5 predefined queries covering a clear request, an ambiguous request, a ghost profile (no catalog match), an off-topic input, and a high-energy query. Checks that each run returns the expected number of results, includes a confidence score, and logs correctly.

**What worked:**
- The guardrail reliably catches off-topic queries on the first check
- Claude correctly identifies when a query is too vague and asks one focused question
- Self-critique confidence scores correlate with catalog match quality — ghost profiles score low, exact matches score high

**What didn't work at first:**
- Claude occasionally over-asked — would ask two clarifying questions when one was enough. Fixed by adding an explicit instruction in the system prompt: "Ask at most one clarifying question before proceeding."
- Log file wasn't created on first run if `logs/` didn't exist. Fixed with `os.makedirs("logs", exist_ok=True)` at startup.

**Results summary:**
4/4 unit tests pass; 5/5 eval harness queries pass, including a guardrail rejection test and a ghost-profile (contradictory genre/mood) test. Confidence scores averaged ~0.89 on well-matched catalog requests; the ghost profile and ambiguous queries scored lower and triggered catalog limitation notes in the self-critique output.

---

## Reflection

Building this system made the gap between "a model that can answer questions" and "a system that reliably solves a problem" very concrete. Claude is good at understanding natural language, but left unconstrained it drifts — it would sometimes invent songs not in the catalog, ask too many questions, or format output inconsistently. Every guardrail, prompt constraint, and structured tool call exists to close that gap.

The most important design choice was keeping the recommender engine deterministic. By making `recommend_songs()` a pure Python function that Claude calls as a tool rather than asking Claude to reason about which songs to recommend, the system guarantees that scores are always computed the same way. Claude handles what it's good at (language); the code handles what code is good at (arithmetic).

The self-critique layer was the most surprising addition — making the agent flag its own confidence and catalog limitations turned a black-box output into something a user can actually calibrate their trust against. That feels like the right direction for honest AI systems.

---

## Stretch Features

### RAG Enhancement
The retrieval system uses `data/song_descriptions.json` — a hand-authored text description for each of the 20 songs — injected into the tool result before Claude generates its explanation. This measurably improves output quality in two ways:

- **Without RAG:** Claude only sees structured numbers — `{title: "Focus Flow", score: 8.91, energy: 0.40, acousticness: 0.78}`. Explanations read like score summaries: "Focus Flow scored highest on energy and acousticness."
- **With RAG:** Claude receives the full description alongside the numbers: *"a purposeful lo-fi instrumental... designed to sustain mental stamina during long study or work sessions."* Explanations use qualitative language grounded in the description — the Example 1 output above says "built for concentration," which comes directly from the RAG text, not from any numeric feature.

The descriptions act as a translation layer: scores tell the model *how well* a song matched; descriptions tell it *why that match feels right to a listener*.

### Agentic Workflow with Observable Intermediate Steps
The pipeline has five observable stages, each logged to `logs/agent.log`:

```
[STEP]    Calling Claude (1 message(s) in context)
[CLARIFY] Question: do you prefer aggressive/metal or upbeat pop/EDM?
[CLARIFY] User answered: upbeat pop, I'm doing cardio
[STEP]    Calling Claude (3 message(s) in context)
[TOOL]    recommend_songs(genre=pop, mood=intense, energy=0.90, tempo=132)
[TOOL]    5 result(s) returned: #5 Gym Hero 8.909 / #16 Neon Surge 6.21 / ...
[STEP]    Calling Claude (5 message(s) in context)
[EXPLAIN] Final response generated (412 chars)
[RESULT]  confidence=0.88  limited=True  recs=5
```

Each step is a discrete, inspectable decision point — not a black-box single call.

### Fine-Tuning / Specialization via Few-Shot System Prompt
The system prompt uses few-shot examples and explicit output constraints to produce structured, machine-parseable responses that differ measurably from a baseline Claude call:

| Behavior | Baseline Claude | With system prompt |
|---|---|---|
| Off-topic query | Varies: "I can't help with that" / "Sorry..." | Always: `GUARDRAIL: <reason>` — Python-detectable |
| Confidence | Not included | Always ends with `Confidence: X.XX` — Python-parseable |
| Clarifying questions | May ask several | At most one, then proceeds |
| Song hallucination | Occasionally invents songs | Constrained to catalog-only titles |

The `GUARDRAIL:` prefix and `Confidence: X.XX` pattern are directly tested by the eval harness — the off-topic test checks `guardrail_hit=True` and all other tests check `confidence is not None`, verifying the structured output contract holds on every run.

### Test Harness
`eval/run_eval.py` runs 5 predefined queries and prints a pass/fail summary with confidence ratings. See the Testing Summary section above for results.

---

## Model Card

See [model_card.md](model_card.md) for full bias analysis, evaluation results, and limitations.

## Responsible AI & Reflection

See [reflection.md](reflection.md) for the full responsible AI reflection: system limitations and biases, misuse potential, what surprised me during reliability testing, and a detailed account of AI collaboration during development — including one instance where the AI suggestion was helpful and one where it was flawed.
