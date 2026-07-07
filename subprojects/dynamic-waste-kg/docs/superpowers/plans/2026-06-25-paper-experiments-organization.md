# Paper Experiments Organization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a dedicated `paper_experiments/` layer that organizes the small-paper experiments, generates E3/E4 evidence, and writes submission-oriented result summaries without disrupting the existing YOLO, VLM, and knowledge graph pipeline.

**Architecture:** Keep the reusable system code in `wastekg/`. Add paper-specific protocols, scripts, and outputs under `paper_experiments/`, with generated artifacts under `artifacts/paper/`. Add only small, testable evaluation helpers when the existing graph/query interfaces do not provide the required metrics.

**Tech Stack:** Python 3.14, standard library CSV/JSON/Markdown tooling, existing `wastekg` knowledge graph classes, existing unittest test suite, PowerShell execution on Windows 11 with the project `.venv`.

---

## File Structure

- Create `paper_experiments/README.md`: human-facing experiment map and command index.
- Create `paper_experiments/protocols/e0_dataset_audit.md`: frozen dataset audit summary and evidence locations.
- Create `paper_experiments/protocols/e1_segmentation.md`: frozen YOLO11n-seg test result summary.
- Create `paper_experiments/protocols/e2_vlm_review.md`: explains why text-only models fail E2 and how to choose a real VLM.
- Create `paper_experiments/protocols/e3_policy_routing.md`: policy routing definitions, metrics, and acceptance criteria.
- Create `paper_experiments/protocols/e4_event_replay.md`: event replay definitions, metrics, and acceptance criteria.
- Create `paper_experiments/results/README.md`: result index for manuscript writing.
- Create `paper_experiments/scripts/run_e3_policy_routing.py`: wrapper command that writes E3 results to `artifacts/paper/e3_policy_routing`.
- Create `paper_experiments/scripts/run_e4_event_replay.py`: wrapper command that writes E4 results to `artifacts/paper/e4_event_replay`.
- Create `wastekg/paper/policy.py`: reusable, testable policy-routing evaluator.
- Create `wastekg/paper/event_replay.py`: reusable, testable controlled event replay evaluator.
- Create `tests/test_paper_policy.py`: TDD tests for routing and metric behavior.
- Create `tests/test_paper_event_replay.py`: TDD tests for event replay and metric behavior.
- Modify `docs/journal_manuscript_draft_zh.md`: add a concise, honest "current experimental evidence" section.
- Modify `docs/paper_method_system_design_zh.md`: add a concise method note about E3/E4 evaluation.

## Task 1: E3 Policy Routing Evaluator

**Files:**
- Create: `wastekg/paper/policy.py`
- Create: `tests/test_paper_policy.py`
- Create: `paper_experiments/scripts/run_e3_policy_routing.py`
- Create: `paper_experiments/protocols/e3_policy_routing.md`

- [ ] **Step 1: Write failing tests for routing decisions**

```python
def test_policy_routes_human_only_as_review_required():
    # asbestos_suspect is not a visual class, but it must never be routed to automatic handling.
```

- [ ] **Step 2: Run the focused test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_paper_policy -v`

Expected: FAIL because `wastekg.paper.policy` does not exist.

- [ ] **Step 3: Implement minimal routing**

Create a small policy function that maps an instance plus category prior to one of:

```text
AUTO_CANDIDATE
SUPERVISED_CANDIDATE
HUMAN_REVIEW_REQUIRED
```

- [ ] **Step 4: Add metrics**

Compute:

```text
policy_consistency_rate
restriction_recall
unsafe_automation_rate
over_conservative_rate
human_escalation_rate
```

- [ ] **Step 5: Run focused and full tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_paper_policy -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Task 2: E4 Controlled Event Replay Evaluator

**Files:**
- Create: `wastekg/paper/event_replay.py`
- Create: `tests/test_paper_event_replay.py`
- Create: `paper_experiments/scripts/run_e4_event_replay.py`
- Create: `paper_experiments/protocols/e4_event_replay.md`

- [ ] **Step 1: Write failing tests for replay cases**

```python
def test_event_replay_records_versions_and_events():
    # Each controlled case should produce a monotonic state version and a complete event chain.
