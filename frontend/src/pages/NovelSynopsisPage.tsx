import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Input, message, Modal, Radio, Select, Space, Tag } from 'antd'
import { api } from '../api'
import { useAppStore } from '../store'
import WritingToolbar from '../components/editor/WritingToolbar'
import NovelEditor, { type NovelEditorHandle } from '../components/editor/NovelEditor'
import styles from './NovelSynopsisPage.module.css'

const MAX_ARCHIVES = 5

interface LocalArchive {
  id: string
  version: number
  note?: string
  content: string
  createdAt: string
}

interface SynopsisDraft {
  value?: string
  updatedAt?: string
  archives?: LocalArchive[]
  pendingAI?: PendingSynopsisDraft | null
}

interface PendingSynopsisDraft {
  id: string
  content: string
  prompt: string
  createdAt: string
}

function createArchiveId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function formatSavedAt(value?: string | null) {
  if (!value) return ''
  return new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

export default function NovelSynopsisPage() {
  const { currentNovel, setCurrentNovel, documentDrafts, patchDocumentDraft } = useAppStore()
  const [value, setValue] = useState('')
  const [searchValue, setSearchValue] = useState('')
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [saveArchiveOpen, setSaveArchiveOpen] = useState(false)
  const [archiveNote, setArchiveNote] = useState('')
  const [coverOpen, setCoverOpen] = useState(false)
  const [coverMode, setCoverMode] = useState<'archive' | 'direct'>('archive')
  const [selectedArchiveId, setSelectedArchiveId] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<string | null>(null)
  const [aiGenerating, setAiGenerating] = useState(false)
  const editorRef = useRef<NovelEditorHandle>(null)
  const userEditedRef = useRef(false)
  const docKey = currentNovel ? `novel_synopsis:${currentNovel.id}` : null
  const localDraft = (docKey ? documentDrafts[docKey] : null) as SynopsisDraft | null
  const archives = useMemo(() => localDraft?.archives || [], [localDraft?.archives])
  const pendingAI = localDraft?.pendingAI || null
  const selectedArchive = archives.find(item => item.id === selectedArchiveId) || archives[0] || null
  const searchCount = searchValue.trim() ? value.split(searchValue.trim()).length - 1 : 0

  useEffect(() => {
    if (!currentNovel) return
    const draft = (docKey ? documentDrafts[docKey] : null) as SynopsisDraft | null
    setValue(draft?.value ?? currentNovel.synopsis ?? '')
    setSavedAt(draft?.updatedAt ?? null)
    userEditedRef.current = false
  }, [currentNovel?.id, currentNovel?.synopsis])

  useEffect(() => {
    if (!docKey || !userEditedRef.current) return
    const updatedAt = new Date().toISOString()
    patchDocumentDraft(docKey, { value, updatedAt })
    setSavedAt(updatedAt)
  }, [docKey, value])

  useEffect(() => {
    if (!currentNovel || !userEditedRef.current) return undefined
    if (value === (currentNovel.synopsis || '')) return undefined

    const timer = window.setTimeout(() => {
      void api.novels.update(currentNovel.id, { synopsis: value })
        .then((updated) => {
          setCurrentNovel(updated)
          const updatedAt = new Date().toISOString()
          if (docKey) patchDocumentDraft(docKey, { value, updatedAt })
          setSavedAt(updatedAt)
          userEditedRef.current = false
        })
        .catch(() => {
          // 保留本地草稿，避免保存失败打断写作。
        })
    }, 900)

    return () => window.clearTimeout(timer)
  }, [currentNovel?.id, currentNovel?.synopsis, docKey, value])

  useEffect(() => {
    function handleSynopsisUpdated(event: Event) {
      const customEvent = event as CustomEvent<{ synopsis?: string }>
      const nextSynopsis = customEvent.detail?.synopsis
      if (typeof nextSynopsis !== 'string') return
      userEditedRef.current = true
      setValue(nextSynopsis)
    }

    function handleSynopsisAIRequest(event: Event) {
      const customEvent = event as CustomEvent<{ prompt?: string }>
      void generateSynopsisByAI(customEvent.detail?.prompt || '')
    }

    function handleSynopsisDraft(event: Event) {
      const customEvent = event as CustomEvent<{ synopsis?: string; prompt?: string }>
      const synopsis = customEvent.detail?.synopsis
      if (!docKey || typeof synopsis !== 'string') return
      patchDocumentDraft(docKey, {
        pendingAI: {
          id: createArchiveId(),
          content: synopsis,
          prompt: customEvent.detail?.prompt || '',
          createdAt: new Date().toISOString(),
        },
      })
    }

    window.addEventListener('mobi:novel-synopsis-updated', handleSynopsisUpdated)
    window.addEventListener('mobi:novel-synopsis-ai-request', handleSynopsisAIRequest)
    window.addEventListener('mobi:novel-synopsis-draft', handleSynopsisDraft)
    return () => {
      window.removeEventListener('mobi:novel-synopsis-updated', handleSynopsisUpdated)
      window.removeEventListener('mobi:novel-synopsis-ai-request', handleSynopsisAIRequest)
      window.removeEventListener('mobi:novel-synopsis-draft', handleSynopsisDraft)
    }
  }, [value, currentNovel?.id, docKey])

  if (!currentNovel) return <div className={styles.empty}>请先选择小说</div>

  function setValueFromUser(nextValue: string) {
    userEditedRef.current = true
    setValue(nextValue)
  }

  async function generateSynopsisByAI(prompt: string) {
    if (!currentNovel) return
    setAiGenerating(true)
    try {
      const instruction = [
        value.trim() ? `当前简介草稿：\n${value.trim()}` : '',
        prompt.trim() ? `作者修改要求：\n${prompt.trim()}` : '请根据已确认大纲生成一版适合读者看的作品简介。',
        '请直接输出最终简介正文，不要标题，不要解释。',
      ].filter(Boolean).join('\n\n')
      const result = await api.ai.generateBookSynopsis(currentNovel.id, instruction, { dryRun: true })
      const pendingDraft: PendingSynopsisDraft = {
        id: createArchiveId(),
        content: result.synopsis || '',
        prompt,
        createdAt: new Date().toISOString(),
      }
      if (docKey) patchDocumentDraft(docKey, { pendingAI: pendingDraft })
      window.dispatchEvent(new CustomEvent('mobi:novel-synopsis-ai-response', {
        detail: { ok: true, message: '已生成简介修改稿，等待你确认后才会写入编辑器。' },
      }))
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '简介生成失败'
      window.dispatchEvent(new CustomEvent('mobi:novel-synopsis-ai-response', {
        detail: { ok: false, message: detail },
      }))
      message.error(detail)
    } finally {
      setAiGenerating(false)
    }
  }

  function acceptPendingAI() {
    if (!pendingAI || !docKey) return
    userEditedRef.current = true
    setValue(pendingAI.content)
    patchDocumentDraft(docKey, { value: pendingAI.content, pendingAI: null, updatedAt: new Date().toISOString() })
    window.dispatchEvent(new CustomEvent('mobi:novel-synopsis-ai-response', {
      detail: { ok: true, message: '已采用简介修改稿，系统会自动保存到正式简介。' },
    }))
  }

  function rejectPendingAI() {
    if (!docKey) return
    patchDocumentDraft(docKey, { pendingAI: null })
    window.dispatchEvent(new CustomEvent('mobi:novel-synopsis-ai-response', {
      detail: { ok: true, message: '已放弃这版简介修改稿，正式简介未改变。' },
    }))
  }

  function saveArchive() {
    if (!docKey) return
    if (archives.length >= MAX_ARCHIVES) {
      message.warning('简介最多保留 5 个存档，请先删除旧存档。')
      setArchiveOpen(true)
      return
    }
    const nextVersion = Math.max(0, ...archives.map(item => item.version)) + 1
    const nextArchive: LocalArchive = {
      id: createArchiveId(),
      version: nextVersion,
      note: archiveNote.trim() || undefined,
      content: value,
      createdAt: new Date().toISOString(),
    }
    patchDocumentDraft(docKey, {
      value,
      archives: [nextArchive, ...archives].slice(0, MAX_ARCHIVES),
    })
    setArchiveNote('')
    setSaveArchiveOpen(false)
    message.success(`已保存简介存档 v${nextVersion}`)
  }

  function deleteArchive(archiveId: string) {
    if (!docKey) return
    const nextArchives = archives.filter(item => item.id !== archiveId)
    patchDocumentDraft(docKey, { archives: nextArchives })
    setSelectedArchiveId(nextArchives[0]?.id || null)
    message.success('已删除存档')
  }

  function coverCurrentWithArchive() {
    if (!docKey || !selectedArchive) return
    let nextArchives = archives
    if (coverMode === 'archive' && value.trim() && value !== selectedArchive.content) {
      if (archives.length >= MAX_ARCHIVES) {
        message.warning('最多保留 5 个存档。请先删除一个旧存档，或选择直接覆盖。')
        return
      }
      const nextVersion = Math.max(0, ...archives.map(item => item.version)) + 1
      nextArchives = [{
        id: createArchiveId(),
        version: nextVersion,
        note: '覆盖前自动存档',
        content: value,
        createdAt: new Date().toISOString(),
      }, ...archives]
    }
    userEditedRef.current = true
    setValue(selectedArchive.content)
    patchDocumentDraft(docKey, { value: selectedArchive.content, archives: nextArchives })
    setCoverOpen(false)
    setArchiveOpen(false)
  }

  return (
    <div className={styles.page}>
      <div className={styles.editorSection}>
        <WritingToolbar
          wordCount={value.length}
          statusText={savedAt ? `输入已自动保存 ${formatSavedAt(savedAt)}` : undefined}
          searchValue={searchValue}
          searchCount={searchCount}
          onSearchChange={setSearchValue}
          onUndo={() => editorRef.current?.undo()}
          onRedo={() => editorRef.current?.redo()}
          onSaveVersion={() => {
            if (archives.length >= MAX_ARCHIVES) {
              message.warning('简介最多保留 5 个存档，请先删除旧存档。')
              setArchiveOpen(true)
              return
            }
            setArchiveNote('')
            setSaveArchiveOpen(true)
          }}
          saveVersionDisabled={aiGenerating}
          saveVersionTooltip={archives.length >= MAX_ARCHIVES ? '最多保留 5 个存档，请先删除旧存档' : '保存当前简介为存档节点'}
          onOpenVersions={() => setArchiveOpen(true)}
          versionsDisabled={archives.length < 1}
          versionsTooltip={archives.length < 1 ? '还没有简介存档' : '查看简介存档'}
        />
        {pendingAI ? (
          <div className={styles.pendingAI}>
            <div className={styles.pendingHeader}>
              <Space size={8}>
                <Tag color="gold">待确认</Tag>
                <strong>AI 简介修改稿</strong>
              </Space>
              <Space size={8}>
                <Button size="small" onClick={rejectPendingAI}>放弃</Button>
                <Button size="small" type="primary" onClick={acceptPendingAI}>采用并写入</Button>
              </Space>
            </div>
            <div className={styles.pendingContent}>{pendingAI.content}</div>
          </div>
        ) : null}
        <div className={styles.editorWrap}>
          <NovelEditor
            ref={editorRef}
            value={value}
            onChange={setValueFromUser}
            searchValue={searchValue}
            placeholder="这里是读者看到的小说简介。你可以手写，也可以在右侧让 AI 多轮打磨。"
          />
        </div>
      </div>

      <Modal
        title="简介存档"
        open={archiveOpen}
        onCancel={() => setArchiveOpen(false)}
        footer={null}
        width={780}
      >
        <div className={styles.archivePicker}>
          <span>选择存档节点</span>
          <Select
            value={selectedArchive?.id}
            onChange={setSelectedArchiveId}
            style={{ width: 280 }}
            options={archives.map(item => ({
              value: item.id,
              label: `存档 v${item.version}${item.note ? ` · ${item.note}` : ''}`,
            }))}
          />
          {selectedArchive ? (
            <>
              <Button onClick={() => setCoverOpen(true)}>覆盖当前草稿</Button>
              <Button danger onClick={() => deleteArchive(selectedArchive.id)}>删除存档</Button>
            </>
          ) : null}
        </div>
        <pre className={styles.archiveContent}>{selectedArchive?.content || '暂无存档'}</pre>
      </Modal>

      <Modal
        title="保存简介存档"
        open={saveArchiveOpen}
        onCancel={() => setSaveArchiveOpen(false)}
        onOk={saveArchive}
        okText={`保存为存档 v${Math.max(0, ...archives.map(item => item.version)) + 1}`}
        cancelText="取消"
      >
        <div className={styles.archiveTip}>当前简介是实时草稿，不算存档。最多保留 5 个存档节点。</div>
        <Input.TextArea
          value={archiveNote}
          onChange={event => setArchiveNote(event.target.value)}
          maxLength={80}
          showCount
          autoSize={{ minRows: 3, maxRows: 5 }}
          placeholder="写一句存档备注，例如：突出复仇线、改成更商业化"
        />
      </Modal>

      <Modal
        title="覆盖当前简介？"
        open={coverOpen}
        onCancel={() => setCoverOpen(false)}
        onOk={coverCurrentWithArchive}
        okText="确认覆盖"
        cancelText="取消"
      >
        <div className={styles.archiveTip}>你将用选中的存档覆盖当前正在编辑的简介。</div>
        <Radio.Group value={coverMode} onChange={event => setCoverMode(event.target.value)}>
          <div className={styles.coverChoices}>
            <Radio value="archive">先把当前简介存档，再覆盖</Radio>
            <Radio value="direct">直接覆盖，不额外保存当前简介</Radio>
          </div>
        </Radio.Group>
      </Modal>
    </div>
  )
}
