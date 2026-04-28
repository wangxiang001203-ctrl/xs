import { useEffect, useMemo, useState } from 'react'
import { Button, Input, Select, Space, Spin, Tag, message } from 'antd'
import { NodeIndexOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'

import { api } from '../api'
import { useAppStore } from '../store'
import type { EntityRelation, StoryEntity } from '../types'
import styles from './RelationshipNetworkPage.module.css'

const ENTITY_TYPE_LABELS: Record<string, string> = {
  character: '角色',
  location: '地点',
  faction: '势力',
  item: '道具',
  technique: '功法',
  event: '事件',
  custom: '设定',
}

function entityLabel(entity?: StoryEntity | null) {
  if (!entity) return '未知实体'
  return `${ENTITY_TYPE_LABELS[entity.entity_type] || entity.entity_type} · ${entity.name}`
}

export default function RelationshipNetworkPage() {
  const { currentNovel, characters } = useAppStore()
  const [entities, setEntities] = useState<StoryEntity[]>([])
  const [relations, setRelations] = useState<EntityRelation[]>([])
  const [activeEntityId, setActiveEntityId] = useState<string | undefined>()
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [scanning, setScanning] = useState(false)

  useEffect(() => {
    void loadNetwork()
  }, [currentNovel?.id])

  async function loadNetwork(preferredEntityId?: string) {
    if (!currentNovel) return
    setLoading(true)
    try {
      await api.entities.bootstrap(currentNovel.id).catch(() => null)
      const [entityList, relationList] = await Promise.all([
        api.entities.list(currentNovel.id),
        api.entities.relations(currentNovel.id),
      ])
      setEntities(entityList)
      setRelations(relationList)
      const protagonistName = characters.find(item => item.role === '主角')?.name
      const protagonist = protagonistName
        ? entityList.find(item => item.entity_type === 'character' && item.name === protagonistName)
        : null
      setActiveEntityId(preferredEntityId || protagonist?.id || entityList.find(item => item.entity_type === 'character')?.id || entityList[0]?.id)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '关系网加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function scanMentions() {
    if (!currentNovel) return
    setScanning(true)
    try {
      const result = await api.entities.scan(currentNovel.id)
      await loadNetwork(activeEntityId)
      message.success(`已回扫 ${result.scanned_chapters} 章，新增 ${result.created_mentions} 条出现记录`)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '回扫失败')
    } finally {
      setScanning(false)
    }
  }

  const activeEntity = entities.find(item => item.id === activeEntityId) || null
  const entityById = useMemo(() => new Map(entities.map(entity => [entity.id, entity])), [entities])
  const filteredEntities = entities.filter(entity => {
    const keyword = query.trim()
    if (!keyword) return true
    return entity.name.includes(keyword)
      || (ENTITY_TYPE_LABELS[entity.entity_type] || entity.entity_type).includes(keyword)
      || (entity.summary || '').includes(keyword)
  })
  const focusedRelations = relations.filter(relation => (
    !activeEntityId
      ? true
      : relation.source_entity_id === activeEntityId || relation.target_entity_id === activeEntityId
  ))

  if (!currentNovel) return <div className={styles.empty}>请选择作品</div>

  if (loading && !entities.length) {
    return (
      <div className={styles.empty}>
        <Spin size="small" />
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>关系网</div>
          <div className={styles.meta}>
            <span>{entities.length} 个实体</span>
            <span>{relations.length} 条关系</span>
            <Tag color="processing">多对多设定</Tag>
          </div>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => loadNetwork(activeEntityId)} loading={loading}>
            刷新
          </Button>
          <Button icon={<NodeIndexOutlined />} onClick={scanMentions} loading={scanning}>
            全书回扫
          </Button>
        </Space>
      </div>

      <div className={styles.content}>
        <aside className={styles.entityPane}>
          <Input
            value={query}
            onChange={event => setQuery(event.target.value)}
            prefix={<SearchOutlined />}
            placeholder="搜索人物、地点、道具、事件"
          />
          <Select
            value={activeEntityId}
            onChange={setActiveEntityId}
            showSearch
            optionFilterProp="label"
            placeholder="选择中心实体"
            options={entities.map(entity => ({ value: entity.id, label: entityLabel(entity) }))}
          />
          <div className={styles.entityList}>
            {filteredEntities.map(entity => (
              <button
                type="button"
                key={entity.id}
                className={`${styles.entityItem} ${entity.id === activeEntityId ? styles.active : ''}`}
                onClick={() => setActiveEntityId(entity.id)}
              >
                <strong>{entity.name}</strong>
                <span>{ENTITY_TYPE_LABELS[entity.entity_type] || entity.entity_type}</span>
              </button>
            ))}
            {!filteredEntities.length ? <div className={styles.emptyList}>没有匹配实体。</div> : null}
          </div>
        </aside>

        <main className={styles.graphPane}>
          <section className={styles.centerCard}>
            <div className={styles.nodeIcon}><NodeIndexOutlined /></div>
            <div>
              <h2>{activeEntity?.name || '请选择中心实体'}</h2>
              <p>{activeEntity?.summary || activeEntity?.body_md || '这里会以选中的实体为中心，展示它和人物、地点、道具、事件之间的关系。'}</p>
            </div>
          </section>

          <div className={styles.relationRows}>
            {focusedRelations.map(relation => {
              const source = entityById.get(relation.source_entity_id)
              const target = relation.target_entity_id ? entityById.get(relation.target_entity_id) : null
              return (
                <div key={relation.id} className={styles.relationRow}>
                  <span>{source?.name || '未知'}</span>
                  <strong>{relation.relation_type}</strong>
                  <span>{target?.name || relation.target_name || '未入库对象'}</span>
                  <Tag color={relation.status === 'active' ? 'green' : 'default'}>{relation.status}</Tag>
                  {relation.evidence_text ? <p>{relation.evidence_text}</p> : null}
                </div>
              )
            })}
            {!focusedRelations.length ? (
              <div className={styles.emptyRelations}>暂无关系。章节定稿和设定补录后，这里会逐步形成主角为中心的多对多网络。</div>
            ) : null}
          </div>
        </main>
      </div>
    </div>
  )
}
