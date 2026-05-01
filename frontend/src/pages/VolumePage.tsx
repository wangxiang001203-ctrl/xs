import { useEffect, useMemo, useRef, useState } from 'react'
import { Alert, Button, Space, Spin, Tag, message } from 'antd'
import { CheckOutlined, SaveOutlined, ThunderboltOutlined } from '@ant-design/icons'

import { api } from '../api'
import { useAppStore } from '../store'
import type { VolumeWorkspace } from '../types'
import WritingToolbar from '../components/editor/WritingToolbar'
import NovelEditor, { type NovelEditorHandle } from '../components/editor/NovelEditor'
import styles from './VolumePage.module.css'

interface ChapterOutlineDraft {
  chapterId: string
  chapterNumber: number
  title?: string
  content: string
  status: string
  finalApproved: boolean
  synopsisReviewStatus: string
}

const CHINESE_DIGITS: Record<string, number> = {
  零: 0,
  〇: 0,
  一: 1,
  二: 2,
  两: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
}

const CHAPTER_NUMBER_PATTERN = '[0-9零〇一二两三四五六七八九十百千]+'

function parseChapterNumber(raw: string) {
  const text = raw.trim()
  if (/^\d+$/.test(text)) return Number(text)
  let result = 0
  let current = 0
  for (const char of text) {
    if (char === '千' || char === '百' || char === '十') {
      const unit = char === '千' ? 1000 : char === '百' ? 100 : 10
      result += (current || 1) * unit
      current = 0
      continue
    }
    if (char in CHINESE_DIGITS) {
      current = CHINESE_DIGITS[char]
    }
  }
  return result + current
}

function getChapterHeading(chapterNumber: number, title?: string) {
  const defaultTitle = `第${chapterNumber}章`
  const cleanTitle = normalizeChapterTitle(chapterNumber, title)
  return !cleanTitle || cleanTitle === defaultTitle ? defaultTitle : `${defaultTitle} ${cleanTitle}`
}

function normalizeChapterTitle(chapterNumber: number, title?: string) {
  const defaultTitle = `第${chapterNumber}章`
  return (title || '')
    .trim()
    .replace(new RegExp(`^第\\s*${CHAPTER_NUMBER_PATTERN}\\s*章\\s*[：:、\\-—]?\\s*`), '')
    .trim() || defaultTitle
}

function stripChapterHeading(content: string, chapterNumber: number) {
  const lines = (content || '').split(/\r?\n/)
  const firstContentIndex = lines.findIndex(line => line.trim())
  if (firstContentIndex === -1) return ''
  const firstLine = lines[firstContentIndex].trim()
  const headingPattern = new RegExp(`^#{0,6}\\s*第\\s*(${CHAPTER_NUMBER_PATTERN})\\s*章(?:\\s|$|[：:、\\-—])`)
  const match = firstLine.match(headingPattern)
  if (!match || parseChapterNumber(match[1]) !== chapterNumber) {
    return content.trim()
  }
  return [
    ...lines.slice(0, firstContentIndex),
    ...lines.slice(firstContentIndex + 1),
  ].join('\n').trim()
}

function parseVolumePlanMarkdown(markdown: string) {
  const result = new Map<number, { title?: string; content: string }>()
  const lines = (markdown || '').split(/\r?\n/)
  let currentNumber: number | null = null
  let currentTitle = ''
  let buffer: string[] = []

  function flush() {
    if (currentNumber === null) return
    const content = buffer.join('\n').trim()
    result.set(currentNumber, {
      title: currentTitle,
      content: content === '（待生成）' ? '' : content,
    })
  }

  for (const line of lines) {
    const match = line.match(new RegExp(`^\\s{0,3}#{0,6}\\s*第\\s*(${CHAPTER_NUMBER_PATTERN})\\s*章\\s*(.*)$`))
    if (match) {
      const nextNumber = parseChapterNumber(match[1])
      if (!Number.isFinite(nextNumber) || nextNumber <= 0) {
        continue
      }
      flush()
      currentNumber = nextNumber
      currentTitle = match[2]?.trim() || ''
      buffer = []
      continue
    }
    if (currentNumber !== null) {
      buffer.push(line)
    }
  }
  flush()
  return result
}

function getParsedChapterNumbers(markdown: string) {
  return [...parseVolumePlanMarkdown(markdown).keys()].sort((a, b) => a - b)
}

