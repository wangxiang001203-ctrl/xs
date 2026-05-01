from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AIWorkflowRun, AIWorkflowStep, Character, Novel, Outline
from app.services import ai_job_service, ai_service
from app.services.agent_contracts import IntentPlan
from app.services.agent_memory_service import build_memory_pack
from app.services.assistant_graph_runtime import AssistantGraphState, create_runtime
from app.services.assistant_service import (
    build_file_catalog,
    build_smart_chat_context,
    clarification_for,
)
from app.services.structured_output_service import StructuredOutputError, generate_structured


ALLOWED_INTENTS = {
    "generate_outline",
    "revise_outline",
    "rewrite_outline",
    "generate_synopsis",
    "revise_synopsis",
    "create_character",
    "revise_character",
    "revise_worldbuilding",
    "write_chapter",
    "revise_chapter",
    "continuity_check",
    "ask_question",
    "clarify",
    "reject",
}

WRITE_INTENTS_NEED_CONFIRMED_OUTLINE = {
    "generate_synopsis",
    "revise_synopsis",
    "create_character",
    "revise_character",
    "revise_worldbuilding",
    "write_chapter",
    "revise_chapter",
}

OUTLINE_REVISE_RE = re.compile(
    r"(大纲|简介|卖点|核心|定位|主线|冲突|主角|女主|男主|反派|角色|世界观|分卷|章节|"
    r"字数|目标|节奏|后宫|感情线|扩写|加长|缩短|增加|减少|提高|降低|突出|删掉|改成|调整|优化|打磨)"
)

SYNOPSIS_REVISE_RE = re.compile(r"(作品简介|小说简介|读者简介|详情页简介|简介页|简介)(?:.*)(改|写|生成|优化|打磨|扩写|缩短|加长|重写)")

VAGUE_OUTLINE_ACTION_RE = re.compile(
    r"^(?:请|麻烦)?(?:帮|给|替)?我?(?:写|生成|创建|做|弄|起草|出)"
    r"(?:一下|一个|一份|个|份)?(?:小说|故事|作品)?(?:的)?"
    r"(?:大纲|故事大纲|作品大纲|小说大纲)(?:吧|呗|可以吗|行吗)?[。.!！?？]*$",
    re.I,
)

OUTLINE_DETAIL_RE = re.compile(
    r"(玄幻|修仙|都市|历史|科幻|末世|悬疑|言情|女频|男频|主角|男主|女主|"
    r"反派|废柴|重生|穿越|系统|金手指|宗门|女帝|复仇|升级|爽点|目标|"
    r"万字|百万|字|主线|冲突|世界|背景|设定|开局|结局)"
)

CAPABILITY_RE = re.compile(r"(能干什么|能做什么|你会什么|怎么用|有什么功能|可以做什么|能帮我什么|帮助|help)", re.I)

LOW_VALUE_RE = re.compile(r"^(随便写|随便|不知道|无所谓|都行|你看着办|看着办|乱写|写点啥|随便来点)$", re.I)


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _extract_json(text: str) -> dict[str, Any] | None:
    raw = _text(text)
    if not raw:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S | re.I)
    if fenced:
        raw = fenced.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start:end + 1]
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _question_set(kind: str) -> list[dict[str, Any]]:
    if kind == "outline":
        return [
            {"question": "这本书的核心题材是什么？", "options": ["玄幻修仙", "都市异能", "历史权谋", "科幻末世"]},
            {"question": "主角开局状态更接近哪一种？", "options": ["废柴逆袭", "强者重生", "身份隐藏", "普通人卷入大局"]},
            {"question": "你最想突出的阅读爽点是什么？", "options": ["升级突破", "复仇打脸", "宗门经营", "感情拉扯"]},
        ]
    if kind == "capability":
        return [
            {"question": "你现在最想推进哪件事？", "options": ["生成/打磨大纲", "补角色/设定", "写正文/改正文", "查连续性"]},
            {"question": "结果希望怎么交付？", "options": ["只给建议", "生成待确认草稿", "列出要改的文件"]},
            {"question": "这次优先参考哪里？", "options": ["当前文件", "全书设定", "指定章节", "由 AI 自动检索"]},
        ]
    if kind == "low_value":
        return [
            {"question": "你想先从哪类内容开始？", "options": ["写大纲", "补角色", "补世界观", "写正文"]},
            {"question": "作品大概是什么类型？", "options": ["玄幻修仙", "都市异能", "古代权谋", "还没想好"]},
            {"question": "AI 这次做到什么程度？", "options": ["先给方向", "生成一版待确认草稿", "先问我更多问题"]},
        ]
    return [
        {"question": "你希望我做哪类事？", "options": ["生成新内容", "修改当前内容", "检查逻辑连续性", "补充设定"]},
        {"question": "这次主要参考哪里？", "options": ["当前文件", "指定章节", "全书设定", "由 AI 自动检索"]},
        {"question": "结果怎么处理？", "options": ["只给建议", "生成待确认草稿", "列出要改的文件"]},
    ]


def _is_unsafe(text: str) -> bool:
    return any(
        pattern.search(text)
        for pattern in [
            re.compile(r"(?:教我|如何|怎么|教程|方法).*(?:制毒|炸药|爆炸|杀人|诈骗|盗号|恐袭|自杀)"),
            re.compile(r"(?:报复社会|恐怖袭击|炸学校|伤害现实|屠杀现实)"),
        ]
    )


def _latest_outline(db: Session, novel_id: str) -> Outline | None:
    return db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()


def _confirmed_outline(db: Session, novel_id: str) -> Outline | None:
    return db.query(Outline).filter(
        Outline.novel_id == novel_id,
        Outline.confirmed == True,  # noqa: E712
    ).order_by(Outline.version.desc()).first()


def _current_kind(payload: dict[str, Any]) -> str:
    current_file = payload.get("current_file")
    if isinstance(current_file, dict) and current_file.get("kind"):
        return _text(current_file.get("kind"))
    return _text(payload.get("context_type"), "outline")


