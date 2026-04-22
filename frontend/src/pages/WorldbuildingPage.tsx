import { useState, useEffect } from 'react'
import { Tabs, Button, Input, InputNumber, message } from 'antd'
import { PlusOutlined, DeleteOutlined, SaveOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { api, streamGenerateWorldbuilding } from '../api'
import { useAppStore } from '../store'
import type { Worldbuilding, RealmLevel } from '../types'
import styles from './WorldbuildingPage.module.css'

export default function WorldbuildingPage() {
  const { currentNovel, worldbuilding, setWorldbuilding } = useAppStore()
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [local, setLocal] = useState<Partial<Worldbuilding>>({})

  useEffect(() => {
    if (worldbuilding) setLocal(worldbuilding)
  }, [worldbuilding])

  async function save() {
    if (!currentNovel) return
    setSaving(true)
    try {
      const updated = await api.worldbuilding.update(currentNovel.id, local)
      setWorldbuilding(updated)
      message.success('世界观设定已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  function generateWorldbuilding() {
    if (!currentNovel) return
    setGenerating(true)
    setStreamText('AI 正在根据大纲推演世界观设定，请稍候...')
    
    fetch('/api/ai/generate/worldbuilding', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ novel_id: currentNovel.id })
    })
      .then(async (res) => {
        if (!res.ok) throw new Error('生成失败或请先生成大纲')
        const data = await res.json()
        setWorldbuilding(data)
        setLocal(data)
        message.success('世界观生成完成，已自动写入')
      })
      .catch(err => {
        message.error(`生成失败：${err.message}`)
      })
      .finally(() => {
        setGenerating(false)
        setStreamText('')
      })
  }

  if (!currentNovel) return <div className={styles.empty}>请先选择小说</div>

  const tabs = [
    {
      key: 'power_system',
      label: '力量/境界体系',
      children: <ListTab
        title="境界/能力"
        items={local.power_system || []}
        onChange={v => setLocal(p => ({ ...p, power_system: v }))}
        fields={['name', 'description']}
        labels={['境界/能力名称', '特征描述']}
      />,
    },
    {
      key: 'factions',
      label: '势力/组织',
      children: <ListTab
        title="门派/势力"
        items={local.factions || []}
        onChange={v => setLocal(p => ({ ...p, factions: v }))}
        fields={['name', 'type', 'description']}
        labels={['名称', '类型', '宗旨与实力']}
      />,
    },
    {
      key: 'geography',
      label: '地理/地点',
      children: <ListTab
        title="地理位置"
        items={local.geography || []}
        onChange={v => setLocal(p => ({ ...p, geography: v }))}
        fields={['name', 'description']}
        labels={['名称', '地貌与特色']}
      />,
    },
    {
      key: 'core_rules',
      label: '核心法则',
      children: <ListTab
        title="世界规则"
        items={local.core_rules || []}
        onChange={v => setLocal(p => ({ ...p, core_rules: v }))}
        fields={['rule_name', 'description']}
        labels={['法则名称', '具体表现与限制']}
      />,
    },
    {
      key: 'items',
      label: '关键物品',
      children: <ListTab
        title="资源/道具"
        items={local.items || []}
        onChange={v => setLocal(p => ({ ...p, items: v }))}
        fields={['name', 'description']}
        labels={['物品名称', '作用与稀有度']}
      />,
    },
  ]

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <span className={styles.title}>世界观设定</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button size="small" icon={<ThunderboltOutlined />} loading={generating} onClick={generateWorldbuilding}>
            AI推演世界观
          </Button>
          <Button type="primary" size="small" icon={<SaveOutlined />} loading={saving} onClick={save}>
            保存
          </Button>
        </div>
      </div>
      <Tabs items={tabs} className={styles.tabs} size="small" />
    </div>
  )
}

function ListTab({ title, items, onChange, fields, labels }: {
  title: string
  items: Record<string, any>[]
  onChange: (v: Record<string, any>[]) => void
  fields: string[]
  labels: string[]
}) {
  function add() {
    onChange([...items, Object.fromEntries(fields.map(f => [f, '']))])
  }

  function update(i: number, field: string, value: string) {
    onChange(items.map((item, idx) => idx === i ? { ...item, [field]: value } : item))
  }

  function remove(i: number) {
    onChange(items.filter((_, idx) => idx !== i))
  }

  return (
    <div className={styles.tabContent}>
      <div className={styles.listHeader}>
        <span>{title}（{items.length}）</span>
        <Button size="small" icon={<PlusOutlined />} onClick={add}>添加</Button>
      </div>
      {items.map((item, i) => (
        <div key={i} className={styles.listRow}>
          {fields.map((f, fi) => (
            <Input
              key={f}
              value={item[f] || ''}
              onChange={e => update(i, f, e.target.value)}
              placeholder={labels[fi]}
              style={{ flex: fi === fields.length - 1 ? 2 : 1 }}
            />
          ))}
          <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => remove(i)} />
        </div>
      ))}
    </div>
  )
}
