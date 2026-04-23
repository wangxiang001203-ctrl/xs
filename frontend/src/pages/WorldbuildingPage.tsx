import { useEffect, useMemo, useState } from 'react'
import { Button, Empty, Input, message, Tabs } from 'antd'
import { DeleteOutlined, PlusOutlined, SaveOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { api } from '../api'
import { useAppStore } from '../store'
import type { Worldbuilding, WorldbuildingEntry, WorldbuildingSection } from '../types'
import styles from './WorldbuildingPage.module.css'

const DEFAULT_SECTIONS = [
  {
    id: 'power_system',
    name: '力量体系',
    description: '修炼路径、境界划分、突破条件、代价与上限。',
  },
  {
    id: 'factions',
    name: '势力组织',
    description: '宗门、王朝、联盟、世家、魔门等核心势力。',
  },
  {
    id: 'geography',
    name: '地图地点',
    description: '大陆、城池、秘境、禁地、山脉等关键地点。',
  },
  {
    id: 'core_rules',
    name: '世界法则',
    description: '世界规则、禁忌、边界与长期约束。',
  },
  {
    id: 'items',
    name: '关键道具',
    description: '宝物、资源、法器、遗物、丹药等重要道具。',
  },
]

function newId(prefix: string) {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID().slice(0, 8)}`
  }
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`
}

function mapLegacyItems(items: Record<string, any>[] = [], nameKey = 'name'): WorldbuildingEntry[] {
  return items.map((item) => ({
    id: newId('entry'),
    name: String(item?.[nameKey] || item?.name || '').trim(),
    summary: String(item?.description || item?.desc || item?.summary || '').trim(),
    details: '',
    tags: [],
    attributes: Object.fromEntries(
      Object.entries(item || {}).filter(([key]) => ![nameKey, 'name', 'description', 'desc', 'summary'].includes(key)),
    ),
  }))
}

function normalizeWorldbuilding(doc?: Partial<Worldbuilding> | null): Partial<Worldbuilding> {
  const sections = (doc?.sections && doc.sections.length > 0)
    ? doc.sections.map(section => ({
        id: section.id || newId('section'),
        name: section.name || '未命名栏目',
        description: section.description || '',
        generation_hint: section.generation_hint || '',
        entries: (section.entries || []).map((entry) => ({
          id: entry.id || newId('entry'),
          name: entry.name || '',
          summary: entry.summary || '',
          details: entry.details || '',
          tags: entry.tags || [],
          attributes: entry.attributes || {},
        })),
      }))
    : DEFAULT_SECTIONS.map((section) => {
        const legacySource =
          section.id === 'power_system' ? mapLegacyItems(doc?.power_system || []) :
          section.id === 'factions' ? mapLegacyItems(doc?.factions || []) :
          section.id === 'geography' ? mapLegacyItems(doc?.geography || []) :
          section.id === 'core_rules' ? mapLegacyItems(doc?.core_rules || [], 'rule_name') :
          mapLegacyItems(doc?.items || [])

        return {
          ...section,
          generation_hint: '',
          entries: legacySource,
        }
      })

  return {
    ...doc,
    overview: doc?.overview || '',
    sections,
  }
}

function createBlankSection(): WorldbuildingSection {
  return {
    id: newId('section'),
    name: '自定义设定',
    description: '',
    generation_hint: '',
    entries: [],
  }
}

function createBlankEntry(): WorldbuildingEntry {
  return {
    id: newId('entry'),
    name: '',
    summary: '',
    details: '',
    tags: [],
    attributes: {},
  }
}

