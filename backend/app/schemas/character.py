from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class CharacterCreate(BaseModel):
    name: str
    gender: Optional[str] = None
    age: Optional[int] = None
    race: Optional[str] = "人族"
    realm: Optional[str] = None
    realm_level: int = 0
    faction: Optional[str] = None
    techniques: list = []
    artifacts: list = []
    appearance: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    relationships: list = []
    status: str = "alive"
    first_appearance_chapter: Optional[int] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    race: Optional[str] = None
    realm: Optional[str] = None
    realm_level: Optional[int] = None
    faction: Optional[str] = None
    techniques: Optional[list] = None
    artifacts: Optional[list] = None
    appearance: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    relationships: Optional[list] = None
    status: Optional[str] = None
    last_updated_chapter: Optional[int] = None


class CharacterOut(BaseModel):
    id: str
    novel_id: str
    name: str
    gender: Optional[str]
    age: Optional[int]
    race: Optional[str]
    realm: Optional[str]
    realm_level: int
    faction: Optional[str]
    techniques: Optional[list]
    artifacts: Optional[list]
    appearance: Optional[str]
    personality: Optional[str]
    background: Optional[str]
    relationships: Optional[list]
    status: str
    first_appearance_chapter: Optional[int]
    last_updated_chapter: Optional[int]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
