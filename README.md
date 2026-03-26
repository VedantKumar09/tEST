# MindMesh v2 - AI Assessment and Proctoring Platform

MindMesh v2 is an online assessment platform with live proctoring, coding evaluation, and AI-assisted admin workflows.

This project now supports dynamic exam generation (MCQ + coding), active question-set publishing, enhanced proctor event handling, and robust fallback behavior when model quotas are exhausted.

## What Is New

### 1) AI-Generated Question Sets (Admin)
- Admin can generate a complete exam set from the dashboard.
- Each generated set includes:
	- MCQ questions (default 15)
	- Coding questions (default 5)
- New sets are saved in MongoDB as the active set and immediately used for upcoming exams.
- Admin dashboard now shows active-set metadata:
	- Provider/model
	- Topic
	- MCQ count and coding count

### 2) Coding Questions Improved to Challenge Style
- Generated coding questions are now written in a challenge format similar to competitive coding platforms.
- Coding prompts now include structured sections such as:
	- Problem Statement
	- Input Format
	- Constraints
	- Output Format
	- Sample Input/Output
- Coding items include starter code and hidden test cases for scoring.

### 3) Active Set Consumption Across Exam and Code Routes
- Exam delivery now reads both MCQ and coding from the active generated set.
- Code question listing, detail fetch, and code submission all resolve against the active coding set.
- If no active generated set exists, the system safely falls back to built-in static questions.

### 4) AI Reliability and Fallback Behavior
- Admin generation is AI-first.
- If OpenAI key is out of quota, generation falls back to a local rule-based bank so exams are not blocked.
- API responses now include clearer error and notice messages (for example insufficient_quota details).

### 5) Proctoring and Exam UX Stability Improvements
- Improved tab-switch detection and fullscreen exit handling.
- Fullscreen entry on exam start, and lifecycle cleanup improvements.
- Better mapping/handling of proctoring payload fields for consistent scoring and reporting.
- MediaPipe initialization and fallback paths improved for better camera robustness.

## Core Features
- Real-time browser-side proctoring using MediaPipe (face landmarks, head pose, gaze signals)
- Browser event monitoring (tab switch, copy/paste, right click, fullscreen exit)
- Secondary camera support via QR flow (phone-to-viewer WebSocket relay)
- Agentic supervisor reasoning report at submission time
- Integrated coding executor for Python, C, Java, and SQL
- Admin dashboard for submissions, risk review, and question generation

## Tech Stack
- Backend: FastAPI, Motor (MongoDB), Pydantic settings
- Frontend: React + Vite + Monaco editor
- Database: MongoDB
- AI providers in project config: OpenAI, Groq, Gemini (provider usage depends on route logic)

## Prerequisites
- Python 3.11+
- Node.js LTS
- MongoDB running locally on localhost:27017

## Setup

### 1) Start MongoDB
```powershell
New-Item -ItemType Directory -Force -Path data\db
Start-Process mongod -ArgumentList "--dbpath `"$PWD\data\db`" --port 27017" -WindowStyle Hidden
```

### 2) Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks activation scripts, use a temporary policy in the current terminal:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

You can also skip activation and run tools directly via the venv interpreter:
```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create backend/.env:
```env
MONGODB_URL=mongodb://localhost:27017/mindmesh
DATABASE_NAME=mindmesh

# Provider config used by AI supervisor path
AI_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash

# Used by admin question-generation path
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

### 3) Frontend
```powershell
cd frontend
npm install --legacy-peer-deps
```

## Run

### Backend
```powershell
cd backend
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Activation-free backend run (recommended when script policy is restricted):
```powershell
cd backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

If port 8000 is already in use (WinError 10013), either stop the existing process or use another port:
```powershell
Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -eq 8000 }
Stop-Process -Id <PID> -Force
# or
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8001
```

### Frontend
```powershell
cd frontend
npm run dev
```

If PowerShell blocks npm scripts due execution policy, run Vite directly:
```powershell
cd frontend
node node_modules/vite/bin/vite.js
```

The frontend runs on HTTPS. Accept the local certificate in the browser so camera APIs can work.

## Important Endpoints

### Admin Generation
- POST /api/admin/questions/generate
- GET /api/admin/questions/active

### Exam
- GET /api/exam/questions
- POST /api/exam/submit

### Code
- GET /api/code/questions
- GET /api/code/questions/{question_id}
- POST /api/code/execute
- POST /api/code/submit

## Operational Notes
- Generation publishes a single active set at a time; previous active sets are deactivated.
- Generated coding questions use IDs in the generated range and are fully gradable through hidden test cases.
- If database is unavailable, write operations for generated sets cannot proceed.

## Stop Services

Press Ctrl+C in backend/frontend terminals.

Stop MongoDB if needed:
```powershell
Stop-Process -Name mongod -Force
```
