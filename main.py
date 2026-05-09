import os
import json
from typing import AsyncGenerator, Optional
from datetime import datetime
import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
import redis.asyncio as redis  # ✅ Импорт Redis
import models
import schemas
from models import Base, Note
from schemas import NoteCreate, NoteUpdate, NoteRead
from dotenv import load_dotenv
from contextlib import asynccontextmanager

load_dotenv()

# ═══════════════════════════════════════════════════════════
# КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════
DATABASE_URL = os.getenv("DATABASE_URL")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set")

# ═══════════════════════════════════════════════════════════
# ПОДКЛЮЧЕНИЯ
# ═══════════════════════════════════════════════════════════
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ═══════════════════════════════════════════════════════════
# DEPENDENCIES
# ═══════════════════════════════════════════════════════════
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

# ═══════════════════════════════════════════════════════════
# LIFESPAN
# ═══════════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    await redis_client.close()

app = FastAPI(lifespan=lifespan)

# ═══════════════════════════════════════════════════════════
# REDIS HELPERS
# ═══════════════════════════════════════════════════════════
async def get_from_cache(key: str) -> Optional[dict]:
    cached = await redis_client.get(key)
    return json.loads(cached) if cached else None

async def set_to_cache(key: str, data: dict, ttl: int = CACHE_TTL):
    await redis_client.setex(key, ttl, json.dumps(data))

async def invalidate_cache(pattern: str):
    keys = await redis_client.keys(pattern)
    if keys:
        await redis_client.delete(*keys)

# ═══════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════
@app.get("/")
async def root():
    return {"status": "ok", "service": "cache-api"}

@app.post("/notes", response_model=NoteRead, status_code=201)
async def create_note(note: NoteCreate, db: AsyncSession = Depends(get_db)):
    db_note = Note(title=note.title, content=note.content)
    db.add(db_note)
    await db.commit()
    await db.refresh(db_note)
    await invalidate_cache("notes:*")  # Очистка кэша
    return db_note

@app.get("/notes", response_model=list[NoteRead])
async def get_notes(db: AsyncSession = Depends(get_db)):
    cache_key = "notes:all"
    
    # 1. Проверяем кэш
    cached = await get_from_cache(cache_key)
    if cached:
        return cached
    
    # 2. Если нет → БД
    result = await db.execute(select(Note).order_by(Note.created_at.desc()))
    notes = result.scalars().all()
    
    # 3. Сохраняем в кэш
    notes_data = [
        {"id": n.id, "title": n.title, "content": n.content,
         "created_at": n.created_at.isoformat(),
         "updated_at": n.updated_at.isoformat()}
        for n in notes
    ]
    await set_to_cache(cache_key, notes_data)
    
    return notes

@app.get("/notes/{note_id}", response_model=NoteRead)
async def get_note(note_id: int, db: AsyncSession = Depends(get_db)):
    cache_key = f"notes:{note_id}"
    
    # 1. Проверяем кэш
    cached = await get_from_cache(cache_key)
    if cached:
        return cached
    
    # 2. Если нет → БД
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # 3. Сохраняем в кэш
    note_data = {
        "id": note.id, "title": note.title, "content": note.content,
        "created_at": note.created_at.isoformat(),
        "updated_at": note.updated_at.isoformat()
    }
    await set_to_cache(cache_key, note_data)
    
    return note
@app.get("/health")
async def health_check():
    health = {"api": "ok", "redis": "unknown", "database": "unknown"}
    
    try:
        await redis_client.ping()
        health["redis"] = "ok"
    except:
        health["redis"] = "error"
    
    try:
        async with async_session() as session:
            await session.execute(select(1))
        health["database"] = "ok"
    except:
        health["database"] = "error"
    
    return health

@app.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    await db.delete(note)
    await db.commit()
    
    await invalidate_cache(f"notes:{note_id}")
    await invalidate_cache("notes:*")
    
    return None

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True, host="0.0.0.0", port=8000)