def _outline_file(status: str = "pending", label: str = "大纲") -> dict[str, Any]:
    return {"id": "outline", "label": label, "path": "outline/outline.md", "kind": "outline", "status": status}


def _synopsis_file(status: str = "pending") -> dict[str, Any]:
    return {"id": "book_synopsis", "label": "作品简介", "path": "book/synopsis.md", "kind": "synopsis", "status": status}


def _engine_status(db: Session, novel_id: str) -> dict[str, Any]:
    latest = _latest_outline(db, novel_id)
    confirmed = _confirmed_outline(db, novel_id)
    return {
        "has_outline": bool(latest and latest.content),
        "outline_confirmed": bool(confirmed),
        "latest_outline_version": latest.version if latest else None,
        "confirmed_outline_version": confirmed.version if confirmed else None,
    }


def _rule_intent(db: Session, payload: dict[str, Any]) -> dict[str, Any] | None:
    message = _text(payload.get("user_message"))
    normalized = re.sub(r"\s+", "", message)
    context_type = _text(payload.get("context_type"), "outline")
    status = _engine_status(db, payload["novel_id"])
    current_kind = _current_kind(payload)
    current_file = payload.get("current_file") if isinstance(payload.get("current_file"), dict) else {}
    current_preview = _text(current_file.get("content_preview")) if isinstance(current_file, dict) else ""
    has_outline = status["has_outline"] or (current_kind == "outline" and bool(current_preview))

    if not normalized:
        return {
            "intent": "clarify",
            "confidence": 1,
            "needs_clarification": True,
            "reason": "用户还没有说明要做什么。",
            "response_message": "你可以让我生成大纲、打磨设定、创建角色、写正文或检查连续性。先选几个方向，我再继续。",
            "questions": _question_set("capability"),
            "read_files": [],
            "write_targets": [],
        }
    if CAPABILITY_RE.search(normalized):
        return {
            "intent": "ask_question",
            "confidence": 0.99,
            "needs_clarification": False,
            "reason": "用户在询问 AI 助手能力，应直接说明可用能力，不进入追问流程。",
            "response_message": (
                "我能帮你做这些：\n"
                "1. 生成或打磨大纲、简介、分卷细纲。\n"
                "2. 创建或修改角色卡、世界观、地点、势力、道具和自定义设定。\n"
                "3. 根据已确认细纲写正文草稿，或改写当前正文。\n"
                "4. 检查连续性，补录角色状态、道具归属、伏笔和章节记忆。\n"
                "5. 自动阅读当前文件和相关资料，列出本次参考文件、可能修改文件和审批项。\n\n"
                "所有新增和修改都会先生成待确认草稿或待审阅卡片，不会直接覆盖正式内容。"
            ),
            "questions": [],
            "read_files": [],
            "write_targets": [],
        }
    if LOW_VALUE_RE.match(normalized):
        return {
            "intent": "clarify",
            "confidence": 0.98,
            "needs_clarification": True,
            "reason": "用户输入过于宽泛，直接生成容易写偏。",
            "response_message": "这个输入还不够落地，我先帮你收口成一个可以执行的创作任务。",
            "questions": _question_set("low_value"),
            "read_files": [],
            "write_targets": [],
        }
    if _is_unsafe(normalized):
        return {
            "intent": "reject",
            "confidence": 1,
            "needs_clarification": True,
            "reason": "请求涉及现实伤害或违法内容。",
            "response_message": "这个方向不适合直接生成，我建议换成纯虚构冲突。",
            "questions": [
                {
                    "question": "要不要改成纯虚构冲突？",
                    "options": ["门派争斗", "秘境危机", "反派阴谋", "修炼走火入魔"],
                }
            ],
            "read_files": [],
            "write_targets": [],
        }
    if context_type == "outline" or current_kind == "outline":
        if VAGUE_OUTLINE_ACTION_RE.match(normalized):
            return {
                "intent": "clarify",
                "confidence": 0.98,
                "needs_clarification": True,
                "reason": "用户只说要写大纲，但缺少题材、主角、冲突或目标字数。",
                "response_message": "我先确认几个关键点，避免大纲一上来就写偏。",
                "questions": _question_set("outline"),
                "read_files": [],
                "write_targets": [{"id": "outline", "label": "大纲", "path": "outline/outline.md", "kind": "outline", "status": "pending"}],
            }
        # 已经有大纲时，用户提到“简介/卖点/节奏/角色/分卷”等内容，优先视为修改当前大纲。
        # 这条必须放在“帮我写个大纲”的模糊追问前，否则“修改大纲内简介”会被误拦截。
        if has_outline and OUTLINE_REVISE_RE.search(normalized):
            return {
                "intent": "revise_outline",
                "confidence": 0.97,
                "needs_clarification": False,
                "reason": "当前打开的是大纲，用户在修改大纲内的某个段落或设定。",
                "questions": [],
                "read_files": [_outline_file("reference", "当前大纲")],
                "write_targets": [_outline_file("pending", "大纲修改稿")],
            }
        if len(normalized) <= 14 and "大纲" in normalized and not OUTLINE_DETAIL_RE.search(normalized):
            return {
                "intent": "clarify",
                "confidence": 0.98,
                "needs_clarification": True,
                "reason": "用户只说要写大纲，但缺少题材、主角、冲突或目标字数。",
                "response_message": "我先确认几个关键点，避免大纲一上来就写偏。",
                "questions": _question_set("outline"),
                "read_files": [],
                "write_targets": [{"id": "outline", "label": "大纲", "path": "outline/outline.md", "kind": "outline", "status": "pending"}],
            }
        if any(word in normalized for word in ["重做", "重写", "推翻", "不要这个方案", "清空重来"]):
            return {
                "intent": "rewrite_outline",
                "confidence": 0.92,
                "needs_clarification": False,
                "reason": "用户要求舍弃当前方案重新规划大纲。",
                "questions": [],
                "read_files": [{"id": "outline", "label": "当前大纲", "path": "outline/outline.md", "kind": "outline"}],
                "write_targets": [{"id": "outline", "label": "大纲修改稿", "path": "outline/outline.md", "kind": "outline", "status": "pending"}],
            }

        if "大纲" in normalized or not has_outline:
            return {
                "intent": "revise_outline" if has_outline else "generate_outline",
                "confidence": 0.9,
                "needs_clarification": False,
                "reason": "当前页面是大纲，且用户给出了可执行的大纲方向。",
                "questions": [],
                "read_files": [_outline_file("reference", "当前大纲")] if has_outline else [],
                "write_targets": [_outline_file("pending", "大纲")],
            }
    if context_type in {"synopsis", "novel_synopsis"} or current_kind == "synopsis":
        return {
            "intent": "revise_synopsis",
            "confidence": 0.93,
            "needs_clarification": False,
            "reason": "当前打开的是作品简介，用户要求生成或打磨简介。",
            "questions": [],
            "read_files": [_outline_file("reference", "已确认大纲"), _synopsis_file("reference")],
            "write_targets": [_synopsis_file("pending")],
        }
    if SYNOPSIS_REVISE_RE.search(normalized) and not (context_type == "outline" or current_kind == "outline"):
        return {
            "intent": "revise_synopsis",
            "confidence": 0.88,
            "needs_clarification": False,
            "reason": "用户要求修改正式作品简介。",
            "questions": [],
            "read_files": [_outline_file("reference", "已确认大纲"), _synopsis_file("reference")],
            "write_targets": [_synopsis_file("pending")],
        }
    if context_type == "characters" or current_kind == "characters":
        matched_names: list[str] = []
        for character in db.query(Character).filter(Character.novel_id == payload["novel_id"]).all():
            names = [character.name, *(character.aliases or [])]
            if any(name and name in normalized for name in names):
                matched_names.append(character.name)
        if len(set(matched_names)) == 1 and re.search(r"(修改|更新|调整|完善|改成|改为|境界|动机|势力|阵营|状态|角色信息)", normalized):
            target = {
                "id": _text(current_file.get("id") or "characters"),
                "label": current_file.get("label") or "角色设定",
                "path": current_file.get("path") or "characters/characters.json",
                "kind": current_file.get("kind") or "characters",
                "status": "pending",
            }
            return {
                "intent": "revise_character",
                "confidence": 0.96,
                "needs_clarification": False,
                "reason": f"用户要求修改单个角色「{matched_names[0]}」。",
                "questions": [],
                "read_files": [target],
                "write_targets": [target],
            }
    if re.search(
        r"(创建|新增|加|补).*(角色|人物|男主|女主|反派|男配|女配|伙伴|导师|路人|配角)|"
        r"(角色|人物|男主|女主|反派|男配|女配|伙伴|导师|路人|配角).*(创建|新增|加|补)",
        normalized,
    ):
        return {
            "intent": "create_character",
            "confidence": 0.95,
            "needs_clarification": False,
            "reason": "用户要求创建或补充角色。",
            "questions": [],
            "read_files": [{"id": "characters", "label": "角色设定", "path": "characters/characters.json", "kind": "characters"}],
            "write_targets": [{"id": "characters", "label": "角色设定", "path": "characters/characters.json", "kind": "characters", "status": "pending"}],
        }
    if re.search(
        r"(创建|新增|加|补|完善).*(设定|灵兽|道具|法宝|功法|技能|势力|组织|地点|地图|世界观|规则)|"
        r"(设定|灵兽|道具|法宝|功法|技能|势力|组织|地点|地图|世界观|规则).*(创建|新增|加|补|完善)",
        normalized,
    ):
        target_label = "当前设定文件" if context_type == "worldbuilding" else "设定文件"
        return {
            "intent": "revise_worldbuilding",
            "confidence": 0.9,
            "needs_clarification": False,
            "reason": "用户要求新增或完善世界观/设定类内容。",
            "questions": [],
            "read_files": [{"id": "worldbuilding", "label": "世界观设定", "path": "world/worldbuilding.json", "kind": "worldbuilding"}],
            "write_targets": [{"id": "worldbuilding", "label": target_label, "path": "world/worldbuilding.json", "kind": "worldbuilding", "status": "pending"}],
        }
    return None


