import { useEffect, useMemo, useState } from 'react'
import { Button, Collapse, Input, message, Modal, Radio, Select, Space, Tag } from 'antd'
import {
  BranchesOutlined,
  CheckCircleOutlined,
  CheckOutlined,
  CloseOutlined,
  FileSearchOutlined,
  LeftOutlined,
  QuestionCircleOutlined,
  RightOutlined,
  SendOutlined,
  SafetyCertificateOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'

import { api } from '../../api'
import { useAppStore } from '../../store'
import type {
  AssistantChatResult,
  AssistantContextFile,
  AssistantQuestion,
  AssistantWorkflowStep,
  Chapter,
  ChapterMemory,
  EntityProposal,
  NovelGlobalState,
  Outline,
  OutlineChatMessage,
  PromptSnippet,
  Volume,
} from '../../types'
import styles from './SettingsAI.module.css'

type AgentRole = 'user' | 'assistant' | 'system'

interface AgentMessage {
  id: string
  role: AgentRole
  content: string
  timestamp: Date
  metadata?: {
    contextFiles?: AssistantContextFile[]
    nextStep?: string
    changeTargets?: string[]
    changedFiles?: Array<AssistantContextFile & { status?: string }>
    proposals?: EntityProposal[]
    workflowSteps?: AssistantWorkflowStep[]
    intent?: string
    confidence?: number
    status?: 'pending' | 'done' | 'failed' | 'clarify'
    rawDetail?: string
  }
}

interface ClarifySession {
  originalText: string
  contextType: string
  questions: AssistantQuestion[]
  answers: string[]
  currentIndex: number
}

interface MemoryContext {
  globalState: NovelGlobalState | null
  recentMemories: ChapterMemory[]
  currentChapterMemory: ChapterMemory | null
  loading: boolean
}

const OUTLINE_INPUT_HINT = '先说说你想写什么类型的小说，比如”玄幻修仙，废柴主角逆袭，目标百万字，主线是复仇和登仙”。'

function createMessage(role: AgentRole, content: string, metadata?: AgentMessage['metadata']): AgentMessage {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    role,
    content,
    timestamp: new Date(),
    metadata,
  }
}

function reviveMessage(raw: any): AgentMessage | null {
  if (!raw || typeof raw !== 'object') return null
  const role = raw.role === 'user' || raw.role === 'system' ? raw.role : 'assistant'
  return {
    id: String(raw.id || `${Date.now()}-${Math.random()}`),
    role,
    content: String(raw.content || ''),
    timestamp: raw.timestamp ? new Date(raw.timestamp) : new Date(),
    metadata: raw.metadata || undefined,
  }
}

function fromOutlineMessage(item: OutlineChatMessage): AgentMessage {
  return {
    id: item.id,
    role: item.role,
    content: item.content,
    timestamp: new Date(item.created_at),
    metadata: item.metadata?.error_detail
      ? {
          status: 'failed',
          rawDetail: JSON.stringify(item.metadata.error_detail, null, 2),
        }
      : item.metadata?.outline_version
        ? {
            status: 'done',
            changeTargets: ['大纲'],
            changedFiles: [
              { id: 'outline', label: '大纲', path: 'outline/outline.md', kind: 'outline', status: 'done' },
            ],
            nextStep: `已写入大纲 v${item.metadata.outline_version}`,
          }
        : undefined,
  }
}

function formatProposalPayload(value: unknown) {
  if (!value) return ''
  if (typeof value === 'string') return value
  if (typeof value !== 'object') return String(value)
  const record = value as Record<string, unknown>
  const lines = Object.entries(record)
    .filter(([, item]) => item !== null && item !== undefined && String(item).trim() !== '')
    .map(([key, item]) => `${key}: ${Array.isArray(item) ? item.join('、') : String(item)}`)
  return lines.join('\n')
}

function getContextType(currentView: string) {
  if (currentView === 'characters') return 'characters'
  if (currentView === 'worldbuilding') return 'worldbuilding'
  if (currentView === 'novel_synopsis' || currentView === 'synopsis') return 'synopsis'
  if (currentView === 'volume') return 'volume'
  if (currentView === 'chapter') return 'chapter'
  return 'outline'
}

function buildPageTitle(currentView: string, hasOutline: boolean) {
  if (currentView === 'outline') return hasOutline ? '打磨大纲' : '生成大纲'
  if (currentView === 'novel_synopsis' || currentView === 'synopsis') return '简介助手'
  if (currentView === 'worldbuilding') return '设定助手'
  if (currentView === 'characters') return '角色助手'
  if (currentView === 'book_volumes') return '分卷助手'
  if (currentView === 'volume') return '卷纲助手'
  if (currentView === 'chapter') return '正文助手'
  if (currentView === 'relationship_network') return '关系网助手'
  return 'AI 助手'
}

function buildPlaceholder(currentView: string, hasOutline: boolean) {
  if (currentView === 'outline') {
    return hasOutline
      ? '说说想怎么改，例如“第一卷节奏再快一点，女主提前登场”。'
      : OUTLINE_INPUT_HINT
  }
  if (currentView === 'novel_synopsis' || currentView === 'synopsis') {
    return '例如：简介更燃一点，突出复仇线、升级爽点和女主反差。'
  }
  if (currentView === 'worldbuilding') {
    return '例如：新增灵兽设定，并同步考虑它和角色、势力、地点的关系。'
  }
  if (currentView === 'characters') {
    return '例如：检查主角关系网，补一条女主与反派的旧怨。'
  }
  if (currentView === 'book_volumes') {
    return '例如：根据大纲重排全书分卷，让每卷目标、主线、钩子更清楚。'
  }
  if (currentView === 'volume') {
    return '例如：补齐本卷全部章节细纲，检查每章开头、发展、结尾是否连贯。'
  }
  if (currentView === 'chapter') {
    return '例如：参考本章细纲写正文草稿，或检查正文是否违反角色状态和道具归属。'
  }
  if (currentView === 'relationship_network') {
    return '例如：从主角出发检查人物、道具、地点之间还缺哪些关系。'
  }
  return '告诉 AI 你想查资料、补设定、生成草稿还是检查连续性。'
}

function chapterLabel(chapter?: Chapter | null) {
  if (!chapter) return '当前章节'
  return chapter.title && chapter.title !== `第${chapter.chapter_number}章`
    ? `第${chapter.chapter_number}章 ${chapter.title}`
    : `第${chapter.chapter_number}章`
}

