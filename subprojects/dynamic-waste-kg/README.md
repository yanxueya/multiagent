# Dynamic Waste Knowledge Graph

This repository contains a working prototype of a dynamic knowledge graph for hazardous waste recognition and human-robot collaborative decision-making in complex construction environments.

If you are new to the project, start here:

- [Beginner guide](docs/beginner_guide.md)
- [Tests that explain the graph](tests/)

## What it does

- Stores long-term category knowledge and short-term scene memory
- Tracks object instances and spatial relations
- Records observation and action events
- Exposes planning-oriented query helpers for multi-agent systems
- Provides a small CLI demo that builds a sample scene

## Run tests

```bash
python -m unittest discover -s tests
```

## Run the demo

```bash
python -m wastekg.cli
python -m wastekg.cli --json
```

## Main modules

- `wastekg.models`: graph data model
- `wastekg.store`: in-memory dynamic graph store and update engine
- `wastekg.query`: planning-context extraction
- `wastekg.cli`: demo graph builder and CLI entrypoint

## Learning goals

- Understand long-term knowledge versus short-term memory
- Understand how object relations are stored and updated
- Understand how attributes affect planning
- Understand how this graph can later connect to multi-agent agents and ROS2
