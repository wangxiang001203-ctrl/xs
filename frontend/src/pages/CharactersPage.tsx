import { useEffect, useMemo, useState } from 'react'
import { Button, Form, Input, InputNumber, message, Modal, Popconfirm, Select, Slider, Tag, Tooltip } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined, ThunderboltOutlined, UserOutlined } from '@ant-design/icons'
import { api } from '../api'
import { useAppStore } from '../store'
import type { Character, EntityEvent, EntityMention, StoryEntity } from '../types'
import styles from './CharactersPage.module.css'

const STATUS_LABELS: Record<string, string> = { alive: '在场', dead: '死亡', unknown: '未知' }
const STATUS_COLORS: Record<string, string> = { alive: 'green', dead: 'red', unknown: 'default' }
type CharacterDraft = Partial<Character> & { name: string }

const ROLE_OPTIONS = [
  { value: '男主', label: '男主' },
  { value: '女主', label: '女主' },
  { value: '男配', label: '男配' },
  { value: '女配', label: '女配' },
  { value: '反派', label: '反派' },
  { value: '导师', label: '导师' },
  { value: '伙伴', label: '伙伴' },
  { value: '亲族', label: '亲族' },
  { value: '势力人物', label: '势力人物' },
  { value: '路人', label: '路人' },
  { value: '群像角色', label: '群像角色' },
  { value: '未知', label: '未知' },
]

const EVENT_TYPES = [
  { value: 'appear', label: '首次出现' },
  { value: 'upgrade', label: '能力变化' },
  { value: 'transfer', label: '归属变化' },
  { value: 'location_change', label: '位置变化' },
  { value: 'status_change', label: '状态变化' },
  { value: 'manual_fix', label: '补录修正' },
]

function characterProfileFromFields(char?: Partial<Character> | null) {
  if (char?.profile_md?.trim()) return char.profile_md
  const parts = [
    char?.motivation ? `## 核心动机\n${char.motivation}` : '',
    char?.background ? `## 背景\n${char.background}` : '',
    char?.personality ? `## 性格与说话方式\n${char.personality}` : '',
    char?.golden_finger ? `## 特殊能力\n${char.golden_finger}` : '',
    char?.appearance ? `## 外貌辨识\n${char.appearance}` : '',
  ].filter(Boolean)
  return parts.join('\n\n')
}

function parseLines(value?: string) {
  return (value || '').split('\n').map(item => item.trim()).filter(Boolean)
}