export default function WorldbuildingPage() {
  const { currentNovel, worldbuilding, setWorldbuilding, documentDrafts, patchDocumentDraft } = useAppStore()
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [local, setLocal] = useState<Partial<Worldbuilding>>({})
  const [activeTab, setActiveTab] = useState<string>('overview')
  const docKey = currentNovel ? `worldbuilding:${currentNovel.id}` : null

  useEffect(() => {
    if (!currentNovel) return
    const draft = (docKey ? documentDrafts[docKey] : null) as { local?: Partial<Worldbuilding> } | null
    if (draft?.local) {
      setLocal(normalizeWorldbuilding(draft.local))
      return
    }
    setLocal(normalizeWorldbuilding(worldbuilding))
  }, [currentNovel?.id, worldbuilding])

  useEffect(() => {
    if (!docKey) return
    patchDocumentDraft(docKey, { local })
  }, [docKey, local])

  async function save() {
    if (!currentNovel) return
    setSaving(true)
    try {
      const updated = await api.worldbuilding.update(currentNovel.id, normalizeWorldbuilding(local))
      setWorldbuilding(updated)
      setLocal(normalizeWorldbuilding(updated))
      message.success('世界观设定已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function generateWorldbuilding() {
    if (!currentNovel) return
    setGenerating(true)
    try {
      const data = await api.ai.generateWorldbuilding(currentNovel.id, {
        currentWorldbuilding: normalizeWorldbuilding(local),
      })
      setWorldbuilding(data)
      setLocal(normalizeWorldbuilding(data))
      message.success('世界观补全完成，已自动写入')
    } catch (err: any) {
      message.error(`生成失败：${err?.response?.data?.detail || err.message}`)
    } finally {
      setGenerating(false)
    }
  }

  function updateSection(sectionId: string, patch: Partial<WorldbuildingSection>) {
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).map(section => section.id === sectionId ? { ...section, ...patch } : section),
    }))
  }

  function removeSection(sectionId: string) {
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).filter(section => section.id !== sectionId),
    }))
  }

  function addSection() {
    setLocal(prev => ({
      ...prev,
      sections: [...(prev.sections || []), createBlankSection()],
    }))
  }

  function addEntry(sectionId: string) {
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).map(section => section.id === sectionId
        ? { ...section, entries: [...(section.entries || []), createBlankEntry()] }
        : section),
    }))
    setActiveTab(sectionId)
  }

  function updateEntry(sectionId: string, entryId: string, patch: Partial<WorldbuildingEntry>) {
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).map(section => section.id === sectionId
        ? {
            ...section,
            entries: (section.entries || []).map(entry => entry.id === entryId ? { ...entry, ...patch } : entry),
          }
        : section),
    }))
  }

  function removeEntry(sectionId: string, entryId: string) {
    setLocal(prev => ({
      ...prev,
      sections: (prev.sections || []).map(section => section.id === sectionId
        ? { ...section, entries: (section.entries || []).filter(entry => entry.id !== entryId) }
        : section),
    }))
  }

  if (!currentNovel) return <div className={styles.empty}>请先选择小说</div>

  const sections = local.sections || []
  const tabItems = useMemo(() => [
    {
      key: 'overview',
      label: '世界总述',
      children: (
        <div className={styles.tabPanel}>
          <div className={styles.overviewCard}>
            <div className={styles.cardTitle}>世界总述</div>
            <Input.TextArea
              rows={5}
              value={local.overview || ''}
              onChange={e => setLocal(prev => ({ ...prev, overview: e.target.value }))}
              placeholder="用一段话概括这个世界最核心的运行逻辑、戏剧张力和长期冲突。"
            />
          </div>
        </div>
      ),
    },
    ...sections.map(section => ({
      key: section.id || section.name,
      label: section.name || '未命名栏目',
      children: (
        <div className={styles.tabPanel}>
          <div className={styles.sectionCard}>
            <div className={styles.sectionHeader}>
              <Input
                value={section.name}
                onChange={e => updateSection(section.id || '', { name: e.target.value })}
                placeholder="栏目名称"
                className={styles.sectionName}
              />
              <div className={styles.sectionActions}>
                <Button size="small" icon={<PlusOutlined />} onClick={() => addEntry(section.id || '')}>
                  添加条目
                </Button>
                <Button size="small" danger icon={<DeleteOutlined />} onClick={() => removeSection(section.id || '')}>
                  删除栏目
                </Button>
              </div>
            </div>

            <Input.TextArea
              rows={2}
              value={section.description || ''}
              onChange={e => updateSection(section.id || '', { description: e.target.value })}
              placeholder="这个栏目主要记录什么，后续写作时会在哪些地方反复引用。"
            />

            <Input.TextArea
              rows={2}
              value={section.generation_hint || ''}
              onChange={e => updateSection(section.id || '', { generation_hint: e.target.value })}
              placeholder="给 AI 的补全提示，例如：重点补齐宗门戒律、惩罚机制和外门升迁路径。"
            />

            <div className={styles.entries}>
              {(section.entries || []).length === 0 ? (
                <div className={styles.entryEmpty}>当前栏目还没有条目，可以手动添加，或交给 AI 补全。</div>
              ) : (
                section.entries.map((entry) => (
                  <div key={entry.id} className={styles.entryCard}>
                    <div className={styles.entryHeader}>
                      <Input
                        value={entry.name}
                        onChange={e => updateEntry(section.id || '', entry.id || '', { name: e.target.value })}
                        placeholder="设定名"
                      />
                      <Button
                        type="text"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        onClick={() => removeEntry(section.id || '', entry.id || '')}
                      />
                    </div>
                    <Input.TextArea
                      rows={2}
                      value={entry.summary || ''}
                      onChange={e => updateEntry(section.id || '', entry.id || '', { summary: e.target.value })}
                      placeholder="一句话定义或核心描述"
                    />
                    <Input.TextArea
                      rows={3}
                      value={entry.details || ''}
                      onChange={e => updateEntry(section.id || '', entry.id || '', { details: e.target.value })}
                      placeholder="补充限制、代价、边界、与人物或剧情的关系"
                    />
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      ),
    })),
  ], [local.overview, sections])

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>世界观设定</div>
          <div className={styles.subtitle}>现在改成多标签栏展示，避免所有设定一次性平铺，方便你按模块维护。</div>
        </div>
        <div className={styles.actions}>
          <Button size="small" icon={<PlusOutlined />} onClick={addSection}>
            新增栏目
          </Button>
          <Button size="small" icon={<ThunderboltOutlined />} loading={generating} onClick={generateWorldbuilding}>
            AI补全设定
          </Button>
          <Button type="primary" size="small" icon={<SaveOutlined />} loading={saving} onClick={save}>
            保存
          </Button>
        </div>
      </div>

      <div className={styles.scrollArea}>
        {sections.length === 0 ? (
          <div className={styles.emptyState}>
            <Empty description="还没有设定栏目，先新增一个，或者让 AI 帮你补全。" />
          </div>
        ) : (
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={tabItems}
            className={styles.tabs}
          />
        )}
      </div>
    </div>
  )
}
