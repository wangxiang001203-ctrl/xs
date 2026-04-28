import { useState, useEffect, useMemo, useRef } from 'react'
import { Button, Checkbox, Input, message, Modal, Radio, Select, Tag, Tooltip } from 'antd'
import { CheckOutlined, DeleteOutlined } from '@ant-design/icons'
import { api } from '../api'
import { useAppStore } from '../store'
import type { Outline, OutlineDraft } from '../types'
import WritingToolbar from '../components/editor/WritingToolbar'
import NovelEditor, { type NovelEditorHandle } from '../components/editor/NovelEditor'
import {
  applyInlineSuggestion,
  buildInlineSuggestions,
  type InlineSuggestion,
} from '../utils/inlineDiff'
import { normalizeAuthorText } from '../utils/authorText'
import styles from './OutlinePage.module.css'

const MAX_OUTLINE_VERSIONS = 5

interface OutlineLocalDraft {
  editContent?: string
  updatedAt?: string
  rejectedDraftKey?: string
  rejectedSuggestionSignatures?: string[]
  handledDraftKeys?: string[]
}

function getOutlineDraftKey(draft?: OutlineDraft | null) {
  if (!draft?.content) return ''
  return `${draft.target_version || 0}:${draft.content.length}:${draft.content.slice(0, 80)}`
}

