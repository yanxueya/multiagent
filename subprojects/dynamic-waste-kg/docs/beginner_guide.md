# Dynamic Waste Knowledge Graph Beginner Guide

This guide is written for a beginner. It shows how to use the knowledge graph step by step, what each part means, and how to extend it later.

## 1. What this project is

This project is a small but working knowledge-graph prototype for construction waste and hazardous waste scenes.

It has three layers:

- Long-term knowledge: what an object is, such as its category, risk level, and material
- Short-term memory: what is happening now, such as position, pose, priority, and current relations
- Event log: what changed, when it changed, and why it changed

The graph is designed to support later multi-agent planning and ROS2 execution.

## 2. Where to start

Start with these files:

- `wastekg/models.py`: defines the data structures
- `wastekg/store.py`: stores and updates the graph
- `wastekg/query.py`: builds planning context for later agents
- `wastekg/cli.py`: builds a demo scene

## 3. Step-by-step usage

### Step 1: Create a graph

```python
from wastekg.store import KnowledgeGraph

graph = KnowledgeGraph()
```

This gives you an empty graph with no categories, no objects, and no relations.

### Step 2: Add long-term knowledge

```python
from wastekg.models import CategorySpec

graph.register_category(
    CategorySpec(
        name="paint_can",
        category="hazardous_waste",
        material="metal",
        risk_level="high",
        graspability="caution",
        recyclability="low",
    )
)
```

This is long-term knowledge. It should not change just because the object moves.

### Step 3: Add a first observation

```python
from wastekg.models import DetectedObject, Observation

obs1 = Observation(
    frame_id="frame_001",
    source="realsense",
    objects=[
        DetectedObject(
            temp_id="t1",
            class_name="paint_can",
            confidence=0.93,
            center_xyz=(0.10, 0.12, 0.08),
            risk_level="high",
        )
    ],
)

summary1 = graph.apply_observation(obs1)
```

This creates a short-term memory node, such as `paint_can_01`.

### Step 4: Read the result

```python
print(summary1)
print(graph.instances["paint_can_01"].to_dict())
```

You should look for:

- `instance_id`
- `class_name`
- `center_xyz`
- `priority`
- `risk_level`
- `task_status`

### Step 5: Add a second observation for the same object

```python
obs2 = Observation(
    frame_id="frame_002",
    source="realsense",
    objects=[
        DetectedObject(
            temp_id="t1",
            class_name="paint_can",
            confidence=0.96,
            center_xyz=(0.14, 0.15, 0.08),
            risk_level="high",
        )
    ],
)

summary2 = graph.apply_observation(obs2)
```

This should update the same instance instead of creating a new one.

What you are learning here:

- short-term memory keeps identity across frames
- position changes over time
- confidence can change
- the event log records the update

### Step 6: Add relations between objects

```python
obs3 = Observation(
    frame_id="frame_003",
    source="realsense",
    objects=[
        DetectedObject(temp_id="a", class_name="brick", confidence=0.95, center_xyz=(0.0, 0.0, 0.0)),
        DetectedObject(temp_id="b", class_name="paint_can", confidence=0.94, center_xyz=(0.0, 0.0, 0.10), risk_level="high"),
    ],
)

graph.apply_observation(obs3)
```

Because the `paint_can` is above the `brick`, the graph can infer a relation such as `on_top_of`.

This is important because task planning depends on relations.

### Step 7: Query planning context

```python
from wastekg.query import build_planning_context

context = build_planning_context(graph)
print(context["candidates"])
print(context["blocked"])
print(context["risky"])
```

This is the interface that later multi-agent components should use.

### Step 8: Mark an object as processed

```python
graph.mark_processed("paint_can_01", action="picked_and_removed")
```

This changes the short-term memory state and writes an event.

## 4. How long-term and short-term memory differ

### Long-term knowledge

Stored in `graph.categories`

Example:

- `paint_can` is hazardous
- `brick` is low risk
- `metal` is medium risk

This should stay stable unless your domain knowledge changes.

### Short-term memory

Stored in `graph.instances`

Example:

- `paint_can_01` moved from one position to another
- `paint_can_01` may be blocked by `brick_01`
- `paint_can_01` may be processed or waiting

This changes every time you observe the scene or execute an action.

## 5. How interaction works

Interaction means that one object affects another.

Examples:

- `on_top_of`
- `touching`
- `near`
- `blocked_by`
- `supports`

These relations are important because the planner should not treat all objects as independent.

## 6. How attributes work

Attributes are the information stored on nodes and edges.

Examples of instance attributes:

- `center_xyz`
- `priority`
- `risk_level`
- `processable`
- `graspable`
- `blocked_by`

Examples of category attributes:

- `material`
- `risk_level`
- `graspability`
- `recyclability`

## 7. How to continue later

Once you understand this prototype, the next step is to connect:

1. RealSense D435i input
2. YOLOv11 object detection
3. Multi-modal verification
4. LangGraph agents
5. ROS2 execution

The graph should remain the shared state center for all of them.

## 8. Suggested learning order

1. Run the tests
2. Read the beginner guide
3. Inspect the demo CLI
4. Modify one category
5. Add one new object
6. Add one relation
7. Query the planning context
8. Mark one object as processed

## 9. Run commands

From `subprojects/dynamic-waste-kg`:

```bash
python -m unittest discover -s tests
python -m wastekg.cli
python -m wastekg.cli --json
```

