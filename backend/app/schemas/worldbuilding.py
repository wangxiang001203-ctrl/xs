from typing import Any

from pydantic import BaseModel, Field


class WorldbuildingEntry(BaseModel):
    id: str | None = None
    name: str = ""
    summary: str = ""
    details: str = ""
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class WorldbuildingSection(BaseModel):
    id: str | None = None
    name: str = ""
    description: str = ""
    generation_hint: str = ""
    entries: list[WorldbuildingEntry] = Field(default_factory=list)


class WorldbuildingUpdate(BaseModel):
    overview: str | None = None
    sections: list[WorldbuildingSection] | None = None
    power_system: list | None = None
    factions: list | None = None
    geography: list | None = None
    core_rules: list | None = None
    items: list | None = None


class WorldbuildingOut(BaseModel):
    id: str
    novel_id: str
    overview: str = ""
    sections: list[WorldbuildingSection] = Field(default_factory=list)
    power_system: list = Field(default_factory=list)
    factions: list = Field(default_factory=list)
    geography: list = Field(default_factory=list)
    core_rules: list = Field(default_factory=list)
    items: list = Field(default_factory=list)

    model_config = {"from_attributes": True}