function chooseVolumePlanMarkdown(workspace: VolumeWorkspace, serverMarkdown: string, draftMarkdown?: string) {
  const cleanDraft = (draftMarkdown || '').trim()
  if (!cleanDraft) return serverMarkdown
  const serverChapterCount = getParsedChapterNumbers(serverMarkdown).length
  const draftChapterCount = getParsedChapterNumbers(cleanDraft).length
  const expectedCount = workspace.chapters.length || workspace.volume.planned_chapter_count || 0
  if (serverChapterCount && expectedCount && serverChapterCount >= expectedCount && draftChapterCount < serverChapterCount) {
    return serverMarkdown
  }
  return cleanDraft
}

function buildChapterOutlineDrafts(workspace: VolumeWorkspace, markdown: string): ChapterOutlineDraft[] {
  const parsed = parseVolumePlanMarkdown(markdown)
  return [...workspace.chapters]
    .sort((a, b) => a.chapter_number - b.chapter_number)
    .map((chapter) => {
      const parsedBlock = parsed.get(chapter.chapter_number)
      const fallbackContent = chapter.content_md?.trim()
        || chapter.content_preview?.trim()
        || chapter.plot_summary_update?.trim()
        || chapter.summary_line?.trim()
        || ''
      return {
        chapterId: chapter.id,
        chapterNumber: chapter.chapter_number,
        title: normalizeChapterTitle(chapter.chapter_number, parsedBlock?.title || chapter.title),
        content: stripChapterHeading(parsedBlock?.content || fallbackContent, chapter.chapter_number),
        status: chapter.status,
        finalApproved: chapter.final_approved,
        synopsisReviewStatus: chapter.synopsis_review_status,
      }
    })
}

function buildVolumePlanMarkdown(volume: VolumeWorkspace['volume'], chapterOutlines: ChapterOutlineDraft[]) {
  const parts = [
    `# 第${volume.volume_number}卷 ${volume.title}`,
    '',
    `本卷共 ${chapterOutlines.length} 章。`,
    '',
    '## 章节细纲',
    '',
  ]

  chapterOutlines.forEach((chapter) => {
    parts.push(`### ${getChapterHeading(chapter.chapterNumber, chapter.title)}`)
    parts.push(stripChapterHeading(chapter.content, chapter.chapterNumber) || '（待生成）')
    parts.push('')
  })

  return parts.join('\n').trim()
}

