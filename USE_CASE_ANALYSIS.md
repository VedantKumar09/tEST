# MindMesh v2 - Use Case Analysis

## Executive Summary

This document provides a comprehensive analysis of how the MindMesh v2 project implements various use cases for an online examination and proctoring platform. The analysis maps the implemented features against typical use cases found in e-learning and proctoring systems.

---

## System Overview

**MindMesh v2** is an AI-powered online assessment platform that combines:
- Real-time browser-based proctoring using MediaPipe and YOLOv8
- Multi-language code execution and evaluation
- AI-generated examination questions
- Intelligent exam supervision and integrity assessment

---

## Actors in the System

### 1. Student
- **Description**: The primary user who takes examinations
- **Authentication**: Email/password (JWT-based)
- **Demo Account**: `student@mindmesh.ai / student123`

### 2. Administrator (Admin)
- **Description**: System manager who oversees exam creation and reviews submissions
- **Authentication**: Email/password (JWT-based)
- **Demo Account**: `admin@mindmesh.ai / admin123`

### 3. AI Supervisor
- **Description**: Automated agent that analyzes exam integrity
- **Type**: System actor (Groq/Gemini/OpenAI models)

### 4. Secondary Camera (Phone)
- **Description**: Additional monitoring device for environment surveillance
- **Type**: External device actor

---

## Primary Use Cases

### ACTOR: Student

#### UC-1: Register/Login to System
**Status**: ✅ Implemented

**Implementation Details**:
- **File**: `/backend/app/routes/auth.py`
- **Endpoint**: `POST /api/auth/login`
- **Method**: JWT token-based authentication
- **Flow**:
  1. Student enters email and password
  2. System validates credentials against user store
  3. JWT token generated (480-minute expiry)
  4. Token stored in localStorage
  5. Student redirected to exam page

**Code Reference**:
- Backend: `backend/app/routes/auth.py:23-51`
- Frontend: `frontend/src/pages/LoginPage.jsx:38-67`

---

#### UC-2: Setup Examination Environment
**Status**: ✅ Implemented

**Sub-Use Cases**:

##### UC-2.1: Enable Primary Camera
- Camera permissions requested via browser API
- Face detection initialized using MediaPipe
- Identity photo captured and stored
- **File**: `frontend/src/pages/ExamPage.jsx:130-180`

##### UC-2.2: Setup Secondary Camera (Phone)
- QR code generated with student ID and WebSocket URL
- Phone scans QR code and navigates to camera page
- Phone streams video frames via WebSocket (`/ws/phone/{student_id}`)
- Exam page receives frames via viewer WebSocket (`/ws/viewer/{student_id}`)
- **Files**:
  - Frontend: `frontend/src/pages/ExamPage.jsx:280-320`
  - Phone Page: `frontend/src/pages/QRCameraPage.jsx`
  - Backend WebSocket: `backend/app/main.py:120-180`

##### UC-2.3: Enter Fullscreen Mode
- Mandatory fullscreen mode on exam start
- Exit detection triggers violation event
- **File**: `frontend/src/pages/ExamPage.jsx:350-370`

---

#### UC-3: Take Examination
**Status**: ✅ Implemented

**Implementation Details**:
- **Endpoint**: `GET /api/exam/questions`
- **Duration**: 10 minutes (600 seconds)
- **Question Mix**: 15 MCQ + 5 Coding questions
- **Question Source**: Active AI-generated set (fallback to static questions)

**Flow**:
1. Student starts exam (timer begins)
2. Questions loaded from active question set
3. Student answers MCQ questions
4. Student solves coding challenges
5. Student submits exam (or auto-submit on timeout)

**Features**:
- Question navigation
- Answer selection/modification
- Code writing with Monaco editor
- Real-time timer
- Answer persistence before submission

**Code Reference**:
- Backend: `backend/app/routes/exam.py:40-95`
- Frontend: `frontend/src/pages/ExamPage.jsx:400-850`

