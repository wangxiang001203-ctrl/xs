import json
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.ai_request import (
    GenerateOutlineRequest,
    GenerateSynopsisRequest,
    GenerateChapterRequest,
    ValidateSynopsisRequest,
    GenerateVolumeSynopsisRequest,
    GenerateCharactersFromSynopsisRequest,
    GenerateWorldbuildingRequest,
    GenerateChapterSegmentRequest,
    ChatRequest,
)
from app.services import ai_service, context_builder
from app.services.validator import validate_synopsis_characters
from app.models import Novel, Character
from app.models.project import Outline
from app.models.volume import Volume
from app.models.worldbuilding import Worldbuilding
from app.models.chapter import Chapter
from app.models.synopsis import Synopsis

router = APIRouter(prefix="/api/ai", tags=["ai"])

SYSTEM_NOVEL = "你是一位专业的玄幻/修仙小说作家，擅长构建宏大世界观、塑造鲜明人物、编写引人入胜的剧情。"


async def _sse_stream(generator):
    """将异步生成器包装为SSE格式"""
    try:
        async for chunk in generator:
            data = json.dumps({"text": chunk}, ensure_ascii=False)
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


def _extract_json(text: str):
    """从AI输出中提取JSON，兼容markdown代码块包裹"""
    # 尝试提取 ```json ... ``` 块
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
    if m:
        return m.group(1).strip()
    return text.strip()


