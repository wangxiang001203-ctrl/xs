"""
文件系统服务：同步数据库内容到文件系统
"""
import json
import os
from pathlib import Path
from app.config import get_settings

settings = get_settings()


def get_project_dir(novel_id: str) -> Path:
    base = Path(settings.storage_path)
    project_dir = base / novel_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def save_outline(novel_id: str, content: str):
    path = get_project_dir(novel_id) / "outline.md"
    path.write_text(content, encoding="utf-8")


def save_synopsis(novel_id: str, content: str):
    path = get_project_dir(novel_id) / "synopsis.md"
    path.write_text(content, encoding="utf-8")


def save_book_meta(novel_id: str, title: str, synopsis: str | None):
    path = get_project_dir(novel_id) / "book_meta.json"
    path.write_text(
        json.dumps(
            {"title": title, "synopsis": synopsis or ""},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def save_characters(novel_id: str, characters_data: list):
    path = get_project_dir(novel_id) / "characters.json"
    path.write_text(
        json.dumps({"characters": characters_data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_worldbuilding(novel_id: str, wb_data: dict):
    path = get_project_dir(novel_id) / "worldbuilding.json"
    path.write_text(
        json.dumps(wb_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def append_plot_summary(novel_id: str, chapter_number: int, title: str, summary: str):
    path = get_project_dir(novel_id) / "plot_summary.md"
    entry = f"\n## 第{chapter_number}章 {title}\n{summary}\n"
    with open(path, "a", encoding="utf-8") as f:
        f.write(entry)


def save_chapter_synopsis(novel_id: str, chapter_number: int, synopsis_data: dict):
    chapter_dir = get_project_dir(novel_id) / "chapters" / f"chapter_{chapter_number:03d}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    path = chapter_dir / "synopsis.json"
    path.write_text(
        json.dumps(synopsis_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_chapter_content(novel_id: str, chapter_number: int, content: str):
    chapter_dir = get_project_dir(novel_id) / "chapters" / f"chapter_{chapter_number:03d}"
    chapter_dir.mkdir(parents=True, exist_ok=True)
    path = chapter_dir / "content.md"
    path.write_text(content, encoding="utf-8")