---

#### UC-4: Solve Coding Problems
**Status**: ✅ Implemented

**Sub-Use Cases**:

##### UC-4.1: View Coding Problem
- Problem statement displayed in challenge format:
  - Problem description
  - Input format
  - Constraints
  - Output format
  - Sample input/output
- **File**: `frontend/src/components/compiler/QuestionDisplay.jsx`

##### UC-4.2: Write Code Solution
- Monaco editor with syntax highlighting
- Language selection: Python, C, Java, SQL
- Starter code provided
- **File**: `frontend/src/components/compiler/CodeEditor.jsx`

##### UC-4.3: Test Code Execution
- **Endpoint**: `POST /api/code/execute`
- Run code with custom input
- View output, errors, execution time
- No grading (testing only)
- **File**: `backend/app/routes/code.py:40-80`

##### UC-4.4: Submit Code for Grading
- **Endpoint**: `POST /api/code/submit`
- Code runs against hidden test cases
- Results show pass/fail per test case
- Score calculated as percentage of passed tests
- **File**: `backend/app/routes/code.py:85-145`

**Supported Languages**:
- Python (interpreter)
- C (gcc compilation)
- Java (javac/java)
- SQL (SQLite with pre-seeded database)

**Code Reference**: `backend/app/services/code_executor.py`

---

#### UC-5: View Examination Results
**Status**: ✅ Implemented

**Implementation Details**:
- **Endpoint**: Results displayed from submission data
- **Score Page**: `frontend/src/pages/ScorePage.jsx`

**Information Displayed**:
- Overall score percentage
- MCQ score
- Coding score (weighted)
- Questions answered/total
- Category-wise performance
- Time used
- Risk level assessment
- Violation summary

**Score Calculation**:
- 50% weight: MCQ questions
- 50% weight: Coding questions
- Coding score = average of all coding test case scores

**Code Reference**: `frontend/src/pages/ScorePage.jsx:45-180`

---

#### UC-6: Be Monitored During Examination
**Status**: ✅ Implemented

**Proctoring Features**:

##### Real-Time Face Detection (Every frame)
- Face presence/absence detection
- Head pose tracking (yaw, pitch)
- Eye gaze direction
- Multiple face detection
- **Service**: `backend/app/ai/face_analyzer.py`

##### Object Detection (Every 2 seconds)
- YOLOv8 nano model
- Detects: phone, book, laptop, remote
- Confidence threshold: 40%
- **Service**: `backend/app/ai/object_detector.py`

##### Browser Event Monitoring
- Tab switches
- Fullscreen exit
- Copy/paste attempts
- Right-click blocking
- **Implementation**: `frontend/src/pages/ExamPage.jsx:600-750`

##### Violation Thresholds
- No face: 3.0 seconds persistence
- Looking away: 2.0 seconds persistence
- Gaze offscreen: 2.0 seconds persistence
- **Config**: `backend/app/ai/proctor_config.py`

##### Evidence Collection
- Screenshots captured on violations
- Stored in `proctor_logs/{student_id}/`
- Timestamp and violation type recorded
- **Service**: `backend/app/ai/screenshot_manager.py`

**Code Reference**: `backend/app/services/proctor_service.py`

---

### ACTOR: Administrator

#### UC-7: Generate AI-Powered Exam Questions
**Status**: ✅ Implemented

**Implementation Details**:
- **Endpoint**: `POST /api/admin/questions/generate`
- **AI Provider**: OpenAI (GPT-4o-mini)
- **Fallback**: Local rule-based question bank

**Flow**:
1. Admin enters exam topic
2. System calls OpenAI API with structured prompt
3. 15 MCQ + 5 coding questions generated
4. Response validated and parsed
5. New question set stored in MongoDB
6. Previous active sets deactivated
7. New set marked as active

**Question Format**:

