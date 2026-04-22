import { useState, useEffect, useRef } from 'react'
import { Button, Input, Alert, Spin, message, Tag, Radio, Space, Modal } from 'antd'
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
  const [titlePrompt, setTitlePrompt] = useState('')
  const [titleOptions, setTitleOptions] = useState<string[]>([])
  const [selectedTitle, setSelectedTitle] = useState<string>('')
  const [generatingTitles, setGeneratingTitles] = useState(false)
  const [synopsisPrompt, setSynopsisPrompt] = useState('')
  const [synopsis, setSynopsis] = useState(currentNovel?.synopsis || '')
  const [generatingSynopsis, setGeneratingSynopsis] = useState(false)
  const [titleModalOpen, setTitleModalOpen] = useState(false)
  const [synopsisModalOpen, setSynopsisModalOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    if (currentNovel) {
      setIdea(currentNovel.idea || '')
      setSynopsis(currentNovel.synopsis || '')
      setSelectedTitle(currentNovel.title || '')
      loadOutline()
    }
  }, [currentNovel?.id])

  useEffect(() => {
    setSynopsis(currentNovel?.synopsis || '')
    setSelectedTitle(currentNovel?.title || '')
  }, [currentNovel?.title, currentNovel?.synopsis])

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
    setOutline(null)
    setStreamText('AI 正在推演大纲结构，请稍候...')

    fetch('/api/ai/generate/outline', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ novel_id: currentNovel.id, idea })
    })
      .then(async (res) => {
        if (!res.ok) throw new Error('生成失败')
        const data = await res.json()
        setOutline(data)
        setEditContent(data.content)
        message.success('大纲生成完成')
        
        // 更新小说状态
        setCurrentNovel({
          ...currentNovel,
          idea,
          title: data.title || currentNovel.title,
          synopsis: data.synopsis || currentNovel.synopsis
        })
      })
      .catch((err) => {
        message.error(`生成失败：${err.message}`)
      })
      .finally(() => {
        setGenerating(false)
        setStreamText('')
      })
  }

  function stopGenerate() {
    setGenerating(false)
    setStreamText('')
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
      message.success('书名已替换')
    } catch {
      message.error('书名更新失败')
    }
  }

  async function generateSynopsis() {
    if (!currentNovel) return
    if (!outline?.confirmed) {
      message.warning('请先确认大纲')
      return
    }
    setGeneratingSynopsis(true)
    try {
      const res = await api.ai.generateBookSynopsis(currentNovel.id, synopsisPrompt.trim() || undefined)
      setSynopsis(res.synopsis || '')
      const updated = await api.novels.get(currentNovel.id)
      setCurrentNovel(updated)
      message.success('简介已生成并保存到文件')
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '简介生成失败')
    } finally {
      setGeneratingSynopsis(false)
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
            大纲内容
            {outline && <span className={styles.version}>v{outline.version}</span>}
          </span>
          <div className={styles.editorActions}>
            {outline && !editing && (
              <Button
                size="small" icon={<EditOutlined />}
                onClick={() => { setEditing(true); setEditContent(outline.content || '') }}
              >
                编辑源码
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
              <>
                <Button size="small" onClick={() => setTitleModalOpen(true)}>
                  重新生成标题
                </Button>
                <Button size="small" onClick={() => setSynopsisModalOpen(true)}>
                  重新生成简介
                </Button>
              </>
            )}
          </div>
        </div>

        {generating && !streamText && (
          <div className={styles.loadingArea}>
            <Spin tip="AI正在推演大纲结构..." />
          </div>
        )}

        {(streamText || outline) ? (
          editing ? (
            <CodeMirror
              value={editContent}
              onChange={setEditContent}
              extensions={[markdown(), EditorView.lineWrapping]}
              theme="dark"
              className={styles.editor}
            />
          ) : (
            <div className={styles.structuredOutline}>
              {outline ? (
                <>
                  <div className={styles.fieldGroup}>
                    <h3>书名</h3>
                    <p>{outline.title || currentNovel?.title}</p>
                  </div>
                  <div className={styles.fieldGroup}>
                    <h3>简介</h3>
                    <p>{outline.synopsis || currentNovel?.synopsis}</p>
                  </div>
                  <div className={styles.fieldGroup}>
                    <h3>核心卖点 / 金手指</h3>
                    <p>{outline.selling_points || '暂无'}</p>
                  </div>
                  <div className={styles.fieldGroup}>
                    <h3>主线大纲</h3>
                    <pre className={styles.plotContent}>{outline.main_plot || '暂无'}</pre>
                  </div>
                </>
              ) : (
                <div className={styles.preview}>
                  <pre className={styles.previewContent}>{streamText}</pre>
                </div>
              )}
            </div>
          )
        ) : (
          !generating && (
            <div className={styles.emptyEditor}>
              <span>输入创意后点击「AI推演企划」</span>
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

      <Modal
        title="生成简介"
        open={synopsisModalOpen}
        onCancel={() => setSynopsisModalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Input.TextArea
          value={synopsisPrompt}
          onChange={e => setSynopsisPrompt(e.target.value)}
          placeholder="可选：输入简介偏好，例如“强调成长线与复仇线，语气更燃”"
          autoSize={{ minRows: 2, maxRows: 4 }}
        />
        <Space className={styles.postActions}>
          <Button loading={generatingSynopsis} onClick={generateSynopsis} type="primary">
            生成简介
          </Button>
        </Space>
        {!!synopsis && (
          <pre className={styles.synopsisPreview}>{synopsis}</pre>
        )}
      </Modal>
    </div>
  )
}
