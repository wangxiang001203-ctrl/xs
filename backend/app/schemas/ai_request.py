from pydantic import BaseModel
from typing import Optional


class GenerateOutlineRequest(BaseModel):
    novel_id: str
    idea: str


class GenerateWorldbuildingRequest(BaseModel):
    novel_id: str
    outline_id: Optional[str] = None
    extra_instruction: Optional[str] = None
    current_worldbuilding: Optional[dict] = None


class GenerateCharactersFromOutlineRequest(BaseModel):
    novel_id: str
    outline_id: Optional[str] = None
    genre: str = "玄幻修仙"


class GenerateTitlesRequest(BaseModel):
    novel_id: str
    extra_instruction: Optional[str] = None


class GenerateBookSynopsisRequest(BaseModel):
    novel_id: str
    extra_instruction: Optional[str] = None


class GenerateSynopsisRequest(BaseModel):
    novel_id: str
    chapter_id: str
    chapter_number: int
    extra_instruction: Optional[str] = None


class CreateMissingCharactersRequest(BaseModel):
    novel_id: str
    missing_names: list[str]


class GenerateChapterRequest(BaseModel):
    novel_id: str
    chapter_id: str
    extra_instruction: Optional[str] = None


class ValidateSynopsisRequest(BaseModel):
    novel_id: str
    characters_in_synopsis: list[str]


class GenerateVolumeSynopsisRequest(BaseModel):
    novel_id: str
    volume_id: str
    extra_instruction: Optional[str] = None


class GenerateCharactersFromSynopsisRequest(BaseModel):
    novel_id: str


class GenerateChapterSegmentRequest(BaseModel):
    novel_id: str
    chapter_id: str
    segment: str
    prev_segment_text: Optional[str] = ""
    extra_instruction: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    novel_id: str
    context_type: str
    context_id: Optional[str] = None
    messages: list[ChatMessage]
    user_message: str
