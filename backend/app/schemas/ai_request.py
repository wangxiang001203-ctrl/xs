from pydantic import BaseModel
from typing import Optional, List

class GenerateOutlineRequest(BaseModel):
    novel_id: str
    idea: str

class GenerateWorldbuildingRequest(BaseModel):
    novel_id: str
    outline_id: Optional[str] = None # 如果不传，默认使用最新大纲

class GenerateCharactersFromOutlineRequest(BaseModel):
    novel_id: str
    outline_id: Optional[str] = None # 如果不传，默认使用最新大纲
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


class GenerateChapterRequest(BaseModel):
    novel_id: str
    chapter_id: str
    extra_instruction: Optional[str] = None


class GenerateCharactersRequest(BaseModel):
    novel_id: str
    outline_content: str


class ValidateSynopsisRequest(BaseModel):
    novel_id: str
    characters_in_synopsis: list[str]


class GenerateVolumeSynopsisRequest(BaseModel):
    novel_id: str
    volume_id: str
    extra_instruction: Optional[str] = None


class GenerateCharactersFromSynopsisRequest(BaseModel):
    novel_id: str


class GenerateWorldbuildingRequest(BaseModel):
    novel_id: str


class GenerateChapterSegmentRequest(BaseModel):
    novel_id: str
    chapter_id: str
    segment: str  # opening / middle / ending
    prev_segment_text: Optional[str] = ""
    extra_instruction: Optional[str] = None


class ChatMessage(BaseModel):
    role: str  # user / assistant
    content: str


class ChatRequest(BaseModel):
    novel_id: str
    context_type: str  # outline / characters / worldbuilding / chapter
    context_id: Optional[str] = None
    messages: list[ChatMessage]
    user_message: str