function uniqueLast(items: string[], limit = 30) {
  return Array.from(new Set(items.filter(Boolean))).slice(-limit)
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
  const [outline, setOutline] = useState<Outline | null>(null)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [outlines, setOutlines] = useState<Outline[]>([])
  const [searchValue, setSearchValue] = useState('')
  const [compareOpen, setCompareOpen] = useState(false)
  const [compareOutlineId, setCompareOutlineId] = useState<string | null>(null)
  const [pendingDraft, setPendingDraft] = useState<OutlineDraft | null>(null)
  const [rejectedSuggestionSignatures, setRejectedSuggestionSignatures] = useState<string[]>([])
  const [reviewUndoStack, setReviewUndoStack] = useState<Array<{
    content: string
    pendingDraft: OutlineDraft | null
    rejectedSuggestionSignatures: string[]
  }>>([])
  const [reviewRedoStack, setReviewRedoStack] = useState<Array<{
    content: string
    pendingDraft: OutlineDraft | null
    rejectedSuggestionSignatures: string[]
  }>>([])
  const [outlineLoaded, setOutlineLoaded] = useState(false)
  const [editSavedAt, setEditSavedAt] = useState<string | null>(null)
  const [saveVersionOpen, setSaveVersionOpen] = useState(false)
  const [versionNote, setVersionNote] = useState('')
  const [coverVersionOpen, setCoverVersionOpen] = useState(false)
  const [coverMode, setCoverMode] = useState<'archive' | 'direct'>('archive')
  const [confirmMetaOpen, setConfirmMetaOpen] = useState(false)
  const [adoptTitleOnConfirm, setAdoptTitleOnConfirm] = useState(true)
  const [adoptSynopsisOnConfirm, setAdoptSynopsisOnConfirm] = useState(true)
  const editorRef = useRef<NovelEditorHandle>(null)
  const skipNextAutoSaveRef = useRef(false)
  const userEditedRef = useRef(false)
  const docKey = currentNovel ? `outline:${currentNovel.id}` : null
  const outlineDraft = (docKey ? documentDrafts[docKey] : null) as OutlineLocalDraft | null

  const activeContent = outline ? editContent : ''
  const searchCount = useMemo(() => {
    if (!searchValue.trim()) return 0
    return activeContent.split(searchValue.trim()).length - 1
  }, [activeContent, searchValue])
  const archiveOutlines = useMemo(
    () => outlines.filter(item => item.id !== outline?.id),
    [outline?.id, outlines],
  )
  const archiveCount = archiveOutlines.length
  const compareOutline = archiveOutlines.find(item => item.id === compareOutlineId) || archiveOutlines[0] || null
  const inlineSuggestions = useMemo(
    () => (pendingDraft?.content
      ? buildInlineSuggestions(activeContent, pendingDraft.content)
      : [])
      .filter(item => !rejectedSuggestionSignatures.includes(item.signature)),
    [activeContent, pendingDraft?.content, rejectedSuggestionSignatures],
  )
  const pendingDraftFullyApplied = Boolean(pendingDraft?.content && activeContent === pendingDraft.content)
  const hasPendingSuggestion = Boolean(pendingDraft && inlineSuggestions.length > 0 && !pendingDraftFullyApplied)
  const hasConfirmedOutline = useMemo(
    () => Boolean(outline?.confirmed || outlines.some(item => item.confirmed)),
    [outline?.confirmed, outlines],
  )

  useEffect(() => {
    if (currentNovel) {
      setOutlineLoaded(false)
      setEditSavedAt(outlineDraft?.updatedAt ?? null)
      loadOutline(outlineDraft)
    }
  }, [currentNovel?.id])

  useEffect(() => {
    function handleOutlineGenerated(event: Event) {
      const customEvent = event as CustomEvent<Outline>
      if (!customEvent.detail) return
      const normalizedOutline = {
        ...customEvent.detail,
        content: normalizeAuthorText(customEvent.detail.content),
      }
      setOutline(normalizedOutline)
      setEditorContentFromSystem(normalizedOutline.content || '')
      if ((pendingDraft?.target_version || 0) <= customEvent.detail.version) {
        setPendingDraft(null)
        setRejectedSuggestionSignatures([])
      }
      void loadOutlines()
    }

    window.addEventListener('mobi:outline-generated', handleOutlineGenerated)
    return () => window.removeEventListener('mobi:outline-generated', handleOutlineGenerated)
  }, [pendingDraft?.target_version])

  useEffect(() => {
    function handleOutlineDraft(event: Event) {
      const customEvent = event as CustomEvent<OutlineDraft>
      if (!customEvent.detail?.content) return
      const nextDraft = {
        ...customEvent.detail,
        content: normalizeAuthorText(customEvent.detail.content),
      }
      setPendingDraft(nextDraft)
      setRejectedSuggestionSignatures([])
      setReviewRedoStack([])
      if (docKey) {
        patchDocumentDraft(docKey, {
          rejectedDraftKey: getOutlineDraftKey(nextDraft),
          rejectedSuggestionSignatures: [],
        })
      }
      editorRef.current?.focus()
    }

    window.addEventListener('mobi:outline-draft', handleOutlineDraft)
    return () => window.removeEventListener('mobi:outline-draft', handleOutlineDraft)
  }, [docKey, patchDocumentDraft])

  useEffect(() => {
    function handleOutlineReset() {
      setOutline(null)
      setOutlines([])
      setEditorContentFromSystem('')
      setOutlineLoaded(true)
      setPendingDraft(null)
      setRejectedSuggestionSignatures([])
      setReviewUndoStack([])
      setReviewRedoStack([])
      setCompareOpen(false)
      setCompareOutlineId(null)
      if (docKey) clearDocumentDraft(docKey)
    }

    window.addEventListener('mobi:outline-reset', handleOutlineReset)
    return () => window.removeEventListener('mobi:outline-reset', handleOutlineReset)
  }, [docKey, clearDocumentDraft])

  useEffect(() => {
    if (!docKey || !outlineLoaded) return
    if (!userEditedRef.current) return
    const updatedAt = new Date().toISOString()
    patchDocumentDraft(docKey, {
      editContent,
      updatedAt,
    })
    setEditSavedAt(updatedAt)
  }, [docKey, editContent, outlineLoaded])

  useEffect(() => {
    if (!outlineLoaded) return undefined
    if (!outline || !currentNovel) return undefined
    if (!userEditedRef.current) return undefined
    if (skipNextAutoSaveRef.current) {
      skipNextAutoSaveRef.current = false
      return undefined
    }
    if (editContent === (outline.content || '')) return undefined

    const timer = window.setTimeout(() => {
      void api.outline.update(currentNovel.id, outline.id, { content: editContent })
        .then((updated) => {
          setOutline(updated)
          setEditSavedAt(new Date().toISOString())
          userEditedRef.current = false
        })
        .catch(() => {
          // 后端自动保存失败时保留本地草稿，避免打断作者输入。
        })
    }, 1200)

    return () => window.clearTimeout(timer)
  }, [currentNovel?.id, editContent, outline?.content, outline?.id, outlineLoaded])

  useEffect(() => {
    if (!pendingDraft) return
    if (inlineSuggestions.length > 0) return
    rememberHandledDraft(pendingDraft)
    setPendingDraft(null)
    setRejectedSuggestionSignatures([])
  }, [inlineSuggestions.length, pendingDraft])

  function formatSavedAt(value: string | null) {
    if (!value) return ''
    return new Date(value).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }

  function setEditorContentFromSystem(nextContent: string) {
    userEditedRef.current = false
    setEditContent(nextContent)
  }

  function setEditorContentFromUser(nextContent: string) {
    userEditedRef.current = true
    setEditContent(nextContent)
  }

  function setEditorContentFromAction(nextContent: string) {
    userEditedRef.current = true
    setEditContent(nextContent)
  }

  async function loadOutline(draft?: { editContent?: string } | null) {
    if (!currentNovel) return
    try {
      const [o, list] = await Promise.all([
        api.outline.latest(currentNovel.id),
        api.outline.list(currentNovel.id).catch(() => [] as Outline[]),
      ])
      const normalizedOutline = {
        ...o,
        content: normalizeAuthorText(o.content),
      }
      setOutline(normalizedOutline)
      setOutlines(list)
      setCompareOutlineId(list.find(item => item.id !== o.id)?.id || null)
      const backendContent = normalizedOutline.content || ''
      const localContent = typeof draft?.editContent === 'string' ? draft.editContent : null
      const shouldUseLocalDraft = localContent !== null && (
        localContent.trim().length > 0 || backendContent.trim().length === 0
      )
      skipNextAutoSaveRef.current = true
      if (shouldUseLocalDraft) {
        setEditorContentFromSystem(localContent)
      } else {
        setEditorContentFromSystem(backendContent)
      }
      void loadPendingDraft(normalizedOutline, draft as OutlineLocalDraft | null)
    } catch {
      setOutline(null)
      setOutlines([])
      skipNextAutoSaveRef.current = true
      if (typeof draft?.editContent === 'string' && draft.editContent.trim().length > 0) {
        setEditorContentFromSystem(draft.editContent)
      } else {
        setEditorContentFromSystem('')
      }
    } finally {
      setOutlineLoaded(true)
    }
  }

  async function loadPendingDraft(currentOutline: Outline, localDraft?: OutlineLocalDraft | null) {
    if (!currentNovel) return
    try {
      const handledDraftKeys = Array.isArray(localDraft?.handledDraftKeys) ? localDraft.handledDraftKeys : []
      const messages = await api.outline.messages(currentNovel.id)
      const draft = [...messages]
        .reverse()
        .map(item => item.metadata?.draft_outline as OutlineDraft | undefined)
        .find((item) => {
          if (!item?.content || (item.target_version || 0) <= currentOutline.version) return false
          return !handledDraftKeys.includes(getOutlineDraftKey({
            ...item,
            content: normalizeAuthorText(item.content),
          }))
        })
      if (draft) {
        const normalizedDraft = {
          ...draft,
          content: normalizeAuthorText(draft.content),
        }
        const draftKey = getOutlineDraftKey(normalizedDraft)
        const storedRejected = localDraft?.rejectedDraftKey === draftKey && Array.isArray(localDraft.rejectedSuggestionSignatures)
          ? localDraft.rejectedSuggestionSignatures
          : []
        setPendingDraft(normalizedDraft)
        setRejectedSuggestionSignatures(storedRejected)
      } else {
        setPendingDraft(null)
        setRejectedSuggestionSignatures([])
      }
    } catch {
      // 对话草稿只是辅助入口，加载失败不影响大纲编辑。
    }
  }

  async function persistOutlineContent(nextContent: string) {
    if (!currentNovel || !outline || !docKey) return
    const updatedAt = new Date().toISOString()
    patchDocumentDraft(docKey, { editContent: nextContent, updatedAt })
    setEditSavedAt(updatedAt)
    try {
      const updated = await api.outline.update(currentNovel.id, outline.id, { content: nextContent })
      setOutline({
        ...updated,
        content: normalizeAuthorText(updated.content),
      })
      setEditSavedAt(new Date().toISOString())
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '自动保存失败，请稍后再试')
    }
  }

  function rememberRejectedSignatures(nextSignatures: string[], draft = pendingDraft) {
    if (!docKey || !draft) return
    patchDocumentDraft(docKey, {
      rejectedDraftKey: getOutlineDraftKey(draft),
      rejectedSuggestionSignatures: nextSignatures,
    })
  }

  function rememberHandledDraft(draft: OutlineDraft | null) {
    if (!docKey || !draft) return
    const draftKey = getOutlineDraftKey(draft)
    const previous = Array.isArray(outlineDraft?.handledDraftKeys) ? outlineDraft.handledDraftKeys : []
    patchDocumentDraft(docKey, {
      handledDraftKeys: uniqueLast([...previous, draftKey]),
      rejectedDraftKey: null,
      rejectedSuggestionSignatures: [],
    })
  }

  function forgetHandledDraft(draft: OutlineDraft | null, signatures: string[]) {
    if (!docKey || !draft) return
    const draftKey = getOutlineDraftKey(draft)
    const previous = Array.isArray(outlineDraft?.handledDraftKeys) ? outlineDraft.handledDraftKeys : []
    patchDocumentDraft(docKey, {
      handledDraftKeys: previous.filter(item => item !== draftKey),
      rejectedDraftKey: draftKey,
      rejectedSuggestionSignatures: signatures,
    })
  }

  async function loadOutlines() {
    if (!currentNovel) return
    const list = await api.outline.list(currentNovel.id).catch(() => [] as Outline[])
    setOutlines(list)
    const nextArchiveOutlines = list.filter(item => item.id !== outline?.id)
    if (!compareOutlineId || !nextArchiveOutlines.some(item => item.id === compareOutlineId)) {
      setCompareOutlineId(nextArchiveOutlines[0]?.id || null)
    }
  }

  async function confirmOutline() {
    if (!outline || !currentNovel || !docKey) return
    if (hasConfirmedOutline) {
      message.info('大纲已确认过，确认按钮只能使用一次')
      return
    }
    const hasTitleDraft = Boolean(outline.title?.trim())
    const hasSynopsisDraft = Boolean(outline.synopsis?.trim())
    if (hasTitleDraft || hasSynopsisDraft) {
      setAdoptTitleOnConfirm(hasTitleDraft)
      setAdoptSynopsisOnConfirm(hasSynopsisDraft)
      setConfirmMetaOpen(true)
      return
    }
    await executeConfirmOutline({ adoptTitle: false, adoptSynopsis: false })
  }

  async function executeConfirmOutline(options: { adoptTitle: boolean; adoptSynopsis: boolean }) {
    if (!outline || !currentNovel || !docKey) return
    setSaving(true)
    try {
      const updatePayload: Partial<Outline> = {
        confirmed: true,
        content: editContent,
      }
      if (outline.title?.trim() && !options.adoptTitle) {
        updatePayload.title = ''
      }
      if (outline.synopsis?.trim() && !options.adoptSynopsis) {
        updatePayload.synopsis = ''
      }
      const updated = await api.outline.update(currentNovel.id, outline.id, {
        ...updatePayload,
      })
      setOutline(updated)
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
      clearDocumentDraft(docKey)
      window.dispatchEvent(new CustomEvent('mobi:outline-confirmed', { detail: updated }))
      setConfirmMetaOpen(false)
      message.success('大纲已确认保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  function openSaveVersion() {
    if (!outline) return
    if (archiveCount >= MAX_OUTLINE_VERSIONS) {
      message.warning('最多保留 5 个大纲存档节点。请先在存档里删除不需要的旧节点。')
      setCompareOpen(true)
      return
    }
    setVersionNote('')
    setSaveVersionOpen(true)
  }

  async function saveNewVersion() {
    if (!outline || !currentNovel) return
    if (archiveCount >= MAX_OUTLINE_VERSIONS) {
      message.warning('最多保留 5 个大纲存档节点。请先删除旧节点。')
      return
    }
    setSaving(true)
    try {
      const created = await api.outline.create(currentNovel.id, {
        title: outline.title,
        synopsis: outline.synopsis,
        selling_points: outline.selling_points,
        main_plot: outline.main_plot,
        content: activeContent,
        ai_generated: false,
        version_note: versionNote.trim() || undefined,
      })
      setOutline(created)
      setEditorContentFromSystem(created.content || '')
      if (pendingDraft?.content && activeContent === pendingDraft.content) {
        setPendingDraft(null)
        setRejectedSuggestionSignatures([])
      }
      setSaveVersionOpen(false)
      setVersionNote('')
      await loadOutlines()
      message.success(`已保存为存档 v${created.version}`)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '保存存档失败'
      message.error(detail)
    } finally {
      setSaving(false)
    }
  }

  async function deleteSelectedVersion() {
    if (!currentNovel || !compareOutline) return
    if (compareOutline.confirmed) {
      message.info('已确认的大纲存档不能删除')
      return
    }
    Modal.confirm({
      title: `删除存档 v${compareOutline.version}？`,
      content: compareOutline.version_note || '删除后这个存档节点将无法恢复。',
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        setSaving(true)
        try {
          await api.outline.delete(currentNovel.id, compareOutline.id)
          const list = await api.outline.list(currentNovel.id).catch(() => [] as Outline[])
          setOutlines(list)
          if (outline?.id === compareOutline.id) {
            const latest = list[0] || null
            setOutline(latest)
            setEditorContentFromSystem(latest?.content || '')
          }
          setCompareOutlineId(list.find(item => item.id !== outline?.id)?.id || null)
          message.success('已删除存档')
        } catch (err: any) {
          const detail = err?.response?.data?.detail || err?.message || '删除存档失败'
          message.error(detail)
        } finally {
          setSaving(false)
        }
      },
    })
  }

  function openCoverVersion() {
    if (!compareOutline) return
    setCoverMode('archive')
    setCoverVersionOpen(true)
  }

  async function coverCurrentWithSelectedVersion() {
    if (!currentNovel || !outline || !compareOutline) return
    const selectedContent = normalizeAuthorText(compareOutline.content)
    setSaving(true)
    try {
      if (coverMode === 'archive' && activeContent.trim() && activeContent !== selectedContent) {
        if (archiveCount >= MAX_OUTLINE_VERSIONS) {
          message.warning('最多保留 5 个存档节点。请先删除一个旧节点，或选择直接覆盖。')
          return
        }
        await api.outline.create(currentNovel.id, {
          title: outline.title,
          synopsis: outline.synopsis,
          selling_points: outline.selling_points,
          main_plot: outline.main_plot,
          content: activeContent,
          ai_generated: false,
          version_note: '覆盖前自动存档',
        })
      }

      const updated = await api.outline.update(currentNovel.id, outline.id, {
        content: selectedContent,
      })
      setOutline({
        ...updated,
        content: normalizeAuthorText(updated.content),
      })
      setEditorContentFromAction(selectedContent)
      setPendingDraft(null)
      setRejectedSuggestionSignatures([])
      setReviewUndoStack([])
      setCoverVersionOpen(false)
      setCompareOpen(false)
      await loadOutlines()
      message.success('已用所选存档覆盖当前草稿')
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || '覆盖失败'
      message.error(detail)
    } finally {
      setSaving(false)
    }
  }

  function resetOutlineSeed() {
    if (!currentNovel) return
    if (hasConfirmedOutline) {
      message.info('大纲已确认过，不能再清空重写')
      return
    }

    Modal.confirm({
      title: '清空初版和大纲记录？',
      content: '这会删除当前未确认的大纲草稿、待确认修改稿和右侧大纲对话记录。清空后不会自动生成新大纲，你需要重新输入新的想法再生成第一版草稿。',
      okText: '清空',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        setSaving(true)
        try {
          await api.outline.reset(currentNovel.id)
          const latestNovel = await api.novels.get(currentNovel.id).catch(() => null)
          if (latestNovel) setCurrentNovel(latestNovel)
          setOutline(null)
          setOutlines([])
          setEditorContentFromSystem('')
          setPendingDraft(null)
          setRejectedSuggestionSignatures([])
          setCompareOpen(false)
          setCompareOutlineId(null)
          if (docKey) clearDocumentDraft(docKey)
          window.dispatchEvent(new CustomEvent('mobi:outline-reset'))
          message.success('已清空未确认的大纲和记录，可以重新输入想法生成第一版草稿')
        } catch (err: any) {
          const detail = err?.response?.data?.detail || err?.message || '清空失败'
          message.error(detail)
        } finally {
          setSaving(false)
        }
      },
    })
  }

  function acceptSuggestion(suggestion: InlineSuggestion) {
    pushReviewUndo()
    setReviewRedoStack([])
    const nextContent = applyInlineSuggestion(editContent, suggestion)
    setEditorContentFromAction(nextContent)
    setRejectedSuggestionSignatures(prev => prev.filter(item => item !== suggestion.signature))
    void persistOutlineContent(nextContent)
  }

  function rejectSuggestion(suggestion: InlineSuggestion) {
    pushReviewUndo()
    setReviewRedoStack([])
    const nextSignatures = rejectedSuggestionSignatures.includes(suggestion.signature)
      ? rejectedSuggestionSignatures
      : [...rejectedSuggestionSignatures, suggestion.signature]
    setRejectedSuggestionSignatures(nextSignatures)
    rememberRejectedSignatures(nextSignatures)
    void persistOutlineContent(editContent)
  }

  function acceptAllSuggestions() {
    if (!pendingDraft?.content) return
    pushReviewUndo()
    setReviewRedoStack([])
    setEditorContentFromAction(pendingDraft.content)
    rememberHandledDraft(pendingDraft)
    setPendingDraft(null)
    setRejectedSuggestionSignatures([])
    void persistOutlineContent(pendingDraft.content)
    message.success('已采用 AI 修改稿，当前已回到普通草稿。点撤销可回到刚才的对比状态。')
  }

  function discardPendingDraft() {
    pushReviewUndo()
    setReviewRedoStack([])
    rememberHandledDraft(pendingDraft)
    setPendingDraft(null)
    setRejectedSuggestionSignatures([])
    void persistOutlineContent(editContent)
    message.info('已放弃这份 AI 修改稿')
  }

  function pushReviewUndo() {
    setReviewUndoStack(prev => [
      ...prev,
      {
        content: editContent,
        pendingDraft,
        rejectedSuggestionSignatures,
      },
    ].slice(-20))
  }

  function undoEditorAction() {
    const last = reviewUndoStack[reviewUndoStack.length - 1]
    if (!last) {
      editorRef.current?.undo()
      return
    }
    setReviewRedoStack(prev => [
      ...prev,
      {
        content: editContent,
        pendingDraft,
        rejectedSuggestionSignatures,
      },
    ].slice(-20))
    setEditorContentFromAction(last.content)
    setPendingDraft(last.pendingDraft)
    setRejectedSuggestionSignatures(last.rejectedSuggestionSignatures)
    forgetHandledDraft(last.pendingDraft, last.rejectedSuggestionSignatures)
    void persistOutlineContent(last.content)
    setReviewUndoStack(prev => prev.slice(0, -1))
  }

  function redoEditorAction() {
    const next = reviewRedoStack[reviewRedoStack.length - 1]
    if (!next) {
      editorRef.current?.redo()
      return
    }
    const currentPendingDraft = pendingDraft
    setReviewUndoStack(prev => [
      ...prev,
      {
        content: editContent,
        pendingDraft,
        rejectedSuggestionSignatures,
      },
    ].slice(-20))
    setEditorContentFromAction(next.content)
    setPendingDraft(next.pendingDraft)
    setRejectedSuggestionSignatures(next.rejectedSuggestionSignatures)
    if (currentPendingDraft && !next.pendingDraft) {
      rememberHandledDraft(currentPendingDraft)
    } else if (next.pendingDraft) {
      forgetHandledDraft(next.pendingDraft, next.rejectedSuggestionSignatures)
    }
    void persistOutlineContent(next.content)
    setReviewRedoStack(prev => prev.slice(0, -1))
  }

  return (
    <div className={styles.page}>
      {/* 大纲编辑区 */}
      <div className={styles.editorSection}>
        <WritingToolbar
          wordCount={activeContent.length}
          titleExtra={outline && !hasConfirmedOutline ? (
            <span className={styles.outlineStatusPending}>大纲待确认</span>
          ) : null}
          statusText={editSavedAt ? `输入已自动保存 ${formatSavedAt(editSavedAt)}` : undefined}
          searchValue={searchValue}
          searchCount={searchCount}
          onSearchChange={setSearchValue}
          onUndo={undoEditorAction}
          onRedo={redoEditorAction}
          onSaveVersion={openSaveVersion}
          saveVersionDisabled={!outline || archiveCount >= MAX_OUTLINE_VERSIONS}
          saveVersionTooltip={archiveCount >= MAX_OUTLINE_VERSIONS ? '最多保留 5 个存档，请先删除旧存档' : '保存当前草稿为存档节点'}
          onOpenVersions={() => setCompareOpen(true)}
          versionsDisabled={archiveCount < 1}
          versionsTooltip={archiveCount < 1 ? '还没有存档节点' : '查看大纲存档节点'}
        />
        {(hasPendingSuggestion || (outline && !hasConfirmedOutline)) ? (
          <div className={styles.editorHeader}>
            <div className={styles.editorMeta}>
              <div className={styles.statusLine}>
                {hasPendingSuggestion ? (
                  <Tag color="gold">
                    {`${inlineSuggestions.length} 处 AI 建议待处理`}
                  </Tag>
                ) : null}
              </div>
            </div>
            <div className={styles.editorActions}>
              {hasPendingSuggestion ? (
                <>
                  <Button size="small" onClick={acceptAllSuggestions}>全部采用</Button>
                  <Button size="small" onClick={discardPendingDraft}>放弃修改稿</Button>
                </>
              ) : null}
              {outline && !hasConfirmedOutline && (
                <Tooltip title={hasConfirmedOutline ? '大纲已确认过，不能再清空重写' : '清空未确认的大纲草稿和大纲对话记录'}>
                  <span>
                    <Button
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      disabled={hasConfirmedOutline}
                      loading={saving}
                      onClick={resetOutlineSeed}
                    >
                      清空初版和记录
                    </Button>
                  </span>
                </Tooltip>
              )}
              {outline && !hasConfirmedOutline && (
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
        ) : null}

        {outline ? (
          <div className={styles.editorDraftWrap}>
            <NovelEditor
              ref={editorRef}
              value={editContent}
              onChange={setEditorContentFromUser}
              searchValue={searchValue}
              inlineSuggestions={inlineSuggestions}
              onAcceptSuggestion={acceptSuggestion}
              onRejectSuggestion={rejectSuggestion}
              placeholder="在这里修改大纲。AI 修改建议会直接出现在编辑器里，可以逐块接受或拒绝。"
            />
          </div>
        ) : (
          <div className={styles.emptyEditor}>
            <span>在右侧 AI 助手中输入你的小说想法，AI 会帮你生成完整大纲</span>
          </div>
        )}
      </div>

      <Modal
        title="确认大纲前，是否采用 AI 给出的书名和简介？"
        open={confirmMetaOpen}
        onCancel={() => setConfirmMetaOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setConfirmMetaOpen(false)}>
            取消
          </Button>,
          <Button
            key="later"
            loading={saving}
            onClick={() => executeConfirmOutline({ adoptTitle: false, adoptSynopsis: false })}
          >
            稍后手动生成
          </Button>,
          <Button
            key="confirm"
            type="primary"
            loading={saving}
            onClick={() => executeConfirmOutline({
              adoptTitle: adoptTitleOnConfirm,
              adoptSynopsis: adoptSynopsisOnConfirm,
            })}
          >
            确认大纲
          </Button>,
        ]}
        width={640}
      >
        <div className={styles.confirmMetaBody}>
          <p>大纲只能确认一次。标题和简介可以现在采用，也可以之后在对应页面重新生成。</p>
          {outline?.title?.trim() ? (
            <label className={styles.confirmMetaItem}>
              <Checkbox
                checked={adoptTitleOnConfirm}
                onChange={event => setAdoptTitleOnConfirm(event.target.checked)}
              />
              <span>
                <strong>采用书名</strong>
                <em>{outline.title}</em>
              </span>
            </label>
          ) : null}
          {outline?.synopsis?.trim() ? (
            <label className={styles.confirmMetaItem}>
              <Checkbox
                checked={adoptSynopsisOnConfirm}
                onChange={event => setAdoptSynopsisOnConfirm(event.target.checked)}
              />
              <span>
                <strong>采用简介</strong>
                <em>{outline.synopsis}</em>
              </span>
            </label>
          ) : null}
        </div>
      </Modal>

      <Modal
        title="大纲存档"
        open={compareOpen}
        onCancel={() => setCompareOpen(false)}
        footer={null}
        width={860}
      >
        <div className={styles.comparePicker}>
          <span>选择存档节点</span>
          <Select
            value={compareOutline?.id}
            onChange={setCompareOutlineId}
            style={{ width: 280 }}
            options={archiveOutlines
              .map(item => ({
                value: item.id,
                label: `存档 v${item.version}${item.version_note ? ` · ${item.version_note}` : ''}${item.confirmed ? '（已确认）' : ''}`,
              }))}
          />
          {compareOutline ? (
            <>
              <Button onClick={openCoverVersion}>
                覆盖当前草稿
              </Button>
              <Button
                danger
                disabled={compareOutline.confirmed}
                loading={saving}
                onClick={deleteSelectedVersion}
              >
                删除存档
              </Button>
            </>
          ) : null}
        </div>
        <div className={styles.versionViewer}>
          <div className={styles.versionViewerMeta}>
            <span>{compareOutline ? `存档 v${compareOutline.version}` : '暂无存档'}</span>
            {compareOutline?.version_note ? <span>{compareOutline.version_note}</span> : null}
            {compareOutline?.confirmed ? <Tag color="green">已确认</Tag> : null}
          </div>
          <pre className={styles.versionViewerContent}>
            {normalizeAuthorText(compareOutline?.content) || '暂无可查看存档'}
          </pre>
        </div>
      </Modal>

      <Modal
        title="覆盖当前草稿？"
        open={coverVersionOpen}
        onCancel={() => setCoverVersionOpen(false)}
        onOk={coverCurrentWithSelectedVersion}
        okText="确认覆盖"
        cancelText="取消"
        confirmLoading={saving}
      >
        <div className={styles.versionModalBody}>
          <div className={styles.versionModalTip}>
            你将用选中的存档内容覆盖当前正在编辑的大纲草稿。覆盖前可以选择是否先给当前草稿打一个存档节点。
          </div>
          <Radio.Group value={coverMode} onChange={event => setCoverMode(event.target.value)}>
            <div className={styles.coverChoices}>
              <Radio value="archive">先把当前草稿存档，再覆盖</Radio>
              <Radio value="direct">直接覆盖，不额外保存当前草稿</Radio>
            </div>
          </Radio.Group>
        </div>
      </Modal>

      <Modal
        title="保存存档节点"
        open={saveVersionOpen}
        onCancel={() => setSaveVersionOpen(false)}
        onOk={saveNewVersion}
        okText={`保存为存档 v${(outlines[0]?.version || 0) + 1}`}
        cancelText="取消"
        confirmLoading={saving}
      >
        <div className={styles.versionModalBody}>
          <div className={styles.versionModalTip}>
            当前编辑内容是实时草稿，不算存档。你可以在关键节点手动存档，系统会自动编号，最多保留 {MAX_OUTLINE_VERSIONS} 个，当前已有 {archiveCount} 个。
          </div>
          <Input.TextArea
            value={versionNote}
            onChange={event => setVersionNote(event.target.value)}
            maxLength={80}
            showCount
            autoSize={{ minRows: 3, maxRows: 5 }}
            placeholder="写一句存档备注，例如：调整第一卷节奏、加入女主提前登场"
          />
        </div>
      </Modal>
    </div>
  )
}
