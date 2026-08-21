# Shopee Automization (Device Farm Manager)

An enterprise-grade automation platform designed for managing and orchestrating Shopee Live host tools across multiple Android devices simultaneously. The application utilizes a centralized FastAPI backend and a modern Single-Page Application (SPA) dashboard to interface with connected devices via the Android Debug Bridge (ADB).

## System Architecture

The system operates on a client-server model:

1.  **Devices**: Multiple Android devices connected via USB or TCP/IP.
2.  **Protocol**: Android Debug Bridge (ADB) for direct low-level device control and screen coordinate tapping.
3.  **Backend**: High-performance FastAPI application handling task scheduling, device routing, concurrent device locks, and WebSocket log streaming.
4.  **Frontend**: A modern dark-mode Single-Page Application (SPA) providing real-time device monitoring, coordinate calibration, and task configuration.

## Core Features

*   **Multi-Device Orchestration**: Manage, monitor, and configure tasks for multiple connected Android devices concurrently.
*   **Real-time Monitoring Dashboard**: View active tasks, queue lengths, and operation statuses across all devices via an optimized polling matrix (no heavy screen streaming).
*   **Task Scheduling Engine**: Assign background tasks (e.g., Claim Bonus, Ads, Check In) with precise interval execution and collision-safe queuing.
*   **Vision-based Calibration**: A dedicated GUI for plotting dynamic percentage-based coordinates against static reference UI images, ensuring cross-device compatibility regardless of screen resolution.
*   **Dry-run Validation**: Safe-by-default execution mode that simulates interactions and logs planned screen coordinates without transmitting touch events to the device.
*   **Auto-Provisioned Dependencies**: Automatically provisions and downloads essential binaries (e.g., ADB) to the local project environment if not found globally, ensuring portability.

## Installation & Setup

### Prerequisites
*   Python 3.11 or newer
*   Android devices with **USB Debugging** enabled
*   (Optional) ADB installed globally. If not available, the system will automatically download and isolate a local version for the project.

### Environment Preparation

```powershell
cd C:\Users\oktan\Work\Project\Shopee-Automization
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Running the Application

Ensure the virtual environment is active, then launch the FastAPI server:

```powershell
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Access the management dashboard by navigating to `http://127.0.0.1:8000/` in a web browser.

## Operational Workflow

### 1. Device Registration & Monitoring
Upon connecting Android devices to the host machine, navigate to the **Monitoring Dashboard**. The system automatically detects and registers all ADB-authorized devices. Click on any specific device card to open its dedicated task configuration scope.

### 2. Coordinate Calibration
Before executing tasks, coordinate points must be mapped to match your specific screen layout.
1.  Navigate to the **Coordinate Calibration** menu.
2.  Select a reference UI (e.g., "Home Live bar", "Form Lelang").
3.  Plot the required points on the reference frame. Coordinates are calculated dynamically as percentages.
4.  Save the calibration points to generate the specific layout profile.

### 3. Task Execution
1.  Navigate to the **Configure Task** menu.
2.  Ensure **Dry-run ON** is checked for initial testing.
3.  Configure desired tasks (e.g., repeating interval for "Lelang").
4.  Select **Start Bot** to inject the schedule into the worker queue.
5.  Monitor the execution via the built-in WebSocket live logs.
6.  Once verified, disable **Dry-run** to execute physical tap events on the Android device.

## Application Interface (API) Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/devices` | Retrieves a list of all active ADB devices. |
| `GET` | `/api/bots` | Retrieves a comprehensive snapshot of all bot runners and queues. |
| `POST` | `/api/bot/control` | Dispatches control signals (`start`, `pause`, `stop`) to a specific device runner. |
| `POST` | `/api/tasks` | Injects a scheduled task into a device's execution queue. |
| `POST` | `/api/tasks/run-once` | Forces immediate execution of a specific task payload. |
| `POST` | `/api/profiles/{name}/points` | Persists plotted coordinate data for the specified reference. |
| `WS` | `/ws/logs` | Upgrades connection to stream live execution logs. |

## Project Structure

```text
Shopee-Automization/
├── backend/
│   ├── app/                 # FastAPI core, ADB wrappers, Scheduler, Task flows
│   └── static/              # Dashboard frontend, modern SPA layout
├── config/                  # Global application settings and calibration profiles
├── assets/
│   └── image/               # Reference UI assets for the calibration tool
├── requirements.txt         # Project dependencies
└── README.md                # Project documentation
```
