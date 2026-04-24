"""
文件系统服务：同步数据库内容到文件系统
"""
import json
from pathlib import Path
from app.config import get_settings

settings = get_settings()


def get_project_dir(novel_id: str) -> Path:
    base = Path(settings.storage_path)
    project_dir = base / novel_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def _write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: dict | list):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_outline(novel_id: str, content: str):
    project_dir = get_project_dir(novel_id)
    _write_text(project_dir / "outline.md", content)
    _write_text(project_dir / "outline" / "outline.md", content)


def save_outline_struct(novel_id: str, outline_data: dict):
    project_dir = get_project_dir(novel_id)
    _write_json(project_dir / "outline" / "outline.json", outline_data)


def save_synopsis(novel_id: str, content: str):
    project_dir = get_project_dir(novel_id)
    _write_text(project_dir / "synopsis.md", content)
    _write_text(project_dir / "book" / "synopsis.md", content)


def save_book_meta(novel_id: str, title: str, synopsis: str | None):
    project_dir = get_project_dir(novel_id)
    data = {"title": title, "synopsis": synopsis or ""}
    _write_json(project_dir / "book_meta.json", data)
    _write_json(project_dir / "book" / "book_meta.json", data)


def save_characters(novel_id: str, characters_data: list):
    project_dir = get_project_dir(novel_id)
    data = {"characters": characters_data}
    _write_json(project_dir / "characters.json", data)
    _write_json(project_dir / "characters" / "characters.json", data)


def save_worldbuilding(novel_id: str, wb_data: dict):
    project_dir = get_project_dir(novel_id)
    _write_json(project_dir / "worldbuilding.json", wb_data)
    _write_json(project_dir / "world" / "worldbuilding.json", wb_data)


def append_plot_summary(novel_id: str, chapter_number: int, title: str, summary: str):
    path = get_project_dir(novel_id) / "plot_summary.md"
    entry = f"\n## 第{chapter_number}章 {title}\n{summary}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


def save_chapter_synopsis(novel_id: str, chapter_number: int, synopsis_data: dict):
    chapter_dir = get_project_dir(novel_id) / "chapters" / f"chapter_{chapter_number:03d}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    path = chapter_dir / "synopsis.json"
    _write_json(path, synopsis_data)
    markdown = synopsis_data.get("content_md")
    if isinstance(markdown, str) and markdown.strip():
        _write_text(chapter_dir / "synopsis.md", markdown)
        _write_text(get_project_dir(novel_id) / "synopses" / f"chapter_{chapter_number:03d}.md", markdown)
    _write_json(get_project_dir(novel_id) / "synopses" / f"chapter_{chapter_number:03d}.json", synopsis_data)


def save_chapter_plot_summary(novel_id: str, chapter_number: int, summary: str):
    clean_summary = (summary or "").strip()
    if not clean_summary:
        return
    _write_text(get_project_dir(novel_id) / "plots" / f"chapter_{chapter_number:03d}.md", clean_summary)


def save_chapter_content(novel_id: str, chapter_number: int, content: str):
    chapter_dir = get_project_dir(novel_id) / "chapters" / f"chapter_{chapter_number:03d}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    path = chapter_dir / "content.md"
    _write_text(path, content)


def save_volume_plan(novel_id: str, volume_number: int, content: str, plan_data: dict):
    volume_dir = get_project_dir(novel_id) / "volumes" / f"volume_{volume_number:02d}"
    volume_dir.mkdir(parents=True, exist_ok=True)
    _write_text(volume_dir / "plan.md", content)
    _write_json(volume_dir / "plan.json", plan_data)


def save_chapter_memory(novel_id: str, chapter_number: int, memory_data: dict):
    chapter_dir = get_project_dir(novel_id) / "chapters" / f"chapter_{chapter_number:03d}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    _write_json(chapter_dir / "memory.json", memory_data)


def save_entity_proposals(novel_id: str, proposals_data: list[dict]):
    project_dir = get_project_dir(novel_id)
    _write_json(project_dir / "proposals" / "proposals.json", proposals_data)