def _normalize_plan(plan: dict[str, Any] | IntentPlan | None, payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(plan, IntentPlan):
        plan = plan.to_legacy_dict()
    plan = plan or {}
    intent = _text(plan.get("intent"), "ask_question")
    if intent not in ALLOWED_INTENTS:
        intent = "ask_question"
    questions = plan.get("questions") if isinstance(plan.get("questions"), list) else []
    read_files = plan.get("read_files") if isinstance(plan.get("read_files"), list) else []
    write_targets = plan.get("write_targets") if isinstance(plan.get("write_targets"), list) else []
    current_file = payload.get("current_file")
    if isinstance(current_file, dict) and current_file.get("label"):
        file_id = _text(current_file.get("id") or current_file.get("kind") or current_file.get("path"), "current")
        current_file_ref = {
            "id": file_id,
            "label": current_file.get("label") or "当前文件",
            "path": current_file.get("path") or "current",
            "kind": current_file.get("kind") or payload.get("context_type") or "current",
            "status": "pending",
        }
        if not any(item.get("id") == file_id for item in read_files if isinstance(item, dict)):
            read_files.insert(0, {**current_file_ref, "status": "reference"})
        message = _text(payload.get("user_message"))
        explicit_batch = any(word in message for word in ["全部", "所有", "整库", "全库", "批量", "全书"])
        if (
            intent in {"revise_worldbuilding", "create_character", "revise_character"}
            and current_file.get("scope") in {"current_file_only", "proposal_only"}
            and not explicit_batch
        ):
            write_targets = [current_file_ref]
    return {
        "intent": intent,
        "confidence": float(plan.get("confidence") or 0.65),
        "needs_clarification": bool(plan.get("needs_clarification") or intent in {"clarify", "reject"}),
        "reason": _text(plan.get("reason"), "AI 已完成意图识别。"),
        "response_message": _text(plan.get("response_message")),
        "questions": questions[:5],
        "read_files": [item for item in read_files if isinstance(item, dict)][:8],
        "write_targets": [item for item in write_targets if isinstance(item, dict)][:8],
    }


async def _dynamic_clarification_plan(
    db: Session,
    payload: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    """Ask the model to create only the clarification questions this turn needs.

    Local rules decide when a request is too ambiguous to execute safely; this
    model pass decides what to ask, so we do not keep showing a fixed template.
    """

    message = _text(payload.get("user_message"))
    current_file = payload.get("current_file") if isinstance(payload.get("current_file"), dict) else {}
    catalog = build_file_catalog(db, payload["novel_id"])
    file_overview = "\n".join(f"- {item.id}｜{item.kind}｜{item.label}｜{item.path}" for item in catalog[:40])
    status = _engine_status(db, payload["novel_id"])
    fallback_questions = fallback.get("questions") if isinstance(fallback.get("questions"), list) else []

    system_prompt = "你是小说创作产品里的追问规划器。只输出 JSON，不要 Markdown。"
    user_prompt = f"""
用户消息：{message}
当前页面：{payload.get("context_type") or "outline"}
当前文件：{json.dumps(current_file, ensure_ascii=False)}
作品状态：{json.dumps(status, ensure_ascii=False)}
本地规则判断：{fallback.get("reason") or ""}

作品文件目录：
{file_overview or "暂无文件"}

你的任务：
1. 判断这个请求是否真的需要追问。只有缺少“无法安全继续”的关键信息时才追问。
2. 如果需要追问，生成 1-3 个非常具体的问题，每题 2-5 个选项；优先少问，能 1-2 题解决就不要问 3 题。
3. 问题必须根据用户当前语境生成，不要使用固定模板。
4. 选项要短，适合点击；不要包含“其他/自定义”，前端会提供自定义输入。
5. 如果用户只是问“你能做什么/怎么用”，不要追问，直接返回 ask_question 和能力说明。
6. 如果用户只是“帮我写个大纲”且没有题材、主角、冲突、目标规模等，则需要追问。
7. 如果可以直接继续，返回 needs_clarification=false，并给出最合适的 intent。
8. 不要机械输出“题材、开局、爽点”三连问；除非这三个点确实是当前语境最缺的。

输出 JSON：
{{
  "intent": "clarify",
  "confidence": 0.0,
  "needs_clarification": true,
  "reason": "中文一句话说明为什么需要/不需要追问",
  "response_message": "给用户看的简短说明",
  "questions": [{{"question": "问题", "options": ["选项1", "选项2"]}}],
  "read_files": [],
  "write_targets": []
}}
"""
    try:
        structured, meta = await generate_structured(
            IntentPlan,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            repair_context=f"用户消息：{message}\n当前上下文：{payload.get('context_type') or 'outline'}",
            max_retries=2,
            temperature=0.15,
        )
        plan = _normalize_plan(structured, payload)
        if plan["needs_clarification"] and not plan["questions"]:
            plan["questions"] = fallback_questions[:3]
        if not plan["response_message"]:
            plan["response_message"] = fallback.get("response_message") or "我先确认几个关键点，避免写偏。"
        plan["read_files"] = plan["read_files"] or fallback.get("read_files") or []
        plan["write_targets"] = plan["write_targets"] or fallback.get("write_targets") or []
        plan["_structured_meta"] = meta
        return plan
    except Exception as exc:
        plan = _normalize_plan(fallback, payload)
        plan["_structured_error"] = {"message": str(exc)}
        return plan


def _apply_router_policy(
    db: Session,
    payload: dict[str, Any],
    plan: dict[str, Any],
    rule: dict[str, Any] | None,
) -> dict[str, Any]:
    """把 AI 分类结果收敛到产品工作流，不让模型把页面上下文读歪。"""
    normalized = re.sub(r"\s+", "", _text(payload.get("user_message")))
    context_type = _text(payload.get("context_type"), "outline")
    current_kind = _current_kind(payload)
    status = _engine_status(db, payload["novel_id"])
    current_file = payload.get("current_file") if isinstance(payload.get("current_file"), dict) else {}
    current_preview = _text(current_file.get("content_preview")) if isinstance(current_file, dict) else ""
    has_outline_context = status["has_outline"] or (current_kind == "outline" and bool(current_preview))

    if rule and rule.get("intent") in {"clarify", "reject"}:
        return _normalize_plan(rule, payload)

    if (context_type == "outline" or current_kind == "outline") and has_outline_context:
        if OUTLINE_REVISE_RE.search(normalized) or plan["intent"] in {"generate_synopsis", "revise_synopsis"}:
            return _normalize_plan({
                "intent": "revise_outline",
                "confidence": max(float(plan.get("confidence") or 0), 0.96),
                "needs_clarification": False,
                "reason": "当前文件是大纲，用户要求调整的是大纲内的内容，不是正式简介文件。",
                "questions": [],
                "read_files": [_outline_file("reference", "当前大纲")],
                "write_targets": [_outline_file("pending", "大纲修改稿")],
            }, payload)

    if rule and rule.get("intent") and plan["intent"] in {"ask_question", "clarify"}:
        return _normalize_plan(rule, payload)

    if rule and float(rule.get("confidence") or 0) >= 0.92:
        # 高置信本地策略只处理产品边界，比如当前页、未确认大纲、角色创建。
        return _normalize_plan(rule, payload)

    if context_type == "outline" and not status["has_outline"] and plan["intent"] in {"revise_outline", "ask_question"}:
        return _normalize_plan({
            "intent": "generate_outline",
            "confidence": 0.85,
            "needs_clarification": False,
            "reason": "当前还没有大纲，用户提供了可执行方向，应生成第一版大纲。",
            "questions": [],
            "read_files": [],
            "write_targets": [_outline_file("pending", "大纲")],
        }, payload)

    return plan


def _gatekeeper(db: Session, payload: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    status = _engine_status(db, payload["novel_id"])
    intent = plan["intent"]
    if intent in WRITE_INTENTS_NEED_CONFIRMED_OUTLINE and not status["outline_confirmed"]:
        return {
            "blocked": True,
            "reason": "当前大纲还没有确认。为了避免后续角色、世界观、简介和正文建立在不稳定方案上，AI 不会正式新增或修改这些文件。",
            "message": "当前大纲还没确认，我先不改简介、角色、世界观或正文。你可以继续让我打磨大纲，或者确认大纲后再让我生成/修改这些内容。",
            "questions": [
                {"question": "接下来要怎么做？", "options": ["继续打磨当前大纲", "先确认大纲", "只给建议不写入文件"]},
            ],
            "allowed_intents": ["generate_outline", "revise_outline", "rewrite_outline", "ask_question"],
        }
    return {"blocked": False}


async def classify_intent(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    rule = _rule_intent(db, payload)
    if rule and rule["intent"] == "clarify":
        return await _dynamic_clarification_plan(db, payload, rule)
    if rule and rule["intent"] in {"reject", "ask_question"}:
        return _normalize_plan(rule, payload)

    catalog = build_file_catalog(db, payload["novel_id"])
    file_overview = "\n".join(f"- {item.id}｜{item.kind}｜{item.label}｜{item.path}" for item in catalog[:80])
    recent_messages = payload.get("messages") or []
    history = "\n".join(f"{item.get('role')}: {item.get('content')}" for item in recent_messages[-8:] if isinstance(item, dict))
    system_prompt = "你是小说创作系统的专业意图分类器。只输出 JSON，不要输出解释、Markdown 或代码块。"
    user_prompt = f"""
当前上下文：{payload.get("context_type") or "outline"}
当前文件：{json.dumps(payload.get("current_file") or {}, ensure_ascii=False)}
用户消息：{payload.get("user_message") or ""}

最近对话：
{history or "无"}

当前作品可用文件目录：
{file_overview or "暂无文件"}

当前作品状态：
{json.dumps(_engine_status(db, payload["novel_id"]), ensure_ascii=False)}

可选意图：
{", ".join(sorted(ALLOWED_INTENTS))}

判断规则：
1. 用户意图不清时必须返回 clarify，并给 2-4 个可选问题。
2. 如果用户只是说“帮我写个大纲/生成大纲/给我创建一下大纲”但没有题材、主角、冲突、目标字数等有效信息，必须 clarify。
3. 如果当前文件是 outline，大纲里“简介/卖点/字数/主角/分卷/节奏”的调整都属于 revise_outline，不要误判为 revise_synopsis。
4. 如果当前文件是 synopsis，才把“简介修改”判成 revise_synopsis。
5. 如果需要新增或修改角色、道具、设定，只能返回待确认写入目标，不允许直接写入。
6. 大纲未确认时，除 generate_outline/revise_outline/rewrite_outline/ask_question 外，不要规划正式写入。
7. read_files 是建议读取文件；write_targets 是建议修改文件，status 用 pending。
8. 不要虚构已读文件，只能从目录里选，或者用 current_file。

典型例子：
- 当前文件 outline，用户“把简介字数提高到300字” => revise_outline，写入目标 outline。
- 当前文件 outline，用户“多加一些后宫和感情线” => revise_outline，写入目标 outline。
- 当前文件 synopsis，用户“简介更燃一点” => revise_synopsis，写入目标 book_synopsis。
- 用户“给我创建一下大纲”且没有具体题材/主角/冲突 => clarify。
- 用户“创建一个叫林羽的女主” => create_character，但大纲未确认时会被系统门禁拦截。

输出 JSON：
{{
  "intent": "generate_outline",
  "confidence": 0.0,
  "needs_clarification": false,
  "reason": "中文一句话",
  "questions": [{{"question": "问题", "options": ["选项1", "选项2"]}}],
  "read_files": [{{"id": "outline", "label": "大纲", "path": "outline/outline.md", "kind": "outline"}}],
  "write_targets": [{{"id": "outline", "label": "大纲", "path": "outline/outline.md", "kind": "outline", "status": "pending"}}]
}}
"""
    try:
        structured, meta = await generate_structured(
            IntentPlan,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            repair_context=f"用户消息：{payload.get('user_message') or ''}\n当前上下文：{payload.get('context_type') or 'outline'}",
            max_retries=3,
            temperature=0.1,
        )
        plan = _normalize_plan(structured, payload)
        plan["_structured_meta"] = meta
        return _apply_router_policy(db, payload, plan, rule)
    except StructuredOutputError as exc:
        if rule:
            plan = _normalize_plan(rule, payload)
            plan["_structured_error"] = {"message": str(exc), "raw": exc.raw, "attempts": exc.attempts}
            return _apply_router_policy(db, payload, plan, rule)
        clarification = clarification_for(payload.get("user_message") or "", payload.get("context_type") or "")
        if clarification:
            return _normalize_plan({
                "intent": "clarify",
                "confidence": 0.8,
                "needs_clarification": True,
                "reason": "AI 分类输出格式异常，系统使用本地规则发起追问。",
                "response_message": clarification.get("message") or "我先确认几个关键点。",
                "questions": clarification.get("questions") or [],
                "read_files": [],
                "write_targets": [],
            }, payload)
        return _normalize_plan({
            "intent": "clarify",
            "confidence": 0.5,
            "needs_clarification": True,
            "reason": "AI 分类输出格式异常，无法安全判断要修改哪些文件。",
            "response_message": "我没能稳定识别这次需求。请先选一个方向，我再继续。",
            "questions": _question_set("generic"),
            "read_files": [],
            "write_targets": [],
            "_structured_error": {"message": str(exc), "raw": exc.raw, "attempts": exc.attempts},
        }, payload)
    except Exception:
        if rule:
            return _apply_router_policy(db, payload, _normalize_plan(rule, payload), rule)
        clarification = clarification_for(payload.get("user_message") or "", payload.get("context_type") or "")
        if clarification:
            return _normalize_plan({
                "intent": "clarify",
                "confidence": 0.8,
                "needs_clarification": True,
                "reason": "AI 分类不可用，系统使用本地规则发起追问。",
                "questions": clarification.get("questions") or [],
                "read_files": [],
                "write_targets": [],
            }, payload)
        return _normalize_plan({
            "intent": "ask_question",
            "confidence": 0.4,
            "reason": "AI 分类不可用，系统降级为普通问答。",
            "read_files": [],
            "write_targets": [],
        }, payload)


def create_run(db: Session, payload: dict[str, Any], job_id: str | None) -> AIWorkflowRun:
    run = AIWorkflowRun(
        novel_id=payload["novel_id"],
        job_id=job_id,
        context_type=payload.get("context_type") or "outline",
        context_id=payload.get("context_id"),
        user_message=payload.get("user_message") or "",
        status="running",
        payload={"current_file": payload.get("current_file") or {}, "context_files": payload.get("context_files") or []},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def add_step(
    db: Session,
    run: AIWorkflowRun,
    *,
    title: str,
    status: str = "done",
    detail: str | None = None,
    files: list[dict[str, Any]] | None = None,
    payload: dict[str, Any] | None = None,
) -> AIWorkflowStep:
    count = db.query(AIWorkflowStep).filter(AIWorkflowStep.run_id == run.id).count()
    step = AIWorkflowStep(
        run_id=run.id,
        step_order=count + 1,
        title=title,
        status=status,
        detail=detail,
        files=files or [],
        payload=payload or {},
        finished_at=datetime.utcnow() if status in {"done", "failed", "skipped"} else None,
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def finish_run(db: Session, run: AIWorkflowRun, *, status: str, summary: str, payload: dict[str, Any] | None = None):
    run.status = status
    run.result_summary = summary
    run.payload = {**(run.payload or {}), **(payload or {})}
    run.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(run)


def serialize_step(step: AIWorkflowStep) -> dict[str, Any]:
    return {
        "id": step.id,
        "step_order": step.step_order,
        "title": step.title,
        "status": step.status,
        "detail": step.detail,
        "files": step.files or [],
        "payload": step.payload or {},
        "created_at": step.created_at.isoformat() if step.created_at else None,
        "finished_at": step.finished_at.isoformat() if step.finished_at else None,
    }


def _steps_for_run(db: Session, run_id: str) -> list[dict[str, Any]]:
    steps = db.query(AIWorkflowStep).filter(AIWorkflowStep.run_id == run_id).order_by(AIWorkflowStep.step_order.asc()).all()
    return [serialize_step(step) for step in steps]


def _result_with_workflow(db: Session, run: AIWorkflowRun, result: dict[str, Any]) -> dict[str, Any]:
    return {
        **result,
        "workflow_run_id": run.id,
        "workflow_steps": _steps_for_run(db, run.id),
        "intent": run.intent,
        "confidence": run.confidence,
    }


async def _execute_outline_intent(db: Session, payload: dict[str, Any], job_id: str, intent: str) -> dict[str, Any]:
    from app.routers.ai import _execute_outline_job

    mode = "rewrite" if intent == "rewrite_outline" else "revise"
    result = await _execute_outline_job(
        db,
        {
            "novel_id": payload["novel_id"],
            "idea": payload.get("user_message") or "",
            "outline_chat": True,
            "mode": mode,
        },
        job_id,
    )
    if result.get("saved"):
        outline = result.get("outline") or {}
        # 大纲保存后，分析变更影响范围
        impact_report_text = ""
        try:
            from app.services.outline_linkage_service import analyze_outline_change_impact
            # 获取旧大纲（上一个版本）
            from app.models import Outline
            new_outline = (
                db.query(Outline)
                .filter(
                    Outline.novel_id == payload["novel_id"],
                    Outline.version == outline.get("version", 1),
                )
                .order_by(Outline.created_at.desc())
                .first()
            )
            old_outlines = (
                db.query(Outline)
                .filter(Outline.novel_id == payload["novel_id"], Outline.version < outline.get("version", 999))
                .order_by(Outline.version.desc())
                .first()
            )
            if new_outline:
                report = analyze_outline_change_impact(db, payload["novel_id"], old_outlines, new_outline)
                impact_report_text = "\n\n" + report.as_text()
                pending_items = report.as_proposal_items()
                if pending_items:
                    ai_job_service.set_running(job_id, "大纲已保存，正在分析影响范围...")
        except Exception:
            impact_report_text = ""

        return {
            "message": f"已生成大纲 v{outline.get('version', 1)}。如果不满意，可以继续告诉我哪里要改。{impact_report_text}",
            "mode": "answer",
            "outline_result": result,
            "outline": outline,
            "changed_files": [
                {"id": "outline", "label": "大纲", "path": "outline/outline.md", "kind": "outline", "status": "done"},
                {"id": "synopsis-draft", "label": "简介草案", "path": "book/synopsis.md", "kind": "synopsis", "status": "draft"},
            ],
        }
    return {
        "message": "已生成待审阅的大纲修改稿。请在大纲编辑器里逐处采用或放弃，确认满意后再存档。",
        "mode": "answer",
        "outline_result": result,
        "draft_outline": result.get("draft_outline"),
        "changed_files": [
            {"id": "outline", "label": "大纲修改稿", "path": "outline/outline.md", "kind": "outline", "status": "pending"}
        ],
    }


async def _execute_entity_intent(db: Session, payload: dict[str, Any], job_id: str) -> dict[str, Any]:
    from app.routers.ai import _chat_entity_proposal

    result = _chat_entity_proposal(db, payload)
    if result:
        ai_job_service.update_partial(job_id, result.get("message") or "", "已生成待确认卡片")
        return result
    return {
        "message": "可以创建角色，但我还缺少角色名字或定位。先确认几个点后，我会生成待审阅角色卡。",
        "mode": "clarify",
        "questions": _question_set("generic"),
        "context_files": [{"id": "characters", "label": "角色设定", "path": "characters/characters.json", "kind": "characters"}],
        "changed_files": [{"id": "characters", "label": "角色设定", "path": "characters/characters.json", "kind": "characters", "status": "pending"}],
    }


async def _execute_synopsis_intent(db: Session, payload: dict[str, Any], job_id: str) -> dict[str, Any]:
    from app.routers.ai import _execute_book_synopsis_job

    result = await _execute_book_synopsis_job(
        db,
        {
            "novel_id": payload["novel_id"],
            "extra_instruction": payload.get("user_message") or "根据已确认大纲生成作品简介修改稿。",
            "dry_run": True,
        },
        job_id,
    )
    synopsis = _text(result.get("synopsis"))
    return {
        "message": "已生成作品简介待确认修改稿。它不会直接覆盖正式简介，请在简介编辑器里确认采用或放弃。",
        "mode": "answer",
        "synopsis_draft": synopsis,
        "context_files": [_outline_file("reference", "已确认大纲"), _synopsis_file("reference")],
        "changed_files": [_synopsis_file("pending")],
    }


def _engine_base_context(db: Session, payload: dict[str, Any]) -> str:
    novel = db.query(Novel).filter(Novel.id == payload["novel_id"]).first()
    latest = _latest_outline(db, payload["novel_id"])
    confirmed = _confirmed_outline(db, payload["novel_id"])
    current = payload.get("current_file") if isinstance(payload.get("current_file"), dict) else {}
    lines = [
        f"你是小说《{novel.title if novel else '当前作品'}》的专业 AI 创作引擎。",
        "你必须像编辑器 Agent 一样工作：先判断意图，再说明读取了哪些资料，再输出待确认方案。",
        "任何写入、覆盖、新增、删除都不能直接执行，只能生成待审阅草稿或提案。",
        f"当前打开文件：{current.get('label') or payload.get('context_type') or '未知'}。",
    ]
    if isinstance(current, dict) and current.get("scope") in {"current_file_only", "proposal_only"}:
        lines.append("范围锁定：除非作者明确说全部/批量/整库，否则本次只处理当前文件或当前提案，不得扩散修改整套设定。")
    if latest and latest.content:
        lines.append(f"当前最新大纲 v{latest.version}（{'已确认' if latest.confirmed else '未确认'}）：\n{latest.content[:1800]}")
    else:
        lines.append("当前还没有可用大纲。")
    if isinstance(current, dict) and current.get("content_preview"):
        lines.append(f"当前编辑器草稿片段：\n{_text(current.get('content_preview'))[:1800]}")
    if confirmed:
        lines.append(f"已确认大纲版本：v{confirmed.version}。")
    else:
        lines.append("大纲尚未确认。除打磨大纲外，正式简介、角色、世界观、正文写入都必须先等待作者确认大纲。")
    return "\n\n".join(lines)


async def _execute_generic_intent(db: Session, payload: dict[str, Any], job_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    base_context = _engine_base_context(db, payload)
    memory_pack = build_memory_pack(
        db,
        novel_id=payload["novel_id"],
        query=payload.get("user_message") or "",
        context_type=payload.get("context_type") or "outline",
        selected_file_ids=payload.get("context_files") or [],
    )
    smart_context = build_smart_chat_context(
        db,
        novel_id=payload["novel_id"],
        context_type=payload.get("context_type") or "outline",
        context_id=payload.get("context_id"),
        user_message=payload.get("user_message") or "",
        selected_file_ids=payload.get("context_files") or [],
        base_context=f"{base_context}\n\n{memory_pack.as_prompt()}",
    )
    system_prompt = smart_context["system_prompt"] + f"""

【本次工作流识别结果】
意图：{plan["intent"]}
原因：{plan["reason"]}
建议修改文件：{json.dumps(plan.get("write_targets") or [], ensure_ascii=False)}

重要：如果涉及改文件，只能输出待确认方案，不能说已经写入。
"""

    # 注入前端传来的额外上下文（如记忆上下文）
    extra_contexts = payload.get("context_files") or []
    for extra in extra_contexts:
        if isinstance(extra, str) and extra.startswith("memory:"):
            system_prompt += f"\n\n【记忆上下文（前端注入）】\n{extra[len('memory:'):]}"

    messages = [
        {"role": item.get("role", "user"), "content": item.get("content", "")}
        for item in (payload.get("messages") or [])[-8:]
        if isinstance(item, dict)
    ]
    messages.append({"role": "user", "content": payload.get("user_message") or ""})
    ai_job_service.set_running(job_id, "AI 正在按工作流阅读资料并生成方案...")
    result_text = await ai_service.generate_once(system_prompt, "\n".join(f"{m['role']}：{m['content']}" for m in messages))
    ai_job_service.update_partial(job_id, result_text, "AI 已生成待审阅回复")
    return {
        "message": result_text,
        "mode": "answer",
        "context_files": smart_context["context_files"] or [item.model_dump() for item in memory_pack.source_files],
        "search_terms": smart_context["terms"] or memory_pack.search_terms,
        "changed_files": plan.get("write_targets") or [],
        "memory": memory_pack.model_dump(),
    }


async def execute_assistant_workflow(db: Session, payload: dict[str, Any], job_id: str) -> dict[str, Any]:
    novel = db.query(Novel).filter(Novel.id == payload["novel_id"]).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    run = create_run(db, payload, job_id)
    try:
        runtime = create_runtime()

        async def classify_node(state: AssistantGraphState) -> AssistantGraphState:
            ai_job_service.set_running(job_id, "AI 正在识别意图...")
            add_step(db, run, title="识别意图", detail="判断用户想生成、修改、补设定、写正文还是需要追问。")
            plan = await classify_intent(db, state.payload)
            run.intent = plan["intent"]
            run.confidence = plan["confidence"]
            run.payload = {**(run.payload or {}), "intent_plan": plan, "runtime": "assistant_graph"}
            db.commit()
            add_step(
                db,
                run,
                title="意图识别完成",
                detail=f"{plan['reason']}（置信度 {plan['confidence']:.2f}）",
                files=plan.get("read_files") or [],
                payload={
                    "intent": plan["intent"],
                    "questions": plan.get("questions") or [],
                    "structured": plan.get("_structured_meta"),
                    "structured_error": plan.get("_structured_error"),
                },
            )
            state.plan = plan
            state.next_node = "gate"
            return state

        async def gate_node(state: AssistantGraphState) -> AssistantGraphState:
            plan = state.plan or {}
            gate = _gatekeeper(db, state.payload, plan)
            state.gate = gate
            if gate["blocked"]:
                add_step(
                    db,
                    run,
                    title="写入门禁拦截",
                    detail=gate["reason"],
                    files=plan.get("write_targets") or [],
                    payload={"allowed_intents": gate.get("allowed_intents") or []},
                )
                state.result = {
                    "message": gate["message"],
                    "mode": "clarify",
                    "questions": gate.get("questions") or [],
                    "context_files": plan.get("read_files") or [],
                    "changed_files": plan.get("write_targets") or [],
                }
                state.next_node = "finalize"
                return state

            if plan.get("needs_clarification") or plan.get("intent") in {"clarify", "reject"}:
                questions = plan.get("questions") or _question_set("outline" if state.payload.get("context_type") == "outline" else "generic")
                message = plan.get("response_message") or (
                    "我先确认几个关键点，避免直接写偏：" if plan.get("intent") != "reject" else "这个方向不适合直接生成，我建议换成纯虚构冲突："
                )
                add_step(db, run, title="发起追问", detail="用户补充选择后，会继续进入生成/修改流程。", payload={"questions": questions})
                state.result = {
                    "message": message,
                    "mode": "clarify",
                    "questions": questions,
                    "context_files": [],
                    "changed_files": plan.get("write_targets") or [],
                }
                state.next_node = "finalize"
                return state

            state.next_node = "load_memory"
            return state

        async def load_memory_node(state: AssistantGraphState) -> AssistantGraphState:
            plan = state.plan or {}
            memory_pack = build_memory_pack(
                db,
                novel_id=state.payload["novel_id"],
                query=state.payload.get("user_message") or "",
                context_type=state.payload.get("context_type") or "outline",
                selected_file_ids=state.payload.get("context_files") or [],
            )
            state.memory = memory_pack.model_dump()
            add_step(
                db,
                run,
                title="装载长期记忆",
                detail="使用项目自己的大纲、角色、设定、章节记忆和最近工作流记录，不依赖模型黑盒记忆。",
                files=[item.model_dump() for item in memory_pack.source_files],
                payload={"search_terms": memory_pack.search_terms, "facts_count": len(memory_pack.facts)},
            )
            add_step(
                db,
                run,
                title="规划读写范围",
                detail="优先读取当前打开文件，再按作品目录和用户关键词补充上下文。",
                files=plan.get("read_files") or [],
                payload={"write_targets": plan.get("write_targets") or []},
            )
            state.next_node = "execute"
            return state

        async def execute_node(state: AssistantGraphState) -> AssistantGraphState:
            plan = state.plan or {}
            intent = plan["intent"]
            if intent in {"generate_outline", "revise_outline", "rewrite_outline"}:
                add_step(db, run, title="生成大纲草稿", detail="大纲会进入编辑器审阅；确认前不会锁定后续设定。")
                result = await _execute_outline_intent(db, state.payload, job_id, intent)
            elif intent in {"generate_synopsis", "revise_synopsis"}:
                add_step(db, run, title="生成简介待确认稿", detail="简介只生成草稿，作者采用后才写入正式简介。")
                result = await _execute_synopsis_intent(db, state.payload, job_id)
            elif intent in {"create_character", "revise_character"}:
                add_step(db, run, title="生成待审阅角色卡", detail="只创建提案，作者通过后才会写入角色库。")
                result = await _execute_entity_intent(db, state.payload, job_id)
            elif intent == "ask_question" and plan.get("response_message"):
                add_step(db, run, title="回答能力说明", detail="这是普通问答，不触发文件修改或审批。")
                result = {
                    "message": plan["response_message"],
                    "mode": "answer",
                    "context_files": plan.get("read_files") or [],
                    "changed_files": [],
                }
            else:
                add_step(db, run, title="生成待确认方案", detail="根据检索到的资料组织答复，不直接覆盖文件。")
                result = await _execute_generic_intent(db, state.payload, job_id, plan)
            if state.memory and "memory" not in result:
                result["memory"] = state.memory
            state.result = result
            state.next_node = "finalize"
            return state

        async def finalize_node(state: AssistantGraphState) -> AssistantGraphState:
            plan = state.plan or {}
            result = state.result or {
                "message": "AI 工作流已完成，但没有生成可展示结果。",
                "mode": "answer",
            }
            add_step(
                db,
                run,
                title="生成结果",
                detail="结果已返回聊天框；如包含改动文件，请在对应编辑器或待审阅卡片中确认。",
                files=result.get("changed_files") or plan.get("write_targets") or [],
                payload={"mode": result.get("mode")},
            )
            summary = "已发起追问" if result.get("mode") == "clarify" else result.get("message", "")[:300]
            finish_run(db, run, status="completed", summary=summary, payload=result)
            state.result = _result_with_workflow(db, run, result)
            state.next_node = "end"
            return state

        runtime.add_node("classify", classify_node)
        runtime.add_node("gate", gate_node)
        runtime.add_node("load_memory", load_memory_node)
        runtime.add_node("execute", execute_node)
        runtime.add_node("finalize", finalize_node)

        final_state = await runtime.run(AssistantGraphState(payload=payload))
        return final_state.result or {}
    except Exception as exc:
        add_step(db, run, title="执行失败", status="failed", detail=str(exc))
        finish_run(db, run, status="failed", summary=str(exc), payload={"error": str(exc)})
        raise
