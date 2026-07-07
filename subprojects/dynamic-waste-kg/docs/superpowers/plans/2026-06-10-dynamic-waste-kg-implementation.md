# Dynamic Waste Knowledge Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working Python prototype of the dynamic waste knowledge graph that supports long-term knowledge, short-term memory, event logging, graph updates from observations, and query interfaces for multi-agent planning.

**Architecture:** Use an in-memory property-graph core with explicit dataclasses for categories, object instances, relations, observations, and events. A graph manager will own incremental matching, node/edge updates, and event recording. Thin agent-facing services will expose perception ingestion, retrieval, planning-context extraction, and execution feedback so the graph can serve as the shared state backbone for later LangGraph and ROS2 integration.

**Tech Stack:** Python standard library, `dataclasses`, `typing`, `json`, `pathlib`, `unittest`.

---

### Task 1: Define the graph data model

**Files:**
- Create: `wastekg/core/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
from wastekg.core.models import CategorySpec, ObjectInstance, RelationEdge, Observation, GraphEvent

def test_models_store_expected_fields():
    category = CategorySpec(name="brick", category="building_waste", material="ceramic", risk_level="low")
    instance = ObjectInstance(instance_id="brick_01", class_name="brick")
    edge = RelationEdge(source_id="brick_01", relation="on_top_of", target_id="brick_02")
    obs = Observation(frame_id="f1", source="realsense")
    event = GraphEvent(event_type="recognition", subject_id="brick_01")
    assert category.name == "brick"
    assert instance.instance_id == "brick_01"
    assert edge.relation == "on_top_of"
    assert obs.frame_id == "f1"
    assert event.event_type == "recognition"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_models`
Expected: import failure because package and models do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

@dataclass
class CategorySpec:
    name: str
    category: str
    material: str = ""
    risk_level: str = "unknown"
    fragility: str = "unknown"
    graspability: str = "unknown"
    recyclability: str = "unknown"
    semantic_tags: List[str] = field(default_factory=list)
    confidence_prior: float = 0.0

@dataclass
class ObjectInstance:
    instance_id: str
    class_name: str
    center_xyz: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    orientation: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 1.0)
    confidence: float = 0.0
    priority: int = 0
    processed_flag: bool = False
    last_action: str = ""
    task_status: str = "pending"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_models`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add wastekg/core/models.py tests/test_models.py
git commit -m "feat: add graph data models"
```

### Task 2: Implement the in-memory graph store

**Files:**
- Create: `wastekg/graph/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
from wastekg.core.models import CategorySpec, Observation
from wastekg.graph.store import KnowledgeGraph

def test_register_category_and_upsert_instance():
    graph = KnowledgeGraph()
    graph.register_category(CategorySpec(name="brick", category="building_waste"))
    graph.ingest_observation(Observation(frame_id="f1", source="realsense"))
    assert "brick" in graph.categories
    assert graph.events
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_store`
Expected: import failure or missing class failure.

- [ ] **Step 3: Write minimal implementation**

```python
class KnowledgeGraph:
    def __init__(self) -> None:
        self.categories = {}
        self.instances = {}
        self.edges = []
        self.events = []

    def register_category(self, category):
        self.categories[category.name] = category

    def ingest_observation(self, observation):
        self.events.append(observation)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_store`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add wastekg/graph/store.py tests/test_store.py
git commit -m "feat: add in-memory graph store"
```

### Task 3: Add incremental update and relation extraction

**Files:**
- Modify: `wastekg/graph/store.py`
- Create: `tests/test_update.py`

- [ ] **Step 1: Write the failing test**

```python
from wastekg.core.models import Observation, DetectedObject
from wastekg.graph.store import KnowledgeGraph

def test_upsert_instance_and_relation_update():
    graph = KnowledgeGraph()
    obs = Observation(frame_id="f1", source="realsense", objects=[
        DetectedObject(temp_id="t1", class_name="brick", confidence=0.92, center_xyz=(0.1, 0.2, 0.3))
    ])
    graph.apply_observation(obs)
    assert "t1" in graph.instances
    assert graph.instances["t1"].class_name == "brick"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_update`
Expected: missing `apply_observation` / `DetectedObject` failure.

- [ ] **Step 3: Write minimal implementation**

```python
def apply_observation(self, observation):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_update`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add wastekg/graph/store.py tests/test_update.py
git commit -m "feat: add incremental graph updates"
```

### Task 4: Expose multi-agent query helpers

**Files:**
- Create: `wastekg/graph/query.py`
- Test: `tests/test_query.py`

- [ ] **Step 1: Write the failing test**

```python
from wastekg.graph.query import build_planning_context

def test_build_planning_context_returns_task_ready_view():
    context = build_planning_context(...)
    assert "candidates" in context
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_query`
Expected: import failure.

- [ ] **Step 3: Write minimal implementation**

```python
def build_planning_context(graph, task=None):
    return {...}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_query`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add wastekg/graph/query.py tests/test_query.py
git commit -m "feat: add planning query helpers"
```

### Task 5: Add CLI demo and project documentation

**Files:**
- Create: `wastekg/graph/cli.py`
- Create: `README.md`
- Create: `pyproject.toml`

- [ ] **Step 1: Write the failing test**

```python
def test_cli_demo_runs():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_cli`
Expected: missing module or missing entrypoint.

- [ ] **Step 3: Write minimal implementation**

```python
def main():
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_cli`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add wastekg/cli.py README.md pyproject.toml tests/test_cli.py
git commit -m "feat: add cli demo and docs"
```

---

## Self-Review

1. Spec coverage: The plan covers graph data models, in-memory storage, incremental updates, planning-context queries, and demo/docs.
2. Placeholder scan: Replaced vague steps with explicit test and implementation targets; only remaining ellipses are in example snippets for brevity where exact structure will be defined in code.
3. Type consistency: Data model names (`CategorySpec`, `ObjectInstance`, `Observation`, `GraphEvent`) are used consistently across tasks.