**MCQ Structure**:
```json
{
  "id": 1,
  "type": "mcq",
  "category": "Data Structures",
  "text": "Question text...",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct": 1
}
```

**Coding Structure**:
```json
{
  "id": 1001,
  "type": "coding",
  "title": "Array Left Rotation",
  "category": "Coding — Python",
  "language": "python",
  "difficulty": "Medium",
  "description": "Problem Statement\n...\nConstraints\n...",
  "starter_code": "# Write your solution here",
  "test_cases": [
    {"input": "5 2\n1 2 3 4 5", "expected_output": "3 4 5 1 2"}
  ]
}
```

**Fallback Mechanism**:
- Triggered on OpenAI quota exhaustion
- Uses pre-defined question templates
- Admin notified via response notice
- Exam generation never blocked

**Code Reference**: `backend/app/routes/admin.py:45-180`

---

#### UC-8: View Active Question Set
**Status**: ✅ Implemented

**Implementation Details**:
- **Endpoint**: `GET /api/admin/questions/active`
- **Response Includes**:
  - Provider (openai/local)
  - Model (gpt-4o-mini/rule-based-fallback)
  - Topic
  - MCQ count
  - Coding count
  - Created timestamp
  - Notice (if fallback used)

**Code Reference**: `backend/app/routes/admin.py:185-210`

---

#### UC-9: View All Exam Submissions
**Status**: ✅ Implemented

**Implementation Details**:
- **Endpoint**: `GET /api/admin/submissions`
- **Data Displayed**:
  - Student name and email
  - Overall score percentage
  - Questions answered/total
  - Time used (seconds)
  - Violation count
  - Risk level badge
  - Submission timestamp

**Filtering/Sorting**:
- Sort by score (descending)
- Filter by risk level
- Search by student name/email

**Code Reference**:
- Backend: `backend/app/routes/admin.py:215-245`
- Frontend: `frontend/src/pages/AdminPage.jsx:120-280`

---

#### UC-10: Review Detailed Submission Report
**Status**: ✅ Implemented

**Implementation Details**:
- Expandable row in submissions table
- **Information Displayed**:
  - Final score breakdown (MCQ + Coding)
  - Correct/total questions
  - Category-wise performance
  - Violation types and counts
  - AI supervisor report
  - Risk assessment
  - Time statistics

**AI Supervisor Report Includes**:
- Cheating probability (None/Low/Medium/High)
- Reasoning analysis
- Recommended action (Pass/Review/Invalidate)

**Code Reference**: `frontend/src/pages/AdminPage.jsx:285-420`

---

#### UC-11: View System Statistics
**Status**: ✅ Implemented

**Metrics Displayed**:
- Total submissions count
- Average score across all exams
- High-risk students count
- Average violations per exam

**Code Reference**: `frontend/src/pages/AdminPage.jsx:85-115`

---

### ACTOR: AI Supervisor

#### UC-12: Analyze Exam Integrity
**Status**: ✅ Implemented

**Trigger Conditions**:
- Exam submission (always)
- High violation count (≥3 violations)

**Implementation Details**:
- **Service**: `backend/app/ai/agent.py`
- **AI Provider**: Groq (llama-3.1-8b-instant)
- **Fallback**: Gemini 2.0 Flash

**Analysis Input**:
- Exam duration
- Total violations
- Violation breakdown (by type)
- Coding performance
- MCQ performance

**Analysis Output**:
```json
{
  "probability_cheating": "High | Medium | Low | None",
  "reasoning": "Short analysis text",
  "recommended_action": "Pass | Review Timeline | Invalidate Exam"
}
```

**Rate Limiting**:
- 20-second cooldown between API calls
- Prevents API quota exhaustion

**Error Handling**:
- If all providers fail: Manual review required
- Error state clearly communicated to admin

**Code Reference**: `backend/app/ai/agent.py:60-180`

---

#### UC-13: Calculate Risk Score
**Status**: ✅ Implemented

