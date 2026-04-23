import { useState, useEffect } from 'react'
import { Tabs, Button, Input, InputNumber, Select, Tag, Alert, message, Spin, Tooltip } from 'antd'
import { ThunderboltOutlined, CheckOutlined, WarningOutlined } from '@ant-design/icons'
import CodeMirror from '@uiw/react-codemirror'
import { markdown } from '@codemirror/lang-markdown'
import { EditorView } from '@codemirror/view'
import { api } from '../api'
import { useAppStore } from '../store'
import type { Synopsis } from '../types'
import styles from './ChapterPage.module.css'

export default function ChapterPage() {
  const {
    currentNovel,
    currentChapter,
    setCurrentChapter,
    characters,
    setCharacters,
    chapters,
    setChapters,
    documentDrafts,
    patchDocumentDraft,
    clearDocumentDraft,
  } = useAppStore()
  const [synopsis, setSynopsis] = useState<Synopsis | null>(null)
  const [localSynopsis, setLocalSynopsis] = useState<Partial<Synopsis>>({})
  const [content, setContent] = useState('')
  const [activeTab, setActiveTab] = useState('synopsis')
  const [generating, setGenerating] = useState(false)
  const [validation, setValidation] = useState<{ valid: boolean; missing: string[] } | null>(null)
  const [saving, setSaving] = useState(false)
  const docKey = currentChapter ? `chapter:${currentChapter.id}` : null

  useEffect(() => {
    if (currentChapter) {
      loadData()
    }
  }, [currentChapter?.id])

  useEffect(() => {
    if (!docKey) return
    patchDocumentDraft(docKey, {
      localSynopsis,
      content,
      activeTab,
    })
  }, [docKey, localSynopsis, content, activeTab])

  async function loadData(ignoreDraft = false) {
    if (!currentChapter || !currentNovel) return
    const draft = (ignoreDraft || !docKey ? null : documentDrafts[docKey]) as {
      localSynopsis?: Partial<Synopsis>
      content?: string
      activeTab?: string
    } | null
    // 加载正文
    const ch = await api.chapters.get(currentNovel.id, currentChapter.id)
    setContent(draft?.content ?? ch.content ?? '')
    setActiveTab(draft?.activeTab || 'synopsis')
    // 加载细纲
    try {
      const s = await api.chapters.getSynopsis(currentNovel.id, currentChapter.id)
      setSynopsis(s)
      setLocalSynopsis(draft?.localSynopsis ?? s)
    } catch {
      setSynopsis(null)
      setLocalSynopsis(draft?.localSynopsis ?? { word_count_target: 3000, opening_characters: [], development_characters: [], development_events: [], development_conflicts: [], all_characters: [] })
    }
  }

  // 收集细纲中所有人物
  function collectAllChars(): string[] {
    return Array.from(new Set([
      ...(localSynopsis.opening_characters || []),
      ...(localSynopsis.development_characters || []),
    ]))
  }

  // 实时校验人物
  async function validateChars() {
    if (!currentNovel) return
    const names = collectAllChars()
    if (names.length === 0) { setValidation({ valid: true, missing: [] }); return }
    const result = await api.ai.validateCharacters(currentNovel.id, names)
    setValidation(result)
  }

  async function saveSynopsis() {
    if (!currentNovel || !currentChapter) return
    setSaving(true)
    try {
      const allChars = collectAllChars()
      const payload = { ...localSynopsis, all_characters: allChars }
      const saved = await api.chapters.upsertSynopsis(currentNovel.id, currentChapter.id, payload)
      setSynopsis(saved)
      message.success('细纲已保存')
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err?.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function generateSynopsis() {
    if (!currentNovel || !currentChapter) return
    setGenerating(true)
    try {
      const result = await api.ai.generateSynopsis({
        novel_id: currentNovel.id,
        chapter_id: currentChapter.id,
        chapter_number: currentChapter.chapter_number,
      })
      if (result.auto_created_characters && result.auto_created_characters.length > 0) {
        const nextCharacters = await api.characters.list(currentNovel.id)
        setCharacters(nextCharacters)
        message.success(`细纲生成成功，并自动补录了角色：${result.auto_created_characters.join('、')}`)
      } else {
        message.success('细纲生成并保存成功，请检查内容')
      }
      if (docKey) clearDocumentDraft(docKey)
      await loadData(true)
      validateChars()
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      if (detail?.missing) {
        setValidation({ valid: false, missing: detail.missing })
        message.warning(`细纲中出现新角色：${detail.missing.join('、')}`)
      } else {
        message.error(`生成失败: ${detail?.message || detail || e.message}`)
      }
    } finally {
      setGenerating(false)
    }
  }

  async function generateSegment(segment: 'opening' | 'middle' | 'ending') {
    if (!currentNovel || !currentChapter) return
    if (!synopsis) { message.warning('请先保存细纲'); return }
    setGenerating(true)
    setActiveTab('content')
    const prevText = content.slice(-300)
    try {
      const result = await api.ai.generateChapterSegment(currentNovel.id, currentChapter.id, segment, prevText)
      setContent(result.full_content)
      await api.chapters.update(currentNovel.id, currentChapter.id, { content: result.full_content })
      message.success(`${segment === 'opening' ? '开头' : segment === 'middle' ? '中间' : '结尾'}段生成完成`)
    } catch (e: any) {
      message.error(`生成失败：${e?.response?.data?.detail || e.message}`)
      await loadData(true)
    } finally {
      setGenerating(false)
    }
  }

  async function saveContent() {
    if (!currentNovel || !currentChapter) return
    setSaving(true)
    try {
      await api.chapters.update(currentNovel.id, currentChapter.id, { content })
      message.success('正文已保存')
    } finally {
      setSaving(false)
    }
  }

  async function completeChapter() {
    if (!currentNovel || !currentChapter) return
    const plotSummary = localSynopsis.plot_summary_update || ''
    await api.chapters.update(currentNovel.id, currentChapter.id, {
      status: 'completed',
      plot_summary: plotSummary,
    })
    const updated = { ...currentChapter, status: 'completed' as const, plot_summary: plotSummary }
    setCurrentChapter(updated)
    setChapters(chapters.map(c => c.id === updated.id ? updated : c))
    message.success('章节已完成，剧情缩略已更新')
  }

  if (!currentNovel || !currentChapter) return <div className={styles.empty}>请选择章节</div>

  const charOptions = characters.map(c => ({ value: c.name, label: `${c.name}（${c.realm || '—'}）` }))

  async function quickCreateMissingCharacters() {
    if (!currentNovel || !validation || validation.valid) return
    try {
      const res = await api.ai.createMissingCharacters(currentNovel.id, validation.missing)
      message.success(`已创建 ${res.created.length} 个缺失角色`)
      await loadData()
      validateChars()
    } catch (e: any) {
      message.error(`创建失败: ${e.message}`)
    }
  }

  const synopsisTab = (
    <div className={styles.synopsisForm}>
      {/* AI生成细纲 */}
      <div className={styles.aiBar}>
        <Button
          size="small" icon={<ThunderboltOutlined />}
          loading={generating && activeTab === 'synopsis'}
          onClick={generateSynopsis}
        >
          AI生成细纲
        </Button>
      </div>

      {/* 人物校验提示 */}
      {validation && !validation.valid && (
        <Alert
          type="error"
          icon={<WarningOutlined />}
          message={`未定义角色：${validation.missing.join('、')}，请先在角色库中创建`}
          showIcon
          action={
            <Button size="small" type="primary" onClick={quickCreateMissingCharacters}>
              快速创建缺失角色
            </Button>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      <SynopsisSection title="开头">
        <Field label="场景">
          <Input.TextArea
            rows={2}
            value={localSynopsis.opening_scene || ''}
            onChange={e => setLocalSynopsis(p => ({ ...p, opening_scene: e.target.value }))}
          />
        </Field>
        <Field label="基调">
          <Input
            value={localSynopsis.opening_mood || ''}
            onChange={e => setLocalSynopsis(p => ({ ...p, opening_mood: e.target.value }))}
            placeholder="如：紧张、期待"
          />
        </Field>
        <Field label="钩子">
          <Input.TextArea
            rows={2}
            value={localSynopsis.opening_hook || ''}
            onChange={e => setLocalSynopsis(p => ({ ...p, opening_hook: e.target.value }))}
          />
        </Field>
        <Field label="出场人物">
          <Select
            mode="multiple"
            options={charOptions}
            value={localSynopsis.opening_characters || []}
            onChange={v => { setLocalSynopsis(p => ({ ...p, opening_characters: v })); validateChars() }}
            placeholder="选择出场角色"
            style={{ width: '100%' }}
          />
        </Field>
      </SynopsisSection>

      <SynopsisSection title="发展">
        <Field label="事件">
          <TagInput
            value={localSynopsis.development_events || []}
            onChange={v => setLocalSynopsis(p => ({ ...p, development_events: v }))}
            placeholder="输入事件后回车"
          />
        </Field>
        <Field label="冲突">
          <TagInput
            value={localSynopsis.development_conflicts || []}
            onChange={v => setLocalSynopsis(p => ({ ...p, development_conflicts: v }))}
            placeholder="输入冲突后回车"
          />
        </Field>
        <Field label="出场人物">
          <Select
            mode="multiple"
            options={charOptions}
            value={localSynopsis.development_characters || []}
            onChange={v => { setLocalSynopsis(p => ({ ...p, development_characters: v })); validateChars() }}
            style={{ width: '100%' }}
          />
        </Field>
      </SynopsisSection>

      <SynopsisSection title="结尾">
        <Field label="解决">
          <Input.TextArea rows={2} value={localSynopsis.ending_resolution || ''} onChange={e => setLocalSynopsis(p => ({ ...p, ending_resolution: e.target.value }))} />
        </Field>
        <Field label="悬念">
          <Input.TextArea rows={2} value={localSynopsis.ending_cliffhanger || ''} onChange={e => setLocalSynopsis(p => ({ ...p, ending_cliffhanger: e.target.value }))} />
        </Field>
        <Field label="下章钩子">
          <Input value={localSynopsis.ending_next_hook || ''} onChange={e => setLocalSynopsis(p => ({ ...p, ending_next_hook: e.target.value }))} />
        </Field>
      </SynopsisSection>

      <SynopsisSection title="其他">
        <Field label="目标字数">
          <InputNumber
            value={localSynopsis.word_count_target || 3000}
            onChange={v => setLocalSynopsis(p => ({ ...p, word_count_target: v || 3000 }))}
            min={500} step={500}
          />
        </Field>
        <Field label="剧情缩略">
          <Input.TextArea
            rows={2}
            value={localSynopsis.plot_summary_update || ''}
            onChange={e => setLocalSynopsis(p => ({ ...p, plot_summary_update: e.target.value }))}
            placeholder="一句话概括本章主要事件（完成后写入主线剧情）"
          />
        </Field>
      </SynopsisSection>

      <div className={styles.synopsisActions}>
        <Button type="primary" size="small" loading={saving} onClick={saveSynopsis}>
          保存细纲
        </Button>
        <Button size="small" icon={<ThunderboltOutlined />} onClick={() => generateSegment('opening')} disabled={!synopsis} loading={generating}>
          生成开头
        </Button>
        <Button size="small" icon={<ThunderboltOutlined />} onClick={() => generateSegment('middle')} disabled={!synopsis} loading={generating}>
          生成中间
        </Button>
        <Button size="small" icon={<ThunderboltOutlined />} onClick={() => generateSegment('ending')} disabled={!synopsis} loading={generating}>
          生成结尾
        </Button>
      </div>
    </div>
  )

  const contentTab = (
    <div className={styles.contentArea}>
      <div className={styles.contentHeader}>
        <span className={styles.wordCount}>
          {content.length} 字
          {synopsis?.word_count_target && ` / 目标 ${synopsis.word_count_target} 字`}
        </span>
        <div className={styles.contentActions}>
          {generating && <Spin size="small" />}
          <Button size="small" loading={saving} onClick={saveContent}>保存</Button>
          {currentChapter.status !== 'completed' && (
            <Tooltip title="完成后将剧情缩略写入主线">
              <Button size="small" type="primary" icon={<CheckOutlined />} onClick={completeChapter}>
                完成本章
              </Button>
            </Tooltip>
          )}
          {currentChapter.status === 'completed' && <Tag color="green">已完成</Tag>}
        </div>
      </div>
      <CodeMirror
        value={content}
        onChange={setContent}
        extensions={[markdown(), EditorView.lineWrapping]}
        theme="dark"
        className={styles.editor}
      />
    </div>
  )

  return (
    <div className={styles.page}>
      <div className={styles.chapterTitle}>
        {currentChapter.title || `第${currentChapter.chapter_number}章`}
      </div>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="small"
        className={styles.tabs}
        items={[
          { key: 'synopsis', label: '细纲', children: synopsisTab },
          { key: 'content', label: '正文', children: contentTab },
        ]}
      />
    </div>
  )
}

function SynopsisSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={styles.synopsisSection}>
      <div className={styles.sectionTitle}>{title}</div>
      <div className={styles.sectionBody}>{children}</div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className={styles.field}>
      <label className={styles.fieldLabel}>{label}</label>
      <div className={styles.fieldInput}>{children}</div>
    </div>
  )
}

function TagInput({ value, onChange, placeholder }: {
  value: string[]
  onChange: (v: string[]) => void
  placeholder?: string
}) {
  const [input, setInput] = useState('')
  function add() {
    const trimmed = input.trim()
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed])
    }
    setInput('')
  }
  return (
    <div className={styles.tagInput}>
      <div className={styles.tagList}>
        {value.map((v, i) => (
          <Tag key={i} closable onClose={() => onChange(value.filter((_, idx) => idx !== i))}>
            {v}
          </Tag>
        ))}
      </div>
      <Input
        size="small"
        value={input}
        onChange={e => setInput(e.target.value)}
        onPressEnter={add}
        placeholder={placeholder}
        style={{ width: 160 }}
      />
    </div>
  )
}
