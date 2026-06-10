# Dynamic Waste Knowledge Graph

This repository contains a working prototype of a dynamic knowledge graph for hazardous waste recognition and human-robot collaborative decision-making in complex construction environments.

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

