# CrowdSense

---
CrowdSense is a **desktop application** that analyzes video footage to detect people, estimate crowd density, and trigger alerts when occupancy exceeds a configurable safety limit. It is intended for safety monitoring in locations such as corridors, venues, and public spaces.

---
## Features (Planned MVP by June 20, 2026)
- Load and preview local video files (**offline**)
- Detect people using **Ultralytics YOLOv8** (default: `yolov8n`)
- Live people count + density level classification (Low/Med/High/Critical)
- Configurable safety limit with alert + cooldown (prevents repeated alert spam)
- Export run logs to `output/` (CSV)

---
## Tech Stack
- Python 3.10+ (recommended: **3.11**)
- PyQt6 (desktop UI)
- OpenCV (video reading + drawing overlays)
- Ultralytics YOLOv8 (person detection)

---
## Project Structure
```text
CrowdSense/
  README.md
  requirements.txt
  .gitignore
  models/           # local model weights
  output/           # logs/exports
  videos/        
  src/
    main.py
```

---
## Setup (PyCharm)
### 1) Create and select a virtual environment (venv)
PyCharm:
- Settings → Project → Python Interpreter → Add Interpreter
- Virtualenv → **Generate new**
- Base interpreter: Python **3.11**
- Location: `<project>/.venv`
- Leave “Inherit packages…” unchecked

### 2) Install dependencies
From the PyCharm terminal:
```bash
pip install -r requirements.txt
```

---
## Model Weights (Offline)
CrowdSense uses **YOLOv8n** by default.

1) Create a folder:
```bash
mkdir models
```

2) Download weights once (Ultralytics will fetch them):
```bash
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

3) Place the weights here:
```text
models/yolov8n.pt
```

> Note: Model weight files (`*.pt`) are ignored by git and should not be committed.

---
## Run
```bash
python src/main.py
```

---
## Output
- Logs/exports will be written to:
```text
output/
```

---
## Troubleshooting
### OpenCV cannot open a video
```bash
python -c "import cv2; cap=cv2.VideoCapture('path/to/video.mp4'); print('opened:', cap.isOpened())"
```

### Ultralytics model not found / offline issues
- Confirm the file exists at `models/yolov8n.pt`
- Ensure your code loads the model by local path (not by name)

---
## Roadmap (High Level)
- Phase 0: environment + UI skeleton
- Phase 1: video load + playback
- Phase 2: detection + overlays + counting
- Phase 3: alerts + logging + export (CSV)
- Phase 4: packaging (PyInstaller) + final demo build