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
    setStreamText('')
    streamGenerateWorldbuilding(
      currentNovel.id,
      chunk => setStreamText(prev => prev + chunk),
      async () => {
        setGenerating(false)
        setStreamText('')
        message.success('世界观生成完成，已自动写入')
        const wb = await api.worldbuilding.get(currentNovel.id).catch(() => null)
        if (wb) { setWorldbuilding(wb); setLocal(wb) }
      },
      err => { setGenerating(false); message.error(`生成失败：${err}`) },
    )
  }

  if (!currentNovel) return <div className={styles.empty}>请先选择小说</div>

  const tabs = [
    {
      key: 'realm',
      label: '境界体系',
      children: <RealmTab local={local} setLocal={setLocal} />,
    },
    {
      key: 'currency',
      label: '灵石货币',
      children: <CurrencyTab local={local} setLocal={setLocal} />,
    },
    {
      key: 'factions',
      label: '门派势力',
      children: <ListTab
        title="门派/势力"
        items={local.factions || []}
        onChange={v => setLocal(p => ({ ...p, factions: v }))}
        fields={['name', 'type', 'location', 'desc']}
        labels={['名称', '类型', '所在地', '简介']}
      />,
    },
    {
      key: 'artifacts',
      label: '道具库',
      children: <ListTab
        title="公共道具"
        items={local.artifacts || []}
        onChange={v => setLocal(p => ({ ...p, artifacts: v }))}
        fields={['name', 'grade', 'type', 'desc']}
        labels={['名称', '品级', '类型', '描述']}
      />,
    },
    {
      key: 'techniques',
      label: '功法库',
      children: <ListTab
        title="公共功法"
        items={local.techniques || []}
        onChange={v => setLocal(p => ({ ...p, techniques: v }))}
        fields={['name', 'grade', 'type', 'desc']}
        labels={['名称', '品级', '类型', '描述']}
      />,
    },
    {
      key: 'geography',
      label: '地理',
      children: <ListTab
        title="地理位置"
        items={local.geography || []}
        onChange={v => setLocal(p => ({ ...p, geography: v }))}
        fields={['name', 'type', 'desc']}
        labels={['名称', '类型', '描述']}
      />,
    },
  ]

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <span className={styles.title}>世界观设定</span>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button size="small" icon={<ThunderboltOutlined />} loading={generating} onClick={generateWorldbuilding}>
            AI生成世界观
          </Button>
          <Button type="primary" size="small" icon={<SaveOutlined />} loading={saving} onClick={save}>
            保存
          </Button>
        </div>
      </div>
      {generating && streamText && (
        <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 4, margin: '0 0 8px', fontSize: 12, color: 'var(--text-secondary)', maxHeight: 100, overflow: 'auto' }}>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{streamText}</pre>
        </div>
      )}
      <Tabs items={tabs} className={styles.tabs} size="small" />
    </div>
  )
}

function RealmTab({ local, setLocal }: { local: Partial<Worldbuilding>; setLocal: (fn: (p: Partial<Worldbuilding>) => Partial<Worldbuilding>) => void }) {
  const levels: RealmLevel[] = local.realm_system?.levels || []

  function addLevel() {
    const newLevel: RealmLevel = { name: '', level: levels.length + 1 }
    setLocal(p => ({
      ...p,
      realm_system: { name: p.realm_system?.name || '修仙境界', levels: [...levels, newLevel] },
    }))
  }

  function updateLevel(i: number, field: keyof RealmLevel, value: string | number) {
    const updated = levels.map((l, idx) => idx === i ? { ...l, [field]: value } : l)
    setLocal(p => ({ ...p, realm_system: { ...p.realm_system!, levels: updated } }))
  }

  function removeLevel(i: number) {
    const updated = levels.filter((_, idx) => idx !== i)
    setLocal(p => ({ ...p, realm_system: { ...p.realm_system!, levels: updated } }))
  }

  return (
    <div className={styles.tabContent}>
      <div className={styles.fieldRow}>
        <label>体系名称</label>
        <Input
          value={local.realm_system?.name || ''}
          onChange={e => setLocal(p => ({ ...p, realm_system: { ...p.realm_system!, name: e.target.value } }))}
          placeholder="修仙境界体系"
          style={{ width: 200 }}
        />
      </div>
      <div className={styles.levelList}>
        {levels.map((l, i) => (
          <div key={i} className={styles.levelRow}>
            <span className={styles.levelNum}>{i + 1}</span>
            <Input
              value={l.name}
              onChange={e => updateLevel(i, 'name', e.target.value)}
              placeholder="境界名称"
              style={{ width: 120 }}
            />
            <InputNumber
              value={l.sub_levels}
              onChange={v => updateLevel(i, 'sub_levels', v || 0)}
              placeholder="层数"
              min={0}
              style={{ width: 70 }}
            />
            <Input
              value={l.desc || ''}
              onChange={e => updateLevel(i, 'desc', e.target.value)}
              placeholder="描述"
              style={{ flex: 1 }}
            />
            <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => removeLevel(i)} />
          </div>
        ))}
        <Button size="small" icon={<PlusOutlined />} onClick={addLevel}>添加境界</Button>
      </div>
    </div>
  )
}

function CurrencyTab({ local, setLocal }: { local: Partial<Worldbuilding>; setLocal: (fn: (p: Partial<Worldbuilding>) => Partial<Worldbuilding>) => void }) {
  const currency = local.currency || { name: '灵石', units: [], exchange_rate: [], note: '' }

  function update(field: string, value: unknown) {
    setLocal(p => ({ ...p, currency: { ...currency, [field]: value } }))
  }

  return (
    <div className={styles.tabContent}>
      <div className={styles.fieldRow}>
        <label>货币名称</label>
        <Input value={currency.name} onChange={e => update('name', e.target.value)} style={{ width: 150 }} />
      </div>
      <div className={styles.fieldRow}>
        <label>单位（逗号分隔）</label>
        <Input
          value={(currency.units || []).join('、')}
          onChange={e => update('units', e.target.value.split(/[,，、]/).map(s => s.trim()).filter(Boolean))}
          placeholder="下品灵石、中品灵石、上品灵石、极品灵石"
          style={{ width: 400 }}
        />
      </div>
      <div className={styles.fieldRow}>
        <label>兑换比例（逗号分隔）</label>
        <Input
          value={(currency.exchange_rate || []).join(',')}
          onChange={e => update('exchange_rate', e.target.value.split(',').map(s => Number(s.trim())).filter(n => !isNaN(n)))}
          placeholder="100,100,100"
          style={{ width: 200 }}
        />
      </div>
      <div className={styles.fieldRow}>
        <label>备注</label>
        <Input value={currency.note || ''} onChange={e => update('note', e.target.value)} style={{ width: 400 }} />
      </div>
    </div>
  )
}

function ListTab({ title, items, onChange, fields, labels }: {
  title: string
  items: Record<string, string>[]
  onChange: (v: Record<string, string>[]) => void
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