**Implementation Details**:
- **Service**: `backend/app/ai/scoring.py`

**Violation Weights**:
```
No Face: 2 points
Looking Away: 1 point
Gaze Offscreen: 1 point
Multiple Faces: 5 points
Object Detected: 10 points
Tab Switch: 3 points
Fullscreen Exit: 2 points
Copy/Paste: 3 points
Right Click: 1 point
```

**Risk Level Classification**:
- **Safe**: Score ≤ 5
- **Suspicious**: Score 6-10
- **High Risk**: Score 11-20
- **Cheating**: Score > 20

**Cumulative Scoring**:
- Score accumulates throughout exam
- Risk level updated in real-time
- Final score stored in submission

**Code Reference**: `backend/app/ai/scoring.py:15-85`

---

### ACTOR: System

#### UC-14: Manage Question Sets
**Status**: ✅ Implemented

**Operations**:

##### Store Generated Questions
- MongoDB collection: `exam_question_sets`
- Schema: MCQ array + Coding array
- Metadata: provider, model, topic, timestamp

##### Activate Question Set
- Mark new set as active
- Deactivate all previous sets
- Only one active set at a time

##### Retrieve Active Questions
- Exams fetch from active set
- Fallback to static questions if no active set

**Code Reference**: `backend/app/routes/admin.py:45-210`

---

#### UC-15: Store Exam Submissions
**Status**: ✅ Implemented

**Storage Details**:
- MongoDB collection: `submissions`
- **Data Stored**:
  - Student information
  - Scores (overall, MCQ, coding)
  - Answers to all questions
  - Coding test results
  - Category performance
  - Proctoring summary
  - Violation events
  - AI supervisor report
  - Timestamps

**Submission Schema**:
```json
{
  "submission_id": "unique_id",
  "student_name": "Demo Student",
  "student_email": "student@mindmesh.ai",
  "score": 75,
  "mcq_score": 80,
  "coding_score": 70,
  "correct": 12,
  "questions_total": 15,
  "questions_answered": 15,
  "time_used": 245,
  "category_scores": {...},
  "proctoring_summary": {...},
  "ai_supervisor": {...},
  "submitted_at": 1234567890
}
```

**Code Reference**: `backend/app/routes/exam.py:100-250`

---

#### UC-16: Store Violation Events
**Status**: ✅ Implemented

**Storage Details**:
- MongoDB collection: `violation_events`
- **Event Data**:
  - Student ID
  - Violation types (array)
  - Frame score
  - Cumulative score
  - Risk level
  - Screenshot path
  - Timestamp

**Event Schema**:
```json
{
  "student_id": "student@mindmesh.ai",
  "violations": ["no_face", "multiple_faces"],
  "frame_score": 7,
  "cumulative_score": 7,
  "risk_level": "Safe",
  "screenshot_path": "proctor_logs/student_001/no_face_1234567890.jpg",
  "timestamp": 1234567890
}
```

**Code Reference**: `backend/app/routes/proctoring.py:75-125`

---

#### UC-17: Execute Code in Sandbox
**Status**: ✅ Implemented

**Security Features**:
- Isolated subprocess execution
- Temporary file creation (deleted after execution)
- 10-second timeout per execution
- Output truncation (50,000 chars max)
- No network access
- No file system access (except temp)

**Execution Flow**:
1. Create temp directory
2. Write code to temp file
3. Execute with subprocess
4. Capture stdout/stderr
5. Calculate execution time
6. Cleanup temp files
7. Return results

**Language-Specific Execution**:

**Python**:
```bash
python3 <temp_file.py>
```

**C**:
```bash
gcc <temp_file.c> -o <temp_executable>
./<temp_executable>
```

**Java**:
```bash
javac <ClassName.java>
java <ClassName>
```

**SQL**:
```python
# In-memory SQLite database
conn = sqlite3.connect(':memory:')
# Pre-seeded with tables and data
cursor.execute(user_query)
```

