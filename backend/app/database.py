# MindMesh v2 — Database Connection (MongoDB via Motor)
import motor.motor_asyncio
from .config import settings

_client = None
_db = None

async def connect_db():
    global _client, _db
    try:
        _client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=2000)
        _db = _client[settings.DATABASE_NAME]
        print(f"[DB] Connected to MongoDB: {settings.DATABASE_NAME}")
    except Exception as e:
        print(f"[DB] MongoDB connection failed: {e}. Running without DB.")
        _db = None

async def close_db():
    global _client
    if _client:
        _client.close()

def get_db():
    return _db
