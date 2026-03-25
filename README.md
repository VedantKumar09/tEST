# 🧠 MindMesh v2 — AI-Powered Assessment & Proctoring Platform

MindMesh v2 is a modern, high-performance platform for online assessments. It features a **Hybrid Agentic AI Architecture** that combines local browser-based real-time tracking with backend Generative AI reasoning.

## ✨ Features
- **Real-Time Proctoring (30-60 FPS)**: Uses WebAssembly (MediaPipe) to track face landmarks, head-pose, and eye gaze directly in the browser with **zero network latency**.
- **Native Object Detection**: In-browser detection for unauthorized devices (phones, tablets, books) using Google's EfficientDet-Lite2.
- **Agentic AI Supervisor**: Uses **Google Gemini 1.5 Pro** to analyze behavioral telemetry logs and generate intelligent, human-like proctoring reports.
- **Integrated Code Executor**: Multi-language support (Python, C, Java, SQL) with a Monaco-based development environment.
- **Secure Exam Mode**: Built-in protection against copy-pasting, tab-switching, and unauthorized terminal/right-click access.

---

## 🛠️ Prerequisites
- **Python 3.12+**
- **Node.js LTS** (v24+)
- **MongoDB** (v8.2+) — Must be running on `localhost:27017`
- **Gemini API Key** — Required for the Agentic Supervisor logic

---

## 🚀 Installation & Setup

### 1. Database Setup
Ensure MongoDB is running locally. You can start it pointing to a local directory:
```powershell
New-Item -ItemType Directory -Force -Path data\db
Start-Process mongod -ArgumentList "--dbpath `"$PWD\data\db`" --port 27017" -WindowStyle Hidden
```

### 2. Backend Setup (FastAPI)
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```
**Important**: Create a `.env` file in the `backend/` folder and add your Gemini key:
```env
GEMINI_API_KEY=your_gemini_api_key_here
MONGODB_URL=mongodb://localhost:27017/mindmesh
```

### 3. Frontend Setup (React + Vite)
```powershell
cd frontend
npm install --legacy-peer-deps
```

---

## 🏃 Running the Application

### Terminal 1: Backend
```powershell
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

### Terminal 2: Frontend
```powershell
cd frontend
npm run dev
```
**Note**: The frontend uses HTTPS. Accept the self-signed certificate in your browser (Advanced -> Proceed to localhost) to allow camera access.

---

## 🛡️ Proctoring Architecture
- **Perception (Frontend)**: Real-time face tracking and object detection happens locally on the student's machine. Zero image data is sent over the network during the exam.
- **Reasoning (Backend)**: When the exam is submitted, the backend feeds the behavioral "events log" to the Gemini-based **Agentic Supervisor**. It contextually evaluates if the student's behavior (e.g., looking away) was suspicious or part of normal coding flow.
- **Reporting (Admin)**: Instructors view a synthesized AI report in the dashboard with a "Cheating Probability" and detailed reasoning.

---

## 🛑 Stopping
Press `Ctrl + C` in both terminals. To stop MongoDB:
```powershell
Stop-Process -Name mongod -Force
```
