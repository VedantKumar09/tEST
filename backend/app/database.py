from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

client = None
db = None


async def connect_db():
    global client, db
    try:
        client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=3000)
        await client.admin.command("ping")
        db = client[settings.DATABASE_NAME]
        print(f"[DB] Connected to MongoDB: {settings.DATABASE_NAME}")
    except Exception as e:
        print(f"[DB] MongoDB unavailable, running without DB: {e}")
        client = None
        db = None


async def close_db():
    global client
    if client:
        client.close()
        print("[DB] MongoDB connection closed")


def get_db():
    return db