export default function VolumePage() {
  const {
    currentNovel,
    currentVolume,
    chapters,
    setVolumes,
    setCurrentVolume,
    setCurrentChapter,
    setChapters,
    documentDrafts,
    patchDocumentDraft,
    openTab,
  } = useAppStore()
  const [workspace, setWorkspace] = useState<VolumeWorkspace | null>(null)
  const [planMarkdown, setPlanMarkdown] = useState('')
  const [chapterOutlines, setChapterOutlines] = useState<ChapterOutlineDraft[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [approving, setApproving] = useState(false)
  const [searchValue, setSearchValue] = useState('')
  const editorRef = useRef<NovelEditorHandle>(null)
  const docKey = currentVolume ? `volume:${currentVolume.id}` : null

  useEffect(() => {
    if (!currentNovel || !currentVolume) return
    const draft = (docKey ? documentDrafts[docKey] : null) as { planMarkdown?: string } | null
    void loadWorkspace(draft?.planMarkdown)
  }, [currentNovel?.id, currentVolume?.id])

  useEffect(() => {
    if (!docKey) return
    patchDocumentDraft(docKey, { planMarkdown })
    if (workspace) {
      setChapterOutlines(buildChapterOutlineDrafts(workspace, planMarkdown))
    }
  }, [docKey, planMarkdown])

  async function loadWorkspace(draftPlan?: string) {
    if (!currentNovel || !currentVolume) return
    setLoading(true)
    try {
      await reloadVolumeState(draftPlan)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '分卷数据加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function reloadVolumeState(draftPlan?: string) {
    if (!currentNovel || !currentVolume) return null
    const [workspaceData, chapterList, volumeList] = await Promise.all([
      api.volumes.workspace(currentNovel.id, currentVolume.id),
      api.chapters.list(currentNovel.id),
      api.volumes.list(currentNovel.id),
    ])
    const serverMarkdown = workspaceData.volume_synopsis_markdown || workspaceData.volume.plan_markdown || ''
    const nextMarkdown = chooseVolumePlanMarkdown(workspaceData, serverMarkdown, draftPlan)
    setWorkspace(workspaceData)
    setPlanMarkdown(nextMarkdown)
    setChapterOutlines(buildChapterOutlineDrafts(workspaceData, nextMarkdown))
    setChapters(chapterList)
    setVolumes(volumeList)
    setCurrentVolume(volumeList.find(volume => volume.id === currentVolume.id) || workspaceData.volume || currentVolume)
    return workspaceData
  }

  async function savePlan() {
    if (!currentNovel || !currentVolume || !workspace) return
    setSaving(true)
    try {
      const updatePayload = buildPlanUpdatePayload()
      if (!updatePayload) return
      await api.volumes.update(currentNovel.id, currentVolume.id, updatePayload.payload as any)
      await reloadVolumeState(updatePayload.planMarkdown)
      message.success('分卷细纲已保存，并已同步到对应章节')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || err?.message || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function generateVolumeSynopsis() {
    if (!currentNovel || !currentVolume) return
    setGenerating(true)
    try {
      await api.ai.generateVolumeSynopsis(currentNovel.id, currentVolume.id)
      const refreshed = await reloadVolumeState()
      const readyCount = refreshed?.chapters.filter(item => item.content_md?.trim()).length || 0
      const expectedCount = refreshed?.chapters.length || refreshed?.volume.planned_chapter_count || 0
      if (expectedCount && readyCount < expectedCount) {
        message.warning(`已刷新本卷细纲，目前完成 ${readyCount}/${expectedCount} 章。请检查模型输出或调整提示后重新生成。`)
      } else {
        message.success('本卷全部章节细纲已生成，请先审完整卷节奏再进入正文')
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err.message || '生成失败'
      try {
        const refreshed = await reloadVolumeState()
        const readyCount = refreshed?.chapters.filter(item => item.content_md?.trim()).length || 0
        const expectedCount = refreshed?.chapters.length || refreshed?.volume.planned_chapter_count || 0
        if (readyCount > 0 && expectedCount) {
          message.warning(`${detail}。已刷新已落库的 ${readyCount}/${expectedCount} 章。`)
        } else {
          message.error(detail)
        }
      } catch {
        message.error(detail)
      }
    } finally {
      setGenerating(false)
    }
  }

  async function approveVolume() {
    if (!currentNovel || !currentVolume) return
    const blockReason = getApproveBlockReason()
    if (blockReason) {
      message.warning(blockReason)
      return
    }
    setApproving(true)
    try {
      const updatePayload = buildPlanUpdatePayload()
      if (updatePayload) {
        await api.volumes.update(currentNovel.id, currentVolume.id, updatePayload.payload as any)
      }
      const updated = await api.volumes.approve(currentNovel.id, currentVolume.id)
      await reloadVolumeState(updatePayload?.planMarkdown)
      setCurrentVolume(updated)
      message.success('本卷节奏已批准，可以开始逐章创作')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || err?.message || '审批失败')
    } finally {
      setApproving(false)
    }
  }

  function buildPlanUpdatePayload() {
    if (!workspace) return null
    const latestOutlines = buildChapterOutlineDrafts(workspace, planMarkdown)
    const parsedNumbers = getParsedChapterNumbers(planMarkdown)
    if (workspace.chapters.length && parsedNumbers.length !== workspace.chapters.length) {
      throw new Error(`当前文本里识别到 ${parsedNumbers.length} 章，但本卷已有 ${workspace.chapters.length} 章。请保持每一章都有“第X章”标题。`)
    }
    const emptyChapter = latestOutlines.find(item => !item.content.trim())
    if (emptyChapter) {
      throw new Error(`第${emptyChapter.chapterNumber}章还没有细纲内容，不能保存/审批。`)
    }
    const nextPlanMarkdown = planMarkdown.trim() || buildVolumePlanMarkdown(workspace.volume, latestOutlines)
    return {
      planMarkdown: nextPlanMarkdown,
      payload: {
        plan_markdown: nextPlanMarkdown,
        chapter_synopses: latestOutlines.map(chapter => ({
          chapter_id: chapter.chapterId,
          title: normalizeChapterTitle(chapter.chapterNumber, chapter.title),
          summary_line: chapter.content.trim().split(/\r?\n/).find(Boolean)?.slice(0, 120) || '',
          content_md: stripChapterHeading(chapter.content, chapter.chapterNumber),
        })),
      },
    }
  }

  const synopsisReadyCount = useMemo(() => (
    chapterOutlines.filter(item => Boolean(item.content.trim())).length
  ), [chapterOutlines])

  const volumeApproved = workspace?.volume.review_status === 'approved'
  const bookPlanApproved = workspace?.volume.plan_data?.book_plan_status === 'approved'
  const expectedSynopsisCount = workspace?.chapters.length || workspace?.volume.planned_chapter_count || 0
  const synopsisComplete = expectedSynopsisCount > 0 && synopsisReadyCount >= expectedSynopsisCount
  const orderedWorkspaceChapters = useMemo(
    () => [...(workspace?.chapters || [])].sort((a, b) => a.chapter_number - b.chapter_number),
    [workspace?.chapters],
  )

  function getApproveBlockReason() {
    if (!bookPlanApproved) return '请先审批全书分卷，再审批本卷节奏'
    if (volumeApproved) return '本卷节奏已经审批通过'
    if (!synopsisComplete) return `本卷细纲还没有补齐：${synopsisReadyCount}/${expectedSynopsisCount || 0} 章`
    return ''
  }

  const approveBlockReason = getApproveBlockReason()

  function openChapterForWriting(item: VolumeWorkspace['chapters'][number]) {
    if (!currentNovel || !currentVolume) return
    if (!volumeApproved) {
      message.warning('请先审批本卷细纲，再进入正文写作')
      return
    }
    if (!item.content_md?.trim() || item.synopsis_review_status !== 'approved') {
      message.warning(`第${item.chapter_number}章细纲尚未确认，不能进入正文`)
      return
    }
    const chapter = chapters.find(ch => ch.id === item.id)
    if (!chapter) {
      message.warning('章节列表还在同步，请稍后重试')
      return
    }
    const chapterForTab = { ...chapter, volume_id: chapter.volume_id || currentVolume.id }
    setCurrentChapter(chapterForTab)
    openTab({ type: 'chapter', novelSnapshot: currentNovel, chapterSnapshot: chapterForTab })
  }

  if (!currentNovel || !currentVolume) return <div className={styles.empty}>请选择一个分卷</div>

  if (loading && !workspace) {
    return (
      <div className={styles.empty}>
        <Spin size="small" />
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>第{currentVolume.volume_number}卷 {workspace?.volume.title || currentVolume.title}</div>
          <div className={styles.meta}>
            <span>预计 {workspace?.volume.planned_chapter_count || 0} 章</span>
            <span>细纲 {synopsisReadyCount}/{expectedSynopsisCount} 章</span>
            <span>目标 {workspace?.volume.target_words || 0} 字</span>
            <Tag color={workspace?.volume.review_status === 'approved' ? 'green' : 'orange'}>
              {workspace?.volume.review_status === 'approved' ? '节奏已批准' : '待审批'}
            </Tag>
          </div>
        </div>
        <Space>
          <Button icon={<SaveOutlined />} onClick={savePlan} loading={saving} disabled={!bookPlanApproved}>保存卷计划</Button>
          <Button icon={<ThunderboltOutlined />} onClick={generateVolumeSynopsis} loading={generating} disabled={!bookPlanApproved}>
            生成本卷全部细纲
          </Button>
          <Button type="primary" icon={<CheckOutlined />} onClick={approveVolume} loading={approving} disabled={Boolean(approveBlockReason)} title={approveBlockReason}>
            审批本卷节奏
          </Button>
        </Space>
      </div>

      {!bookPlanApproved ? (
        <Alert
          type="warning"
          showIcon
          message="全书分卷尚未审批。请先在“全书分卷”页确认整本书的卷级推进，再生成本卷章节细纲。"
          className={styles.alert}
        />
      ) : null}

      {bookPlanApproved && !volumeApproved && !synopsisComplete ? (
        <Alert
          type="info"
          showIcon
          message={`本卷需要一次性生成并审完全部章节细纲，当前 ${synopsisReadyCount}/${expectedSynopsisCount || 0} 章。`}
          className={styles.alert}
        />
      ) : null}

      <div className={styles.content}>
        {!volumeApproved ? (
          <div className={styles.planReviewLayout}>
            <section className={styles.editorShell}>
              <WritingToolbar
                title={`第${currentVolume.volume_number}卷细纲`}
                wordCount={planMarkdown.length}
                statusText="本地草稿会自动保留，保存后同步到章节细纲"
                searchValue={searchValue}
                searchCount={searchValue.trim() ? planMarkdown.split(searchValue.trim()).length - 1 : 0}
                onSearchChange={setSearchValue}
                onUndo={() => editorRef.current?.undo()}
                onRedo={() => editorRef.current?.redo()}
              />
              <NovelEditor
                ref={editorRef}
                value={planMarkdown}
                onChange={setPlanMarkdown}
                searchValue={searchValue}
                placeholder={`按固定格式写完整卷节奏：\n\n# 第${currentVolume.volume_number}卷 ${workspace?.volume.title || currentVolume.title}\n\n本卷概述：\n这里写本卷主线、核心矛盾、高潮和卷末钩子。\n\n第1章 章节标题\n这一章完整细纲写成一整块：本章目标、关键事件、冲突推进、爽点/转折、章末钩子。\n\n第2章 章节标题\n继续写下一章。`}
              />
            </section>
            <aside className={styles.outlinePreview}>
              <div className={styles.previewHeader}>
                <strong>章节细纲总览</strong>
                <Tag color={synopsisReadyCount === (workspace?.chapters.length || 0) && synopsisReadyCount > 0 ? 'green' : 'orange'}>
                  {synopsisReadyCount}/{workspace?.chapters.length || 0}
                </Tag>
              </div>
              <div className={styles.previewList}>
                {chapterOutlines.map(item => {
                  const ready = Boolean(item.content.trim())
                  return (
                    <button
                      type="button"
                      key={item.chapterId}
                      className={`${styles.previewItem} ${ready ? styles.ready : ''}`}
                      onClick={() => {
                        setSearchValue(`第${item.chapterNumber}章`)
                      }}
                    >
                      <span>
                        第{item.chapterNumber}章 {normalizeChapterTitle(item.chapterNumber, item.title)}
                      </span>
                      <small>{ready ? item.content.replace(/\s+/g, ' ').slice(0, 92) : '待生成本章细纲'}</small>
                      <Tag color={ready ? 'processing' : 'orange'}>{ready ? '已生成' : '待生成'}</Tag>
                    </button>
                  )
                })}
                {!chapterOutlines.length ? <div className={styles.emptyPlan}>生成后这里会一次性列出本卷所有章节细纲。</div> : null}
              </div>
            </aside>
          </div>
        ) : (
          <section className={styles.approvedShell}>
            <div className={styles.approvedHeader}>
              <div>
                <strong>本卷已确认，可以逐章写正文</strong>
                <span>所有已审批细纲都会映射为正文入口；定稿顺序由作者控制，系统只在定稿时做连续性校验。</span>
              </div>
              <Tag color="green">已锁定节奏</Tag>
            </div>
            <div className={styles.chapterRows}>
              {orderedWorkspaceChapters.map(item => {
                const synopsisApproved = Boolean(item.content_md?.trim()) && item.synopsis_review_status === 'approved'
                const disabled = !synopsisApproved
                const defaultTitle = `第${item.chapter_number}章`
                const displayTitle = !item.title || item.title === defaultTitle ? defaultTitle : `${defaultTitle} ${item.title}`
                return (
                  <button
                    type="button"
                    key={item.id}
                    className={styles.chapterRow}
                    disabled={disabled}
                    onClick={() => openChapterForWriting(item)}
                  >
                    <span className={styles.chapterRowTitle}>{displayTitle}</span>
                    <span className={styles.chapterRowSummary}>{item.content_preview || item.summary_line || '本章细纲已确认'}</span>
                    <Tag color={item.final_approved ? 'green' : synopsisApproved ? 'processing' : 'orange'}>
                      {item.final_approved ? '已定稿' : synopsisApproved ? '去写正文' : '细纲待确认'}
                    </Tag>
                  </button>
                )
              })}
              {!orderedWorkspaceChapters.length ? (
                <div className={styles.emptyPlan}>本卷还没有章节。</div>
              ) : null}
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