```

- [ ] **Step 2: Run the focused test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_paper_event_replay -v`

Expected: FAIL because `wastekg.paper.event_replay` does not exist.

- [ ] **Step 3: Implement minimal replay cases**

Generate at least 30 deterministic controlled cases covering:

```text
normal_confirmation
vlm_correction
vlm_uncertain_fallback
low_confidence_human_review
sensitive_class_review
object_removed
object_reappeared
api_schema_error_fallback
```

- [ ] **Step 4: Add metrics**

Compute:

```text
instance_update_success_rate
event_chain_completeness
state_version_consistency
temporal_policy_consistency
```

- [ ] **Step 5: Run focused and full tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_paper_event_replay -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Task 3: Paper Experiment Folder and Result Index

**Files:**
- Create: `paper_experiments/README.md`
- Create: `paper_experiments/protocols/e0_dataset_audit.md`
- Create: `paper_experiments/protocols/e1_segmentation.md`
- Create: `paper_experiments/protocols/e2_vlm_review.md`
- Create: `paper_experiments/results/README.md`

- [ ] **Step 1: Add the folder-level README**

Explain which experiments are complete, blocked, or generated by scripts.

- [ ] **Step 2: Add E0/E1/E2 protocol files**

Use existing frozen result paths and explicitly state that E2 is blocked until a true VLM is configured.

- [ ] **Step 3: Verify files are readable**

Run:

```powershell
Get-ChildItem -Recurse paper_experiments
```

## Task 4: Generate E3/E4 Results

**Files:**
- Generated: `artifacts/paper/e3_policy_routing/*`
- Generated: `artifacts/paper/e4_event_replay/*`

- [ ] **Step 1: Run E3 script**

Run:

```powershell
.\.venv\Scripts\python.exe paper_experiments\scripts\run_e3_policy_routing.py
```

- [ ] **Step 2: Run E4 script**

Run:

```powershell
.\.venv\Scripts\python.exe paper_experiments\scripts\run_e4_event_replay.py
```

- [ ] **Step 3: Check output files**

Expected files:

```text
artifacts/paper/e3_policy_routing/policy_cases.csv
artifacts/paper/e3_policy_routing/policy_metrics.json
artifacts/paper/e3_policy_routing/policy_report.md
artifacts/paper/e4_event_replay/event_replay_cases.csv
artifacts/paper/e4_event_replay/event_replay_metrics.json
artifacts/paper/e4_event_replay/event_replay_report.md
```

## Task 5: Manuscript Evidence Integration

**Files:**
- Modify: `docs/journal_manuscript_draft_zh.md`
- Modify: `docs/paper_method_system_design_zh.md`
- Modify: `paper_experiments/results/README.md`

- [ ] **Step 1: Add a result summary by research problem**

Cover:

```text
P1: perception-to-task semantic gap
P2: static and untraceable graph-state problem
RQ1: YOLO11n-seg baseline result
RQ2: VLM review status and limitation
RQ3: layered knowledge-state routing and event replay
```

- [ ] **Step 2: Keep claims inside verified scope**

State clearly:

```text
E2 is not complete until a real VLM accepts image evidence.
E3/E4 are controlled software validations, not physical robot grasping validation.
```

- [ ] **Step 3: Run final verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Self-Review

- Spec coverage: The plan covers experiment organization, E3 policy routing, E4 event replay, result generation, manuscript integration, and E2 model-resolution guidance.
- Placeholder scan: No task uses TBD or undefined outputs; all expected files and commands are listed.
- Type consistency: Route labels and metrics are fixed across tests, code, scripts, and protocols.