**Code Reference**: `backend/app/services/code_executor.py`

---

#### UC-18: Relay Secondary Camera Stream
**Status**: ✅ Implemented

**WebSocket Architecture**:

**Phone Endpoint**: `/ws/phone/{student_id}`
- Receives JPEG frames from phone
- Stores latest frame in memory
- Relays to connected viewers

**Viewer Endpoint**: `/ws/viewer/{student_id}`
- Receives frames from phone connection
- Streams to exam page in real-time
- Updates every frame received

**Status Endpoint**: `/ws/status/{student_id}`
- Returns phone connection status
- Used to verify secondary camera setup

**Flow**:
```
Phone Camera → WebSocket (Phone) → Server → WebSocket (Viewer) → Exam Page
```

**Code Reference**: `backend/app/main.py:120-180`

---

## Use Case Coverage Analysis

### Comparison with Standard E-Learning Proctoring Systems

| Use Case | MindMesh v2 | Standard Systems |
|----------|-------------|------------------|
| User Authentication | ✅ JWT-based | ✅ Typically available |
| Student Registration | ⚠️ Demo users only | ✅ Full registration flow |
| Exam Creation | ✅ AI-generated | ⚠️ Manual creation typical |
| Question Banking | ✅ MongoDB storage | ✅ Typically available |
| Multiple Question Types | ✅ MCQ + Coding | ✅ MCQ + Essay typically |
| Live Proctoring | ✅ Advanced AI | ⚠️ Human proctors typical |
| Face Detection | ✅ MediaPipe | ✅ Typically available |
| Object Detection | ✅ YOLOv8 | ⚠️ Less common |
| Browser Monitoring | ✅ Comprehensive | ✅ Typically available |
| Secondary Camera | ✅ WebSocket relay | ⚠️ Rare feature |
| Code Execution | ✅ Multi-language | ⚠️ Rare in exams |
| AI Supervision | ✅ Agentic analysis | ❌ Not typical |
| Risk Scoring | ✅ Real-time | ⚠️ Basic typically |
| Admin Dashboard | ✅ Comprehensive | ✅ Typically available |
| Results Analytics | ✅ Detailed | ✅ Typically available |
| Screenshot Evidence | ✅ Automatic | ⚠️ Variable |
| Session Recording | ❌ Not implemented | ⚠️ Sometimes available |

### Legend:
- ✅ Fully implemented/available
- ⚠️ Partially implemented or less common
- ❌ Not implemented

---

## Advanced Features Beyond Standard Systems

### 1. AI-Powered Question Generation
- **Uniqueness**: Uses GPT-4o-mini to generate contextual exam questions
- **Benefit**: Reduces admin workload, creates diverse question banks
- **Implementation**: `backend/app/routes/admin.py`

### 2. Agentic Exam Supervision
- **Uniqueness**: AI agent analyzes violation patterns and provides reasoning
- **Benefit**: Intelligent decision support for manual review
- **Implementation**: `backend/app/ai/agent.py`

### 3. Multi-Language Code Execution
- **Uniqueness**: Supports Python, C, Java, SQL with hidden test cases
- **Benefit**: Comprehensive programming assessment
- **Implementation**: `backend/app/services/code_executor.py`

### 4. Real-Time Object Detection
- **Uniqueness**: YOLOv8-based detection of unauthorized items
- **Benefit**: Enhanced proctoring beyond face detection
- **Implementation**: `backend/app/ai/object_detector.py`

### 5. Dual-Camera Proctoring
- **Uniqueness**: Primary laptop camera + secondary phone camera via QR/WebSocket
- **Benefit**: 360-degree monitoring of exam environment
- **Implementation**: `backend/app/main.py` (WebSocket relay)

### 6. Temporal Violation Buffering
- **Uniqueness**: Violations require sustained duration to trigger (reduces false positives)
- **Benefit**: More accurate violation detection
- **Implementation**: `backend/app/services/proctor_service.py`