function profileSnippet(char: Partial<Character>) {
  const source = characterProfileFromFields(char)
  if (!source.trim()) return '还没有角色档案。'
  return source.replace(/#+\s*/g, '').replace(/\s+/g, ' ').slice(0, 96)
}

function eventTypeLabel(value?: string) {
  return EVENT_TYPES.find(item => item.value === value)?.label || value || '变化'
}

function statePreview(state?: Record<string, any>) {
  const entries = Object.entries(state || {}).filter(([, value]) => value !== undefined && value !== null && String(value).trim())
  if (!entries.length) return <span className={styles.traceMuted}>暂无当前状态变化。</span>
  return entries.map(([key, value]) => (
    <span key={key} className={styles.statePill}>{key}：{String(value)}</span>
  ))
}

export default function CharactersPage() {
  const { currentNovel, characters, setCharacters } = useAppStore()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Character | null>(null)
  const [generating, setGenerating] = useState(false)
  const [characterDrafts, setCharacterDrafts] = useState<CharacterDraft[]>([])
  const [applyingDraftName, setApplyingDraftName] = useState<string | null>(null)
  const [linkedEntity, setLinkedEntity] = useState<StoryEntity | null>(null)
  const [mentions, setMentions] = useState<EntityMention[]>([])
  const [events, setEvents] = useState<EntityEvent[]>([])
  const [traceLoading, setTraceLoading] = useState(false)
  const [eventOpen, setEventOpen] = useState(false)
  const [form] = Form.useForm()
  const [eventForm] = Form.useForm()

  const sortedCharacters = useMemo(
    () => [...characters].sort((a, b) => (b.importance || 3) - (a.importance || 3)),
    [characters],
  )

  function openCreate() {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({
      role: '未知',
      status: 'alive',
      importance: 3,
      race: '',
      profile_md: '',
    })
    setOpen(true)
  }

  function openEdit(char: Character) {
    setEditing(char)
    form.setFieldsValue({
      ...char,
      aliases_text: (char.aliases || []).join('\n'),
      profile_md: characterProfileFromFields(char),
    })
    setOpen(true)
  }

  function closeEditor() {
    setOpen(false)
    setEditing(null)
    setLinkedEntity(null)
    setMentions([])
    setEvents([])
    form.resetFields()
  }

  function closeCharacterDrafts() {
    setCharacterDrafts([])
    setApplyingDraftName(null)
  }

  function closeEventEditor() {
    setEventOpen(false)
    eventForm.resetFields()
  }

  useEffect(() => {
    if (!open || !editing || !currentNovel) {
      setLinkedEntity(null)
      setMentions([])
      setEvents([])
      return
    }
    void loadCharacterTrace(editing)
  }, [open, editing?.id, currentNovel?.id])

  async function loadCharacterTrace(char: Character) {
    if (!currentNovel) return
    setTraceLoading(true)
    try {
      await api.entities.bootstrap(currentNovel.id).catch(() => null)
      const list = await api.entities.list(currentNovel.id, { entityType: 'character', q: char.name })
      const entity = list.find(item => item.name === char.name) || list.find(item => (item.aliases || []).includes(char.name)) || null
      setLinkedEntity(entity)
      if (!entity) {
        setMentions([])
        setEvents([])
        return
      }
      const [nextMentions, nextEvents] = await Promise.all([
        api.entities.mentions(currentNovel.id, entity.id).catch(() => []),
        api.entities.events(currentNovel.id, entity.id).catch(() => []),
      ])
      setMentions(nextMentions)
      setEvents(nextEvents)
    } catch {
      setLinkedEntity(null)
      setMentions([])
      setEvents([])
    } finally {
      setTraceLoading(false)
    }
  }

  async function handleSubmit(values: Record<string, any>) {
    if (!currentNovel) return
    const payload = {
      name: values.name,
      aliases: parseLines(values.aliases_text),
      role: values.role || '未知',
      importance: values.importance || 3,
      gender: values.gender || undefined,
      status: values.status || 'alive',
      race: values.race || undefined,
      realm: values.realm || undefined,
      faction: values.faction || undefined,
      first_appearance_chapter: values.first_appearance_chapter || undefined,
      motivation: values.motivation || undefined,
      profile_md: values.profile_md || '',
    }

    try {
      if (editing) {
        const updated = await api.characters.update(currentNovel.id, editing.id, payload)
        setCharacters(characters.map(char => char.id === updated.id ? updated : char))
        message.success('角色档案已更新')
      } else {
        const created = await api.characters.create(currentNovel.id, payload)
        setCharacters([...characters, created])
        message.success('角色已创建')
      }
      closeEditor()
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err?.response?.data?.detail || '操作失败')
    }
  }

  async function handleDelete(char: Character) {
    if (!currentNovel) return
    const result = await api.characters.delete(currentNovel.id, char.id)
    if (result.archived && result.character) {
      setCharacters(characters.map(item => item.id === result.character?.id ? result.character : item))
      message.warning('该角色已有正文/事件/关系记录，已改为停用保留，未硬删除')
      return
    }
    setCharacters(characters.filter(item => item.id !== char.id))
    message.success('已删除')
  }

  async function createCharacterEvent(values: Record<string, any>) {
    if (!currentNovel || !editing || !linkedEntity) return
    const field = String(values.field_name || '').trim()
    const fromValue = String(values.from_value || '').trim()
    const toValue = String(values.to_value || '').trim()
    if (!field || !toValue) {
      message.warning('请填写变化字段和变化后状态')
      return
    }
    try {
      await api.entities.createEvent(currentNovel.id, linkedEntity.id, {
        event_type: values.event_type || 'manual_fix',
        chapter_number: values.chapter_number || undefined,
        title: values.title || `${field}：${fromValue || '未记录'} -> ${toValue}`,
        from_state: fromValue ? { [field]: fromValue } : {},
        to_state: { [field]: toValue },
        source: 'manual',
        reason: values.reason,
        evidence_text: values.evidence_text,
      })
      const updated = await api.entities.recompute(currentNovel.id, linkedEntity.id)
      setLinkedEntity(updated)
      await loadCharacterTrace(editing)
      closeEventEditor()
      message.success('角色变化已补记')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '补记失败')
    }
  }

  function generateCharacters() {
    if (!currentNovel) return
    setGenerating(true)
    api.ai.generateCharactersFromOutline(currentNovel.id, { dryRun: true })
      .then((drafts) => {
        const validDrafts = (drafts || [])
          .filter((item): item is CharacterDraft => Boolean(item?.name?.trim()))
          .filter(item => !characters.some(char => char.name === item.name))
        if (!validDrafts.length) {
          message.info('AI 没有找到新的可入库角色，可能已经存在。')
          return
        }
        setCharacterDrafts(validDrafts)
        message.success('AI 已生成角色提案，请确认后入库')
      })
      .catch((err: any) => {
        message.error(err?.response?.data?.detail || '生成失败或请先生成大纲')
      })
      .finally(() => {
        setGenerating(false)
      })
  }

  async function applyCharacterDraft(index: number) {
    if (!currentNovel) return
    const draft = characterDrafts[index]
    if (!draft?.name) return
    if (characters.some(char => char.name === draft.name)) {
      message.info('这个角色已经在库里了')
      setCharacterDrafts(prev => prev.filter((_, itemIndex) => itemIndex !== index))
      return
    }
    setApplyingDraftName(draft.name)
    try {
      await api.characters.create(currentNovel.id, {
        name: draft.name,
        aliases: draft.aliases || [],
        role: draft.role || '未知',
        importance: draft.importance || 3,
        gender: draft.gender || undefined,
        status: draft.status || 'alive',
        race: draft.race || undefined,
        realm: draft.realm || undefined,
        faction: draft.faction || undefined,
        appearance: draft.appearance || undefined,
        personality: draft.personality || undefined,
        background: draft.background || undefined,
        golden_finger: draft.golden_finger || undefined,
        motivation: draft.motivation || undefined,
        profile_md: characterProfileFromFields(draft),
      })
      const latest = await api.characters.list(currentNovel.id)
      setCharacters(latest)
      setCharacterDrafts(prev => prev.filter((_, itemIndex) => itemIndex !== index))
      message.success(`「${draft.name}」已入库`)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '角色入库失败')
    } finally {
      setApplyingDraftName(null)
    }
  }

  if (!currentNovel) return <div className={styles.empty}>请先选择小说</div>

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>角色档案 <span className={styles.count}>{characters.length}</span></div>
          <div className={styles.subtitle}>保留角色定位、重要度和状态，正文档案自由编辑；后续人物星图会基于角色与关系数据生成。</div>
        </div>
        <div className={styles.headerActions}>
          <Button size="small" icon={<ThunderboltOutlined />} loading={generating} onClick={generateCharacters}>
            AI 从大纲提取
          </Button>
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={openCreate}>
            新建角色
          </Button>
        </div>
      </div>

      <div className={styles.grid}>
        {sortedCharacters.map(char => (
          <CharCard key={char.id} char={char} onEdit={openEdit} onDelete={handleDelete} />
        ))}
        {sortedCharacters.length === 0 && (
          <div className={styles.emptyGrid}>
            <UserOutlined style={{ fontSize: 34, color: 'var(--text-muted)' }} />
            <p>暂无角色。可以手动新建，也可以先让 AI 从已确认大纲里提取。</p>
          </div>
        )}
      </div>

      <Modal
        title={editing ? '编辑角色档案' : '新建角色档案'}
        open={open}
        onCancel={closeEditor}
        footer={[
          <Button key="cancel" onClick={closeEditor}>
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={() => form.submit()}>
            保存
          </Button>,
        ]}
        width={820}
        destroyOnHidden
        forceRender
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <div className={styles.formGrid}>
            <Form.Item name="name" label="角色名" rules={[{ required: true, message: '请输入角色名' }]}>
              <Input placeholder="例如：林辰" />
            </Form.Item>
            <Form.Item name="role" label="角色定位">
              <Select options={ROLE_OPTIONS} />
            </Form.Item>
            <Form.Item name="importance" label="重要度">
              <Slider min={1} max={5} marks={{ 1: '路人', 3: '重要', 5: '核心' }} />
            </Form.Item>
          </div>

          <div className={styles.formGrid}>
            <Form.Item name="gender" label="性别/呈现">
              <Input placeholder="男、女、未知、无性别、机械体等" />
            </Form.Item>
            <Form.Item name="status" label="当前状态">
              <Select options={[
                { value: 'alive', label: '在场' },
                { value: 'dead', label: '死亡' },
                { value: 'unknown', label: '未知' },
              ]} />
            </Form.Item>
            <Form.Item name="first_appearance_chapter" label="首次出场">
              <InputNumber min={1} placeholder="章节号" style={{ width: '100%' }} />
            </Form.Item>
          </div>

          <div className={styles.formGrid}>
            <Form.Item name="race" label="种族/身份">
              <Input placeholder="人族、妖族、AI、异能者、普通人等" />
            </Form.Item>
            <Form.Item name="realm" label="能力/等级">
              <Input placeholder="筑基期、S级、普通人、无能力等" />
            </Form.Item>
            <Form.Item name="faction" label="所属组织">
              <Input placeholder="宗门、公司、家族、阵营、国家等" />
            </Form.Item>
          </div>

          <Form.Item name="aliases_text" label="别名/称号">
            <Input.TextArea rows={2} placeholder="每行一个，例如：青衣剑客、少宗主" />
          </Form.Item>

          <Form.Item name="motivation" label="一句话动机">
            <Input placeholder="这个角色当前最想要什么，或者最怕失去什么" />
          </Form.Item>

          <Form.Item name="profile_md" label="角色档案正文">
            <Input.TextArea
              rows={12}
              placeholder={'可以自由写：\n## 核心设定\n...\n\n## 背景\n...\n\n## 关系与秘密\n...\n\n## 当前状态变化\n...'}
              className={styles.profileEditor}
            />
          </Form.Item>
        </Form>

        {editing ? (
          <div className={styles.tracePanel}>
            <div className={styles.traceHeader}>
              <div>
                <strong>连续性记录</strong>
                <span>出现章节、状态变化和后续人物星图会从这里读取；你仍然只需要在角色页维护。</span>
              </div>
              <Button
                size="small"
                type="primary"
                disabled={!linkedEntity}
                loading={traceLoading}
                onClick={() => setEventOpen(true)}
              >
                补记变化
              </Button>
            </div>
            <div className={styles.traceState}>
              {statePreview(linkedEntity?.current_state)}
            </div>
            <div className={styles.traceGrid}>
              <div>
                <div className={styles.traceTitle}>出现章节</div>
                <div className={styles.traceList}>
                  {mentions.slice(0, 6).map(item => (
                    <div key={item.id} className={styles.traceItem}>
                      <strong>第{item.chapter_number || '?'}章</strong>
                      <span>{item.evidence_text || item.mention_text}</span>
                    </div>
                  ))}
                  {!mentions.length ? <span className={styles.traceMuted}>暂无出现记录。章节定稿后会自动扫描，也可以之后做全书回扫。</span> : null}
                </div>
              </div>
              <div>
                <div className={styles.traceTitle}>变化历史</div>
                <div className={styles.traceList}>
                  {events.slice(0, 6).map(item => (
                    <div key={item.id} className={styles.traceItem}>
                      <strong>{item.chapter_number ? `第${item.chapter_number}章` : '全局'} · {eventTypeLabel(item.event_type)}</strong>
                      <span>{item.title || item.reason || item.evidence_text || '状态变化'}</span>
                    </div>
                  ))}
                  {!events.length ? <span className={styles.traceMuted}>暂无变化事件。比如突破、受伤、换阵营、关系反转都可以补记。</span> : null}
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal
        title="AI 角色提案"
        open={characterDrafts.length > 0}
        onCancel={closeCharacterDrafts}
        width={860}
        destroyOnHidden
        footer={[
          <Button key="cancel" onClick={closeCharacterDrafts}>
            先不入库
          </Button>,
        ]}
      >
        <div className={styles.proposalIntro}>
          AI 只生成提案，不会直接改角色库。每张角色卡都需要单独确认，避免一次性误改整组角色。
        </div>
        <div className={styles.proposalList}>
          {characterDrafts.map((draft, index) => (
            <div key={`${draft.name}-${index}`} className={styles.proposalCard}>
              <div className={styles.proposalHeader}>
                <strong>{draft.name}</strong>
                <div className={styles.proposalActions}>
                  <div className={styles.badges}>
                    <Tag className={styles.roleTag}>{draft.role || '未知'}</Tag>
                    <Tag>重要度 {draft.importance || 3}</Tag>
                  </div>
                  <Button
                    size="small"
                    type="text"
                    danger
                    onClick={() => setCharacterDrafts(characterDrafts.filter((_, itemIndex) => itemIndex !== index))}
                  >
                    移除
                  </Button>
                  <Button
                    size="small"
                    type="primary"
                    loading={applyingDraftName === draft.name}
                    onClick={() => applyCharacterDraft(index)}
                  >
                    确认这个角色
                  </Button>
                </div>
              </div>
              {(draft.aliases || []).length ? (
                <div className={styles.cardMeta}>别名：{(draft.aliases || []).join(' / ')}</div>
              ) : null}
              <div className={styles.cardMeta}>
                {[draft.gender, draft.race, draft.realm, draft.faction].filter(Boolean).join(' · ') || '基础信息待补充'}
              </div>
              {draft.motivation ? <div className={styles.motivation}>{draft.motivation}</div> : null}
              <p className={styles.profileSnippet}>{profileSnippet(draft)}</p>
            </div>
          ))}
        </div>
      </Modal>

      <Modal
        title={`补记「${editing?.name || ''}」变化`}
        open={eventOpen}
        onCancel={closeEventEditor}
        onOk={() => eventForm.submit()}
        okText="确认补记"
        cancelText="取消"
        width={720}
        destroyOnHidden
        forceRender
      >
        <div className={styles.proposalIntro}>
          这里处理 AI 漏记或后期回溯修正。不会删除旧事实，只会追加一个从第几章开始生效的状态节点。
        </div>
        <Form form={eventForm} layout="vertical" onFinish={createCharacterEvent} initialValues={{ event_type: 'manual_fix' }}>
          <div className={styles.formGrid}>
            <Form.Item name="event_type" label="变化类型">
              <Select options={EVENT_TYPES} />
            </Form.Item>
            <Form.Item name="chapter_number" label="生效章节">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <div className={styles.formGrid}>
            <Form.Item name="field_name" label="变化字段" rules={[{ required: true, message: '比如：境界、身份、位置、所属势力' }]}>
              <Input placeholder="例如：境界" />
            </Form.Item>
            <Form.Item name="from_value" label="变化前">
              <Input placeholder="例如：炼气三层" />
            </Form.Item>
            <Form.Item name="to_value" label="变化后" rules={[{ required: true, message: '请输入变化后状态' }]}>
              <Input placeholder="例如：炼气四层" />
            </Form.Item>
          </div>
          <Form.Item name="title" label="事件标题">
            <Input placeholder="例如：林辰吞服青元丹后突破" />
          </Form.Item>
          <Form.Item name="reason" label="补记原因">
            <Input.TextArea rows={2} placeholder="例如：第20章已突破，但角色状态漏记" />
          </Form.Item>
          <Form.Item name="evidence_text" label="证据片段">
            <Input.TextArea rows={3} placeholder="粘贴正文里能证明变化的片段，后续冲突扫描会优先参考它。" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

function CharCard({ char, onEdit, onDelete }: {
  char: Character
  onEdit: (character: Character) => void
  onDelete: (character: Character) => void
}) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <div>
          <span className={styles.charName}>{char.name}</span>
          {(char.aliases || []).length > 0 ? (
            <span className={styles.alias}> / {(char.aliases || []).slice(0, 2).join(' / ')}</span>
          ) : null}
        </div>
        <div className={styles.cardActions}>
          <Tooltip title="编辑档案">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(char)} />
          </Tooltip>
          <Popconfirm
            title="确认移除？"
            description="如果角色已经出现在正文、事件或关系网里，系统会停用保留，不会硬删除。"
            onConfirm={() => onDelete(char)}
            okText="确认"
            cancelText="取消"
          >
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </div>
      </div>

      <div className={styles.badges}>
        <Tag className={styles.roleTag}>{char.role || '未知'}</Tag>
        <Tag color={STATUS_COLORS[char.status]}>{STATUS_LABELS[char.status] || char.status}</Tag>
        <Tag>重要度 {char.importance || 3}</Tag>
      </div>

      <div className={styles.cardMeta}>
        {[char.gender, char.race, char.realm, char.faction].filter(Boolean).join(' · ') || '基础信息待补充'}
      </div>

      {char.motivation ? <div className={styles.motivation}>{char.motivation}</div> : null}
      <p className={styles.profileSnippet}>{profileSnippet(char)}</p>
    </div>
  )
}
