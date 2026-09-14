# Datasets

This directory contains the pre-extracted embedding features and pose data
used by STREAMTRACK. The actual `.npy` feature files are **not** included in
the repository due to size limitations.

## Required Datasets

### 1. Woven VisionAI WTS Dataset

- **Source:** [WTS Dataset Homepage](https://woven-visionai.github.io/wts-dataset-homepage/)
- **Cameras used:** 4 (camera IDs `0101`–`0104`)
- **Expected format:** one `.npy` file per frame per camera, named `000001.npy`, `000002.npy`, etc.
- **Place in:** `Datasets/EmbedFeature/scene_001/` (main experiments) or `Datasets/EmbedFeature/scene_003/` (additional scene)
- **Used for:** five-stage parity (RQ1), stage speedups, and state-growth scaling (RQ4)

### 2. NVIDIA SmartSpaces (AI City 2025 Track 1)

- **Source:** [AI City 2025 Challenge](https://www.aicitychallenge.org/2025-track1/) — data hosted at [nvidia/PhysicalAI-SmartSpaces](https://huggingface.co/datasets/nvidia/PhysicalAI-SmartSpaces)
- **Cameras used:** 9 (camera IDs `0001, 0002, 0011, 0017, 0019, 0021, 0025, 0027, 0030`)
- **Expected format:** `.npy` embedding files, one per frame per camera
- **Place in:** `Datasets/EmbedFeature/scene_002/`
- **Used for:** topology-aware latency reduction (RQ2) and live reconfiguration (RQ3)

### 3. Pose Data (Optional)

- Used by the visualisation scripts only; not required for the tracking pipeline.
- Place in: `Datasets/Pose/`

## Directory Structure

After downloading and extracting, the layout must match:

```
Datasets/
├── EmbedFeature/
│   ├── scene_001/           # WTS-derived scene (4 cameras: 0101–0104)
│   │   ├── camera_0101/
│   │   │   ├── 000001.npy
│   │   │   └── ...
│   │   ├── camera_0102/
│   │   ├── camera_0103/
│   │   └── camera_0104/
│   ├── scene_002/           # NVIDIA SmartSpaces (9 cameras: 0001, 0002, 0011, 0017, 0019, 0021, 0025, 0027, 0030)
│   │   ├── camera_0001/
│   │   ├── camera_0002/
│   │   ├── camera_0011/
│   │   ├── camera_0017/
│   │   ├── camera_0019/
│   │   ├── camera_0021/
│   │   ├── camera_0025/
│   │   ├── camera_0027/
│   │   └── camera_0030/
│   └── scene_003/           # Second WTS-derived scene (4 cameras: 0101–0104)
│       └── ...
└── Pose/                    # Optional pose data
```

> **Note:** the `--scene N` command-line flag selects `scene_NNN/` under this
> directory; it is unrelated to the datasets' own scene numbering.

## Feature Extraction

Embedding features should be extracted from raw video using a suitable
ReID or appearance-embedding model (e.g., OSNet, ResNet). Each `.npy` file
contains a 2D array of shape `(N, D)` where `N` is the number of detections
in that frame and `D` is the embedding dimensionality (512 for the WTS
dataset).