---

## Architecture Patterns

### 1. Microservices-Style Separation
- Authentication service
- Exam service
- Code execution service
- Proctoring service
- Admin service

### 2. AI Service Abstraction
- Provider-agnostic AI interface
- Fallback chains (OpenAI → Groq → Gemini)
- Quota handling and error recovery

### 3. WebSocket Real-Time Communication
- Phone-to-viewer camera relay
- Scalable to multiple concurrent exams

### 4. Sandbox Execution
- Isolated code execution environment
- Language-specific compilers/interpreters
- Timeout and resource limits

---

## Security Considerations

### Implemented Security Features:

1. **Authentication**:
   - JWT tokens with expiration
   - Token validation on protected routes

2. **Code Execution**:
   - Subprocess isolation
   - Timeout limits (10 seconds)
   - No network/file system access
   - Output truncation

3. **Proctoring**:
   - Screenshot evidence collection
   - Violation event logging
   - Risk scoring system

4. **Browser Security**:
   - Fullscreen enforcement
   - Tab switch detection
   - Copy/paste prevention
   - Right-click blocking

### Security Gaps:

1. **Demo User Accounts**:
   - Hardcoded credentials (demo only)
   - No password hashing visible
   - No account lockout

2. **Database Security**:
   - No visible input sanitization
   - Direct MongoDB queries
   - No rate limiting on endpoints

3. **WebSocket Security**:
   - No authentication on WebSocket connections
   - Student ID in URL (could be guessed)

4. **Code Execution**:
   - No resource usage limits (CPU, memory)
   - Potential for infinite loops
   - No network isolation verification

---

## Data Flow Diagrams

### Exam Taking Flow:
```
Student → Login → Camera Setup → QR Setup → Start Exam
  ↓
Load Questions (MongoDB) → Display Questions
  ↓
Student Answers → Real-time Proctoring (Every frame)
  ↓
  ├─ Face Analysis (MediaPipe)
  ├─ Object Detection (YOLOv8)
  ├─ Browser Events
  └─ Violation Scoring
  ↓
Student Submits → Score Calculation
  ↓
AI Supervisor Analysis → Store Submission (MongoDB)
  ↓
Display Results
```

### Code Execution Flow:
```
Student Writes Code → Click "Run" or "Submit"
  ↓
POST to Backend → Code Executor Service
  ↓
Create Temp File → Compile (if needed) → Execute → Capture Output
  ↓
Run Test Cases (if submit) → Calculate Score
  ↓
Return Results → Display in Frontend
```

### Admin Question Generation Flow:
```
Admin Enters Topic → Click Generate
  ↓
POST to Backend → Call OpenAI API
  ↓
Success? → Parse JSON → Store in MongoDB
  ↓ (if quota error)
Fallback to Local Bank → Store in MongoDB
  ↓
Deactivate Old Sets → Activate New Set → Return to Admin
```

---

## Technology Stack Alignment

### Backend Technologies:
- **FastAPI**: Modern async Python framework
- **Motor**: Async MongoDB driver
- **Pydantic**: Data validation
- **MediaPipe**: Face landmark detection
- **Ultralytics**: YOLOv8 object detection
- **OpenAI/Groq/Gemini**: AI providers

### Frontend Technologies:
- **React 18**: UI framework
- **Vite**: Build tool
- **Monaco Editor**: Code editor (VS Code engine)
- **qrcode.react**: QR code generation
- **React Router**: Client-side routing

### Database:
- **MongoDB**: NoSQL document database
- Collections: exam_question_sets, submissions, violation_events

### DevOps:
- **Uvicorn**: ASGI server for FastAPI
- **npm/Node.js**: Frontend build system
- **PowerShell scripts**: Windows automation

---

## Extension Points for Future Features

### Potential Use Cases Not Yet Implemented:

1. **UC-19: Student Profile Management**
   - Edit profile information
   - View exam history
   - Track progress over time

