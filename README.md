# MindMesh v2

MindMesh v2 is an AI-Powered Assessment & Proctoring Platform. It uses a **FastAPI** backend, a **Vite + React** frontend, and **MongoDB** for its database. 

This guide will walk you through setting up and running the project completely locally on Windows.

---

## 🛠️ Prerequisites

Before you start, make sure you have the following installed on your system:
1. **Python 3.12+**
2. **Node.js LTS** (v24+)
3. **MongoDB** (v8.2+)

---

## 🚀 1. Setup

### A. Setup MongoDB Database
MongoDB must be running on `localhost:27017` before starting the backend.
Instead of running it as a background system service, you can run it locally within the project folder for development:

```powershell
# Create a local database directory
New-Item -ItemType Directory -Force -Path data\db

# Run MongoDB in the background pointing to this local directory
Start-Process mongod -ArgumentList "--dbpath `"$PWD\data\db`" --port 27017 --logpath `"$PWD\data\mongod.log`"" -WindowStyle Hidden
```
*(Note: The `data/` folder is already added to `.gitignore`, so your database files will not be accidentally committed to your repository).*

### B. Setup Backend (FastAPI)
The backend requires a Python Virtual Environment.

```powershell
cd backend

# Create the virtual environment
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\activate

# Install all backend dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### C. Setup Frontend (Vite + React)
The frontend requires Node modules.

```powershell
cd frontend

# Install Node modules (if you face peer dependency issues, run with --legacy-peer-deps)
npm install --legacy-peer-deps
```

---

## 🏃 2. Running the Project

You will need **two separate terminals** to run the backend and frontend simultaneously.

### Terminal 1: Backend
```powershell
cd backend
.\venv\Scripts\activate

# Start the FastAPI server (Hot-reload enabled)
uvicorn app.main:app --reload --port 8000
```
*The backend API will be available at: http://localhost:8000*
*The API Documentation (Swagger) is at: http://localhost:8000/docs*

### Terminal 2: Frontend
```powershell
cd frontend

# Start the Vite development server
npm run dev
```
*The frontend will be available at: https://localhost:5173*

**(Important: The frontend uses `https` with a self-signed certificate so that the browser allows local camera access. You may see a "Not Secure" or "Your connection isn't private" warning in your browser. This is normal for local development. Click "Advanced" -> "Proceed to localhost".)**

---

## 🛑 3. Stopping the Project

When you are done developing, you can simply press `Ctrl + C` in both of your terminals to stop the frontend and backend servers.

If you also wish to shut down the background MongoDB process, locate its process and stop it, or use `Stop-Process`:
```powershell
Stop-Process -Name mongod -Force
```
