import json
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.ai_request import (
    GenerateOutlineRequest,
    GenerateTitlesRequest,
    GenerateBookSynopsisRequest,
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
from app.services.file_service import save_synopsis, save_book_meta
from app.services.workflow_config_service import get_workflow_config

router = APIRouter(prefix="/api/ai", tags=["ai"])

SYSTEM_NOVEL = "你是一位专业的玄幻/修仙小说作家，擅长构建宏大世界观、塑造鲜明人物、编写引人入胜的剧情。"


def _prompt_config() -> dict[str, str]:
    config = get_workflow_config()
    prompts = config.get("prompts") or {}
    return {
        "global_system": prompts.get("global_system") or SYSTEM_NOVEL,
        "outline_generation": prompts.get("outline_generation") or "请生成完整小说大纲。",
        "titles_generation": prompts.get("titles_generation") or "请输出10个标题候选。",
        "book_synopsis_generation": prompts.get("book_synopsis_generation") or "请输出小说简介。",
    }


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
    """结构化生成大纲"""
    novel = db.query(Novel).filter(Novel.id == req.novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    prompt = f"""请根据以下想法，为这部小说生成一个极简且结构化的企划。
想法：{req.idea}

你必须严格按照以下 JSON 格式输出，不要输出任何额外的废话：
```json
{{
  "title": "小说的书名（提供1个最合适的）",
  "synopsis": "商业简介（200字以内，吸引读者）",
  "selling_points": "核心卖点/金手指/爽点（100字以内概括）",
  "main_plot": "极简主线大纲（按起承转合四个阶段概括，共计1000字左右）"
}}
```"""

    try:
        response_text = await ai_service.generate(SYSTEM_NOVEL, prompt)
        json_str = _extract_json(response_text)
        data = json.loads(json_str)
        
        last = db.query(Outline).filter(Outline.novel_id == req.novel_id).order_by(Outline.version.desc()).first()
        version = (last.version + 1) if last else 1
        
        outline = Outline(
            novel_id=req.novel_id,
            title=data.get("title", ""),
            synopsis=data.get("synopsis", ""),
            selling_points=data.get("selling_points", ""),
            main_plot=data.get("main_plot", ""),
            content=json_str, # 保留完整内容以兼容
            ai_generated=True,
            confirmed=False,
            version=version,
        )
        db.add(outline)
        novel.idea = req.idea
        novel.title = data.get("title", novel.title)
        novel.synopsis = data.get("synopsis", novel.synopsis)
        db.commit()
        db.refresh(outline)
        return outline
    except Exception as e:
        raise HTTPException(500, f"AI生成失败或格式错误: {str(e)}")


@router.post("/generate/titles")
async def generate_titles(req: GenerateTitlesRequest, db: Session = Depends(get_db)):
    """生成10个候选书名（JSON数组）"""
    novel = db.query(Novel).filter(Novel.id == req.novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    outline = db.query(Outline).filter(
        Outline.novel_id == req.novel_id, Outline.confirmed == True
    ).order_by(Outline.version.desc()).first()
    if not outline or not outline.content:
        raise HTTPException(400, "请先确认大纲")

    prompt_cfg = _prompt_config()
    prompt = f"""{prompt_cfg['titles_generation']}

【类型】{novel.genre}
【当前书名】{novel.title}
【大纲摘要】
{outline.content[:2000]}

输出要求：
1. 必须输出JSON数组，长度为10
2. 每个元素是字符串（书名）
3. 风格偏网文，辨识度高，避免雷同
4. 不要输出任何额外说明
"""
    if req.extra_instruction:
        prompt += f"\n额外要求：{req.extra_instruction}\n"

    full_text = ""
    async for chunk in ai_service.stream_generate(prompt_cfg["global_system"], prompt):
        full_text += chunk

    try:
        raw_json = _extract_json(full_text)
        titles = json.loads(raw_json)
        if not isinstance(titles, list):
            raise ValueError("标题结果格式错误")
        titles = [str(t).strip() for t in titles if str(t).strip()]
        if len(titles) > 10:
            titles = titles[:10]
        return {"titles": titles}
    except Exception as e:
        raise HTTPException(500, f"标题生成解析失败：{e}")


@router.post("/generate/book-synopsis")
async def generate_book_synopsis(req: GenerateBookSynopsisRequest, db: Session = Depends(get_db)):
    """生成小说简介并保存到数据库/文件"""
    novel = db.query(Novel).filter(Novel.id == req.novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    outline = db.query(Outline).filter(
        Outline.novel_id == req.novel_id, Outline.confirmed == True
    ).order_by(Outline.version.desc()).first()
    if not outline or not outline.content:
        raise HTTPException(400, "请先确认大纲")

    prompt_cfg = _prompt_config()
    prompt = f"""{prompt_cfg['book_synopsis_generation']}

【书名】{novel.title}
【类型】{novel.genre}
【大纲摘要】
{outline.content[:2200]}

输出要求：
1. 100-180字
2. 强调主角、核心冲突和爽点
3. 读者导向，适合详情页展示
4. 仅输出简介正文，不要加标题和说明
"""
    if req.extra_instruction:
        prompt += f"\n额外要求：{req.extra_instruction}\n"

    full_text = ""
    async for chunk in ai_service.stream_generate(prompt_cfg["global_system"], prompt):
        full_text += chunk

    synopsis = full_text.strip()
    novel.synopsis = synopsis
    db.commit()
    save_synopsis(req.novel_id, synopsis)
    save_book_meta(req.novel_id, novel.title, synopsis)
    return {"synopsis": synopsis}


@router.post("/generate/synopsis")
async def generate_synopsis(req: GenerateSynopsisRequest, db: Session = Depends(get_db)):
    """生成单章细纲并保存到数据库"""
    prompt = context_builder.build_synopsis_context(db, req.novel_id, req.chapter_number)
    if req.extra_instruction:
        prompt += f"\n\n额外要求：{req.extra_instruction}"

    full_text = await ai_service.generate(SYSTEM_NOVEL, prompt)
    raw_json = _extract_json(full_text)
    try:
        data = json.loads(raw_json)
        
        chapter = db.query(Chapter).filter(Chapter.id == req.chapter_id).first()
        if not chapter:
            raise HTTPException(404, "章节不存在")
        
        if data.get("title"):
            chapter.title = data.get("title")

        opening = data.get("opening", {})
        development = data.get("development", {})
        ending = data.get("ending", {})
        all_chars = list(set(
            opening.get("characters", []) +
            development.get("characters", [])
        ))

        synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == req.chapter_id).first()
        if synopsis:
            synopsis.opening_scene = opening.get("scene", "")
            synopsis.opening_mood = opening.get("mood", "")
            synopsis.opening_hook = opening.get("hook", "")
            synopsis.opening_characters = opening.get("characters", [])
            synopsis.development_events = development.get("events", [])
            synopsis.development_conflicts = development.get("conflicts", [])
            synopsis.development_characters = development.get("characters", [])
            synopsis.ending_resolution = ending.get("resolution", "")
            synopsis.ending_cliffhanger = ending.get("cliffhanger", "")
            synopsis.ending_next_hook = ending.get("next_chapter_hook", "")
            synopsis.all_characters = all_chars
            synopsis.word_count_target = data.get("word_count_target", 3000)
            synopsis.plot_summary_update = data.get("plot_summary_update", "")
        else:
            synopsis = Synopsis(
                chapter_id=req.chapter_id,
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
                word_count_target=data.get("word_count_target", 3000),
                plot_summary_update=data.get("plot_summary_update", ""),
            )
            db.add(synopsis)
        db.commit()
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"解析或保存细纲失败: {str(e)}\n原始内容: {full_text}")


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
    """生成整卷所有章节细纲（JSON数组），并保存到数据库"""
    volume = db.query(Volume).filter(Volume.id == req.volume_id, Volume.novel_id == req.novel_id).first()
    if not volume:
        raise HTTPException(404, "卷不存在")

    prompt = context_builder.build_volume_synopsis_context(db, req.novel_id, req.volume_id)
    if req.extra_instruction:
        prompt += f"\n\n额外要求：{req.extra_instruction}"

    full_text = await ai_service.generate(SYSTEM_NOVEL, prompt)
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
        return {"status": "ok"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"解析或保存卷细纲失败: {str(e)}\n原始内容: {full_text}")


@router.post("/generate/characters")
async def generate_characters(req: GenerateCharactersFromOutlineRequest, db: Session = Depends(get_db)):
    """根据大纲提取和生成核心角色"""
    novel = db.query(Novel).filter(Novel.id == req.novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
        
    if req.outline_id:
        outline = db.query(Outline).filter(Outline.id == req.outline_id).first()
    else:
        outline = db.query(Outline).filter(Outline.novel_id == req.novel_id).order_by(Outline.version.desc()).first()
        
    if not outline:
        raise HTTPException(400, "请先生成并保存大纲")

    prompt = f"""你是一个资深网文架构师。请仔细阅读以下小说大纲：

【书名】：{outline.title or novel.title}
【简介】：{outline.synopsis or novel.synopsis}
【主线大纲】：
{outline.main_plot or outline.content}

请根据大纲的背景和剧情，提取并生成这部小说中最核心的 3-5 个人物（例如：男主、女主、主要反派、核心导师）。
你必须严格按照以下 JSON 格式输出，不要输出任何额外的废话：
```json
[
  {{
    "name": "姓名",
    "role": "主角/女主/反派/配角",
    "personality": "性格特征（如：杀伐果断、腹黑）",
    "appearance": "外貌描写",
    "background": "身世背景",
    "golden_finger": "金手指/特殊能力（如果不是主角可填无）",
    "motivation": "核心动机/执念（他为什么做这些事）"
  }}
]
```"""

    try:
        response_text = await ai_service.generate(SYSTEM_NOVEL, prompt)
        json_str = _extract_json(response_text)
        data = json.loads(json_str)
        
        created_characters = []
        for char_data in data:
            # 检查角色是否已存在（简单按名字去重）
            existing = db.query(Character).filter(
                Character.novel_id == req.novel_id,
                Character.name == char_data.get("name")
            ).first()
            
            if not existing:
                char = Character(
                    novel_id=req.novel_id,
                    name=char_data.get("name"),
                    role=char_data.get("role", "配角"),
                    personality=char_data.get("personality"),
                    appearance=char_data.get("appearance"),
                    background=char_data.get("background"),
                    golden_finger=char_data.get("golden_finger"),
                    motivation=char_data.get("motivation"),
                )
                db.add(char)
                created_characters.append(char)
                
        db.commit()
        for char in created_characters:
            db.refresh(char)
            
        return created_characters
    except Exception as e:
        raise HTTPException(500, f"AI生成角色失败或格式错误: {str(e)}")


@router.post("/generate/worldbuilding")
async def generate_worldbuilding(req: GenerateWorldbuildingRequest, db: Session = Depends(get_db)):
    """根据大纲结构化生成世界观"""
    novel = db.query(Novel).filter(Novel.id == req.novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
        
    if req.outline_id:
        outline = db.query(Outline).filter(Outline.id == req.outline_id).first()
    else:
        outline = db.query(Outline).filter(Outline.novel_id == req.novel_id).order_by(Outline.version.desc()).first()
        
    if not outline:
        raise HTTPException(400, "请先生成并保存大纲")

    prompt = f"""你是一个资深网文架构师。请仔细阅读以下小说大纲：

【书名】：{outline.title or novel.title}
【简介】：{outline.synopsis or novel.synopsis}
【卖点】：{outline.selling_points}
【主线大纲】：
{outline.main_plot or outline.content}

请根据大纲的背景和基调，为这部小说推演世界观设定。你必须严格按照以下 JSON 格式输出，不要输出任何额外的废话：
```json
{{
  "power_system": [
    {{"name": "境界/能力名称（如：炼气期）", "description": "特征描述（寿命、能力表现）"}}
  ],
  "factions": [
    {{"name": "势力名称（如：三大宗门）", "type": "类型（宗门/公司/国家）", "description": "宗旨与实力"}}
  ],
  "geography": [
    {{"name": "地点名称（如：十万大山）", "description": "地貌与特色"}}
  ],
  "core_rules": [
    {{"rule_name": "核心法则（如：灵气衰竭）", "description": "具体表现与限制"}}
  ],
  "items": [
    {{"name": "关键物品（如：某种异火）", "description": "作用与稀有度"}}
  ]
}}
```"""

    try:
        response_text = await ai_service.generate(SYSTEM_NOVEL, prompt)
        json_str = _extract_json(response_text)
        data = json.loads(json_str)
        
        # 保存到数据库
        wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == req.novel_id).first()
        if not wb:
            wb = Worldbuilding(novel_id=req.novel_id)
            db.add(wb)
            
        wb.power_system = data.get("power_system", [])
        wb.factions = data.get("factions", [])
        wb.geography = data.get("geography", [])
        wb.core_rules = data.get("core_rules", [])
        wb.items = data.get("items", [])
        
        db.commit()
        db.refresh(wb)
        
        return wb
    except Exception as e:
        raise HTTPException(500, f"AI生成世界观失败或格式错误: {str(e)}")


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
