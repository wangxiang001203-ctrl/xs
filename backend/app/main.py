from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.config import get_settings
from app.database import engine, Base
import app.models  # noqa: F401 — 触发所有模型注册

from app.routers import projects, outline, characters, worldbuilding, chapters, ai, volumes, admin, review, validation, entities, prompts, assistant

settings = get_settings()

# 创建所有表（开发阶段直接建表，生产用Alembic）
Base.metadata.create_all(bind=engine)


def _ensure_schema():
    """开发环境轻量补列，避免本地旧库缺字段导致启动失败。"""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    alter_sqls: list[str] = []

    if "novels" in tables:
        columns = {col["name"] for col in inspector.get_columns("novels")}
        if "synopsis" not in columns:
            alter_sqls.append("ALTER TABLE novels ADD COLUMN synopsis TEXT")

    if "outlines" in tables:
        columns = {col["name"] for col in inspector.get_columns("outlines")}
        if "title" not in columns:
            alter_sqls.append("ALTER TABLE outlines ADD COLUMN title VARCHAR(200)")
        if "synopsis" not in columns:
            alter_sqls.append("ALTER TABLE outlines ADD COLUMN synopsis TEXT")
        if "selling_points" not in columns:
            alter_sqls.append("ALTER TABLE outlines ADD COLUMN selling_points TEXT")
        if "main_plot" not in columns:
            alter_sqls.append("ALTER TABLE outlines ADD COLUMN main_plot LONGTEXT")
        if "version_note" not in columns:
            alter_sqls.append("ALTER TABLE outlines ADD COLUMN version_note VARCHAR(255)")

    if "characters" in tables:
        columns = {col["name"] for col in inspector.get_columns("characters")}
        if "aliases" not in columns:
            alter_sqls.append("ALTER TABLE characters ADD COLUMN aliases JSON")
        if "role" not in columns:
            alter_sqls.append("ALTER TABLE characters ADD COLUMN `role` VARCHAR(50)")
        if "importance" not in columns:
            alter_sqls.append("ALTER TABLE characters ADD COLUMN importance INTEGER DEFAULT 3")
        if "golden_finger" not in columns:
            alter_sqls.append("ALTER TABLE characters ADD COLUMN golden_finger TEXT")
        if "motivation" not in columns:
            alter_sqls.append("ALTER TABLE characters ADD COLUMN motivation TEXT")
        if "profile_md" not in columns:
            alter_sqls.append("ALTER TABLE characters ADD COLUMN profile_md TEXT")

    if "worldbuilding" in tables:
        columns = {col["name"] for col in inspector.get_columns("worldbuilding")}
        if "overview" not in columns:
            alter_sqls.append("ALTER TABLE worldbuilding ADD COLUMN overview TEXT")
        if "sections" not in columns:
            alter_sqls.append("ALTER TABLE worldbuilding ADD COLUMN sections JSON")
        if "power_system" not in columns:
            alter_sqls.append("ALTER TABLE worldbuilding ADD COLUMN power_system JSON")
        if "core_rules" not in columns:
            alter_sqls.append("ALTER TABLE worldbuilding ADD COLUMN core_rules JSON")
        if "items" not in columns:
            alter_sqls.append("ALTER TABLE worldbuilding ADD COLUMN items JSON")

    if "volumes" in tables:
        columns = {col["name"] for col in inspector.get_columns("volumes")}
        if "target_words" not in columns:
            alter_sqls.append("ALTER TABLE volumes ADD COLUMN target_words INTEGER DEFAULT 0")
        if "planned_chapter_count" not in columns:
            alter_sqls.append("ALTER TABLE volumes ADD COLUMN planned_chapter_count INTEGER DEFAULT 0")
        if "main_line" not in columns:
            alter_sqls.append("ALTER TABLE volumes ADD COLUMN main_line TEXT")
        if "character_arc" not in columns:
            alter_sqls.append("ALTER TABLE volumes ADD COLUMN character_arc TEXT")
        if "ending_hook" not in columns:
            alter_sqls.append("ALTER TABLE volumes ADD COLUMN ending_hook TEXT")
        if "plan_markdown" not in columns:
            alter_sqls.append("ALTER TABLE volumes ADD COLUMN plan_markdown LONGTEXT")
        if "plan_data" not in columns:
            alter_sqls.append("ALTER TABLE volumes ADD COLUMN plan_data JSON")
        if "review_status" not in columns:
            alter_sqls.append("ALTER TABLE volumes ADD COLUMN review_status VARCHAR(20) DEFAULT 'draft'")
        if "approved_at" not in columns:
            alter_sqls.append("ALTER TABLE volumes ADD COLUMN approved_at DATETIME")

    if "chapters" in tables:
        columns = {col["name"] for col in inspector.get_columns("chapters")}
        if "final_approved" not in columns:
            alter_sqls.append("ALTER TABLE chapters ADD COLUMN final_approved BOOLEAN DEFAULT FALSE")
        if "final_approval_note" not in columns:
            alter_sqls.append("ALTER TABLE chapters ADD COLUMN final_approval_note TEXT")
        if "final_approved_at" not in columns:
            alter_sqls.append("ALTER TABLE chapters ADD COLUMN final_approved_at DATETIME")

    if "synopses" in tables:
        columns = {col["name"] for col in inspector.get_columns("synopses")}
        if "summary_line" not in columns:
            alter_sqls.append("ALTER TABLE synopses ADD COLUMN summary_line VARCHAR(255)")
        if "content_md" not in columns:
            alter_sqls.append("ALTER TABLE synopses ADD COLUMN content_md LONGTEXT")
        if "hard_constraints" not in columns:
            alter_sqls.append("ALTER TABLE synopses ADD COLUMN hard_constraints JSON")
        if "referenced_entities" not in columns:
            alter_sqls.append("ALTER TABLE synopses ADD COLUMN referenced_entities JSON")
        if "review_status" not in columns:
            alter_sqls.append("ALTER TABLE synopses ADD COLUMN review_status VARCHAR(20) DEFAULT 'draft'")
        if "approved_at" not in columns:
            alter_sqls.append("ALTER TABLE synopses ADD COLUMN approved_at DATETIME")

    if "story_entities" in tables:
        columns = {col["name"] for col in inspector.get_columns("story_entities")}
        if "graph_role" not in columns:
            alter_sqls.append("ALTER TABLE story_entities ADD COLUMN graph_role VARCHAR(40) DEFAULT 'supporting'")
        if "importance" not in columns:
            alter_sqls.append("ALTER TABLE story_entities ADD COLUMN importance INTEGER DEFAULT 3")
        if "graph_layer" not in columns:
            alter_sqls.append("ALTER TABLE story_entities ADD COLUMN graph_layer INTEGER DEFAULT 2")
        if "graph_position" not in columns:
            alter_sqls.append("ALTER TABLE story_entities ADD COLUMN graph_position JSON")

    if "entity_relations" in tables:
        columns = {col["name"] for col in inspector.get_columns("entity_relations")}
        if "relation_strength" not in columns:
            alter_sqls.append("ALTER TABLE entity_relations ADD COLUMN relation_strength FLOAT DEFAULT 1.0")
        if "is_bidirectional" not in columns:
            alter_sqls.append("ALTER TABLE entity_relations ADD COLUMN is_bidirectional BOOLEAN DEFAULT FALSE")
        if "confidence" not in columns:
            alter_sqls.append("ALTER TABLE entity_relations ADD COLUMN confidence FLOAT DEFAULT 1.0")

    if "ai_generation_jobs" in tables and engine.dialect.name == "mysql":
        columns = {col["name"]: col for col in inspector.get_columns("ai_generation_jobs")}
        job_type = str(columns.get("job_type", {}).get("type", ""))
        if "assistant_workflow" not in job_type or "book_volumes" not in job_type:
            alter_sqls.append(
                "ALTER TABLE ai_generation_jobs MODIFY COLUMN job_type "
                "ENUM('outline','titles','book_synopsis','characters','worldbuilding',"
                "'book_volumes','chapter_synopsis','chapter_content','volume_synopsis','chapter_segment',"
                "'chat','assistant_workflow') NOT NULL"
            )

    if not alter_sqls:
        return
    with engine.begin() as conn:
        for sql in alter_sqls:
            conn.execute(text(sql))


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
app.include_router(review.router)
app.include_router(validation.router)
app.include_router(entities.router)
app.include_router(prompts.router)
app.include_router(assistant.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/health")
def api_health():
    return {"status": "ok"}
