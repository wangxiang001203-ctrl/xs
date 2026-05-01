import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Empty, Input, message, Modal, Radio, Select, Tag } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { api } from '../api'
import WritingToolbar from '../components/editor/WritingToolbar'
import NovelEditor, { type NovelEditorHandle } from '../components/editor/NovelEditor'
import { useAppStore } from '../store'
import type { Worldbuilding, WorldbuildingEntry, WorldbuildingSection } from '../types'
import styles from './WorldbuildingPage.module.css'

const MAX_ARCHIVES = 5

const DEFAULT_SECTIONS: WorldbuildingSection[] = [
  {
    id: 'power_system',
    name: '力量体系',
    description: '修炼路径、能力体系、境界划分、突破条件、代价与上限。',
    generation_hint: '',
    content: '',
    entries: [],
  },
  {
    id: 'techniques',
    name: '功法 / 技能',
    description: '功法、秘术、职业技能、招式体系、学习条件、代价和克制关系。',
    generation_hint: '',
    content: '',
    entries: [],
  },
  {
    id: 'items',
    name: '道具 / 资源',
    description: '宝物、资源、武器、道具、遗物、丹药、钥匙、特殊物资。',
    generation_hint: '',
    content: '',
    entries: [],
  },
  {
    id: 'geography',
    name: '地点 / 地图',
    description: '大陆、城市、秘境、禁地、星域、副本、关键地点和路线。',
    generation_hint: '',
    content: '',
    entries: [],
  },
  {
    id: 'factions',
    name: '势力 / 组织',
    description: '宗门、王朝、联盟、家族、公司、门派、阵营等长期势力。',
    generation_hint: '',
    content: '',
    entries: [],
  },
  {
    id: 'core_rules',
    name: '世界规则',
    description: '这个世界必须遵守的底层规则、禁忌、限制、代价和边界。',
    generation_hint: '',
    content: '',
    entries: [],
  },
]

const STRUCTURED_SECTION_IDS = new Set([
  'power_system',
  'techniques',
  'items',
  'geography',
  'factions',
  'core_rules',
])

const ATTRIBUTE_PRESETS: Record<string, Array<{ key: string; label: string; placeholder?: string }>> = {
  power_system: [
    { key: 'order', label: '层级顺序', placeholder: '例如：1 / 练气之前' },
    { key: 'previous', label: '上一阶段', placeholder: '例如：凡人' },
    { key: 'next', label: '下一阶段', placeholder: '例如：筑基' },
    { key: 'cost', label: '突破代价', placeholder: '资源、风险、条件' },
    { key: 'limit', label: '边界限制', placeholder: '不能越级、寿元限制等' },
  ],
  techniques: [
    { key: 'grade', label: '品阶/等级', placeholder: '黄阶、S级、普通技能等' },
    { key: 'owner', label: '掌握者', placeholder: '角色名，多个用顿号隔开' },
    { key: 'source', label: '来源', placeholder: '宗门、秘境、传承等' },
    { key: 'restriction', label: '限制/代价', placeholder: '消耗、禁忌、冷却等' },
    { key: 'counter', label: '克制关系', placeholder: '克制谁/被谁克制' },
  ],
  items: [
    { key: 'item_type', label: '类型', placeholder: '法宝、丹药、资源、钥匙' },
    { key: 'grade', label: '品阶/等级', placeholder: '下品、上品、唯一等' },
    { key: 'owner', label: '当前归属', placeholder: '男主/宗门/共有资源' },
    { key: 'location', label: '当前位置', placeholder: '地点名，不确定可写“去往XX途中”' },
    { key: 'status', label: '当前状态', placeholder: '完整、损坏、封印、消耗中' },
  ],
  geography: [
    { key: 'location_type', label: '地点类型', placeholder: '城市、宗门、秘境、路上、世界层' },
    { key: 'parent_location', label: '上级地点', placeholder: '大陆/国家/区域' },
    { key: 'coordinates', label: '地图坐标', placeholder: '可先粗略：东域-北三百里' },
    { key: 'controlling_faction', label: '控制势力', placeholder: '宗门/王朝/公司' },
    { key: 'present_characters', label: '当前在场角色', placeholder: '角色名，多个用顿号隔开' },
  ],
  factions: [
    { key: 'faction_type', label: '势力类型', placeholder: '宗门、家族、公司、联盟' },
    { key: 'base_location', label: '据点位置', placeholder: '地点名' },
    { key: 'leader', label: '掌权者', placeholder: '角色名' },
    { key: 'allies', label: '盟友', placeholder: '势力名，多个用顿号隔开' },
    { key: 'enemies', label: '敌对', placeholder: '势力名，多个用顿号隔开' },
  ],
  core_rules: [
    { key: 'scope', label: '适用范围', placeholder: '全世界/某秘境/某功法' },
    { key: 'trigger', label: '触发条件', placeholder: '什么情况下生效' },
    { key: 'cost', label: '代价', placeholder: '违反或使用时的后果' },
    { key: 'exception', label: '例外', placeholder: '谁可以绕过，为什么' },
  ],
  custom: [
    { key: 'category', label: '类别', placeholder: '灵兽、秘境、职业、规则等' },
    { key: 'owner', label: '归属/持有者', placeholder: '角色/势力/地点' },
    { key: 'location', label: '关联地点', placeholder: '地点名' },
    { key: 'related_roles', label: '关联角色', placeholder: '角色名，多个用顿号隔开' },
    { key: 'status', label: '当前状态', placeholder: '有效、封印、失效、待揭示' },
  ],
}

