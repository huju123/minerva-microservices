# MINERVA — Personalized Roadmap Engine
### Backend Integration Guide

Status: **Verified working end-to-end** — all module self-tests pass, a live
Groq API run completed successfully, and all three user journeys (1, 2, 3)
produced validated roadmaps with 0 structural/business-rule errors.

---

## 1. What this package is

A pure orchestration pipeline that turns a "Journey" assessment result
(career-exploration / career-selected / skills-refinement) into a
validated, structured learning roadmap with a week-by-week timeline.

```
Journey output (JSON)
    -> adapter.py        Journey-specific JSON -> common internal profile
    -> level_rules.py    skills -> gap/level actions
    -> retrieval.py      actions -> real resource IDs (never invented)
    -> planner.py        resources -> phased plan (Groq, with deterministic fallback)
    -> timeline.py        plan -> week-by-week schedule (Groq, with deterministic fallback)
    -> schema.py          assembles + structurally validates the roadmap
    -> validator.py        semantic / business-rule validation
    -> FINAL ROADMAP JSON
```

There is **one function you need to call**. Everything else is internal.

---

## 2. Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt    # groq client + any deps used by the modules
export GROQ_API_KEY=sk-...         # required only if use_model=True
```

Confirm the environment before wiring it into the backend:

```bash
python test_groq.py        # expects {"status":"ok"}
python adapter.py          # module self-tests
python level_rules.py
python retrieval.py
python planner.py
python timeline.py
python schema.py
python validator.py
```

If any of these print anything other than `ALL ... TESTS PASSED`, stop and
flag it — do not integrate against a failing module.

---

## 3. The one function to call

```python
from roadmap_engine import generate_roadmap

result = generate_roadmap(
    journey=2,                       # 1, 2, or 3 — required
    journey_output=journey2_json,    # dict — the raw Journey output
    weekly_hours=8,                  # optional override
    goal=None,                       # optional override
    target_role=None,                # optional override
    preferred_days=None,             # optional override
    use_model=True,                  # False = fully deterministic, no network call
    api_key=None,                    # optional, else reads GROQ_API_KEY env var
)
```

### Return type depends on journey — handle both shapes

| Journey | Meaning | Return type |
|---|---|---|
| 1 | Career exploration | `List[Dict]` — **one roadmap per career found** in the input, always a list even if only one career is present |
| 2 | Career already selected | `Dict` — a single roadmap |
| 3 | Skills-focused refinement | `Dict` — a single roadmap (`career` will be `null`; this is expected — J3 is skill-driven, not career-driven) |

```python
if isinstance(result, list):
    for roadmap in result:
        save(roadmap)
else:
    save(result)