function volumeLabel(volume?: Volume | null) {
  if (!volume) return '当前分卷'
  return `第${volume.volume_number}卷 ${volume.title}`
}

function buildCurrentFileMeta(
  currentView: string,
  activeWorldbuildingSectionId?: string | null,
  contentPreview?: string,
  currentChapter?: Chapter | null,
  currentVolume?: Volume | null,
) {
  const withPreview = (meta: Record<string, any>) => ({
    ...meta,
    content_preview: contentPreview ? contentPreview.slice(0, 5000) : undefined,
  })
  if (currentView === 'outline') {
    return withPreview({ id: 'outline', label: '大纲', path: 'outline/outline.md', kind: 'outline' })
  }
  if (currentView === 'novel_synopsis' || currentView === 'synopsis') {
    return withPreview({ id: 'book_synopsis', label: '简介', path: 'book/synopsis.md', kind: 'synopsis' })
  }
  if (currentView === 'characters') {
    return withPreview({ id: 'characters', label: '角色', path: 'characters/characters.json', kind: 'characters', scope: 'proposal_only' })
  }
  if (currentView === 'relationship_network') {
    return withPreview({ id: 'relationships', label: '关系网', path: 'entities/relationships.json', kind: 'relationships' })
  }
  if (currentView === 'worldbuilding') {
    const hasSection = Boolean(activeWorldbuildingSectionId && activeWorldbuildingSectionId !== 'overview')
    return withPreview({
      id: hasSection ? activeWorldbuildingSectionId : 'worldbuilding',
      label: hasSection ? '当前设定文件' : '世界总述',
      path: hasSection ? `world/sections/${activeWorldbuildingSectionId}.json` : 'world/worldbuilding.json',
      kind: hasSection ? 'worldbuilding_section' : 'worldbuilding',
      scope: 'current_file_only',
    })
  }
  if (currentView === 'book_volumes') {
    return withPreview({ id: 'book_volumes', label: '全书分卷', path: 'volumes/book-plan.md', kind: 'book_volumes' })
  }
  if (currentView === 'volume') {
    return withPreview({
      id: currentVolume?.id || 'volume',
      label: volumeLabel(currentVolume),
      path: currentVolume ? `volumes/volume_${String(currentVolume.volume_number).padStart(2, '0')}/plan.md` : 'volumes/current/plan.md',
      kind: 'volume',
    })
  }
  if (currentView === 'chapter') {
    return withPreview({
      id: currentChapter?.id || 'chapter',
      label: `${chapterLabel(currentChapter)}正文`,
      path: currentChapter ? `chapters/chapter_${String(currentChapter.chapter_number).padStart(3, '0')}/content.md` : 'chapters/current/content.md',
      kind: 'chapter',
      scope: 'current_file_only',
    })
  }
  return withPreview({ id: currentView || 'current', label: '当前文件', path: 'current', kind: currentView || 'current' })
}

