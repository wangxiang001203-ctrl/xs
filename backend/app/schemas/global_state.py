from pydantic import BaseModel


class GlobalCharacterStatus(BaseModel):
    character_id: str
    name: str
    current_realm: str
    current_location: str
    current_faction: str
    importance: int
    status: str


class GlobalItemStatus(BaseModel):
    item_id: str
    name: str
    grade: str
    current_holder: str
    holder_name: str
    location: str


class GlobalLocationStatus(BaseModel):
    location_id: str
    name: str
    type: str
    current_state: str
    significance: str


class GlobalEventEntry(BaseModel):
    chapter_number: int
    title: str
    event_type: str
    entities_involved: list[str]
    description: str


class ChapterSnapshotOut(BaseModel):
    id: str
    novel_id: str
    start_chapter: int
    end_chapter: int
    summary: str | None
    key_events: list[str]
    character_arcs: list[str]
    item_changes: list[str]
    open_threads: list[str]
    foreshadowing: list[str]
    created_at: str


class UnresolvedForeshadowing(BaseModel):
    thread: str
    introduced_chapter: int
    related_entities: list[str]


class NovelGlobalState(BaseModel):
    # L0 原始数据摘要
    total_chapters: int
    total_words: int
    approved_chapters: int
    latest_chapter_number: int

    # L1 聚合快照
    snapshots: list[ChapterSnapshotOut]

    # L2 全局知识索引
    characters: list[GlobalCharacterStatus]
    items: list[GlobalItemStatus]
    locations: list[GlobalLocationStatus]
    event_timeline: list[GlobalEventEntry]
    open_threads: list[str]

    # 关键伏笔追踪
    unresolved_foreshadowing: list[UnresolvedForeshadowing]

    # 最后更新时间
    updated_at: str