@router.post("/generate/outline")
async def generate_outline(req: GenerateOutlineRequest, db: Session = Depends(get_db)):
    """流式生成大纲"""
    novel = db.query(Novel).filter(Novel.id == req.novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    prompt = context_builder.build_outline_context(novel, req.idea)

    async def event_stream():
        full_text = ""
        async for chunk in ai_service.stream_generate(SYSTEM_NOVEL, prompt):
            full_text += chunk
            yield chunk

        last = db.query(Outline).filter(Outline.novel_id == req.novel_id).order_by(Outline.version.desc()).first()
        version = (last.version + 1) if last else 1
        outline = Outline(
            novel_id=req.novel_id,
            content=full_text,
            ai_generated=True,
            confirmed=False,
            version=version,
        )
        db.add(outline)
        novel.idea = req.idea
        db.commit()

    return StreamingResponse(
        _sse_stream(event_stream()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate/synopsis")
async def generate_synopsis(req: GenerateSynopsisRequest, db: Session = Depends(get_db)):
    """流式生成单章细纲"""
    prompt = context_builder.build_synopsis_context(db, req.novel_id, req.chapter_number)
    if req.extra_instruction:
        prompt += f"\n\n额外要求：{req.extra_instruction}"

    return StreamingResponse(
        _sse_stream(ai_service.stream_generate(SYSTEM_NOVEL, prompt)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate/chapter")
async def generate_chapter(req: GenerateChapterRequest, db: Session = Depends(get_db)):
    """流式生成完整正文（旧接口保留兼容）"""
    prompt = context_builder.build_chapter_context(db, req.novel_id, req.chapter_id)
    if req.extra_instruction:
        prompt += f"\n\n额外要求：{req.extra_instruction}"

    return StreamingResponse(
        _sse_stream(ai_service.stream_generate(SYSTEM_NOVEL, prompt)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate/volume-synopsis")
async def generate_volume_synopsis(req: GenerateVolumeSynopsisRequest, db: Session = Depends(get_db)):
    """流式生成整卷所有章节细纲（JSON数组），生成完成后自动写入数据库"""
    volume = db.query(Volume).filter(Volume.id == req.volume_id, Volume.novel_id == req.novel_id).first()
    if not volume:
        raise HTTPException(404, "卷不存在")

    prompt = context_builder.build_volume_synopsis_context(db, req.novel_id, req.volume_id)
    if req.extra_instruction:
        prompt += f"\n\n额外要求：{req.extra_instruction}"

    async def event_stream():
        full_text = ""
        async for chunk in ai_service.stream_generate(SYSTEM_NOVEL, prompt):
            full_text += chunk
            yield chunk

        # 解析JSON并写入数据库
        try:
            raw_json = _extract_json(full_text)
            synopsis_list = json.loads(raw_json)
            chapters = db.query(Chapter).filter(Chapter.volume_id == req.volume_id).order_by(Chapter.chapter_number).all()
            ch_map = {c.chapter_number: c for c in chapters}

            for item in synopsis_list:
                ch_num = item.get("chapter_number")
                ch = ch_map.get(ch_num)
                if not ch:
                    continue
                opening = item.get("opening", {})
                development = item.get("development", {})
                ending = item.get("ending", {})
                all_chars = list(set(
                    opening.get("characters", []) +
                    development.get("characters", [])
                ))

                existing = db.query(Synopsis).filter(Synopsis.chapter_id == ch.id).first()
                if existing:
                    existing.opening_scene = opening.get("scene", "")
                    existing.opening_mood = opening.get("mood", "")
                    existing.opening_hook = opening.get("hook", "")
                    existing.opening_characters = opening.get("characters", [])
                    existing.development_events = development.get("events", [])
                    existing.development_conflicts = development.get("conflicts", [])
                    existing.development_characters = development.get("characters", [])
                    existing.ending_resolution = ending.get("resolution", "")
                    existing.ending_cliffhanger = ending.get("cliffhanger", "")
                    existing.ending_next_hook = ending.get("next_chapter_hook", "")
                    existing.all_characters = all_chars
                    existing.word_count_target = item.get("word_count_target", 3000)
                    existing.plot_summary_update = item.get("plot_summary_update", "")
                else:
                    s = Synopsis(
                        chapter_id=ch.id,
                        novel_id=req.novel_id,
                        opening_scene=opening.get("scene", ""),
                        opening_mood=opening.get("mood", ""),
                        opening_hook=opening.get("hook", ""),
                        opening_characters=opening.get("characters", []),
                        development_events=development.get("events", []),
                        development_conflicts=development.get("conflicts", []),
                        development_characters=development.get("characters", []),
                        ending_resolution=ending.get("resolution", ""),
                        ending_cliffhanger=ending.get("cliffhanger", ""),
                        ending_next_hook=ending.get("next_chapter_hook", ""),
                        all_characters=all_chars,
                        word_count_target=item.get("word_count_target", 3000),
                        plot_summary_update=item.get("plot_summary_update", ""),
                    )
                    db.add(s)

                # 更新章节标题
                if item.get("title"):
                    ch.title = item["title"]

            volume.synopsis_generated = True
            db.commit()
        except Exception:
            pass  # JSON解析失败不影响流式输出已完成

    return StreamingResponse(
        _sse_stream(event_stream()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate/characters-from-synopsis")
async def generate_characters_from_synopsis(req: GenerateCharactersFromSynopsisRequest, db: Session = Depends(get_db)):
    """流式生成角色卡列表，完成后自动写入数据库"""
    prompt = context_builder.build_characters_from_synopsis_context(db, req.novel_id)

    async def event_stream():
        full_text = ""
        async for chunk in ai_service.stream_generate(SYSTEM_NOVEL, prompt):
            full_text += chunk
            yield chunk

        try:
            raw_json = _extract_json(full_text)
            char_list = json.loads(raw_json)
            existing_names = {c.name for c in db.query(Character).filter(Character.novel_id == req.novel_id).all()}

            for item in char_list:
                name = item.get("name", "").strip()
                if not name or name in existing_names:
                    continue
                c = Character(
                    novel_id=req.novel_id,
                    name=name,
                    gender=item.get("gender"),
                    age=item.get("age"),
                    race=item.get("race", "人族"),
                    realm=item.get("realm"),
                    realm_level=item.get("realm_level", 0),
                    faction=item.get("faction"),
                    techniques=item.get("techniques", []),
                    artifacts=item.get("artifacts", []),
                    appearance=item.get("appearance"),
                    personality=item.get("personality"),
                    background=item.get("background"),
                    relationships=item.get("relationships", []),
                    status=item.get("status", "alive"),
                )
                db.add(c)
                existing_names.add(name)
            db.commit()
        except Exception:
            pass

    return StreamingResponse(
        _sse_stream(event_stream()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate/worldbuilding")
async def generate_worldbuilding(req: GenerateWorldbuildingRequest, db: Session = Depends(get_db)):
    """流式生成/完善世界观，完成后自动写入数据库"""
    prompt = context_builder.build_worldbuilding_from_outline_context(db, req.novel_id)

    async def event_stream():
        full_text = ""
        async for chunk in ai_service.stream_generate(SYSTEM_NOVEL, prompt):
            full_text += chunk
            yield chunk

        try:
            raw_json = _extract_json(full_text)
            data = json.loads(raw_json)
            wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == req.novel_id).first()
            if wb:
                for field in ("realm_system", "currency", "factions", "artifacts", "techniques", "geography", "custom_rules"):
                    if field in data:
                        setattr(wb, field, data[field])
            else:
                wb = Worldbuilding(novel_id=req.novel_id, **{
                    k: data.get(k) for k in ("realm_system", "currency", "factions", "artifacts", "techniques", "geography", "custom_rules")
                })
                db.add(wb)
            db.commit()
        except Exception:
            pass

    return StreamingResponse(
        _sse_stream(event_stream()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/generate/chapter-segment")
async def generate_chapter_segment(req: GenerateChapterSegmentRequest, db: Session = Depends(get_db)):
    """流式分段生成正文（opening/middle/ending）"""
    if req.segment not in ("opening", "middle", "ending"):
        raise HTTPException(400, "segment 必须是 opening/middle/ending")

    prompt = context_builder.build_chapter_segment_context(
        db, req.novel_id, req.chapter_id, req.segment, req.prev_segment_text or ""
    )
    if req.extra_instruction:
        prompt += f"\n\n额外要求：{req.extra_instruction}"

    return StreamingResponse(
        _sse_stream(ai_service.stream_generate(SYSTEM_NOVEL, prompt)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/chat")
async def ai_chat(req: ChatRequest, db: Session = Depends(get_db)):
    """上下文感知AI对话，流式返回"""
    system_prompt = context_builder.build_chat_context(db, req.novel_id, req.context_type, req.context_id)

    # 构建历史消息
    messages = [{"role": m.role, "content": m.content} for m in req.messages]
    messages.append({"role": "user", "content": req.user_message})

    async def chat_stream():
        async for chunk in ai_service.stream_generate_with_history(system_prompt, messages):
            yield chunk

    return StreamingResponse(
        _sse_stream(chat_stream()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/validate/synopsis-characters")
def validate_characters(req: ValidateSynopsisRequest, db: Session = Depends(get_db)):
    """校验细纲人物是否在角色库中存在"""
    return validate_synopsis_characters(db, req.novel_id, req.characters_in_synopsis)