export default function SettingsAI() {
  const {
    currentNovel,
    currentView,
    currentChapter,
    currentVolume,
    setCurrentNovel,
    setCurrentChapter,
    setChapters,
    setCharacters,
    setWorldbuilding,
    activeWorldbuildingSectionId,
    documentDrafts,
    patchDocumentDraft,
    openTab,
  } = useAppStore()

  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<AgentMessage[]>([])
  const [busy, setBusy] = useState(false)
  const [hasOutline, setHasOutline] = useState(false)
  const [clarifySession, setClarifySession] = useState<ClarifySession | null>(null)
  const [prompts, setPrompts] = useState<PromptSnippet[]>([])
  const [savePromptOpen, setSavePromptOpen] = useState(false)
  const [promptScope, setPromptScope] = useState<'common' | 'project'>('project')
  const [promptTitle, setPromptTitle] = useState('')
  const [promptDesc, setPromptDesc] = useState('')
  const [promptContent, setPromptContent] = useState('')

  const [memoryContext, setMemoryContext] = useState<MemoryContext>({
    globalState: null,
    recentMemories: [],
    currentChapterMemory: null,
    loading: false,
  })
  const [memoryPanelOpen, setMemoryPanelOpen] = useState(false)

  const isOutlineView = currentView === 'outline'
  const isSynopsisView = currentView === 'novel_synopsis' || currentView === 'synopsis'
  const isWorldbuildingView = currentView === 'worldbuilding'
  const contextDraftKey = currentView === 'chapter'
    ? currentChapter?.id || 'unknown'
    : currentView === 'volume'
      ? currentVolume?.id || 'unknown'
      : isWorldbuildingView
        ? activeWorldbuildingSectionId
        : 'default'
  const chatDraftKey = currentNovel
    ? `settings_ai:chat:${currentNovel.id}:${currentView}:${contextDraftKey}`
    : null

  const title = useMemo(() => buildPageTitle(currentView, hasOutline), [currentView, hasOutline])
  const placeholder = useMemo(() => buildPlaceholder(currentView, hasOutline), [currentView, hasOutline])

  useEffect(() => {
    if (!chatDraftKey) {
      setInput('')
      setMessages([])
      return
    }
    const draft = documentDrafts[chatDraftKey] as { input?: string; messages?: unknown[] } | undefined
    setInput(draft?.input || '')
    setMessages((draft?.messages || []).map(reviveMessage).filter(Boolean) as AgentMessage[])
    setClarifySession(null)
  }, [chatDraftKey])

  useEffect(() => {
    if (!chatDraftKey) return
    patchDocumentDraft(chatDraftKey, {
      input,
      messages: messages.map(item => ({
        ...item,
        timestamp: item.timestamp.toISOString(),
      })),
      updatedAt: new Date().toISOString(),
    })
  }, [chatDraftKey, input, messages])

  useEffect(() => {
    if (!currentNovel) return
    if (isOutlineView) {
      void loadOutlineState()
      void loadOutlineMessages()
    }
    void loadMemoryContext()
  }, [currentNovel?.id, isOutlineView])

  useEffect(() => {
    if (!currentNovel) return
    void api.prompts.list(currentNovel.id).then(setPrompts).catch(() => setPrompts([]))
  }, [currentNovel?.id])

  useEffect(() => {
    function handleOutlineReset() {
      setHasOutline(false)
      setMessages([])
      setInput('')
      setClarifySession(null)
    }

    window.addEventListener('mobi:outline-reset', handleOutlineReset)
    return () => window.removeEventListener('mobi:outline-reset', handleOutlineReset)
  }, [])

  useEffect(() => {
    function handleWorldbuildingResponse(event: Event) {
      const customEvent = event as CustomEvent<{ ok?: boolean; message?: string }>
      setBusy(false)
      setMessages(prev => [
        ...prev,
        createMessage(
          customEvent.detail?.ok === false ? 'system' : 'assistant',
          customEvent.detail?.message || '设定草稿已生成，请在主编辑区确认。',
          {
            status: customEvent.detail?.ok === false ? 'failed' : 'pending',
            contextFiles: [
              { id: 'outline', label: '总大纲', path: 'outline/outline.md', kind: 'outline' },
              { id: 'worldbuilding', label: '当前设定文件', path: 'world/worldbuilding.json', kind: 'worldbuilding' },
            ],
            changeTargets: ['当前设定文件'],
            changedFiles: [
              { id: 'worldbuilding', label: '当前设定文件', path: 'world/worldbuilding.json', kind: 'worldbuilding', status: customEvent.detail?.ok === false ? 'failed' : 'pending' },
            ],
            nextStep: customEvent.detail?.ok === false ? '可以换一种说法重试，或展开错误看原始原因。' : '草稿不会直接覆盖，确认应用后才进入当前编辑态。',
          },
        ),
      ])
    }

    window.addEventListener('mobi:worldbuilding-ai-response', handleWorldbuildingResponse)
    return () => window.removeEventListener('mobi:worldbuilding-ai-response', handleWorldbuildingResponse)
  }, [])

  useEffect(() => {
    function handleSynopsisResponse(event: Event) {
      const customEvent = event as CustomEvent<{ ok?: boolean; message?: string }>
      setBusy(false)
      setMessages(prev => [
        ...prev,
        createMessage(
          customEvent.detail?.ok === false ? 'system' : 'assistant',
          customEvent.detail?.message || '简介草稿已更新到编辑器。',
          {
            status: customEvent.detail?.ok === false ? 'failed' : 'pending',
            contextFiles: [
              { id: 'outline', label: '已确认大纲', path: 'outline/outline.md', kind: 'outline' },
              { id: 'synopsis', label: '当前简介', path: 'book/synopsis.md', kind: 'synopsis' },
            ],
            changeTargets: ['简介'],
            changedFiles: [
              { id: 'synopsis', label: '简介', path: 'book/synopsis.md', kind: 'synopsis', status: customEvent.detail?.ok === false ? 'failed' : 'pending' },
            ],
            nextStep: customEvent.detail?.ok === false ? '可以补充修改方向后重试。' : '简介修改稿已生成，进入简介页确认采用后才会写入正式内容。',
          },
        ),
      ])
    }

    window.addEventListener('mobi:novel-synopsis-ai-response', handleSynopsisResponse)
    return () => window.removeEventListener('mobi:novel-synopsis-ai-response', handleSynopsisResponse)
  }, [])

  async function loadOutlineState() {
    if (!currentNovel) return
    try {
      await api.outline.latest(currentNovel.id)
      setHasOutline(true)
    } catch {
      setHasOutline(false)
    }
  }

  async function loadOutlineMessages() {
    if (!currentNovel) return
    try {
      const data = await api.outline.messages(currentNovel.id)
      const restored = data.map(fromOutlineMessage)
      setMessages(restored)
    } catch {
      setMessages([])
    }
  }

  async function loadMemoryContext() {
    if (!currentNovel) return
    setMemoryContext(prev => ({ ...prev, loading: true }))
    try {
      const [globalState, currentMem] = await Promise.all([
        api.novels.globalState(currentNovel.id).catch(() => null),
        currentChapter
          ? api.review.getChapterMemory(currentNovel.id, currentChapter.id).catch(() => null)
          : Promise.resolve(null),
      ])

      // 加载前3章的记忆
      let prevMemories: ChapterMemory[] = []
      if (currentChapter && currentChapter.chapter_number > 1) {
        try {
          const allChapters = await api.chapters.list(currentNovel.id)
          const prevChapterIds = allChapters
            .filter(c =>
              c.volume_id === currentChapter.volume_id &&
              c.chapter_number < currentChapter.chapter_number &&
              c.chapter_number >= Math.max(1, currentChapter.chapter_number - 3)
            )
            .map(c => c.id)
          prevMemories = (await Promise.all(
            prevChapterIds.map(id => api.review.getChapterMemory(currentNovel.id, id).catch(() => null))
          )).filter(Boolean) as ChapterMemory[]
        } catch {
          // ignore
        }
      }

      setMemoryContext({
        globalState,
        recentMemories: prevMemories,
        currentChapterMemory: currentMem,
        loading: false,
      })
    } catch {
      setMemoryContext(prev => ({ ...prev, loading: false }))
    }
  }

  function appendMessage(item: AgentMessage) {
    setMessages(prev => [...prev, item])
  }

  function metadataFromResult(result: AssistantChatResult, fallbackNextStep?: string): AgentMessage['metadata'] {
    return {
      status: result.mode === 'clarify' ? 'clarify' : (result.changed_files?.some(file => file.status === 'pending') ? 'pending' : 'done'),
      contextFiles: result.context_files || [],
      changedFiles: result.changed_files || [],
      proposals: result.pending_proposals || [],
      workflowSteps: result.workflow_steps || [],
      intent: result.intent,
      confidence: result.confidence,
      nextStep: result.mode === 'clarify'
        ? '请在底部追问面板逐题选择，选完后我会继续执行。'
        : fallbackNextStep || '如果需要写入文件，我会先给出待确认草稿。',
    }
  }

  function isClarifyResult(result: AssistantChatResult) {
    return result.mode === 'clarify' && (result.questions || []).length > 0
  }

  function beginClarification(originalText: string, contextType: string, result: AssistantChatResult) {
    const questions = result.questions || []
    appendMessage(createMessage(
      'assistant',
      result.message || '我先确认几个关键点，避免直接写偏。',
      metadataFromResult(result),
    ))
    setClarifySession({
      originalText,
      contextType,
      questions,
      answers: [],
      currentIndex: 0,
    })
  }

  function handleAssistantError(err: any) {
    const rawDetail = err?.response?.data?.raw_detail
    const detail = err?.response?.data?.detail || err?.message || 'AI 助手处理失败'
    appendMessage(createMessage('system', String(detail), {
      status: 'failed',
      rawDetail: rawDetail ? JSON.stringify(rawDetail, null, 2) : undefined,
    }))
    message.error(String(detail))
  }

  function recentHistory() {
    return messages
      .filter(item => item.role !== 'system')
      .slice(-8)
      .map(item => ({ role: item.role, content: item.content }))
  }

  function currentDraftPreview() {
    if (!currentNovel) return ''
    if (currentView === 'outline') {
      return String((documentDrafts[`outline:${currentNovel.id}`] as any)?.editContent || '')
    }
    if (isSynopsisView) {
      return String((documentDrafts[`novel_synopsis:${currentNovel.id}`] as any)?.value || currentNovel.synopsis || '')
    }
    if (currentView === 'volume') {
      const volumeId = useAppStore.getState().currentVolume?.id
      return volumeId ? String((documentDrafts[`volume:${volumeId}`] as any)?.planMarkdown || '') : ''
    }
    if (currentView === 'chapter') {
      const chapterId = useAppStore.getState().currentChapter?.id
      return chapterId ? String((documentDrafts[`chapter:${chapterId}`] as any)?.content || '') : ''
    }
    return ''
  }

  function buildMemoryContextText(): string {
    const parts: string[] = []
    const { globalState, recentMemories, currentChapterMemory } = memoryContext

    if (globalState) {
      parts.push(`【全书进度】第${globalState.latest_chapter_number}章 / ${globalState.total_words.toLocaleString()}字 / 已定稿${globalState.approved_chapters}章`)
      if (globalState.characters.length > 0) {
        const charList = globalState.characters.slice(0, 8)
          .map(c => `${c.name}(${c.current_realm}·${c.current_location})`)
          .join('；')
        parts.push(`【核心角色】${charList}`)
      }
      if (globalState.open_threads.length > 0) {
        parts.push(`【待回收伏笔】${globalState.open_threads.slice(0, 5).join('；')}`)
      }
      if (globalState.snapshots.length > 0) {
        const latest = globalState.snapshots[globalState.snapshots.length - 1]
        parts.push(`【最近剧情】第${latest.start_chapter}-${latest.end_chapter}章：${latest.summary}`)
      }
    }

    if (recentMemories.length > 0) {
      const memText = recentMemories
        .map(m => `第${m.chapter_number}章：${m.summary || '无摘要'} ${m.state_changes.length > 0 ? '|' + m.state_changes.join('、') : ''}`)
        .join(' / ')
      parts.push(`【前3章摘要】${memText}`)
    }

    if (currentChapterMemory) {
      parts.push(`【本章记忆】${currentChapterMemory.summary || '暂无'}`)
      if (currentChapterMemory.open_threads.length > 0) {
        parts.push(`【本章埋下伏笔】${currentChapterMemory.open_threads.join('；')}`)
      }
    }

    return parts.join('\n')
  }

  async function runAssistant(text: string, contextType = getContextType(currentView)) {
    if (!currentNovel) throw new Error('请先选择小说')
    const memoryCtx = buildMemoryContextText()
    return api.assistant.run({
      novel_id: currentNovel.id,
      context_type: contextType,
      context_id: currentView === 'chapter'
        ? currentChapter?.id || null
        : currentView === 'volume'
          ? currentVolume?.id || null
          : isWorldbuildingView
            ? activeWorldbuildingSectionId
            : null,
      messages: recentHistory(),
      user_message: text,
      current_file: buildCurrentFileMeta(currentView, activeWorldbuildingSectionId, currentDraftPreview(), currentChapter, currentVolume),
      ...(memoryCtx ? { context_files: [`memory:${memoryCtx}`] } : {}),
    })
  }

  async function sendOutline(text: string, silentUser = false) {
    if (!currentNovel) return

    const result = await runAssistant(text, 'outline')
    if (isClarifyResult(result)) {
      beginClarification(text, 'outline', result)
      return
    }
    if (!silentUser) appendMessage(createMessage('user', text))

    const latestNovel = await api.novels.get(currentNovel.id).catch(() => null)
    if (latestNovel) setCurrentNovel(latestNovel)
    const outlineResult = result.outline_result

    if (outlineResult?.saved && outlineResult.outline) {
      setHasOutline(true)
      window.dispatchEvent(new CustomEvent<Outline>('mobi:outline-generated', { detail: outlineResult.outline }))
      appendMessage(createMessage('assistant', result.message || `已生成大纲 v${outlineResult.outline.version}。如果不满意，可以继续说要改哪里。`, metadataFromResult(
        result,
        '确认大纲后会解锁简介、角色、世界观和分卷细纲。',
      )))
      return
    }

    if (outlineResult?.draft_outline || result.draft_outline) {
      window.dispatchEvent(new CustomEvent('mobi:outline-draft', { detail: outlineResult?.draft_outline || result.draft_outline }))
      appendMessage(createMessage('assistant', result.message || '已生成待审阅的大纲修改稿，主编辑区会显示行内修改建议。', metadataFromResult(
        result,
        '逐条采用或放弃后，再手动存档成一个版本节点。',
      )))
      return
    }

    appendMessage(createMessage('assistant', result.message, metadataFromResult(result)))
  }

  async function sendSynopsis(text: string, silentUser = false) {
    const result = await runAssistant(text.trim() || '根据已确认大纲生成简介待审阅草稿', 'synopsis')
    if (isClarifyResult(result)) {
      beginClarification(text, 'synopsis', result)
      return
    }
    if (!silentUser) appendMessage(createMessage('user', text))
    if (result.synopsis_draft) {
      window.dispatchEvent(new CustomEvent('mobi:novel-synopsis-draft', {
        detail: { synopsis: result.synopsis_draft, prompt: text },
      }))
    }
    appendMessage(createMessage('assistant', result.message, metadataFromResult(result, '简介内容需要在简介编辑器里确认后才会正式保存。')))
  }

  async function sendWorldbuilding(text: string, silentUser = false) {
    const result = await runAssistant(text, 'worldbuilding')
    if (isClarifyResult(result)) {
      beginClarification(text, 'worldbuilding', result)
      return
    }
    if (!silentUser) appendMessage(createMessage('user', text))
    appendMessage(createMessage('assistant', result.message, metadataFromResult(result, '设定修改只会作为待确认方案展示，确认后才写入当前设定文件。')))
    const hasWorldbuildingTarget = (result.changed_files || []).some(file =>
      file.kind?.startsWith('worldbuilding') || file.path?.includes('world'),
    )
    if (result.intent === 'revise_worldbuilding' || hasWorldbuildingTarget) {
      window.dispatchEvent(new CustomEvent('mobi:worldbuilding-ai-request', {
        detail: { prompt: text },
      }))
    }
  }

  async function sendGeneric(text: string, silentUser = false) {
    if (!currentNovel) return
    const result = await runAssistant(text)
    if (isClarifyResult(result)) {
      beginClarification(text, getContextType(currentView), result)
      return
    }

    if (!silentUser) appendMessage(createMessage('user', text))
    appendMessage(createMessage('assistant', result.message, metadataFromResult(result)))
  }

  async function handleSend() {
    if (!currentNovel || busy) return
    const text = input.trim()
    if (!text) {
      message.warning('先告诉 AI 你想做什么。')
      return
    }

    setInput('')
    setBusy(true)
    try {
      if (isOutlineView) {
        await sendOutline(text)
      } else if (isSynopsisView) {
        await sendSynopsis(text)
      } else if (isWorldbuildingView) {
        await sendWorldbuilding(text)
      } else {
        await sendGeneric(text)
      }
    } catch (err: any) {
      handleAssistantError(err)
    } finally {
      setBusy(false)
    }
  }

  async function continueAfterClarification() {
    if (!clarifySession || busy) return
    const unanswered = clarifySession.questions.findIndex((_, index) => !clarifySession.answers[index]?.trim())
    if (unanswered >= 0) {
      setClarifySession(prev => prev ? { ...prev, currentIndex: unanswered } : prev)
      message.warning('先把这几个关键问题选完。')
      return
    }

    const supplement = clarifySession.questions
      .map((question, index) => `${question.question}：${clarifySession.answers[index]}`)
      .join('\n')
    const combinedText = `${clarifySession.originalText}\n\n用户补充选择：\n${supplement}`
    const contextType = clarifySession.contextType

    setClarifySession(null)
    setBusy(true)
    try {
      if (contextType === 'outline') {
        await sendOutline(combinedText, true)
      } else if (contextType === 'synopsis') {
        await sendSynopsis(combinedText, true)
      } else if (contextType === 'worldbuilding') {
        await sendWorldbuilding(combinedText, true)
      } else {
        await sendGeneric(combinedText, true)
      }
    } catch (err: any) {
      handleAssistantError(err)
    } finally {
      setBusy(false)
    }
  }

  function chooseClarifyOption(option: string) {
    setClarifySession(prev => {
      if (!prev) return prev
      const answers = [...prev.answers]
      answers[prev.currentIndex] = option
      return { ...prev, answers }
    })
  }

  function updateClarifyCustomAnswer(value: string) {
    setClarifySession(prev => {
      if (!prev) return prev
      const answers = [...prev.answers]
      answers[prev.currentIndex] = value
      return { ...prev, answers }
    })
  }

  function openChangedFile(file: AssistantContextFile) {
    if (!currentNovel) return
    if (file.kind === 'synopsis' || file.path.includes('synopsis')) {
      if (file.kind === 'chapter_synopsis' || file.path.includes('/synopsis.json')) {
        openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: currentVolume || undefined })
        return
      }
      openTab({ type: 'novel_synopsis', novelSnapshot: currentNovel })
      return
    }
    if (file.kind === 'chapter' || file.kind === 'chapter_content' || file.path.includes('/content.md')) {
      openTab({ type: 'chapter', novelSnapshot: currentNovel, chapterSnapshot: currentChapter || undefined })
      return
    }
    if (file.kind === 'volume' || file.path.includes('volumes/')) {
      openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: currentVolume || undefined })
      return
    }
    if (file.kind === 'characters' || file.path.includes('characters')) {
      openTab({ type: 'characters', novelSnapshot: currentNovel })
      return
    }
    if (file.kind.startsWith('worldbuilding') || file.path.includes('world')) {
      openTab({ type: 'worldbuilding', novelSnapshot: currentNovel, worldbuildingSectionId: activeWorldbuildingSectionId })
      return
    }
    openTab({ type: 'outline', novelSnapshot: currentNovel })
  }

  function startSavePrompt(content: string) {
    setPromptContent(content)
    setPromptTitle(content.slice(0, 16) || '新提示词')
    setPromptDesc('')
    setPromptScope(currentNovel ? 'project' : 'common')
    setSavePromptOpen(true)
  }

  async function savePrompt() {
    if (!promptTitle.trim() || !promptContent.trim()) {
      message.warning('提示词简称和内容不能为空。')
      return
    }
    try {
      await api.prompts.create({
        scope: promptScope,
        novel_id: promptScope === 'project' ? currentNovel?.id : null,
        title: promptTitle,
        description: promptDesc,
        content: promptContent,
      })
      setSavePromptOpen(false)
      if (currentNovel) setPrompts(await api.prompts.list(currentNovel.id))
      message.success('提示词已保存')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存提示词失败')
    }
  }

  function insertPrompt(promptId: string) {
    const prompt = prompts.find(item => item.id === promptId)
    if (!prompt) return
    setInput(prev => (prev.trim() ? `${prev.trim()}\n\n${prompt.content}` : prompt.content))
  }

  async function handleProposal(proposal: EntityProposal, action: 'approve' | 'reject') {
    if (!currentNovel) return
    try {
      const handler = action === 'approve' ? api.review.approveProposal : api.review.rejectProposal
      await handler(currentNovel.id, proposal.id)
      if (action === 'approve') {
        if (proposal.entity_type === 'character' || currentView === 'characters') {
          const latestCharacters = await api.characters.list(currentNovel.id).catch(() => null)
          if (latestCharacters) setCharacters(latestCharacters)
        }
      if (proposal.entity_type !== 'character' || currentView === 'worldbuilding') {
        const latestWorldbuilding = await api.worldbuilding.get(currentNovel.id).catch(() => null)
        if (latestWorldbuilding) setWorldbuilding(latestWorldbuilding)
      }
      if (currentChapter) {
        const refreshedChapter = await api.chapters.get(currentNovel.id, currentChapter.id).catch(() => null)
        if (refreshedChapter) {
          setCurrentChapter(refreshedChapter)
          const latestChapters = await api.chapters.list(currentNovel.id).catch(() => null)
          if (latestChapters) setChapters(latestChapters)
        }
      }
      }
      setMessages(prev => prev.map(item => ({
        ...item,
        metadata: item.metadata?.proposals
          ? {
              ...item.metadata,
              proposals: item.metadata.proposals.filter(existing => {
                if (existing.id === proposal.id) return false
                if (action === 'approve' && proposal.action === 'create' && existing.action === 'create') {
                  return !(
                    existing.entity_type === proposal.entity_type
                    && existing.entity_name.replace(/\s+/g, '') === proposal.entity_name.replace(/\s+/g, '')
                  )
                }
                return true
              }),
            }
          : item.metadata,
      })))
      message.success(action === 'approve' ? '已通过待确认卡片' : '已放弃待确认卡片')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '处理提案失败')
    }
  }

  function renderMetadata(item: AgentMessage) {
    const metadata = item.metadata
    if (!metadata) return null
    const hasContext = (metadata.contextFiles || []).length > 0
    const hasTargets = (metadata.changeTargets || []).length > 0
    const hasChangedFiles = (metadata.changedFiles || []).length > 0
    const hasProposals = (metadata.proposals || []).length > 0
    const hasWorkflow = (metadata.workflowSteps || []).length > 0
    const hasRaw = Boolean(metadata.rawDetail)
    if (!hasContext && !hasTargets && !hasChangedFiles && !hasProposals && !hasWorkflow && !metadata.nextStep && !hasRaw) return null

    return (
      <>
        {hasChangedFiles ? (
          <div className={styles.changedFilesInline}>
            <span>待处理文件</span>
            {metadata.changedFiles!.map(file => (
              <button
                type="button"
                key={`${file.kind}-${file.id}`}
                className={styles.changedFileChip}
                onClick={() => openChangedFile(file)}
              >
                {file.label}{file.status === 'pending' ? ' · 待确认' : ''}
              </button>
            ))}
          </div>
        ) : null}
      <Collapse
        ghost
        size="small"
        className={styles.agentMeta}
        items={[{
          key: 'meta',
          label: metadata.status === 'failed' ? '查看失败原因' : '查看本次工作详情',
          children: (
            <div className={styles.agentMetaBody}>
              {hasContext ? (
                <div className={styles.metaSection}>
                  <div className={styles.metaTitle}><FileSearchOutlined /> 参考文件</div>
                  <div className={styles.contextFiles}>
                    {metadata.contextFiles!.map(file => (
                      <Tag key={`${file.kind}-${file.id}`} className={styles.contextTag}>
                        {file.label}
                      </Tag>
                    ))}
                  </div>
                </div>
              ) : null}
              {hasWorkflow ? (
                <div className={styles.metaSection}>
                  <div className={styles.metaTitle}><SafetyCertificateOutlined /> 工作流程</div>
                  <div className={styles.workflowList}>
                    {metadata.workflowSteps!.map(step => (
                      <div key={step.id} className={styles.workflowStep}>
                        <div className={styles.workflowStepTitle}>
                          <Tag>{step.step_order}</Tag>
                          <span>{step.title}</span>
                          <Tag color={step.status === 'failed' ? 'red' : step.status === 'running' ? 'processing' : 'green'}>
                            {step.status === 'running' ? '处理中' : step.status === 'failed' ? '失败' : '完成'}
                          </Tag>
                        </div>
                        {step.detail ? <div className={styles.workflowStepDetail}>{step.detail}</div> : null}
                        {(step.files || []).length > 0 ? (
                          <div className={styles.contextFiles}>
                            {(step.files || []).map(file => (
                              <Button key={`${step.id}-${file.kind}-${file.id}`} size="small" onClick={() => openChangedFile(file)}>
                                {file.label || file.path}
                              </Button>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {hasTargets ? (
                <div className={styles.metaSection}>
                  <div className={styles.metaTitle}><BranchesOutlined /> 可能修改</div>
                  <div className={styles.contextFiles}>
                    {metadata.changeTargets!.map(target => <Tag key={target}>{target}</Tag>)}
                  </div>
                </div>
              ) : null}
              {hasChangedFiles ? (
                <div className={styles.metaSection}>
                  <div className={styles.metaTitle}><BranchesOutlined /> 改动文件</div>
                  <div className={styles.contextFiles}>
                    {metadata.changedFiles!.map(file => (
                      <Button key={`${file.kind}-${file.id}`} size="small" onClick={() => openChangedFile(file)}>
                        {file.label}{file.status === 'pending' ? ' · 待确认' : ''}
                      </Button>
                    ))}
                  </div>
                </div>
              ) : null}
              {hasProposals ? (
                <div className={styles.metaSection}>
                  <div className={styles.metaTitle}><CheckCircleOutlined /> 待审阅卡片</div>
                  {metadata.proposals!.map(proposal => (
                    <div key={proposal.id} className={styles.proposalItem}>
                      <div className={styles.proposalHeader}>
                        <Tag color="gold">{proposal.action === 'create' ? '新增' : '修改'}</Tag>
                        <span className={styles.proposalName}>{proposal.entity_name}</span>
                      </div>
                      <div className={styles.proposalReason}>{proposal.reason || '等待作者确认'}</div>
                      <div className={styles.proposalDiff}>
                        <div className={styles.proposalSide}>
                          <div className={styles.proposalSideTitle}>修改前</div>
                          <pre className={styles.proposalPre}>
                            {formatProposalPayload(proposal.payload?.before) || '新增卡片，暂无旧内容'}
                          </pre>
                        </div>
                        <div className={styles.proposalSide}>
                          <div className={styles.proposalSideTitle}>修改后</div>
                          <pre className={styles.proposalPre}>
                            {formatProposalPayload(proposal.payload?.after || proposal.payload?.entry) || '等待 AI 补全内容'}
                          </pre>
                        </div>
                      </div>
                      <Space size={8}>
                        <Button size="small" type="primary" onClick={() => handleProposal(proposal, 'approve')}>
                          通过
                        </Button>
                        <Button size="small" onClick={() => handleProposal(proposal, 'reject')}>
                          放弃
                        </Button>
                      </Space>
                    </div>
                  ))}
                </div>
              ) : null}
              {metadata.nextStep ? (
                <div className={styles.metaSection}>
                  <div className={styles.metaTitle}><CheckCircleOutlined /> 下一步</div>
                  <div className={styles.metaText}>{metadata.nextStep}</div>
                </div>
              ) : null}
              {hasRaw ? (
                <pre className={styles.rawErrorText}>{metadata.rawDetail}</pre>
              ) : null}
            </div>
          ),
        }]}
      />
      </>
    )
  }

  function renderMessages() {
    if (messages.length === 0) {
      return (
        <div className={styles.agentIntro}>
          <div className={styles.agentIntroTitle}>我是这本书的创作助手</div>
          <div className={styles.agentIntroText}>
            我会先读当前作品资料，再给出草稿、修改建议或追问问题。需要写入文件的内容只会以待确认草稿出现，不会静默删除或覆盖。
          </div>
          <div className={styles.introGrid}>
            <div><SafetyCertificateOutlined /> 先备份再改</div>
            <div><FileSearchOutlined /> 自动找参考文件</div>
            <div><QuestionCircleOutlined /> 意图不清先追问</div>
            <div><BranchesOutlined /> 修改走审批</div>
          </div>
        </div>
      )
    }

    return messages.map(item => (
      <div key={item.id} className={styles.messageWrapper}>
        <div
          className={item.role === 'user' ? styles.userBubble : item.role === 'system' ? styles.systemBubble : styles.assistantBubble}
          onContextMenu={(event) => {
            event.preventDefault()
            startSavePrompt(item.content)
          }}
        >
          <div className={styles.messageContent}>{item.content}</div>
          {renderMetadata(item)}
          <div className={styles.messageTime}>
            {item.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
          </div>
        </div>
      </div>
    ))
  }

  function renderClarifySheet() {
    if (!clarifySession) return null
    const currentQuestion = clarifySession.questions[clarifySession.currentIndex]
    if (!currentQuestion) return null
    const currentAnswer = clarifySession.answers[clarifySession.currentIndex]
    const answeredCount = clarifySession.questions.filter((_, index) => Boolean(clarifySession.answers[index]?.trim())).length
    const ready = answeredCount === clarifySession.questions.length
    const isLastQuestion = clarifySession.currentIndex >= clarifySession.questions.length - 1
    const options = currentQuestion.options || []
    const isCustomAnswer = currentAnswer?.trim() && !options.includes(currentAnswer)

    return (
      <div className={styles.clarifySheet}>
        <div className={styles.clarifyHeader}>
          <div>
            <div className={styles.clarifyEyebrow}>需要确认</div>
            <div className={styles.clarifyTitle}>先选关键点，我再继续</div>
          </div>
          <Tag>{clarifySession.currentIndex + 1}/{clarifySession.questions.length}</Tag>
        </div>
        <div className={styles.clarifyQuestion}>
          <div className={styles.clarifyQuestionText}>{currentQuestion.question}</div>
          <div className={styles.clarifyOptionList}>
            {options.map((option, optionIndex) => (
              <button
                type="button"
                key={option}
                className={[
                  styles.clarifyOptionRow,
                  currentAnswer === option ? styles.clarifyOptionActive : '',
                ].filter(Boolean).join(' ')}
                onClick={() => chooseClarifyOption(option)}
              >
                <span className={styles.clarifyOptionNo}>{optionIndex + 1}.</span>
                <span className={styles.clarifyOptionText}>{option}</span>
              </button>
            ))}
            <label className={[
              styles.clarifyCustomRow,
              isCustomAnswer ? styles.clarifyOptionActive : '',
            ].filter(Boolean).join(' ')}>
              <span className={styles.clarifyOptionNo}>{options.length + 1}.</span>
              <Input
                bordered={false}
                value={isCustomAnswer ? currentAnswer : ''}
                placeholder="自定义回答"
                onChange={event => updateClarifyCustomAnswer(event.target.value)}
                onFocus={() => {
                  if (options.includes(currentAnswer || '')) updateClarifyCustomAnswer('')
                }}
              />
            </label>
          </div>
        </div>
        <div className={styles.clarifyProgress}>
          {clarifySession.questions.map((question, index) => (
            <button
              key={question.question}
              type="button"
              className={[
                styles.clarifyDot,
                index === clarifySession.currentIndex ? styles.clarifyDotActive : '',
                clarifySession.answers[index]?.trim() ? styles.clarifyDotDone : '',
              ].filter(Boolean).join(' ')}
              onClick={() => setClarifySession(prev => prev ? { ...prev, currentIndex: index } : prev)}
              aria-label={`切换到第 ${index + 1} 个问题`}
            />
          ))}
        </div>
        <div className={styles.clarifyActions}>
          <Button
            size="small"
            shape="circle"
            icon={<CloseOutlined />}
            title="取消"
            aria-label="取消追问"
            onClick={() => {
              setInput(clarifySession.originalText)
              setClarifySession(null)
            }}
          />
          <Button
            size="small"
            shape="circle"
            icon={<LeftOutlined />}
            title="上一题"
            aria-label="上一题"
            disabled={clarifySession.currentIndex === 0}
            onClick={() => setClarifySession(prev => prev ? { ...prev, currentIndex: Math.max(0, prev.currentIndex - 1) } : prev)}
          />
          <Button
            size="small"
            shape="circle"
            icon={<RightOutlined />}
            title="下一题"
            aria-label="下一题"
            disabled={!currentAnswer?.trim() || isLastQuestion}
            onClick={() => setClarifySession(prev => prev ? {
              ...prev,
              currentIndex: Math.min(prev.questions.length - 1, prev.currentIndex + 1),
            } : prev)}
          />
          <Button
            type="primary"
            size="small"
            shape="circle"
            icon={<CheckOutlined />}
            title="提交并继续"
            aria-label="提交并继续"
            disabled={!ready || busy}
            loading={busy}
            onClick={continueAfterClarification}
          />
        </div>
      </div>
    )
  }

  if (!currentNovel) {
    return (
      <div className={styles.empty}>
        <span>选择小说后显示 AI 助手</span>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span>{title}</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <Tag color="processing">Ask</Tag>
          <Button
            size="small"
            type="text"
            icon={<UnorderedListOutlined />}
            onClick={() => setMemoryPanelOpen(v => !v)}
            style={{
              color: memoryPanelOpen ? 'var(--primary)' : 'var(--text-muted)',
              fontSize: 13,
            }}
            title="记忆上下文"
          />
        </div>
      </div>

      {memoryPanelOpen && (
        <div className={styles.memoryPanel}>
          {memoryContext.loading ? (
            <div className={styles.memoryLoading}>加载中...</div>
          ) : (
            <>
              {/* 全局状态摘要 */}
              {memoryContext.globalState && (
                <div className={styles.memorySection}>
                  <div className={styles.memorySectionTitle}>
                    全局状态 · {memoryContext.globalState.total_chapters}章 / {memoryContext.globalState.total_words.toLocaleString()}字
                  </div>
                  <div className={styles.memoryStats}>
                    <Tag color="green">已定稿 {memoryContext.globalState.approved_chapters} 章</Tag>
                    <Tag>写到第 {memoryContext.globalState.latest_chapter_number} 章</Tag>
                  </div>
                  {/* 角色状态 */}
                  {memoryContext.globalState.characters.length > 0 && (
                    <div className={styles.memorySubSection}>
                      <div className={styles.memorySubTitle}>核心角色状态</div>
                      <div className={styles.memoryTagList}>
                        {memoryContext.globalState.characters.slice(0, 6).map(char => (
                          <Tag key={char.character_id} color={char.status === 'alive' ? 'green' : 'default'} style={{ fontSize: 10 }}>
                            {char.name} · {char.current_realm}
                          </Tag>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* 未回收伏笔 */}
                  {memoryContext.globalState.open_threads.length > 0 && (
                    <div className={styles.memorySubSection}>
                      <div className={styles.memorySubTitle}>待回收伏笔 ({memoryContext.globalState.open_threads.length})</div>
                      <div className={styles.memoryThreadList}>
                        {memoryContext.globalState.open_threads.slice(0, 3).map((thread, i) => (
                          <div key={i} className={styles.memoryThread}>{thread}</div>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* 10章聚合快照 */}
                  {memoryContext.globalState.snapshots.length > 0 && (
                    <div className={styles.memorySubSection}>
                      <div className={styles.memorySubTitle}>剧情进度快照</div>
                      {memoryContext.globalState.snapshots.slice(-2).map(snap => (
                        <div key={snap.id} className={styles.memorySnapshot}>
                          <div className={styles.memorySnapshotHeader}>
                            第{snap.start_chapter}-{snap.end_chapter}章
                          </div>
                          <div className={styles.memorySnapshotSummary}>{snap.summary}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {/* 前3章记忆 */}
              {memoryContext.recentMemories.length > 0 && (
                <div className={styles.memorySection}>
                  <div className={styles.memorySectionTitle}>前3章记忆</div>
                  {memoryContext.recentMemories.map(mem => (
                    <div key={mem.id} className={styles.memoryChapterItem}>
                      <div className={styles.memoryChapterHeader}>第{mem.chapter_number}章</div>
                      {mem.summary && <div className={styles.memoryChapterSummary}>{mem.summary}</div>}
                      {mem.state_changes.length > 0 && (
                        <div className={styles.memoryChanges}>
                          {mem.state_changes.map((change, i) => (
                            <Tag key={i} style={{ fontSize: 10 }}>{change}</Tag>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              {/* 当前章记忆 */}
              {memoryContext.currentChapterMemory && (
                <div className={styles.memorySection}>
                  <div className={styles.memorySectionTitle}>本章已抽取记忆</div>
                  {memoryContext.currentChapterMemory.summary && (
                    <div className={styles.memoryChapterSummary}>{memoryContext.currentChapterMemory.summary}</div>
                  )}
                  {memoryContext.currentChapterMemory.key_events.length > 0 && (
                    <div className={styles.memorySubSection}>
                      <div className={styles.memorySubTitle}>关键事件</div>
                      {memoryContext.currentChapterMemory.key_events.map((evt, i) => (
                        <div key={i} className={styles.memoryEvent}>{evt}</div>
                      ))}
                    </div>
                  )}
                  {memoryContext.currentChapterMemory.open_threads.length > 0 && (
                    <div className={styles.memorySubSection}>
                      <div className={styles.memorySubTitle}>本章埋下伏笔</div>
                      {memoryContext.currentChapterMemory.open_threads.map((t, i) => (
                        <Tag key={i} color="orange" style={{ fontSize: 10 }}>{t}</Tag>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {!memoryContext.globalState && memoryContext.recentMemories.length === 0 && !memoryContext.currentChapterMemory && (
                <div className={styles.memoryEmpty}>暂无记忆数据，开始写章节后会逐步累积。</div>
              )}
            </>
          )}
        </div>
      )}

      <div className={styles.chatPane}>
        <div className={styles.chatList}>
          {messages.length === 0 && !busy ? renderMessages() : renderMessages()}
          {busy ? (
            <div className={styles.assistantBubble}>
              <div className={styles.messageContent}>正在阅读资料并组织回复...</div>
            </div>
          ) : null}
        </div>

        {renderClarifySheet()}

        <div className={styles.chatComposer}>
          <Input.TextArea
            value={input}
            onChange={event => setInput(event.target.value)}
            placeholder={placeholder}
            autoSize={{ minRows: 3, maxRows: 7 }}
            onPressEnter={(event) => {
              if (event.shiftKey) return
              event.preventDefault()
              void handleSend()
            }}
          />
          <div className={styles.composerFooter}>
            <Select
              size="small"
              placeholder="选择提示词"
              popupMatchSelectWidth={false}
              style={{ minWidth: 150 }}
              options={prompts.map(item => ({
                value: item.id,
                label: `${item.scope === 'common' ? '公用' : '本书'} · ${item.title}`,
              }))}
              onChange={insertPrompt}
              value={undefined}
            />
            <Button type="primary" icon={<SendOutlined />} loading={busy} onClick={handleSend}>
              发送
            </Button>
          </div>
        </div>
      </div>
      <Modal
        title="保存为提示词"
        open={savePromptOpen}
        onCancel={() => setSavePromptOpen(false)}
        onOk={savePrompt}
        okText="保存"
        cancelText="取消"
      >
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Radio.Group value={promptScope} onChange={event => setPromptScope(event.target.value)}>
            <Radio value="project">当前小说</Radio>
            <Radio value="common">公用</Radio>
          </Radio.Group>
          <Input value={promptTitle} onChange={event => setPromptTitle(event.target.value)} placeholder="提示词简称" />
          <Input value={promptDesc} onChange={event => setPromptDesc(event.target.value)} placeholder="提示词简介，可选" />
          <Input.TextArea
            value={promptContent}
            onChange={event => setPromptContent(event.target.value)}
            autoSize={{ minRows: 6, maxRows: 12 }}
            placeholder="提示词内容"
          />
        </Space>
      </Modal>
    </div>
  )
}
