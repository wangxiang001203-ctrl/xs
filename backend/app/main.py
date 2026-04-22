from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.config import get_settings
from app.database import engine, Base
import app.models  # noqa: F401 — 触发所有模型注册

from app.routers import projects, outline, characters, worldbuilding, chapters, ai, volumes, admin

settings = get_settings()

# 创建所有表（开发阶段直接建表，生产用Alembic）
Base.metadata.create_all(bind=engine)


def _ensure_schema():
    """开发环境轻量补列，避免本地旧库缺字段导致启动失败。"""
    inspector = inspect(engine)
    if "novels" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("novels")}
    if "synopsis" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE novels ADD COLUMN synopsis TEXT"))


_ensure_schema()

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
app.include_router(admin.router)


@app.get("/health")
def health():
    return {"status": "ok"}
