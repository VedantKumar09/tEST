"""
MindMesh v2 — FastAPI Backend Entry Point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .database import connect_db, close_db
from .routes import auth, exam, proctoring, admin

# WebSocket relay state: student_id -> {"phone": ws, "viewer": ws}
_ws_connections: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="MindMesh v2 API",
    description="AI Assessment & Proctoring Platform",
    version="2.0.0",
    lifespan=lifespan,
)

# HTTP Routers
app.include_router(auth.router)
app.include_router(exam.router)
app.include_router(proctoring.router)
app.include_router(admin.router)


# ── WebSocket Relay: Phone → PC viewer (30 FPS) ───────────────────────────────

@app.websocket("/ws/phone/{student_id}")
async def phone_camera_ws(websocket: WebSocket, student_id: str):
    """Phone streams JPEG frames here; backend relays to PC viewer."""
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
    """PC exam page receives relayed phone frames here."""
    await websocket.accept()
    if student_id not in _ws_connections:
        _ws_connections[student_id] = {}
    _ws_connections[student_id]["viewer"] = websocket
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        _ws_connections.get(student_id, {}).pop("viewer", None)


@app.get("/ws/status/{student_id}")
async def ws_status(student_id: str):
    connected = student_id in _ws_connections and "phone" in _ws_connections[student_id]
    return {"connected": connected}


@app.get("/api/network/lan-ip")
async def lan_ip():
    """Return this PC's LAN IP so the frontend can build a QR URL dynamically."""
    import socket
    try:
        # Connect to a public DNS to determine the outbound LAN IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    return {"ip": ip}


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "MindMesh v2", "version": "2.0.0"}
