import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Collapse, Input, Space, Spin, Tag, message } from 'antd'
import { CheckOutlined, SaveOutlined, ThunderboltOutlined } from '@ant-design/icons'

import { api } from '../api'
import { useAppStore } from '../store'
import type { VolumeWorkspace } from '../types'
import styles from './VolumePage.module.css'

const { TextArea } = Input

interface ChapterOutlineDraft {
  chapterId: string
  chapterNumber: number
  title?: string
  content: string
  status: string
  finalApproved: boolean
  synopsisReviewStatus: string
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
    .replace(new RegExp(`^第\\s*${chapterNumber}\\s*章\\s*[：:、\\-—]?\\s*`), '')
    .trim() || defaultTitle
}

function stripChapterHeading(content: string, chapterNumber: number) {
  const lines = (content || '').split(/\r?\n/)
  const firstContentIndex = lines.findIndex(line => line.trim())
  if (firstContentIndex === -1) return ''
  const firstLine = lines[firstContentIndex].trim()
  const headingPattern = new RegExp(`^#{0,6}\\s*第\\s*${chapterNumber}\\s*章(?:\\s|$|[：:、\\-—])`)
  if (!headingPattern.test(firstLine)) {
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
    const match = line.match(/^\s{0,3}#{0,6}\s*第\s*(\d+)\s*章\s*(.*)$/)
    if (match) {
      flush()
      currentNumber = Number(match[1])
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
  const docKey = currentVolume ? `volume:${currentVolume.id}` : null

  useEffect(() => {
    if (!currentNovel || !currentVolume) return
    const draft = (docKey ? documentDrafts[docKey] : null) as { planMarkdown?: string } | null
    void loadWorkspace(draft?.planMarkdown)
  }, [currentNovel?.id, currentVolume?.id])

  useEffect(() => {
    if (!docKey) return
    patchDocumentDraft(docKey, { planMarkdown })
  }, [docKey, planMarkdown])

  async function loadWorkspace(draftPlan?: string) {
    if (!currentNovel || !currentVolume) return
    setLoading(true)
    try {
      const data = await api.volumes.workspace(currentNovel.id, currentVolume.id)
      const nextMarkdown = draftPlan ?? data.volume_synopsis_markdown ?? data.volume.plan_markdown ?? ''
      setWorkspace(data)
      setPlanMarkdown(nextMarkdown)
      setChapterOutlines(buildChapterOutlineDrafts(data, nextMarkdown))
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '分卷数据加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function savePlan() {
    if (!currentNovel || !currentVolume || !workspace) return
    setSaving(true)
    try {
      const updatePayload = buildPlanUpdatePayload()
      if (!updatePayload) return
      const updated = await api.volumes.update(currentNovel.id, currentVolume.id, updatePayload.payload as any)
      const [workspaceData, chapterList, volumeList] = await Promise.all([
        api.volumes.workspace(currentNovel.id, currentVolume.id),
        api.chapters.list(currentNovel.id),
        api.volumes.list(currentNovel.id),
      ])
      const nextMarkdown = workspaceData.volume_synopsis_markdown || workspaceData.volume.plan_markdown || updatePayload.planMarkdown
      setVolumes(volumeList.map(volume => (volume.id === updated.id ? updated : volume)))
      setCurrentVolume(volumeList.find(volume => volume.id === currentVolume.id) || updated)
      setWorkspace(workspaceData)
      setPlanMarkdown(nextMarkdown)
      setChapterOutlines(buildChapterOutlineDrafts(workspaceData, nextMarkdown))
      setChapters(chapterList)
      message.success('分卷细纲已保存，并已同步到对应章节')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function generateVolumeSynopsis() {
    if (!currentNovel || !currentVolume) return
    setGenerating(true)
    try {
      await api.ai.generateVolumeSynopsis(currentNovel.id, currentVolume.id)
      const [workspaceData, chapterList, volumeList] = await Promise.all([
        api.volumes.workspace(currentNovel.id, currentVolume.id),
        api.chapters.list(currentNovel.id),
        api.volumes.list(currentNovel.id),
      ])
      const nextMarkdown = workspaceData.volume_synopsis_markdown || workspaceData.volume.plan_markdown || ''
      setWorkspace(workspaceData)
      setPlanMarkdown(nextMarkdown)
      setChapterOutlines(buildChapterOutlineDrafts(workspaceData, nextMarkdown))
      setChapters(chapterList)
      setVolumes(volumeList)
      setCurrentVolume(volumeList.find(volume => volume.id === currentVolume.id) || currentVolume)
      message.success('本卷细纲已生成，请先审完整卷节奏再进入正文')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || err.message || '生成失败')
    } finally {
      setGenerating(false)
    }
  }

  async function approveVolume() {
    if (!currentNovel || !currentVolume) return
    setApproving(true)
    try {
      const updatePayload = buildPlanUpdatePayload()
      if (updatePayload) {
        await api.volumes.update(currentNovel.id, currentVolume.id, updatePayload.payload as any)
      }
      const updated = await api.volumes.approve(currentNovel.id, currentVolume.id)
      const [workspaceData, chapterList, volumeList] = await Promise.all([
        api.volumes.workspace(currentNovel.id, currentVolume.id),
        api.chapters.list(currentNovel.id),
        api.volumes.list(currentNovel.id),
      ])
      const nextMarkdown = workspaceData.volume_synopsis_markdown || workspaceData.volume.plan_markdown || ''
      setVolumes(volumeList.map(volume => (volume.id === updated.id ? updated : volume)))
      setCurrentVolume(updated)
      setWorkspace(workspaceData)
      setPlanMarkdown(nextMarkdown)
      setChapterOutlines(buildChapterOutlineDrafts(workspaceData, nextMarkdown))
      setChapters(chapterList)
      message.success('本卷节奏已批准，可以开始逐章创作')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '审批失败')
    } finally {
      setApproving(false)
    }
  }

  function buildPlanUpdatePayload() {
    if (!workspace) return null
    const nextPlanMarkdown = buildVolumePlanMarkdown(workspace.volume, chapterOutlines)
    return {
      planMarkdown: nextPlanMarkdown,
      payload: {
        plan_markdown: nextPlanMarkdown,
        chapter_synopses: chapterOutlines.map(chapter => ({
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
  const orderedWorkspaceChapters = useMemo(
    () => [...(workspace?.chapters || [])].sort((a, b) => a.chapter_number - b.chapter_number),
    [workspace?.chapters],
  )

  function updateChapterOutline(chapterId: string, content: string) {
    if (!workspace) return
    const nextOutlines = chapterOutlines.map(item => (
      item.chapterId === chapterId ? { ...item, content } : item
    ))
    setChapterOutlines(nextOutlines)
    setPlanMarkdown(buildVolumePlanMarkdown(workspace.volume, nextOutlines))
  }

  function buildChapterCollapseItems() {
    return chapterOutlines.map((chapter) => {
      const chapterNumber = chapter.chapterNumber
      const sourceChapter = orderedWorkspaceChapters.find(item => item.id === chapter.chapterId)
      const synopsisApproved = Boolean(chapter.content.trim()) && chapter.synopsisReviewStatus === 'approved'
      const lockedByPrevious = !canOpenChapterContent(chapterNumber)
      const canWrite = volumeApproved && synopsisApproved && !lockedByPrevious
      return {
        key: chapter.chapterId,
        label: (
          <div className={styles.chapterPanelLabel}>
            <span>{getChapterHeading(chapterNumber, chapter.title)}</span>
            <span className={styles.chapterPanelMeta}>{chapter.content.trim().length || 0} 字</span>
          </div>
        ),
        extra: (
          <Space size={6} onClick={event => event.stopPropagation()}>
            <Tag color={chapter.content.trim() ? 'green' : 'orange'}>
              {chapter.content.trim() ? '有细纲' : '待补'}
            </Tag>
            <Button
              size="small"
              disabled={!sourceChapter || !canWrite}
              onClick={() => sourceChapter && openChapterForWriting(sourceChapter)}
            >
              写正文
            </Button>
          </Space>
        ),
        children: (
          <div className={styles.chapterPanelBody}>
            <TextArea
              value={chapter.content}
              onChange={event => updateChapterOutline(chapter.chapterId, event.target.value)}
              autoSize={{ minRows: 7, maxRows: 18 }}
              className={styles.chapterOutlineEditor}
              placeholder={`写第${chapterNumber}章的一整块细纲：本章目标、关键事件、冲突推进、爽点/转折、章末钩子。`}
            />
          </div>
        ),
      }
    })
  }

  function canOpenChapterContent(chapterNumber: number) {
    if (chapterNumber <= 1) return true
    const previous = [...chapters]
      .filter(item => item.chapter_number < chapterNumber)
      .sort((a, b) => b.chapter_number - a.chapter_number)[0]
    return previous ? previous.final_approved : true
  }

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
    if (!canOpenChapterContent(item.chapter_number)) {
      message.warning('上一章尚未人工定稿，暂时不能进入这一章正文')
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
            <span>细纲 {synopsisReadyCount}/{workspace?.chapters.length || workspace?.volume.planned_chapter_count || 0} 章</span>
            <span>目标 {workspace?.volume.target_words || 0} 字</span>
            <Tag color={workspace?.volume.review_status === 'approved' ? 'green' : 'orange'}>
              {workspace?.volume.review_status === 'approved' ? '节奏已批准' : '待审批'}
            </Tag>
          </div>
        </div>
        <Space>
          <Button icon={<SaveOutlined />} onClick={savePlan} loading={saving}>保存卷计划</Button>
          <Button icon={<ThunderboltOutlined />} onClick={generateVolumeSynopsis} loading={generating}>
            生成本卷全部细纲
          </Button>
          <Button type="primary" icon={<CheckOutlined />} onClick={approveVolume} loading={approving}>
            审批本卷节奏
          </Button>
        </Space>
      </div>

      {workspace?.pending_proposals?.length ? (
        <Alert
          type="warning"
          showIcon
          message={`本卷还有 ${workspace.pending_proposals.length} 条待审阅实体提案，处理后才能通过卷节奏审批。`}
          className={styles.alert}
        />
      ) : null}

      <div className={styles.content}>
        <Card
          title={`第${currentVolume.volume_number}卷章节细纲`}
          className={styles.planCard}
          extra={<span className={styles.planHint}>按章节折叠审阅，章数跟随本卷数据，不固定 40 章。</span>}
        >
          {chapterOutlines.length ? (
            <Collapse
              className={styles.chapterCollapse}
              items={buildChapterCollapseItems()}
              defaultActiveKey={chapterOutlines.slice(0, 3).map(item => item.chapterId)}
            />
          ) : (
            <div className={styles.emptyPlan}>
              当前分卷还没有章节。点击“生成本卷全部细纲”后，会按本卷计划章数先创建章节，再一次性生成整卷细纲。
            </div>
          )}
        </Card>
        <aside className={styles.chapterRail}>
          <div className={styles.railTitle}>章节写作入口</div>
          <div className={styles.railHint}>
            先确认整卷节奏，再点具体章节进入正文。已开写章节对应的细纲不能从卷计划中删除。
          </div>
          <div className={styles.chapterList}>
            {orderedWorkspaceChapters.length ? orderedWorkspaceChapters.map(item => {
              const lockedByPrevious = !canOpenChapterContent(item.chapter_number)
              const synopsisApproved = Boolean(item.content_md?.trim()) && item.synopsis_review_status === 'approved'
              const disabled = !volumeApproved || !synopsisApproved || lockedByPrevious
              const defaultTitle = `第${item.chapter_number}章`
              const displayTitle = !item.title || item.title === defaultTitle ? defaultTitle : `${defaultTitle} ${item.title}`
              return (
                <button
                  type="button"
                  key={item.id}
                  className={styles.chapterEntry}
                  disabled={disabled}
                  onClick={() => openChapterForWriting(item)}
                >
                  <span className={styles.chapterEntryTitle}>
                    {displayTitle}
                  </span>
                  <span className={styles.chapterEntryMeta}>
                    {item.final_approved ? '已定稿' : lockedByPrevious ? '等上一章定稿' : synopsisApproved ? '可写作' : '细纲待确认'}
                  </span>
                </button>
              )
            }) : (
              <div className={styles.emptyRail}>生成本卷细纲后，这里会出现逐章写作入口。</div>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}