2. **UC-20: Instructor Role**
   - Create custom question banks
   - Configure exam parameters (duration, difficulty)
   - Grade essay/subjective questions

3. **UC-21: Real-Time Proctoring Dashboard**
   - Live monitoring of active exams
   - Real-time violation alerts
   - Proctor intervention capability

4. **UC-22: Plagiarism Detection**
   - Compare coding solutions
   - Detect similarity patterns
   - Flag suspicious submissions

5. **UC-23: Session Recording**
   - Full video/audio capture
   - Playback for manual review
   - Evidence preservation

6. **UC-24: Advanced Analytics**
   - Question difficulty analysis
   - Student performance trends
   - Anomaly detection

7. **UC-25: Multi-Tenant Support**
   - Organization/institution management
   - Role-based access control
   - Custom branding

8. **UC-26: Exam Scheduling**
   - Calendar integration
   - Automated notifications
   - Timezone handling

9. **UC-27: Export/Reporting**
   - PDF report generation
   - CSV data export
   - Integration with LMS systems

10. **UC-28: Mobile Application**
    - Native Android/iOS proctor app
    - Better camera control
    - Enhanced reliability

---

## Conclusion

MindMesh v2 successfully implements **18 core use cases** across multiple actors (Student, Admin, AI Supervisor, System). The platform goes beyond traditional e-learning systems by incorporating:

- **Advanced AI features**: Question generation, agentic supervision
- **Multi-modal proctoring**: Dual cameras, object detection, behavior analysis
- **Technical assessment**: Multi-language code execution with automated grading
- **Intelligent analytics**: Risk scoring, violation pattern analysis

The architecture is modular, extensible, and well-suited for both educational institutions and technical assessment platforms. The use of modern technologies (FastAPI, React, MongoDB, AI/ML models) ensures scalability and maintainability.

### Key Strengths:
1. Comprehensive proctoring with minimal false positives
2. AI-powered automation reduces admin workload
3. Support for technical assessments (coding)
4. Real-time analysis and decision support
5. Modular architecture for easy extension

### Areas for Enhancement:
1. Full user registration and management system
2. Role-based access control (Instructor, Proctor roles)
3. Enhanced security (rate limiting, input sanitization)
4. Session recording for forensic analysis
5. Multi-tenant support for institutions

---

## File References

For detailed implementation information, refer to:

### Backend Core:
- **Authentication**: `backend/app/routes/auth.py`
- **Exam Management**: `backend/app/routes/exam.py`
- **Code Execution**: `backend/app/routes/code.py` + `backend/app/services/code_executor.py`
- **Proctoring**: `backend/app/routes/proctoring.py` + `backend/app/services/proctor_service.py`
- **Admin**: `backend/app/routes/admin.py`

### AI/ML Components:
- **AI Supervisor**: `backend/app/ai/agent.py`
- **Face Detection**: `backend/app/ai/face_analyzer.py`
- **Object Detection**: `backend/app/ai/object_detector.py`
- **Risk Scoring**: `backend/app/ai/scoring.py`
- **Screenshot Manager**: `backend/app/ai/screenshot_manager.py`

### Frontend Pages:
- **Login**: `frontend/src/pages/LoginPage.jsx`
- **Exam Interface**: `frontend/src/pages/ExamPage.jsx`
- **Phone Camera**: `frontend/src/pages/QRCameraPage.jsx`
- **Score Display**: `frontend/src/pages/ScorePage.jsx`
- **Admin Dashboard**: `frontend/src/pages/AdminPage.jsx`

### Configuration:
- **Backend Settings**: `backend/app/config.py`
- **Proctoring Config**: `backend/app/ai/proctor_config.py`
- **Database**: `backend/app/database.py`

---

**Document Version**: 1.0
**Last Updated**: March 26, 2026
**Project**: MindMesh v2
**Repository**: VedantKumar09/tEST
