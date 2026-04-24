import { useState, useEffect } from 'react'
import { Button, Input, Alert, Spin, message, Tag, Radio, Space, Modal } from 'antd'
import { ThunderboltOutlined, CheckOutlined, EditOutlined } from '@ant-design/icons'
import { api } from '../api'
import { useAppStore } from '../store'
import type { Outline } from '../types'
import styles from './OutlinePage.module.css'

const { TextArea } = Input

interface OutlineDraft {
  idea?: string
  editContent?: string
  titlePrompt?: string
  titleOptions?: string[]
  selectedTitle?: string
  synopsis?: string
  editing?: boolean
}

export default function OutlinePage() {
  const {
    currentNovel,
    setCurrentNovel,
    setCharacters,
    setWorldbuilding,
    setVolumes,
    documentDrafts,
    patchDocumentDraft,
    clearDocumentDraft,
  } = useAppStore()
  const [idea, setIdea] = useState(currentNovel?.idea || '')
  const [outline, setOutline] = useState<Outline | null>(null)
  const [generating, setGenerating] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [titlePrompt, setTitlePrompt] = useState('')
  const [titleOptions, setTitleOptions] = useState<string[]>([])
  const [selectedTitle, setSelectedTitle] = useState<string>('')
  const [generatingTitles, setGeneratingTitles] = useState(false)
  const [synopsis, setSynopsis] = useState(currentNovel?.synopsis || '')
  const [titleModalOpen, setTitleModalOpen] = useState(false)
  const docKey = currentNovel ? `outline:${currentNovel.id}` : null
  const outlineDraft = (docKey ? documentDrafts[docKey] : null) as OutlineDraft | null

  useEffect(() => {
    if (currentNovel) {
      setIdea(outlineDraft?.idea ?? currentNovel.idea ?? '')
      setSynopsis(outlineDraft?.synopsis ?? currentNovel.synopsis ?? '')
      setSelectedTitle(outlineDraft?.selectedTitle ?? '')
      setTitlePrompt(outlineDraft?.titlePrompt ?? '')
      setTitleOptions(outlineDraft?.titleOptions ?? [])
      setEditing(Boolean(outlineDraft?.editing))
      loadOutline(outlineDraft)
    }
  }, [currentNovel?.id])

  useEffect(() => {
    if (!docKey) return
    patchDocumentDraft(docKey, {
      idea,
      editContent,
      titlePrompt,
      titleOptions,
      selectedTitle,
      synopsis,
      editing,
    })
  }, [docKey, idea, editContent, titlePrompt, titleOptions, selectedTitle, synopsis, editing])

  async function loadOutline(draft?: OutlineDraft | null) {
    if (!currentNovel) return
    try {
      const o = await api.outline.latest(currentNovel.id)
      setOutline(o)
      if (!draft?.editContent) {
        setEditContent(o.content || '')
      }
      if (!draft?.selectedTitle) {
        setSelectedTitle(o.title || '')
      }
      if (!draft?.synopsis) {
        setSynopsis(o.synopsis || currentNovel.synopsis || '')
      }
    } catch {
      setOutline(null)
      if (!draft?.editContent) {
        setEditContent('')
      }
    }
  }

  function startGenerate() {
    if (!currentNovel || !idea.trim()) {
      message.warning('请先输入创意')
      return
    }
    setGenerating(true)
    setOutline(null)
    api.ai.generateOutline(currentNovel.id, idea)
      .then((data) => {
        setOutline(data)
        setEditContent(data.content || '')
        setSelectedTitle(data.title || '')
        setSynopsis(data.synopsis || '')
        message.success('大纲生成完成')
        setCurrentNovel({
          ...currentNovel,
          idea,
        })
      })
      .catch((err: any) => {
        message.error(`生成失败：${err?.response?.data?.detail || err.message}`)
      })
      .finally(() => {
        setGenerating(false)
      })
  }

  async function confirmOutline() {
    if (!outline || !currentNovel || !docKey) return
    setSaving(true)
    try {
      const updated = await api.outline.update(currentNovel.id, outline.id, {
        confirmed: true,
        content: editContent || outline.content,
        title: selectedTitle || outline.title,
        synopsis: synopsis || outline.synopsis,
      })
      setOutline(updated)
      await api.novels.update(currentNovel.id, { idea })
      const [novel, volumes, chars, wb] = await Promise.all([
        api.novels.get(currentNovel.id),
        api.volumes.list(currentNovel.id).catch(() => []),
        api.characters.list(currentNovel.id),
        api.worldbuilding.get(currentNovel.id).catch(() => null),
      ])
      setCurrentNovel(novel)
      setVolumes(volumes)
      setCharacters(chars)
      setWorldbuilding(wb)
      setSelectedTitle(updated.title || selectedTitle)
      setSynopsis(updated.synopsis || synopsis)
      clearDocumentDraft(docKey)
      message.success('大纲已确认保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function generateTitles() {
    if (!currentNovel) return
    if (!outline?.confirmed) {
      message.warning('请先确认大纲')
      return
    }
    setGeneratingTitles(true)
    try {
      const res = await api.ai.generateTitles(currentNovel.id, titlePrompt.trim() || undefined)
      if (!res.titles?.length) {
        message.warning('未生成可用标题，请重试')
        return
      }
      setTitleOptions(res.titles)
      setSelectedTitle('')
      message.success('已生成10个候选标题')
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '标题生成失败')
    } finally {
      setGeneratingTitles(false)
    }
  }

  async function applySelectedTitle() {
    if (!currentNovel) return
    if (!selectedTitle) {
      message.warning('请先选择一个标题')
      return
    }
    try {
      const updated = await api.novels.update(currentNovel.id, { title: selectedTitle })
      setCurrentNovel(updated)
      setTitleModalOpen(false)
      message.success('书名已替换')
    } catch {
      message.error('书名更新失败')
    }
  }

  async function saveEdit() {
    if (!outline || !currentNovel) return
    setSaving(true)
    try {
      const updated = await api.outline.update(currentNovel.id, outline.id, {
        content: editContent,
      })
      setOutline(updated)
      setEditing(false)
      message.success('已保存')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={styles.page}>
      {/* 顶部：Idea输入 */}
      <div className={styles.ideaSection}>
        <div className={styles.sectionLabel}>创意 / Idea</div>
        <TextArea
          value={idea}
          onChange={e => setIdea(e.target.value)}
          placeholder="描述你的小说创意，例如：一个废柴少年意外获得上古传承，踏上修仙之路，最终成为一代仙帝..."
          autoSize={{ minRows: 3, maxRows: 6 }}
          className={styles.ideaInput}
          disabled={generating}
        />
        <div className={styles.ideaActions}>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={startGenerate}
            disabled={!idea.trim() || generating}
            loading={generating}
          >
            AI生成大纲
          </Button>
          {outline && !outline.confirmed && (
            <Tag color="orange">待确认</Tag>
          )}
          {outline?.confirmed && (
            <Tag color="green">已确认</Tag>
          )}
        </div>
      </div>

      {/* 大纲编辑区 */}
      <div className={styles.editorSection}>
        <div className={styles.editorHeader}>
          <span className={styles.sectionLabel}>
            大纲内容
            {outline && <span className={styles.version}>v{outline.version}</span>}
          </span>
          <div className={styles.editorActions}>
            {outline && !editing && (
              <Button
                size="small" icon={<EditOutlined />}
                onClick={() => { setEditing(true); setEditContent(editContent || outline.content || '') }}
              >
                编辑大纲
              </Button>
            )}
            {editing && (
              <>
                <Button size="small" onClick={() => setEditing(false)}>取消</Button>
                <Button size="small" type="primary" loading={saving} onClick={saveEdit}>保存</Button>
              </>
            )}
            {outline && !outline.confirmed && !editing && (
              <Button
                size="small" type="primary"
                icon={<CheckOutlined />}
                loading={saving}
                onClick={confirmOutline}
              >
                确认大纲
              </Button>
            )}
            {outline?.confirmed && !editing && (
              <Button size="small" onClick={() => setTitleModalOpen(true)}>
                重新生成标题
              </Button>
            )}
          </div>
        </div>

        {generating && (
          <div className={styles.loadingArea}>
            <Spin tip="AI正在推演大纲结构..." />
          </div>
        )}

        {outline ? (
          editing ? (
            <TextArea
              value={editContent}
              onChange={event => setEditContent(event.target.value)}
              autoSize={false}
              className={`${styles.editor} ${styles.editorTextarea}`}
            />
          ) : (
            <div className={styles.preview}>
              <pre className={styles.previewContent}>{outline.content}</pre>
            </div>
          )
        ) : (
          !generating && (
            <div className={styles.emptyEditor}>
              <span>输入创意后点击「AI生成大纲」</span>
            </div>
          )
        )}
      </div>

      {outline?.confirmed && (
        <Alert
          type="success"
          message="大纲已确认！现在你可以前往「角色库」和「世界观」让 AI 自动推演设定了。"
          showIcon
          className={styles.alert}
        />
      )}

      <Modal
        title="生成标题（10选1）"
        open={titleModalOpen}
        onCancel={() => setTitleModalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Input.TextArea
          value={titlePrompt}
          onChange={e => setTitlePrompt(e.target.value)}
          placeholder="可选：输入标题偏好，例如“偏热血、四字短标题、避免生僻字”"
          autoSize={{ minRows: 2, maxRows: 4 }}
        />
        <Space className={styles.postActions}>
          <Button loading={generatingTitles} onClick={generateTitles} type="primary">
            生成10个标题
          </Button>
          <Button onClick={applySelectedTitle} disabled={!selectedTitle}>
            选择并替换书名
          </Button>
        </Space>
        {!!titleOptions.length && (
          <Radio.Group
            className={styles.titleRadioGroup}
            value={selectedTitle}
            onChange={e => setSelectedTitle(e.target.value)}
          >
            <Space direction="vertical">
              {titleOptions.map((t) => (
                <Radio key={t} value={t}>{t}</Radio>
              ))}
            </Space>
          </Radio.Group>
        )}
      </Modal>

    </div>
  )
}
