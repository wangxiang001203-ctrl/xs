import { useState, useEffect, useRef } from 'react'
import { Button, Input, Alert, Spin, message, Tag } from 'antd'
import { ThunderboltOutlined, CheckOutlined, EditOutlined } from '@ant-design/icons'
import CodeMirror from '@uiw/react-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { EditorView } from '@codemirror/view'
import { api, streamRequest } from '../api'
import { useAppStore } from '../store'
import type { Outline } from '../types'
import styles from './OutlinePage.module.css'

const { TextArea } = Input

export default function OutlinePage() {
  const { currentNovel, setCurrentNovel } = useAppStore()
  const [idea, setIdea] = useState(currentNovel?.idea || '')
  const [outline, setOutline] = useState<Outline | null>(null)
  const [generating, setGenerating] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [editing, setEditing] = useState(false)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (currentNovel) {
      setIdea(currentNovel.idea || '')
      loadOutline()
    }
  }, [currentNovel?.id])

  async function loadOutline() {
    if (!currentNovel) return
    try {
      const o = await api.outline.latest(currentNovel.id)
      setOutline(o)
      setEditContent(o.content || '')
    } catch {
      setOutline(null)
    }
  }

  function startGenerate() {
    if (!currentNovel || !idea.trim()) {
      message.warning('请先输入创意')
      return
    }
    setGenerating(true)
    setStreamText('')
    setOutline(null)

    abortRef.current = streamRequest(
      '/api/ai/generate/outline',
      { novel_id: currentNovel.id, idea, genre: currentNovel.genre },
      (chunk) => setStreamText(prev => prev + chunk),
      async () => {
        setGenerating(false)
        // 重新加载已保存的大纲
        await loadOutline()
        message.success('大纲生成完成')
      },
      (err) => {
        setGenerating(false)
        message.error(`生成失败：${err}`)
      },
    )
  }

  function stopGenerate() {
    abortRef.current?.abort()
    setGenerating(false)
  }

  async function confirmOutline() {
    if (!outline || !currentNovel) return
    setSaving(true)
    try {
      const updated = await api.outline.update(currentNovel.id, outline.id, {
        confirmed: true,
        content: editContent || outline.content,
      })
      setOutline(updated)
      // 更新小说idea
      await api.novels.update(currentNovel.id, { idea })
      setCurrentNovel({ ...currentNovel, idea })
      message.success('大纲已确认保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
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

  const displayContent = editing ? editContent : (outline?.content || streamText)

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
          {!generating ? (
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={startGenerate}
              disabled={!idea.trim()}
            >
              AI生成大纲
            </Button>
          ) : (
            <Button danger onClick={stopGenerate}>停止生成</Button>
          )}
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
            大纲
            {outline && <span className={styles.version}>v{outline.version}</span>}
          </span>
          <div className={styles.editorActions}>
            {outline && !editing && (
              <Button
                size="small" icon={<EditOutlined />}
                onClick={() => { setEditing(true); setEditContent(outline.content || '') }}
              >
                编辑
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
          </div>
        </div>

        {generating && !streamText && (
          <div className={styles.loadingArea}>
            <Spin tip="AI正在生成大纲..." />
          </div>
        )}

        {(streamText || displayContent) ? (
          editing ? (
            <CodeMirror
              value={editContent}
              onChange={setEditContent}
              extensions={[markdown(), EditorView.lineWrapping]}
              theme="dark"
              className={styles.editor}
            />
          ) : (
            <div className={styles.preview}>
              <pre className={styles.previewContent}>
                {displayContent}
                {generating && <span className={styles.cursor}>▋</span>}
              </pre>
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
          message="大纲已确认，可以开始创建角色和世界观设定，然后逐章编写细纲和正文。"
          showIcon
          className={styles.alert}
        />
      )}
    </div>
  )
}
