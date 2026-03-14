"""
MindMesh v2 — FastAPI Backend Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .database import connect_db, close_db
from .routes import auth, exam, proctoring, admin

# ── WebSocket relay state (inline to avoid include_router WS issues) ──────────
# Active connections: student_id -> {"phone": ws, "viewer": ws}
_ws_connections: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="MindMesh v2 API",
    description="AI Assessment & Proctoring Platform — Simplified Backend",
    version="2.0.0",
    lifespan=lifespan,
)

# NOTE: No CORSMiddleware — all browser requests go through the Vite proxy.
# CORSMiddleware caused HTTP 403 on WebSocket upgrade requests.

# ── HTTP Routers ───────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(exam.router)
app.include_router(proctoring.router)
app.include_router(admin.router)


# ── WebSocket Relay: Phone → PC viewer ────────────────────────────────────────

@app.websocket("/ws/phone/{student_id}")
async def phone_camera_ws(websocket: WebSocket, student_id: str):
    """Phone connects here and pushes JPEG frames. Backend relays to PC viewer."""
    await websocket.accept()
    if student_id not in _ws_connections:
        _ws_connections[student_id] = {}
    _ws_connections[student_id]["phone"] = websocket
    try:
        while True:
            frame = await websocket.receive_text()
            viewer = _ws_connections.get(student_id, {}).get("viewer")
            if viewer:
                try:
                    await viewer.send_text(frame)
                except Exception:
                    _ws_connections.get(student_id, {}).pop("viewer", None)
    except WebSocketDisconnect:
        _ws_connections.get(student_id, {}).pop("phone", None)


@app.websocket("/ws/viewer/{student_id}")
async def viewer_ws(websocket: WebSocket, student_id: str):
    """PC exam page connects here to receive relayed phone frames."""
    await websocket.accept()
    if student_id not in _ws_connections:
        _ws_connections[student_id] = {}
    _ws_connections[student_id]["viewer"] = websocket
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        _ws_connections.get(student_id, {}).pop("viewer", None)


@app.get("/ws/status/{student_id}")
async def ws_status(student_id: str):
    """Check if phone WS is connected."""
    connected = student_id in _ws_connections and "phone" in _ws_connections[student_id]
    return {"connected": connected}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "MindMesh v2", "version": "2.0.0"}