interface LocalArchive {
  id: string
  version: number
  note?: string
  content: string
  createdAt: string
}

interface WorldbuildingDraft {
  local?: Partial<Worldbuilding>
  updatedAtByFile?: Record<string, string>
  archives?: Record<string, LocalArchive[]>
}

function newId(prefix: string) {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID().slice(0, 8)}`
  }
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`
}

function entryIsBlank(entry?: WorldbuildingEntry | null) {
  if (!entry) return true
  const hasAttributes = Object.values(entry.attributes || {}).some(value => String(value ?? '').trim())
  return !entry.name?.trim()
    && !entry.summary?.trim()
    && !entry.details?.trim()
    && !(entry.tags || []).length
    && !hasAttributes
}

function entryIsArchived(entry?: WorldbuildingEntry | null) {
  return Boolean(entry?.attributes?.status === 'archived' || (entry?.tags || []).includes('已停用'))
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

function entryToMarkdown(entry: Partial<WorldbuildingEntry>) {
  const parts = [
    entry.name ? `## ${entry.name}` : '',
    entry.summary || '',
    entry.details || '',
  ].filter(Boolean)
  return parts.join('\n')
}

function entriesToMarkdown(entries?: WorldbuildingEntry[]) {
  return (entries || []).map(entryToMarkdown).filter(Boolean).join('\n\n')
}

function attrsToMarkdown(attrs?: Record<string, any>) {
  return Object.entries(attrs || {})
    .filter(([, value]) => value !== undefined && value !== null && String(value).trim())
    .map(([key, value]) => `- ${key}：${String(value)}`)
    .join('\n')
}

function sectionToArchiveText(section?: WorldbuildingSection | null) {
  if (!section) return ''
  const parts = [
    `# ${section.name}`,
    section.description || '',
    section.content ? `## 分类备注\n${section.content}` : '',
    ...(section.entries || []).map(entry => [
      `## ${entry.name || '未命名条目'}`,
      entry.summary || '',
      attrsToMarkdown(entry.attributes),
      entry.details || '',
      (entry.tags || []).length ? `标签：${(entry.tags || []).join('、')}` : '',
    ].filter(Boolean).join('\n')),
  ].filter(Boolean)
  return parts.join('\n\n')
}

function normalizeSection(section: Partial<WorldbuildingSection>): WorldbuildingSection {
  const entries = section.entries || []
  return {
    id: section.id || newId('section'),
    name: section.name || '自定义设定',
    description: section.description || '',
    generation_hint: '',
    content: section.content || '',
    entries,
  }
}

function normalizeWorldbuilding(doc?: Partial<Worldbuilding> | null): Partial<Worldbuilding> {
  const existingSections = (doc?.sections || []).map(normalizeSection)
  const sections = DEFAULT_SECTIONS.map((defaultSection) => {
    const matched = existingSections.find(section => section.id === defaultSection.id || section.name === defaultSection.name)
    const legacySource =
      defaultSection.id === 'power_system' ? doc?.power_system :
      defaultSection.id === 'factions' ? doc?.factions :
      defaultSection.id === 'geography' ? doc?.geography :
      defaultSection.id === 'core_rules' ? doc?.core_rules :
      doc?.items
    const legacyEntries = (legacySource || []).map((item: Record<string, any>) => ({
        id: newId('entry'),
        name: String(item.name || item.rule_name || '').trim(),
        summary: String(item.description || item.desc || item.summary || '').trim(),
        details: '',
        tags: [],
        attributes: {},
      }))
    return normalizeSection({
      ...defaultSection,
      ...matched,
      entries: matched?.entries?.length ? matched.entries : legacyEntries,
      content: matched?.content || defaultSection.content,
    })
  })

  const customSections = existingSections.filter(section =>
    !DEFAULT_SECTIONS.some(defaultSection => defaultSection.id === section.id || defaultSection.name === section.name),
  )

  return {
    ...doc,
    overview: doc?.overview || '',
    sections: [...sections, ...customSections],
  }
}

function createBlankSection(index: number): WorldbuildingSection {
  return {
    id: newId('section'),
    name: `自定义设定 ${index}`,
    description: '',
    generation_hint: '',
    content: '',
    entries: [],
  }
}

export default function WorldbuildingPage() {
  const {
    currentNovel,
    worldbuilding,
    setWorldbuilding,
    documentDrafts,
    patchDocumentDraft,
    activeWorldbuildingSectionId,
    setActiveWorldbuildingSectionId,
  } = useAppStore()
  const [local, setLocal] = useState<Partial<Worldbuilding>>({})
  const [generatedDraft, setGeneratedDraft] = useState<Partial<Worldbuilding> | null>(null)
  const [searchValue, setSearchValue] = useState('')
  const [savedAt, setSavedAt] = useState<string | null>(null)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [saveArchiveOpen, setSaveArchiveOpen] = useState(false)
  const [archiveNote, setArchiveNote] = useState('')
  const [coverOpen, setCoverOpen] = useState(false)
  const [coverMode, setCoverMode] = useState<'archive' | 'direct'>('archive')
  const [selectedArchiveId, setSelectedArchiveId] = useState<string | null>(null)
  const [renameOpen, setRenameOpen] = useState(false)
  const [renameValue, setRenameValue] = useState('')
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null)
  const [generatedDraftScope, setGeneratedDraftScope] = useState<'overview' | 'file' | 'entry'>('file')
  const editorRef = useRef<NovelEditorHandle>(null)
  const userEditedRef = useRef(false)
  const docKey = currentNovel ? `worldbuilding:${currentNovel.id}` : null
  const draft = (docKey ? documentDrafts[docKey] : null) as WorldbuildingDraft | null
  const sections = local.sections || []
  const activeSection = sections.find(section => section.id === activeWorldbuildingSectionId)
  const activeFileKey = activeWorldbuildingSectionId === 'overview' ? 'overview' : activeSection?.id || 'overview'
  const activeTitle = activeWorldbuildingSectionId === 'overview' ? '世界总述' : activeSection?.name || '设定文件'
  const activeContent = activeWorldbuildingSectionId === 'overview' ? local.overview || '' : activeSection?.content || ''
  const isStructuredSection = Boolean(activeSection && (STRUCTURED_SECTION_IDS.has(activeSection.id || '') || !DEFAULT_SECTIONS.some(section => section.id === activeSection.id)))
  const activeEntries = activeSection?.entries || []
  const selectedEntry = activeEntries.find(entry => entry.id === selectedEntryId) || activeEntries[0] || null
  const isCustomSection = Boolean(activeSection?.id && !DEFAULT_SECTIONS.some(section => section.id === activeSection.id))
  const archivesByFile = draft?.archives || {}
  const archives = useMemo(() => archivesByFile[activeFileKey] || [], [archivesByFile, activeFileKey])
  const selectedArchive = archives.find(item => item.id === selectedArchiveId) || archives[0] || null
  const activeReadableContent = activeWorldbuildingSectionId === 'overview' ? activeContent : sectionToArchiveText(activeSection)
  const searchCount = searchValue.trim() ? activeReadableContent.split(searchValue.trim()).length - 1 : 0

  useEffect(() => {
    if (!currentNovel) return
    if (userEditedRef.current) return
    const currentDraft = (docKey ? documentDrafts[docKey] : null) as WorldbuildingDraft | null
    setLocal(normalizeWorldbuilding(currentDraft?.local || worldbuilding))
  }, [currentNovel?.id, worldbuilding])

  useEffect(() => {
    setSavedAt(draft?.updatedAtByFile?.[activeFileKey] || null)
    setSelectedArchiveId((draft?.archives || {})[activeFileKey]?.[0]?.id || null)
  }, [activeFileKey, draft?.updatedAtByFile, draft?.archives])

  useEffect(() => {
    if (!activeSection) {
      setSelectedEntryId(null)
      return
    }
    if (selectedEntryId && activeEntries.some(entry => entry.id === selectedEntryId)) return
    setSelectedEntryId(activeEntries[0]?.id || null)
  }, [activeSection?.id, activeEntries.length, selectedEntryId])

  useEffect(() => {
    if (!docKey || !userEditedRef.current) return
    const currentDraft = useAppStore.getState().documentDrafts[docKey] as WorldbuildingDraft | undefined
    const updatedAt = new Date().toISOString()
    patchDocumentDraft(docKey, {
      local,
      updatedAtByFile: {
        ...(currentDraft?.updatedAtByFile || {}),
        [activeFileKey]: updatedAt,
      },
    })
    setSavedAt(updatedAt)
  }, [docKey, local, activeFileKey])

  useEffect(() => {
    if (!currentNovel || !userEditedRef.current) return undefined

    const timer = window.setTimeout(() => {
      void api.worldbuilding.update(currentNovel.id, normalizeWorldbuilding(local))
        .then((updated) => {
          userEditedRef.current = false
          setWorldbuilding(updated)
          const currentDraft = docKey ? useAppStore.getState().documentDrafts[docKey] as WorldbuildingDraft | undefined : undefined
          const updatedAt = new Date().toISOString()
          if (docKey) {
            patchDocumentDraft(docKey, {
              local: normalizeWorldbuilding(local),
              updatedAtByFile: {
                ...(currentDraft?.updatedAtByFile || {}),
                [activeFileKey]: updatedAt,
              },
            })
          }
          setSavedAt(updatedAt)
        })
        .catch(() => {
          // 本地草稿已经持久化，网络失败时不打断作者编辑。
        })
    }, 900)

    return () => window.clearTimeout(timer)
  }, [currentNovel?.id, docKey, local, activeFileKey])

  useEffect(() => {
    if (!currentNovel) return
    if (activeWorldbuildingSectionId !== '__new_custom__') return
    const customCount = sections.filter(section => !DEFAULT_SECTIONS.some(item => item.id === section.id)).length
    const nextSection = createBlankSection(customCount + 1)
    userEditedRef.current = true
    setLocal(prev => ({
      ...prev,
      sections: [...(prev.sections || []), nextSection],
    }))
    setActiveWorldbuildingSectionId(nextSection.id || 'overview')
  }, [activeWorldbuildingSectionId, currentNovel?.id, sections.length, setActiveWorldbuildingSectionId])

  useEffect(() => {
    if (activeWorldbuildingSectionId === 'overview' || activeWorldbuildingSectionId === '__new_custom__') return
    if (sections.some(section => section.id === activeWorldbuildingSectionId)) return
    setActiveWorldbuildingSectionId('overview')
  }, [activeWorldbuildingSectionId, sections, setActiveWorldbuildingSectionId])

  useEffect(() => {
    function handleWorldbuildingAIRequest(event: Event) {
      const customEvent = event as CustomEvent<{ prompt?: string }>
      void generateWorldbuilding(customEvent.detail?.prompt || '')
    }

    window.addEventListener('mobi:worldbuilding-ai-request', handleWorldbuildingAIRequest)
    return () => window.removeEventListener('mobi:worldbuilding-ai-request', handleWorldbuildingAIRequest)
  }, [activeFileKey, activeTitle, activeContent, currentNovel?.id, local])

  function setActiveContent(nextContent: string) {
    userEditedRef.current = true
    if (activeWorldbuildingSectionId === 'overview') {
      setLocal(prev => ({ ...prev, overview: nextContent }))
      return
    }
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).map(section =>
        section.id === activeSection?.id ? { ...section, content: nextContent } : section,
      ),
    }))
  }

  function patchActiveSection(patch: Partial<WorldbuildingSection>) {
    if (!activeSection?.id) return
    userEditedRef.current = true
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).map(section =>
        section.id === activeSection.id ? { ...section, ...patch } : section,
      ),
    }))
  }

  function patchEntry(entryId: string, patch: Partial<WorldbuildingEntry>) {
    if (!activeSection?.id) return
    userEditedRef.current = true
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).map(section =>
        section.id === activeSection.id
          ? {
              ...section,
              entries: (section.entries || []).map(entry =>
                entry.id === entryId ? { ...entry, ...patch } : entry,
              ),
            }
          : section,
      ),
    }))
  }

  function patchEntryAttribute(entryId: string, key: string, value: string) {
    const entry = activeEntries.find(item => item.id === entryId)
    patchEntry(entryId, {
      attributes: {
        ...(entry?.attributes || {}),
        [key]: value,
      },
    })
  }

  function addEntry() {
    if (!activeSection?.id) return
    const nextEntry: WorldbuildingEntry = {
      id: newId('entry'),
      name: '新设定',
      summary: '',
      details: '',
      tags: [],
      attributes: {},
    }
    userEditedRef.current = true
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).map(section =>
        section.id === activeSection.id
          ? { ...section, entries: [...(section.entries || []), nextEntry] }
          : section,
      ),
    }))
    setSelectedEntryId(nextEntry.id || null)
  }

  function removeEntry(entryId: string) {
    if (!activeSection?.id) return
    const entry = activeEntries.find(item => item.id === entryId)
    const hardRemove = entryIsBlank(entry) || entry?.name === '新设定'
    Modal.confirm({
      title: hardRemove ? `移除「${entry?.name || '未命名条目'}」？` : `停用保留「${entry?.name || '未命名条目'}」？`,
      content: hardRemove
        ? '这个条目还是空白占位，可以直接移除。'
        : '已有内容的设定条目不会硬删除，会标记为“已停用”并保留原始设定，避免破坏正文和关系网连续性。',
      okText: hardRemove ? '移除' : '停用保留',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => {
        userEditedRef.current = true
        setLocal(prev => ({
          ...prev,
          sections: (prev.sections || []).map(section =>
            section.id === activeSection.id
              ? {
                  ...section,
                  entries: hardRemove
                    ? (section.entries || []).filter(item => item.id !== entryId)
                    : (section.entries || []).map(item => item.id === entryId
                        ? {
                            ...item,
                            tags: Array.from(new Set([...(item.tags || []), '已停用'])),
                            attributes: {
                              ...(item.attributes || {}),
                              status: 'archived',
                              archived_at: new Date().toISOString(),
                            },
                            details: `${item.details || ''}\n\n## 停用记录\n作者尝试移除该设定，系统已停用保留，避免破坏连续性。`.trim(),
                          }
                        : item),
                }
              : section,
          ),
        }))
        if (hardRemove && selectedEntryId === entryId) {
          const next = activeEntries.find(item => item.id !== entryId)
          setSelectedEntryId(next?.id || null)
        }
      },
    })
  }

  function setEntryTags(entryId: string, value: string) {
    patchEntry(entryId, {
      tags: value.split(/[、,\n]/).map(item => item.trim()).filter(Boolean),
    })
  }

  function saveActiveArchiveContent() {
    if (activeWorldbuildingSectionId === 'overview') return activeContent
    return sectionToArchiveText(activeSection)
  }

  function renameActiveSection() {
    if (!activeSection?.id) return
    const nextName = renameValue.trim()
    if (!nextName) {
      message.warning('文件名不能为空')
      return
    }
    userEditedRef.current = true
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).map(section =>
        section.id === activeSection.id ? { ...section, name: nextName } : section,
      ),
    }))
    closeRenameDialog()
  }

  function closeGeneratedDraft() {
    setGeneratedDraft(null)
    setGeneratedDraftScope('file')
  }

  function closeRenameDialog() {
    setRenameOpen(false)
    setRenameValue('')
  }

  function closeArchivePanel() {
    setArchiveOpen(false)
    setSelectedArchiveId(null)
  }

  function closeSaveArchiveDialog() {
    setSaveArchiveOpen(false)
    setArchiveNote('')
  }

  function closeCoverDialog() {
    setCoverOpen(false)
    setCoverMode('archive')
  }

  function removeSection(sectionId: string) {
    const section = sections.find(item => item.id === sectionId)
    Modal.confirm({
      title: `删除「${section?.name || '自定义设定'}」？`,
      content: '删除后这份设定会从当前世界观移除。已保存的旧存档不会自动删除。',
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: () => {
        userEditedRef.current = true
        setLocal(prev => ({
          ...prev,
          sections: (prev.sections || []).filter(item => item.id !== sectionId),
        }))
        setActiveWorldbuildingSectionId('overview')
      },
    })
  }

  function shouldLockSelectedEntry(extraInstruction?: string) {
    if (!selectedEntry || !activeSection) return false
    const text = extraInstruction || ''
    if (/(新增|新建|创建|添加|加一个|再加|补一个|新增条目|创建条目)/.test(text)) return false
    if (selectedEntry.name && text.includes(selectedEntry.name)) return true
    if (/(当前|这个|这条|该|此|本)(条目|设定|道具|地点|势力|功法|技能|规则|资源|卡片)/.test(text)) return true
    if (/(改成|改为|调整为|更新为|升级到|降级到|归属改|位置改|状态改)/.test(text)) return true
    return false
  }

  async function generateWorldbuilding(extraInstruction?: string) {
    if (!currentNovel) return
    try {
      const lockSelectedEntry = shouldLockSelectedEntry(extraInstruction)
      const focusInstruction = [
        activeWorldbuildingSectionId === 'overview'
          ? '重点完善「世界总述」这份设定文件。'
          : `重点完善「${activeTitle}」这份设定文件。`,
        '范围锁定：除非作者明确要求“全部/批量/整库”，本次只能生成当前设定文件的草稿，不要重写其他设定文件。',
        lockSelectedEntry && selectedEntry
          ? `当前选中条目：${selectedEntry.name || '未命名条目'}。如果用户是在修改当前条目，只能返回这个条目的更新，不要改动同分类下其他条目。\n当前条目内容：\n${entryToMarkdown(selectedEntry)}`
          : null,
        activeReadableContent.trim() ? `当前文件内容：\n${activeReadableContent.trim()}` : '当前文件内容为空，请根据大纲和已有设定补齐。',
        extraInstruction,
        '请保持设定可扩展。地点、势力、道具、功法等必须优先返回 sections[].entries[] 结构化条目，content 只写分类备注。',
      ].filter(Boolean).join('\n\n')
      const data = await api.ai.generateWorldbuilding(currentNovel.id, {
        currentWorldbuilding: normalizeWorldbuilding(local),
        extraInstruction: focusInstruction,
        dryRun: true,
      })
      setGeneratedDraftScope(activeWorldbuildingSectionId === 'overview' ? 'overview' : lockSelectedEntry ? 'entry' : 'file')
      setGeneratedDraft(normalizeWorldbuilding(data))
      window.dispatchEvent(new CustomEvent('mobi:worldbuilding-ai-response', {
        detail: { ok: true, message: `已生成「${activeTitle}」的设定草稿，请在主编辑区确认是否应用。` },
      }))
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err.message
      window.dispatchEvent(new CustomEvent('mobi:worldbuilding-ai-response', {
        detail: { ok: false, message: `生成失败：${detail}` },
      }))
      message.error(`生成失败：${detail}`)
    }
  }

  function activeGeneratedSection() {
    if (!generatedDraft || !activeSection) return null
    const generatedSections = generatedDraft.sections || []
    return generatedSections.find(section => section.id === activeSection.id)
      || generatedSections.find(section => section.name === activeSection.name)
      || null
  }

  function activeGeneratedEntry(section?: WorldbuildingSection | null) {
    if (!selectedEntry || !section) return null
    const generatedEntries = section.entries || []
    return generatedEntries.find(entry => entry.id && entry.id === selectedEntry.id)
      || generatedEntries.find(entry => entry.name && entry.name === selectedEntry.name)
      || null
  }

  function applyGeneratedDraft() {
    if (!generatedDraft) return
    const nextSection = activeWorldbuildingSectionId === 'overview' ? null : activeGeneratedSection()
    const nextEntry = nextSection && selectedEntry && generatedDraftScope === 'entry'
      ? activeGeneratedEntry(nextSection)
      : null

    if (activeWorldbuildingSectionId !== 'overview' && activeSection && !nextSection) {
      message.warning('AI 草稿里没有找到当前设定文件，已取消应用，避免误覆盖。')
      return
    }
    if (activeWorldbuildingSectionId !== 'overview' && activeSection && selectedEntry && generatedDraftScope === 'entry' && !nextEntry) {
      message.warning('AI 草稿里没有找到当前选中的设定条目，已取消应用，避免误覆盖整个分类。')
      return
    }

    const snapshotTime = new Date().toISOString()
    if (docKey) {
      const currentDraft = useAppStore.getState().documentDrafts[docKey] as WorldbuildingDraft | undefined
      const currentArchiveContent = saveActiveArchiveContent()
      const currentArchives = (currentDraft?.archives || {})[activeFileKey] || []
      patchDocumentDraft(docKey, {
        archives: {
          ...(currentDraft?.archives || {}),
          [activeFileKey]: [
            {
              id: createArchiveId(),
              version: Math.max(0, ...currentArchives.map(item => item.version)) + 1,
              note: 'AI 应用前自动备份',
              content: currentArchiveContent,
              createdAt: snapshotTime,
            },
            ...currentArchives,
          ].slice(0, MAX_ARCHIVES),
        },
      })
    }

    userEditedRef.current = true
    if (activeWorldbuildingSectionId === 'overview') {
      setLocal(prev => ({
        ...prev,
        overview: generatedDraft.overview || prev.overview || '',
      }))
    } else if (activeSection) {
      if (selectedEntry && generatedDraftScope === 'entry') {
        setLocal(prev => ({
          ...prev,
          sections: (prev.sections || []).map(section =>
            section.id === activeSection.id
              ? normalizeSection({
                  ...section,
                  entries: (section.entries || []).map(entry =>
                    entry.id === selectedEntry.id
                      ? { ...entry, ...nextEntry!, id: entry.id }
                      : entry,
                  ),
                })
              : section,
          ),
        }))
        closeGeneratedDraft()
        message.success('已应用到当前设定条目，其他条目未被改动')
        return
      }
      setLocal(prev => ({
        ...prev,
        sections: (prev.sections || []).map(section =>
          section.id === activeSection.id
            ? normalizeSection({
                ...section,
                ...nextSection!,
                id: section.id,
                name: section.name,
              })
            : section,
        ),
      }))
    }
    closeGeneratedDraft()
    message.success('已应用到当前设定文件，其他文件未被改动')
  }

  function openArchivePanel() {
    setSelectedArchiveId(archives[0]?.id || null)
    setArchiveOpen(true)
  }

  function saveArchive() {
    if (!docKey) return
    if (archives.length >= MAX_ARCHIVES) {
      message.warning('每份设定最多保留 5 个存档，请先删除旧存档。')
      setArchiveOpen(true)
      return
    }
    const currentDraft = useAppStore.getState().documentDrafts[docKey] as WorldbuildingDraft | undefined
    const nextVersion = Math.max(0, ...archives.map(item => item.version)) + 1
    const nextArchive: LocalArchive = {
      id: createArchiveId(),
      version: nextVersion,
      note: archiveNote.trim() || undefined,
      content: saveActiveArchiveContent(),
      createdAt: new Date().toISOString(),
    }
    patchDocumentDraft(docKey, {
      archives: {
        ...(currentDraft?.archives || {}),
        [activeFileKey]: [nextArchive, ...archives].slice(0, MAX_ARCHIVES),
      },
    })
    closeSaveArchiveDialog()
    message.success(`已保存「${activeTitle}」存档 v${nextVersion}`)
  }

  function deleteArchive(archiveId: string) {
    if (!docKey) return
    const currentDraft = useAppStore.getState().documentDrafts[docKey] as WorldbuildingDraft | undefined
    const nextArchives = archives.filter(item => item.id !== archiveId)
    patchDocumentDraft(docKey, {
      archives: {
        ...(currentDraft?.archives || {}),
        [activeFileKey]: nextArchives,
      },
    })
    setSelectedArchiveId(nextArchives[0]?.id || null)
    message.success('已删除存档')
  }

  function coverCurrentWithArchive() {
    if (!docKey || !selectedArchive) return
    const currentDraft = useAppStore.getState().documentDrafts[docKey] as WorldbuildingDraft | undefined
    let nextArchives = archives
    const currentArchiveContent = saveActiveArchiveContent()
    if (coverMode === 'archive' && currentArchiveContent.trim() && currentArchiveContent !== selectedArchive.content) {
      if (archives.length >= MAX_ARCHIVES) {
        message.warning('最多保留 5 个存档。请先删除一个旧存档，或选择直接覆盖。')
        return
      }
      const nextVersion = Math.max(0, ...archives.map(item => item.version)) + 1
      nextArchives = [{
        id: createArchiveId(),
        version: nextVersion,
        note: '覆盖前自动存档',
        content: currentArchiveContent,
        createdAt: new Date().toISOString(),
      }, ...archives]
    }
    setActiveContent(selectedArchive.content)
    patchDocumentDraft(docKey, {
      archives: {
        ...(currentDraft?.archives || {}),
        [activeFileKey]: nextArchives,
      },
    })
    closeCoverDialog()
    closeArchivePanel()
  }

  if (!currentNovel) return <div className={styles.empty}>请先选择小说</div>

  return (
    <div className={styles.page}>
      <div className={styles.workspace}>
        <WritingToolbar
          wordCount={activeReadableContent.length}
          statusText={savedAt ? `输入已自动保存 ${formatSavedAt(savedAt)}` : undefined}
          searchValue={searchValue}
          searchCount={searchCount}
          onSearchChange={setSearchValue}
          onUndo={() => editorRef.current?.undo()}
          onRedo={() => editorRef.current?.redo()}
          onSaveVersion={() => {
            if (archives.length >= MAX_ARCHIVES) {
              message.warning('每份设定最多保留 5 个存档，请先删除旧存档。')
              openArchivePanel()
              return
            }
            setArchiveNote('')
            setSaveArchiveOpen(true)
          }}
          saveVersionTooltip={archives.length >= MAX_ARCHIVES ? '最多保留 5 个存档，请先删除旧存档' : '保存当前设定为存档节点'}
          onOpenVersions={openArchivePanel}
          versionsDisabled={archives.length < 1}
          versionsTooltip={archives.length < 1 ? '还没有设定存档' : '查看设定存档'}
        />

        {isCustomSection ? (
          <div className={styles.fileActions}>
            <span>自定义设定文件</span>
            <Button
              size="small"
              onClick={() => {
                setRenameValue(activeSection?.name || '')
                setRenameOpen(true)
              }}
            >
              重命名
            </Button>
            <Button
              size="small"
              danger
              icon={<DeleteOutlined />}
              onClick={() => removeSection(activeSection?.id || '')}
            >
              删除文件
            </Button>
          </div>
        ) : null}

        {activeWorldbuildingSectionId === 'overview' || activeSection ? (
          isStructuredSection && activeSection ? (
            <div className={styles.structuredWrap}>
              <aside className={styles.entryRail}>
                <div className={styles.entryRailHeader}>
                  <div>
                    <strong>{activeTitle}</strong>
                    <span>{activeEntries.length} 个条目</span>
                  </div>
                  <Button size="small" icon={<PlusOutlined />} onClick={addEntry}>
                    新增
                  </Button>
                </div>
                <div className={styles.entryList}>
                  {activeEntries.map(entry => (
                    <button
                      key={entry.id || entry.name}
                      type="button"
                      className={`${styles.entryItem} ${selectedEntry?.id === entry.id ? styles.entryActive : ''}`}
                      onClick={() => setSelectedEntryId(entry.id || null)}
                    >
                      <strong>{entry.name || '未命名条目'}</strong>
                      <span>
                        {entryIsArchived(entry) ? '已停用 · ' : ''}
                        {entry.summary || entry.details || '待补充设定'}
                      </span>
                    </button>
                  ))}
                  {!activeEntries.length ? (
                    <div className={styles.entryEmpty}>还没有结构化条目。比如地点、势力、道具都应该先建条目，再让 AI/正文引用。</div>
                  ) : null}
                </div>
              </aside>

              <main className={styles.entryEditor}>
                {selectedEntry ? (
                  <>
                    <div className={styles.entryTopline}>
                      <Input
                        value={selectedEntry.name}
                        onChange={event => patchEntry(selectedEntry.id || '', { name: event.target.value })}
                        placeholder="条目名称"
                        className={styles.entryNameInput}
                      />
                      {entryIsArchived(selectedEntry) ? <Tag color="default">已停用</Tag> : null}
                      <Button danger icon={<DeleteOutlined />} disabled={entryIsArchived(selectedEntry)} onClick={() => removeEntry(selectedEntry.id || '')}>
                        {entryIsArchived(selectedEntry) ? '已停用' : '停用'}
                      </Button>
                    </div>

                    <Input.TextArea
                      value={selectedEntry.summary || ''}
                      onChange={event => patchEntry(selectedEntry.id || '', { summary: event.target.value })}
                      autoSize={{ minRows: 2, maxRows: 4 }}
                      placeholder="一句话说明。AI 和后续扫描会优先读这里。"
                    />

                    <div className={styles.attributeGrid}>
                      {(ATTRIBUTE_PRESETS[activeSection.id || ''] || ATTRIBUTE_PRESETS.custom).map(field => (
                        <label key={field.key} className={styles.attributeField}>
                          <span>{field.label}</span>
                          <Input
                            value={String(selectedEntry.attributes?.[field.key] || '')}
                            onChange={event => patchEntryAttribute(selectedEntry.id || '', field.key, event.target.value)}
                            placeholder={field.placeholder}
                          />
                        </label>
                      ))}
                    </div>

                    <Input.TextArea
                      value={selectedEntry.details || ''}
                      onChange={event => patchEntry(selectedEntry.id || '', { details: event.target.value })}
                      autoSize={{ minRows: 8, maxRows: 16 }}
                      placeholder="详细设定。可以写来源、限制、历史、当前状态，但归属/位置/关联角色这类请优先填上面的结构字段。"
                      className={styles.detailTextarea}
                    />

                    <Input
                      value={(selectedEntry.tags || []).join('、')}
                      onChange={event => setEntryTags(selectedEntry.id || '', event.target.value)}
                      placeholder="标签，用顿号/逗号分隔"
                    />
                  </>
                ) : (
                  <Empty description="选择或新增一个条目" />
                )}
              </main>

              <aside className={styles.sectionNotes}>
                <strong>分类备注</strong>
                <span>这里只写整体补充，不承担可查询的结构事实。</span>
                <Input.TextArea
                  value={activeSection.content || ''}
                  onChange={event => patchActiveSection({ content: event.target.value })}
                  autoSize={{ minRows: 12, maxRows: 24 }}
                  placeholder="例如：地图整体布局、势力总体矛盾、道具体系通用规则。"
                />
              </aside>
            </div>
          ) : (
            <div className={styles.editorWrap}>
              <NovelEditor
                ref={editorRef}
                value={activeContent}
                onChange={setActiveContent}
                searchValue={searchValue}
                placeholder="写整体世界总述。具体地点、势力、道具、功法请到对应分类里建结构化条目。"
              />
            </div>
          )
        ) : (
          <div className={styles.emptyState}>
            <Empty description="还没有设定文件。可以在左侧自定义设定里新增文件。" />
          </div>
        )}
      </div>

      <Modal
        title="AI 世界观草稿"
        open={Boolean(generatedDraft)}
        onCancel={closeGeneratedDraft}
        onOk={applyGeneratedDraft}
        okText="应用到当前编辑态"
        cancelText="先不应用"
        width={860}
        destroyOnHidden
      >
        <div className={styles.generatedPreview}>
          <p>AI 生成的是当前文件草稿。应用后只会进入当前编辑态，其他设定文件不会被覆盖。</p>
          {activeWorldbuildingSectionId === 'overview' ? (
            <div className={styles.previewBlock}>
              <strong>世界总述</strong>
              <pre>{generatedDraft?.overview || '暂无内容'}</pre>
            </div>
          ) : activeGeneratedSection() ? (
            <div className={styles.previewBlock}>
              <strong>
                {generatedDraftScope === 'entry'
                  ? activeGeneratedEntry(activeGeneratedSection())?.name || selectedEntry?.name || activeTitle
                  : activeGeneratedSection()?.name || activeTitle}
              </strong>
              <pre>
                {generatedDraftScope === 'entry'
                  ? activeGeneratedEntry(activeGeneratedSection())
                    ? entryToMarkdown(activeGeneratedEntry(activeGeneratedSection()) || {})
                    : 'AI 草稿里没有找到当前选中的设定条目，应用时会被拦截。'
                  : activeGeneratedSection()?.content || entriesToMarkdown(activeGeneratedSection()?.entries)}
              </pre>
            </div>
          ) : (
            <div className={styles.previewBlock}>
              <strong>{activeTitle}</strong>
              <pre>AI 草稿里没有找到当前设定文件，应用时会被拦截。</pre>
            </div>
          )}
        </div>
      </Modal>

      <Modal
        title="重命名设定文件"
        open={renameOpen}
        onCancel={closeRenameDialog}
        onOk={renameActiveSection}
        okText="确认"
        cancelText="取消"
        destroyOnHidden
      >
        <Input
          value={renameValue}
          onChange={event => setRenameValue(event.target.value)}
          placeholder="例如：灵兽谱、秘境规则、职业体系"
        />
      </Modal>

      <Modal
        title={`${activeTitle} · 存档`}
        open={archiveOpen}
        onCancel={closeArchivePanel}
        footer={null}
        width={780}
        destroyOnHidden
      >
        <div className={styles.archivePicker}>
          <span>选择存档节点</span>
          <Select
            value={selectedArchive?.id}
            onChange={setSelectedArchiveId}
            style={{ width: 300 }}
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
        title={`保存「${activeTitle}」存档`}
        open={saveArchiveOpen}
        onCancel={closeSaveArchiveDialog}
        onOk={saveArchive}
        okText={`保存为存档 v${Math.max(0, ...archives.map(item => item.version)) + 1}`}
        cancelText="取消"
        destroyOnHidden
      >
        <div className={styles.archiveTip}>当前设定是实时草稿，不算存档。每份设定最多保留 5 个存档节点。</div>
        <Input.TextArea
          value={archiveNote}
          onChange={event => setArchiveNote(event.target.value)}
          maxLength={80}
          showCount
          autoSize={{ minRows: 3, maxRows: 5 }}
          placeholder="写一句存档备注，例如：补齐归属关系、调整境界代价"
        />
      </Modal>

      <Modal
        title="覆盖当前设定？"
        open={coverOpen}
        onCancel={closeCoverDialog}
        onOk={coverCurrentWithArchive}
        okText="确认覆盖"
        cancelText="取消"
        destroyOnHidden
      >
        <div className={styles.archiveTip}>你将用选中的存档覆盖当前正在编辑的设定文件。</div>
        <Radio.Group value={coverMode} onChange={event => setCoverMode(event.target.value)}>
          <div className={styles.coverChoices}>
            <Radio value="archive">先把当前设定存档，再覆盖</Radio>
            <Radio value="direct">直接覆盖，不额外保存当前设定</Radio>
          </div>
        </Radio.Group>
      </Modal>
    </div>
  )
}
