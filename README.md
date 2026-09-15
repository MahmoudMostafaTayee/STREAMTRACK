# STREAMTRACK

**A Streams-and-Tables Architecture for Scalable and Reconfigurable Multi-Camera Object Tracking**

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Java](https://img.shields.io/badge/Java-17%2B-orange)](https://www.java.com)
[![Esper](https://img.shields.io/badge/Esper-9.0.0-green)](https://www.espertech.com/esper/)
[![Maven](https://img.shields.io/badge/Maven-3.8%2B-red)](https://maven.apache.org/)

Official reference implementation of the paper:

> **STREAMTRACK: A Streams-and-Tables Architecture for Scalable and Reconfigurable Multi-Camera Object Tracking**
> Mahmoud Tayee, Mohamed ElHelw, Ahmed Awad — *Future Generation Computer Systems* (under review)

STREAMTRACK recasts multi-camera object tracking (MCOT) from a monolithic computer-vision pipeline into a **streams-and-tables** system. Detections flow as append-only event streams, global identities and camera topology are maintained as queryable relational tables, and cross-camera association is a continuous, topology-aware join over them. On identical hardware and identical algorithm code, the architecture delivers:

- **9.8×** end-to-end speedup over a functionally equivalent JVM batch baseline (12.0× representative selection, 9.5× HAC clustering) with **100% Global-ID parity**
- **4.16×** per-association latency reduction from topology-aware partitioning at 9 cameras (4.27× steady-state)
- **Zero-downtime reconfiguration** of the camera network and tracker parameters via an event-driven control plane (outage 337 ms, recovery 190 ms)
- **SQL-inspectable** identity and topology state at runtime

---

## Table of Contents

- [Repository Layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Building](#building)
- [Testing](#testing)
- [Datasets](#datasets)
- [Quick Start](#quick-start)
- [Command-Line Reference](#command-line-reference)
- [Reproducing the Paper's Results](#reproducing-the-papers-results)
  - [RQ1 — Five-Stage Parity & Architectural Speedup](#rq1--five-stage-parity--architectural-speedup)
  - [RQ2 — Topology-Aware Latency Reduction](#rq2--topology-aware-latency-reduction)
  - [RQ3 — Zero-Downtime Reconfiguration](#rq3--zero-downtime-reconfiguration)
  - [RQ4 — Architectural Speedup under State Growth](#rq4--architectural-speedup-under-state-growth)
- [Architecture Overview](#architecture-overview)
- [Technologies](#technologies)
- [Citation](#citation)
- [License](#license)

---

## Repository Layout

```
STREAMTRACK/
├── src/main/java/com/espertech/esper/example/IOT/
│   ├── clusterers/              # Core tracking algorithms
│   │   ├── MCPT.java                # Multi-camera association (HAC over topology groups)
│   │   ├── SCPT.java                # Single-camera pre-clustering
│   │   ├── Tracker.java             # Tracking orchestration
│   │   ├── GlobalTrackState.java    # Feature tensor store (zero-copy, in-memory)
│   │   ├── CluStreamClusterer.java  # Stream-clustering baseline (MOA)
│   │   └── ClusTreeClusterer.java   # Stream-clustering baseline (MOA)
│   ├── helpers/                 # Parameters & utilities
│   │   ├── TrackingParameters.java  # CLI parsing + configurable parameters
│   │   ├── SimilarityUtils.java
│   │   └── ClusteringUtils.java
│   ├── streamers/               # Data ingestion
│   │   └── EmbeddingFeatureStreamer.java  # Replays pre-extracted .npy embeddings
│   ├── streams/                 # Event type definitions (streams + table schemas)
│   │   ├── EmbeddingFeature.java
│   │   ├── SingleCameraResult.java
│   │   ├── GlobalPersonEvent.java
│   │   ├── CameraTopology.java
│   │   ├── MCPTConfigEvent.java     # Runtime parameter reconfiguration events
│   │   └── TrackExpiredEvent.java
│   ├── utils/                   # Esper integration & networking
│   │   ├── EventEPLUtil.java        # EPL statement deployment
│   │   └── TableSocketServer.java   # Live SQL-table inspection socket (port 9999)
│   ├── IotMain.java             # Streaming entry point
│   └── JavaBatchBaseline.java   # JVM batch baseline (recomputes state per window)
├── src/main/resources/          # Logging configuration (log4j.xml, logback.xml)
├── src/test/java/com/espertech/esper/example/IOT/
│   └── SceneConfigTest.java     # Regression tests for scene-parameter loading
├── scripts/
│   ├── run/                     # Scenario launch scripts (scene experiments, reconfig)
│   ├── benchmark/               # Benchmark harnesses (batch, topology, multi-run)
│   ├── listen_to_table.py       # Live client for the table inspection socket
│   ├── compare_mcpt_dumps.py    # Stage-by-stage Java vs Python parity checker
│   ├── compare_final_outputs.py # End-to-end Java vs Python ID-mapping comparison
│   └── verify_numbers.py        # Extracts headline metrics from benchmark logs
├── paper/FGCS/                  # FGCS submission: main.tex, figures, embedded bibliography
├── paper/Evidence/              # Benchmark figures + generator scripts
├── paper/generate_figures.py    # Chart generator (speedup bars, scalability projection)
├── Datasets/                    # Feature embeddings (not included — see below)
├── Original/                    # Python figure-generation scripts & map assets
├── config/scenes/               # Per-scene tracker parameter files (scene_NNN.json)
├── pom.xml
├── CITATION.cff
├── LICENSE
└── README.md
```

> **Note on the Java package name:** the `com.espertech.esper.example.IOT` package reflects the project's origin as a fork of the open-source Esper IOT example; the implementation itself is entirely the STREAMTRACK system described in the paper.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| JDK | 17+ (tested on OpenJDK 21) | Paper results used `-Xms256m -Xmx256m` |
| Maven | 3.8+ | |
| Python | 3.8+ | Only for parity/analysis scripts |
| OS | Windows / Linux / macOS | Benchmark scripts are PowerShell (Windows) |

## Building

```bash
mvn clean install -Dcheckstyle.skip=true
```

## Testing

```bash
mvn test -Dcheckstyle.skip=true
```

The test suite covers the scene-parameter loader (`TrackingParameters.getParametersForScene`): shipped defaults, local override files, command-line precedence, and graceful fallback when no config file exists. The tests are self-contained and require no datasets.

---

## Datasets

The pipeline consumes **pre-extracted appearance-embedding features** (`.npy`, one file per frame per camera). Download instructions and the expected directory layout are documented in [Datasets/README.md](Datasets/README.md).

| Dataset | Source | Cameras | Used for |
|---|---|---|---|
| Woven VisionAI WTS | [WTS homepage](https://woven-visionai.github.io/wts-dataset-homepage/) | 4 | Parity (RQ1), stage speedups, RQ4 |
| NVIDIA SmartSpaces | [AI City 2025 Track 1](https://www.aicitychallenge.org/2025-track1/) | 9 | Topology pruning (RQ2), reconfiguration (RQ3) |

Once downloaded, place the extracted features under `Datasets/EmbedFeature/scene_001/` (WTS, cameras `0101–0104`) and `Datasets/EmbedFeature/scene_002/` (NVIDIA, cameras `0001, 0002, 0011, 0017, 0019, 0021, 0025, 0027, 0030`). All scripts in this repository use these paths by default.

> **Naming note:** the `--scene` flag selects a folder under `Datasets/EmbedFeature/` and is independent of the datasets' internal scene numbering. In this repository, `--scene 1` selects the WTS-derived 4-camera scene and `--scene 2` selects the 9-camera NVIDIA SmartSpaces scene; the paper's phrase "WTS (Scene 2)" refers to the WTS dataset's own scene index, whose features are stored here under `scene_001/`.

---

## Quick Start

```bash
# Windows (CMD)
scripts\run\run_project.bat

# Or directly with Maven (any OS) — all cameras, topology-aware, 9-camera scene
mvn exec:java -Dexec.mainClass="com.espertech.esper.example.IOT.IotMain" ^
  "-Dexec.args=--scene 2 --features_dir ./Datasets/EmbedFeature --camera all ^
   --camera_groups '2,17;1,11;19,27;21,25,30' --turbo --output_dir ./output/scene2" ^
  -Dcheckstyle.skip=true
```

While running, connect a live viewer to the global ID table:

```bash
python scripts/listen_to_table.py    # streams table updates on localhost:9999
```

---

## Command-Line Reference

All options are parsed by `TrackingParameters` (run without arguments to see the option summary):

| Argument | Description | Default |
|---|---|---|
| `--scene` | Scene number; selects `Datasets/EmbedFeature/scene_NNN/` | 1 |
| `--features_dir` | Base directory containing the scene folders | **required** |
| `--camera` | Comma-separated camera IDs or `all` (auto-discovered from the features dir) | `all` |
| `--camera_groups` | Topology groups, e.g. `2,17;1,11;19,27;21,25,30` — `all` = one global group | `all` |
| `--camera_transitions` | Transition edges, e.g. `0001->0002,0011;...` (used by reconfiguration) | `""` |
| `--output_dir` | Output directory for dumps, logs, and results | `./output` |
| `--turbo` | Disable real-time pacing; stream at max speed (use for benchmarks) | off |
| `--reconfig` | Enable the runtime topology reconfiguration experiment | off |
| `--clusterer` | Clustering algorithm: `agglomerative`, `clustream`, `clustree` | `agglomerative` |
| `--exec_all` / `--exec_scpt` / `--exec_mcpt` | Stage execution level | all |
| `--debug` | Verbose per-window dumps into `mcpt-dumps/` (used for parity checks) | off |

The environment variable `MAX_WINDOWS` bounds the number of synchronisation windows processed (default 50; benchmark scripts set this explicitly).

### Scene Configuration Files

Per-scene tracker parameters (thresholds, clustering settings, NMS options) live in JSON files under `config/scenes/` — e.g. `config/scenes/scene_002.json` is applied automatically when running with `--scene 2`. Resolution order:

1. `config/scene_NNN.json` — explicit per-scene override (not committed; for local experiments)
2. `config/scenes/scene_NNN.json` — shipped scene defaults
3. none found — built-in class defaults

CLI flags always win over config values (e.g. `--clusterer clustream` overrides `clustering_method` from any config file). The keys accepted in a config file mirror the runtime-reconfigurable parameters exposed through `MCPTConfig` events; unknown keys are logged and ignored, and keys prefixed with `_` are treated as comments.

---

## Reproducing the Paper's Results

All experiments below run against the two datasets in [Datasets](#datasets). Commands are Windows-flavoured (PowerShell/CMD) since the harnesses are PowerShell scripts; each is a thin wrapper over Maven, so they translate directly to `bash`.

> **Hardware context (paper, Evaluation section):** Intel Core i7-10610U (4C/8T, 1.80 GHz), 32 GB RAM, JVM heap capped at 256 MB to simulate a resource-constrained edge gateway. Absolute numbers will differ on other hardware; the *ratios* are the reported result.

### RQ1 — Five-Stage Parity & Architectural Speedup

*Paper claim: 100% Global-ID parity with the Python reference pipeline; 9.8× end-to-end speedup over the JVM batch baseline (12.0× representative selection, 9.5× HAC clustering) on Woven WTS.*

**1. Stream processing run (also produces the parity dumps used by the paper):**

```bat
scripts\run\run_scene2_exp2.bat
```

**2. Batch baseline (same JVM, same libraries — isolates the architectural effect):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\benchmark\benchmark_batch_baseline.ps1 -Iterations 5 -MaxWindows 25
```

**3. Verify the numbers:**

```powershell
python scripts\verify_numbers.py
```

For the cross-implementation (Java vs Python) parity evidence:

```bash
# Run both pipelines with --debug to emit stage dumps into <output_dir>/mcpt-dumps/, then:
python scripts/compare_mcpt_dumps.py --output-dir ./output/scene2
python scripts/compare_final_outputs.py output/scene2/batch_whole_tracking_results.json <python_pipeline_results.json>
```

**Expected outcome:** `compare_mcpt_dumps.py` reports PASS for all five stages (similarity matrix, representative selection, clustering, camera dict, global IDs); `verify_numbers.py` extracts cumulative batch vs streaming times whose ratio is the 9.8× headline figure.

### RQ2 — Topology-Aware Latency Reduction

*Paper claim: partitioning the 9-camera network into 4 topology groups reduces mean association latency from 41.96 ms to 10.10 ms (4.16×; 4.27× steady-state).*

```powershell
powershell -ExecutionPolicy Bypass -File scripts\benchmark\benchmark_topology.ps1
# Multi-iteration statistics (recommended; the paper used 10 iterations):
powershell -ExecutionPolicy Bypass -File scripts\benchmark\benchmark_multi_run.ps1 -Iterations 10 -MaxWindows 25
```

The harness runs the same workload twice — once with `--camera_groups all` (global, 36 camera pairs) and once with `2,17;1,11;19,27;21,25,30` (topology-aware, 6 pairs) — parses `Total MCPT Time:` from the logs, and writes per-iteration summaries under `output/benchmark_multi/`.

**Expected outcome:** mean per-window association latency for the topology-aware configuration ≈ 1/4.16 of the global configuration (≈ 1/4.27 after discarding the JIT warm-up window).

### RQ3 — Zero-Downtime Reconfiguration

*Paper claim: live topology outage/recovery in 337 ms / 190 ms with total state preservation; runtime parameter changes (simTh 0.75→0.85, epsilonMcpt 0.37→0.30, shortTrackTh 0→1) applied at frame 270 without restart.*

```bat
scripts\run\run_reconfig_experiment.bat
```

This runs the 9-camera topology for 6 windows, injects a topology change event after window 2, and logs the transition timeline to `output/reconfig_experiment/experiment.log`. Observe the Global ID Table continuously during the run:

```bat
python scripts\listen_to_table.py
```

**Expected outcome:** the log shows the outage and recovery query deployment completing in a few hundred milliseconds each, with no identity loss (global IDs carried across the change) and no restart of the engine. Parameter-change events (`MCPTConfig`) are applied from the next synchronisation window.

### RQ4 — Architectural Speedup under State Growth

*Paper claim: batch cost grows with archive size (re-reads all history per window) while streaming cost stays flat; reported as the 9.8× cumulative figure over 25 windows.*

```powershell
# Batch curve (incremental window counts):
powershell -ExecutionPolicy Bypass -File scripts\benchmark\benchmark_java_batch.ps1

# Streaming curve:
powershell -ExecutionPolicy Bypass -File scripts\benchmark\run_benchmark.ps1
```

**Expected outcome:** cumulative batch time grows superlinearly with the window count while the streaming curve remains linear and shallow; the ratio at 25 windows reproduces the 9.8× end-to-end figure (Fig. 5 in the paper).

---

## Architecture Overview

```
Detection Streams ──▶ Continuous Queries (EPL/SQL) ──▶ Derived Stream (GlobalPersonEvent)
                             │                                   ▲
                             ▼                                   │
                    State Tables (GlobalIDTable,              SCPT per-camera
                    CameraTopologyTable, MCPTConfigTable)     pre-clustering
```

- **Streams** — immutable per-camera detections and tracklet updates (`EmbeddingFeature`, `SingleCameraResult`).
- **Tables** — mutable, queryable state: global identity mapping (`GlobalIDTable`), camera-network topology (`CameraTopologyTable`), runtime-tunable parameters (`MCPTConfigTable`).
- **Queries** — continuous EPL statements that consume streams, read/update tables, and emit results; identity lifecycle (expiring stale tracks after 2 min of inactivity) is enforced by priority-ordered timer queries.
- **Hybrid state management** — Esper owns lightweight relational state; heavy feature tensors live in JVM memory (`GlobalTrackState`) and are shared zero-copy between operators.
- **Plan-time topology** — camera neighbourhoods are compiled into EPL `IN(...)` predicates at query-plan time, so topology filtering costs nothing on the per-tuple hot path.

---

## Technologies

| Component | Version | Purpose |
|---|---|---|
| Java | 17+ (tested on 21) | Core implementation |
| [Esper](https://www.espertech.com/esper/) | 9.0.0 | Complex Event Processing engine (streams, tables, continuous queries) |
| [ND4J](https://deeplearning4j.konduit.ai/) | 1.0.0-beta7 | N-dimensional numerical computing (similarity matrices) |
| [Smile](https://haifengl.github.io/) | 3.0.1 | Hierarchical Agglomerative Clustering |
| [MOA](https://moa.cms.waikato.ac.nz/) | 2024.07.0 | CluStream / ClusTree stream-clustering baselines |
| Maven | 3.8+ | Build system |
| Python | 3.8+ | Parity verification, log analysis, figure generation |

---

## Citation

If you use STREAMTRACK in your research, please cite the accompanying paper:

```bibtex
@article{tayee2026streamtrack,
  author  = {Mahmoud Tayee and Mohamed ElHelw and Ahmed Awad},
  title   = {{STREAMTRACK}: A Streams-and-Tables Architecture for Scalable and
             Reconfigurable Multi-Camera Object Tracking},
  journal = {Future Generation Computer Systems},
  year    = {2026},
  note    = {Under review}
}
```

A machine-readable `CITATION.cff` is provided at the repository root.

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.
