# CrowdSense — Offline Real-Time Crowd Monitoring & Analytics

CrowdSense is an offline-first desktop application designed to monitor entryway and indoor crowd density in real time using local computer vision. The system processes local video files or live camera feeds, counts occupants using optimized **YOLOv11** models, raises desktop notifications and warnings when configurable safety limits are breached, and plots occupancy analytics on an interactive vector trend chart.

Developed as a course project for **COMP 019** (Applications Development and Emerging Technologies) and **COMP 086** (Information Assurance and Security) by **Samuel T. Muralidharan**.

---

## 🌟 Key Features

- **Real-Time Edge Detection**: Asynchronous background detection workers run YOLOv11 person classification without blocking the PyQt6 GUI event loop.
- **Intel/Google OpenVINO CPU Optimization**: Compiles PyTorch models to run on standard consumer CPUs, delivering up to **30 FPS** at sub-15ms latency with zero GPU requirements.
- **Interactive Analytics Board**: Custom QPainter vector graphing widget with a floating tooltip, concentric highlight circle, and vertical guide lines that follow mouse movements.
- **Historical Safety Limit Mapping**: Logs active settings thresholds upon session creation, ensuring that past sessions are rendered using their historical safety limits even if settings change later.
- **Tamper-Evident Cryptographic Audit Trail**: Chains audit log rows sequentially using **SHA-256 hash dependencies** (mini-blockchain). The Admin tab automatically audits the chain on load, displaying alert banners if manual database modification is detected.
- **Real-Time Settings Sliders**: Features smooth horizontal sliders for confidence and safety limit thresholds. Drag to update parameters in real time, or double-click slider labels to input custom numbers (which automatically extends the slider range).
- **Data Retention & Local Backups**: Supports automatic database pruning (retaining logs for 30/60/90 days or indefinitely) alongside side-by-side **Export Backup** and **Import Backup** buttons defaulting to the local `data/` directory.

---

## 🛠️ Technology Stack

| Layer | Component |
| :--- | :--- |
| **Frontend GUI** | PyQt6 (Python bindings for Qt6) |
| **Styling** | Custom Dark-Theme stylesheet overrides (`src/ui/styles.py`) |
| **Database** | SQLite3 (configured with Write-Ahead Logging for concurrent reading/writing) |
| **AI Base Model** | Ultralytics YOLOv11 (YOLO11n person-class classification) |
| **Inference Runtime** | Intel OpenVINO runtime (pruned and compiled for local CPU execution) |
| **Video Processing** | OpenCV-Python (frame preprocessing, scaling, and HUD drawings) |
| **Compiler / Packager** | PyInstaller (bundled standalone directory compilation) |

---

## 📂 Project Structure

```text
CrowdSense/
├── assets/                  # Graphical icons and checkmark textures
├── data/                    # Persistent local SQLite database storage (ignored by git)
├── models/                  # Local YOLO weights and OpenVINO IR files (ignored by git)
├── src/                     # Python source files
│   ├── auth/                # Database interfaces, settings, and cryptographic hashes
│   ├── detection/           # OpenCV video capture and YOLO worker threads
│   ├── ui/                  # Main GUI window, settings, and custom line charts
│   └── main.py              # Application entry point
├── CrowdSense.spec          # PyInstaller build specification
├── requirements.txt         # Python library dependencies
└── README.md                # Project README documentation
```

---

## 🚀 Getting Started

### Option A: Running from Standalone Executable (.exe)
No Python installation is required.
1. Download and extract the **`CrowdSense.zip`** archive from the GitHub Releases tab.
2. Ensure the `models/` directory (containing `yolo11n_openvino_model/`) is located in the same directory as the executable.
3. Double-click **`CrowdSense.exe`** inside `dist/CrowdSense/` to launch.

### Option B: Running from Source (Development)
1. **Clone the repository**:
   ```bash
   git clone https://github.com/masquerad3/CrowdSense.git
   cd CrowdSense
   ```
2. **Set up a Virtual Environment**:
   - Create a virtual env using Python 3.11:
     ```bash
     python -m venv .venv
     .venv\Scripts\activate
     ```
3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Acquire Model Weights**:
   - Create a `models/` folder in the project root.
   - For OpenVINO compilation, place the exported OpenVINO directory inside `models/` as `models/yolo11n_openvino_model`.
5. **Run the Application**:
   ```bash
   python src/main.py
   ```

---

## 🔒 Security & Data Integrity

- **SQL Injection Prevention**: Enforced via fully parameterized queries for all user inputs.
- **Tamper Evidence**: Uses a SHA-256 hash-chain mapping for the `audit_log` table:
  $$\text{Entry Hash}_n = \text{SHA256}(\text{Entry Hash}_{n-1} + \text{Username} + \text{Action} + \text{Details} + \text{Timestamp})$$
  Any direct modification, row deletion, or order swap in the database file will immediately trigger an integrity alarm in the application.

---

## 📦 Compiling and Packaging
To rebuild the standalone executable with your custom configurations and branding icon:
```bash
.venv\Scripts\python.exe -m PyInstaller -y --noconsole --name=CrowdSense --add-data "assets;assets" --icon="assets/logo.ico" src/main.py
```
After building, ensure you copy the `models/` weights directory into `dist/CrowdSense/` next to the compiled executable.