import { useState } from 'react'
import { Button, Modal, Form, Input, InputNumber, Select, Tag, message, Popconfirm, Tooltip } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined, UserOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { api, streamGenerateCharacters } from '../api'
import { useAppStore } from '../store'
import type { Character } from '../types'
import styles from './CharactersPage.module.css'

const STATUS_LABELS = { alive: '存活', dead: '已死', unknown: '未知' }
const STATUS_COLORS = { alive: 'green', dead: 'red', unknown: 'default' }

export default function CharactersPage() {
  const { currentNovel, characters, setCharacters } = useAppStore()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Character | null>(null)
  const [generating, setGenerating] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [form] = Form.useForm()

  function openCreate() {
    setEditing(null)
    form.resetFields()
    setOpen(true)
  }

  function openEdit(char: Character) {
    setEditing(char)
    form.setFieldsValue({
      ...char,
      techniques: (char.techniques || []).join('\n'),
    })
    setOpen(true)
  }

  async function handleSubmit(values: Record<string, unknown>) {
    if (!currentNovel) return
    const payload = {
      ...values,
      techniques: values.techniques
        ? String(values.techniques).split('\n').map((s: string) => s.trim()).filter(Boolean)
        : [],
    }
    try {
      if (editing) {
        const updated = await api.characters.update(currentNovel.id, editing.id, payload)
        setCharacters(characters.map(c => c.id === updated.id ? updated : c))
        message.success('已更新')
      } else {
        const created = await api.characters.create(currentNovel.id, payload)
        setCharacters([...characters, created])
        message.success('角色已创建')
      }
      setOpen(false)
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } }
      message.error(err?.response?.data?.detail || '操作失败')
    }
  }

  async function handleDelete(char: Character) {
    if (!currentNovel) return
    await api.characters.delete(currentNovel.id, char.id)
    setCharacters(characters.filter(c => c.id !== char.id))
    message.success('已删除')
  }

  function generateCharacters() {
    if (!currentNovel) return
    setGenerating(true)
    setStreamText('')
    streamGenerateCharacters(
      currentNovel.id,
      chunk => setStreamText(prev => prev + chunk),
      async () => {
        setGenerating(false)
        setStreamText('')
        message.success('角色生成完成，已自动写入角色库')
        // 刷新角色列表
        const chars = await api.characters.list(currentNovel.id)
        setCharacters(chars)
      },
      err => { setGenerating(false); message.error(`生成失败：${err}`) },
    )
  }

  if (!currentNovel) return <div className={styles.empty}>请先选择小说</div>

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <span className={styles.title}>角色库 <span className={styles.count}>{characters.length}</span></span>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button
            size="small" icon={<ThunderboltOutlined />}
            loading={generating}
            onClick={generateCharacters}
          >
            AI生成角色
          </Button>
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={openCreate}>
            新建角色
          </Button>
        </div>
      </div>

      {generating && streamText && (
        <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 4, margin: '0 0 12px', fontSize: 12, color: 'var(--text-secondary)', maxHeight: 120, overflow: 'auto' }}>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{streamText}</pre>
        </div>
      )}

      <div className={styles.grid}>
        {characters.map(char => (
          <CharCard key={char.id} char={char} onEdit={openEdit} onDelete={handleDelete} />
        ))}
        {characters.length === 0 && (
          <div className={styles.emptyGrid}>
            <UserOutlined style={{ fontSize: 32, color: 'var(--text-muted)' }} />
            <p>暂无角色，点击「新建角色」开始创建</p>
          </div>
        )}
      </div>

      <Modal
        title={editing ? '编辑角色' : '新建角色'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        okText="保存"
        cancelText="取消"
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <div className={styles.formRow}>
            <Form.Item name="name" label="姓名" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="gender" label="性别" style={{ width: 80 }}>
              <Select options={[{ value: '男' }, { value: '女' }, { value: '未知' }]} />
            </Form.Item>
            <Form.Item name="age" label="年龄" style={{ width: 80 }}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <div className={styles.formRow}>
            <Form.Item name="race" label="种族" initialValue="人族" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="realm" label="境界" style={{ flex: 1 }}>
              <Input placeholder="如：筑基期" />
            </Form.Item>
            <Form.Item name="realm_level" label="境界等级" initialValue={0} style={{ width: 90 }}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <div className={styles.formRow}>
            <Form.Item name="faction" label="阵营/门派" style={{ flex: 1 }}>
              <Input />
            </Form.Item>
            <Form.Item name="status" label="状态" initialValue="alive" style={{ width: 100 }}>
              <Select options={[
                { value: 'alive', label: '存活' },
                { value: 'dead', label: '已死' },
                { value: 'unknown', label: '未知' },
              ]} />
            </Form.Item>
          </div>
          <Form.Item name="techniques" label="功法（每行一个）">
            <Input.TextArea rows={2} placeholder="御剑术&#10;太清神雷" />
          </Form.Item>
          <Form.Item name="appearance" label="外貌">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="personality" label="性格">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="background" label="背景">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="first_appearance_chapter" label="首次出场章节">
            <InputNumber min={1} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

function CharCard({ char, onEdit, onDelete }: {
  char: Character
  onEdit: (c: Character) => void
  onDelete: (c: Character) => void
}) {
  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.charName}>{char.name}</span>
        <div className={styles.cardActions}>
          <Tooltip title="编辑">
            <Button type="text" size="small" icon={<EditOutlined />} onClick={() => onEdit(char)} />
          </Tooltip>
          <Popconfirm title="确认删除？" onConfirm={() => onDelete(char)} okText="删除" cancelText="取消">
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </div>
      </div>
      <div className={styles.cardMeta}>
        <span>{char.gender || '—'}</span>
        <span>·</span>
        <span>{char.race || '人族'}</span>
        {char.realm && <><span>·</span><span className={styles.realm}>{char.realm}</span></>}
      </div>
      {char.faction && <div className={styles.faction}>{char.faction}</div>}
      {char.personality && (
        <div className={styles.personality}>{char.personality.slice(0, 60)}{char.personality.length > 60 ? '...' : ''}</div>
      )}
      {(char.techniques || []).length > 0 && (
        <div className={styles.tags}>
          {(char.techniques || []).slice(0, 3).map((t, i) => (
            <Tag key={i} className={styles.techTag}>{t}</Tag>
          ))}
          {(char.techniques || []).length > 3 && <Tag>+{(char.techniques || []).length - 3}</Tag>}
        </div>
      )}
      <Tag color={STATUS_COLORS[char.status]} className={styles.statusTag}>
        {STATUS_LABELS[char.status]}
      </Tag>
    </div>
  )
}
