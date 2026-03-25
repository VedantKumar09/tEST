# MindMesh v2: Project Overview & Presentation Guide

This document summarizes the current architecture, technologies, and features of MindMesh v2 for today's presentation.

## 1. Core Architecture
MindMesh v2 uses a modern, high-performance stack:
*   **Frontend:** React + Vite (Fast, responsive, and handles client-side perception).
*   **Backend:** FastAPI (Python) (Asynchronous, high-concurrency API layer).
*   **Database:** MongoDB (NoSQL) (Flexible storage for telemetry, logs, and screenshots).

## 2. Key Features (Currently Working)

### A. Real-Time Agentic Proctoring
*   **Edge Perception:** Uses **MediaPipe Vision (WebAssembly)** in the browser to detect face tracking, head-pose, and eye-gaze instantly without sending raw video to the server.
*   **Temporal Stabilization:** Built-in 2–3 second buffers eliminate false positives from transient movements.
*   **Agentic AI Supervisor (Google Gemini 1.5 Pro):** 
    *   Acts as an intelligent, human-like proctor.
    *   Reviews telemetry logs and provides an explainable risk assessment report.
    *   Uses a **4-Agent Architecture**: Perception → Reasoning → Decision → Report.

### B. Integrated Code Execution Engine
A native, sandboxed environment for technical assessments:
*   **Monaco Editor:** Rich editing experience (VS Code engine) with syntax highlighting.
*   **Multi-Language Support:** 
    *   **Python:** Direct execution.
    *   **C & Java:** Automated compilation (`gcc`/`javac`) and execution.
    *   **SQL:** Executes against a pre-seeded **in-memory SQLite database** (Employees, Departments, Projects).
*   **Isolation:** Code runs in temporary, isolated directories with strict timeouts and resource limits.

---

## 3. How It Works (Project Workflow)

1.  **Student Login & Environment Check:** The candidate logs in via the React-Vite frontend. The system performs a hardware check (webcam/microphone) before the exam starts.
2.  **Edge Perception (Client-Side Detection):** As the candidate takes the exam, **MediaPipe** runs locally in their browser. It monitors face detection, gaze direction, and distractions without sending heavy video data to the server, ensuring privacy and low latency.
3.  **Event Streaming:** If the client-side AI detects a potential violation (e.g., student looks away or switches tabs), it sends an event to the **FastAPI** backend for further analysis.
4.  **Agentic AI Evaluation:** The backend routes the data to our **Gemini-powered AI Agent**. This agent uses reasoning to evaluate the context of the telemetry (e.g., distinguishing between a natural head movement and looking at a split screen).
5.  **Secure Code Execution:** When the candidate runs code, it's sent to an isolated, sandboxed environment. The backend compiles and executes it in real-time, returning results and errors to the frontend's integrated editor.
6.  **Final Integrity Assessment:** Once the exam is submitted, the AI Agent synthesizes all recorded telemetry into a final report with a reasoning narrative and cheating probability, which is then stored in **MongoDB**.

---

### **Presentation Pitch Summary:**

---

## 4. Presentation Script (Talk Track)

*Use this script as a guide while presenting the project.*

**Introduction:**
"Good morning/afternoon everyone. Today I'm excited to present **MindMesh v2**, an AI-powered assessment platform designed to solve the biggest problem in remote proctoring: **False Positives**. Most systems are too rigid—they flag you for simply sneezing or adjusting your chair. MindMesh v2 changes that by using **Agentic AI**."

**The Tech Stack:**
"Under the hood, we are using a very modern, decoupled stack. Our frontend is built with **React and Vite** for speed. The backend is powered by **FastAPI** in Python, which gives us the concurrency we need for real-time analysis. All our telemetry and logs are stored in **MongoDB**."

**Proctoring (The 'How it Works' Part):**
"What makes this project special is our two-tier AI detection. First, we use **MediaPipe**—running locally in the user's browser via WebAssembly. This handles the 'Perception' layer—detecting faces and gaze in real-time without the lag of sending video to a server."

"Second, we don't just rely on raw numbers. Our backend features an **Agentic AI Supervisor** powered by **Google Gemini 1.5 Pro**. When the edge AI detects something suspicious, it streams that data to the Gemini agent. The agent then **reasons** about the behavior using a 4-step logic: Perception, Reasoning, Decision, and finally, generating a human-readable Report. This means the system can actually understand the difference between a student looking at a phone versus just looking at their keyboard to type."

**The Coding Environment:**
"For the actual assessment, we've integrated the **Monaco Editor**—the same engine that powers VS Code. Candidates can write code in **Python, C, Java, or SQL**. Their code is then executed in a secure, sandboxed environment on our server, with SQL queries running against a pre-seeded database of employees and projects to simulate real-world tasks."

**Conclusion:**
"In summary, MindMesh v2 is built for the future of assessments. It's fast, it's private, and most importantly, it's fair—using the latest in Agentic AI to ensure a smooth experience for both students and examiners. Thank you!"

