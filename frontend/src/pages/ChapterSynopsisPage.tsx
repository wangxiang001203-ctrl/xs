import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Input, Space, Tag, message } from 'antd'
import { CheckOutlined, EditOutlined, FileTextOutlined } from '@ant-design/icons'

import { api } from '../api'
import { useAppStore } from '../store'
import type { Synopsis } from '../types'
import styles from './ChapterSynopsisPage.module.css'

const { TextArea } = Input

export default function ChapterSynopsisPage() {
  const {
    currentNovel,
    currentChapter,
    currentVolume,
    chapters,
    setCurrentChapter,
    documentDrafts,
    patchDocumentDraft,
    openTab,
  } = useAppStore()
  const [synopsis, setSynopsis] = useState<Synopsis | null>(null)
  const [contentMd, setContentMd] = useState('')
  const [saving, setSaving] = useState(false)
  const [approving, setApproving] = useState(false)
  const docKey = currentChapter ? `chapter_synopsis:${currentChapter.id}` : null

  const previousChapter = useMemo(() => {
    if (!currentChapter || currentChapter.chapter_number <= 1) return null
    return [...chapters]
      .filter(item => item.chapter_number < currentChapter.chapter_number)
      .sort((a, b) => b.chapter_number - a.chapter_number)[0] || null
  }, [chapters, currentChapter?.id, currentChapter?.chapter_number])

  useEffect(() => {
    void loadData()
  }, [currentChapter?.id])

  useEffect(() => {
    if (!docKey) return
    patchDocumentDraft(docKey, { contentMd })
  }, [docKey, contentMd])

  async function loadData(ignoreDraft = false) {
    if (!currentNovel || !currentChapter) return
    const draft = (ignoreDraft || !docKey ? null : documentDrafts[docKey]) as { contentMd?: string } | null
    try {
      const loaded = await api.chapters.getSynopsis(currentNovel.id, currentChapter.id)
      setSynopsis(loaded)
      setContentMd(draft?.contentMd ?? loaded.content_md ?? '')
    } catch {
      setSynopsis(null)
      setContentMd(draft?.contentMd ?? '')
    }
  }

  async function saveSynopsis() {
    if (!currentNovel || !currentChapter) return
    setSaving(true)
    try {
      const saved = await api.chapters.upsertSynopsis(currentNovel.id, currentChapter.id, {
        ...(synopsis || {}),
        content_md: contentMd,
        review_status: 'draft',
      })
      setSynopsis(saved)
      setContentMd(saved.content_md || '')
      message.success('单章细纲已保存')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function approveSynopsis() {
    if (!currentNovel || !currentChapter) return
    setApproving(true)
    try {
      const approved = await api.review.approveSynopsis(currentNovel.id, currentChapter.id)
      setSynopsis(approved)
      setContentMd(approved.content_md || '')
      message.success('本章细纲已审批通过')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '审批失败')
    } finally {
      setApproving(false)
    }
  }

  function openContentEditor() {
    if (!currentNovel || !currentChapter) return
    if (currentVolume && currentVolume.review_status !== 'approved') {
      message.warning(`《${currentVolume.title}》的分卷节奏还没审批，先把本卷节奏定下来再进正文`)
      return
    }
    if (!synopsis || synopsis.review_status !== 'approved') {
      message.warning('请先审批当前章节细纲，再进入正文')
      return
    }
    if (previousChapter && !previousChapter.final_approved) {
      message.warning(`第${previousChapter.chapter_number}章尚未定稿，不能进入本章正文`)
      return
    }
    setCurrentChapter(currentChapter)
    openTab({ type: 'chapter', novelSnapshot: currentNovel, chapterSnapshot: currentChapter })
  }

  if (!currentNovel || !currentChapter) return <div className={styles.empty}>请选择章节细纲</div>

  const warnings = [
    !synopsis || !synopsis.content_md ? '当前章还没有来自整卷生成的细纲，请回到分卷页生成整卷细纲。' : null,
    currentVolume && currentVolume.review_status !== 'approved' ? `《${currentVolume.title}》分卷节奏尚未审批，当前只建议编辑细纲，不建议开始正文。` : null,
    previousChapter && !previousChapter.final_approved ? `第${previousChapter.chapter_number}章尚未定稿，本章正文仍被门禁锁定。` : null,
  ].filter(Boolean) as string[]

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>第{currentChapter.chapter_number}章细纲</div>
          <div className={styles.meta}>
            <Tag color={synopsis?.review_status === 'approved' ? 'green' : 'orange'}>
              {synopsis?.review_status === 'approved' ? '细纲已批' : '细纲待批'}
            </Tag>
            {synopsis?.summary_line ? <span className={styles.summary}>{synopsis.summary_line}</span> : null}
          </div>
          {synopsis?.plot_summary_update ? (
            <div className={styles.plotSummary}>主线提炼文件：{synopsis.plot_summary_update}</div>
          ) : null}
        </div>
        <Space>
          <Button icon={<EditOutlined />} onClick={saveSynopsis} loading={saving}>
            保存细纲
          </Button>
          <Button icon={<CheckOutlined />} onClick={approveSynopsis} loading={approving}>
            审批细纲
          </Button>
          <Button type="primary" icon={<FileTextOutlined />} onClick={openContentEditor}>
            打开正文
          </Button>
        </Space>
      </div>

      {warnings.map((item) => (
        <Alert key={item} className={styles.alert} type="warning" showIcon message={item} />
      ))}

      <Card className={styles.editorCard} title="单章细纲文档">
        <TextArea
          value={contentMd}
          onChange={event => setContentMd(event.target.value)}
          className={styles.editor}
          autoSize={false}
          placeholder="这里保存这一章的完整细纲文档，作者和 AI 都围绕这一整块内容来修改。"
        />
      </Card>
    </div>
  )
}
