from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import engine, Base
import app.models  # noqa: F401 — 触发所有模型注册

from app.routers import projects, outline, characters, worldbuilding, chapters, ai, volumes

settings = get_settings()

# 创建所有表（开发阶段直接建表，生产用Alembic）
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AI小说编辑器",
    description="玄幻/修仙小说AI辅助创作平台",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(outline.router)
app.include_router(characters.router)
app.include_router(worldbuilding.router)
app.include_router(chapters.router)
app.include_router(volumes.router)
app.include_router(ai.router)


@app.get("/health")
def health():
    return {"status": "ok"}