```

### Persisting to disk (CLI helper, optional)

```python
from roadmap_engine import save_roadmaps
save_roadmaps(result, output_dir="output/")
```

**⚠️ Known filename collision — action required on the backend side:**
`save_roadmaps` writes Journey 2 and Journey 3 results to the same default
filename, `output/roadmap.json`. In testing, a Journey 3 run silently
overwrote a Journey 2 run's file. When wiring this into the backend,
**always pass a unique `output_dir` or filename per user/session**
(e.g. `output/{user_id}/{session_id}.json`) rather than relying on the
default — or better, don't write to disk at all and persist the returned
dict straight to your DB/object store.

---

## 4. CLI usage (for manual testing / debugging only)

```bash
python roadmap_engine.py --journey 1 --input journey1_result.json --hours 8
python roadmap_engine.py --journey 2 --input journey2_result.json --hours 8 --no-model
python roadmap_engine.py --journey 3 --input journey3_result.json --hours 8
```

`--no-model` skips Groq entirely and runs the deterministic fallback path —
useful for offline testing or if you want zero LLM cost for a given run.

---

## 5. Output schema (every roadmap has this shape)

```jsonc
{
  "career": "ai" | "data" | "cyber" | "development" | "ui_ux" | null,
  "goal": null | string,
  "starting_level": "foundation" | "intermediate" | "advanced",
  "target_level": "...",
  "learning_objectives": [
    { "skill": "machine_learning_reasoning", "priority": "critical|high|medium|low" }
  ],
  "phases": [
    {
      "phase": 1,
      "title": "...",
      "objectives": ["..."],
      "resources": ["ai_ml_001", "..."]   // verified resource IDs only, never invented
    }
  ],
  "certifications": ["..."],
  "job_preparation": ["..."],
  "recommended_jobs": ["..."],
  "timeline": {
    "total_duration_weeks": 55,
    "hours_per_week": 8.0,
    "total_estimated_hours": 440,
    "weeks": [
      { "week": 1, "focus": ["..."], "resources": ["..."], "estimated_hours": 8.0, "milestone": "..." }
    ]
  },
  "meta": {
    "plan_source": "groq" | "deterministic" | "deterministic_fallback" | "empty",
    "timeline_source": "groq" | "deterministic" | "deterministic_fallback" | "empty",
    "plan_fallback_reason": null | string,
    "timeline_fallback_reason": null | string,
    "engine_mode": "groq_with_module_fallbacks" | "deterministic",
    "validation": {
      "is_valid": true,
      "errors": [],
      "warnings": []
    }
  }
}
```

**Always read `meta.validation.is_valid` before showing a roadmap to a
user.** It will always be `true` for anything `generate_roadmap()` returns
(invalid roadmaps are regenerated internally, never silently returned) —
but check it anyway as a safety net, and log `meta.validation.warnings`
even when `is_valid` is `true` (non-fatal, e.g. "long duration" notices).

**`plan_source`/`timeline_source: "empty"`** (seen in Journey 2 testing) is
**not an error** — it means the learner had no skill gaps to close
(e.g. "Highly Ready", 100% readiness). Render this as "you're already
job-ready" rather than treating it as a failure state.

---

## 6. Journey input contracts (what to hand this engine)

- **Journey 1** — the raw multi-career exploration result (contains every
  career the assessment found). Adapter fans it out into one profile per
  career automatically — do not pre-filter to "the best" career before
  calling.
- **Journey 2** — the raw result with `career` already embedded (single
  career, already chosen by the user).
- **Journey 3** — the raw skills-assessment result. `career` stays `None`
  by design; this journey is driven purely by assessed skills.

Sample input/output pairs for all three journeys are included in
`sample_output/` for reference:
`roadmap_ai.json`, `roadmap_cyber.json`, `roadmap_data.json`,
`roadmap_development.json`, `roadmap_ui_ux.json` (Journey 1, 5 careers),
`roadmap.json` (Journey 3 sample — see filename collision note above).

---

## 7. Error handling behavior (already built in, no extra work needed)

- If Groq is unreachable / returns invalid JSON / hallucinates a resource
  ID or violates prerequisite ordering → `planner.py`/`timeline.py`
  automatically fall back to their deterministic logic. The backend never
  sees a raw Groq failure; check `meta.plan_source` /
  `meta.timeline_source` if you want to know which path was used.
- If no `GROQ_API_KEY` is set and `use_model=True`, it degrades gracefully
  to deterministic — it will not raise.
- Resource IDs are always verified against `resources.json` — the engine
  will never emit a resource ID that doesn't exist in that dataset.

---

## 8. What NOT to do on the backend side

- Don't re-score, re-rank, or pick "the best" career out of a Journey 1
  list — the engine already returns one full roadmap per career; let the
  frontend/product layer decide how to present multiple options.
- Don't pass a Journey 2/3 `career` value into a Journey 1 call to try to
  narrow it — Journey 1 always returns all careers found in the input by
  design.
- Don't write directly to `output/roadmap.json` in a multi-user context —
  see the filename collision note in §3.

---

## 9. Verified test results (for reference)

All of the following were run and passed prior to this handoff:

| Test | Result |
|---|---|
| `adapter.py` self-test (Journeys 1/2/3 adaptation, gap/level preservation) | PASS |
| `level_rules.py` self-test (7 rules incl. beginner/foundation, no-evidence) | PASS |
| `retrieval.py` self-test (canonical matching, no invented resource IDs) | PASS |
| `planner.py` self-test (incl. hallucination/duplicate/prereq rejection, Groq stub + real fallback paths) | PASS |
| `timeline.py` self-test (incl. hours-budget enforcement, Groq stub + real fallback paths) | PASS |
| `schema.py` self-test (structural validation, round-trip) | PASS |
| `validator.py` self-test (14 business-rule checks) | PASS |
| Live Groq end-to-end (`test_timeline_groq.py`) | PASS — 14-week, 109-hour plan generated correctly |
| `roadmap_engine.py --journey 1` (5 careers, deterministic + Groq) | PASS — all 5 VALID |
| `roadmap_engine.py --journey 2` (data, deterministic + Groq) | PASS — correctly returned empty roadmap for a no-gap learner |
| `roadmap_engine.py --journey 3` (skills-only, deterministic + Groq) | PASS — 16 phases, VALID, 3 non-fatal warnings |
