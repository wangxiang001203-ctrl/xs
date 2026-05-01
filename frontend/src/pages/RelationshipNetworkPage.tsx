import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from 'react'
import { Button, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Spin, Tag, Tooltip, message } from 'antd'
import {
  AimOutlined,
  DeleteOutlined,
  NodeIndexOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons'

import { api } from '../api'
import { useAppStore } from '../store'
import type { EntityEvent, EntityGraphData, EntityMention, EntityRelation, StoryEntity } from '../types'
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

const RELATION_STATUS_LABELS: Record<string, string> = {
  active: '生效',
  inactive: '失效',
  ended: '已结束',
  disputed: '待核',
}

const ENTITY_TYPE_COLORS: Record<string, string> = {
  character: '#f2b45b',
  location: '#61c7c2',
  faction: '#ef7564',
  item: '#8fcf62',
  technique: '#b68cff',
  event: '#f6e6a6',
  custom: '#d2b48c',
  external: '#c9d0d6',
}

type StarNode = {
  id: string
  entityId?: string
  name: string
  entityType: string
  summary?: string | null
  status?: string
  degree: number
  active: boolean
  direct: boolean
  external: boolean
  x: number
  y: number
  z: number
  radius: number
  color: string
}

type StarEdge = {
  id: string
  sourceId: string
  targetId: string
  relationType: string
  status: string
  direct: boolean
}

type ProjectedNode = StarNode & {
  sx: number
  sy: number
  depth: number
  scale: number
  drawRadius: number
}

function hashString(input: string) {
  let hash = 2166136261
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function truncateLabel(text: string, max = 12) {
  return text.length > max ? `${text.slice(0, max - 1)}...` : text
}

function formatStateValue(value: unknown) {
  if (Array.isArray(value)) return value.join('、')
  if (value && typeof value === 'object') return JSON.stringify(value)
  return String(value ?? '')
}

function entityLabel(entity?: StoryEntity | null) {
  if (!entity) return '未知实体'
  return `${ENTITY_TYPE_LABELS[entity.entity_type] || entity.entity_type} · ${entity.name}`
}

function graphNodeToEntity(novelId: string, node: EntityGraphData['nodes'][number]): StoryEntity {
  const now = new Date().toISOString()
  return {
    id: node.id,
    novel_id: novelId,
    entity_type: node.entity_type,
    name: node.name,
    aliases: [],
    summary: node.summary || undefined,
    body_md: undefined,
    tags: [],
    current_state: node.current_state || {},
    status: node.status,
    graph_role: node.graph_role,
    importance: node.importance,
    graph_layer: node.graph_layer,
    graph_position: node.graph_position || {},
    first_appearance_chapter: null,
    created_at: now,
    updated_at: now,
  }
}

function graphEdgeToRelation(novelId: string, edge: EntityGraphData['edges'][number]): EntityRelation {
  const now = new Date().toISOString()
  return {
    id: edge.id,
    novel_id: novelId,
    source_entity_id: edge.source_entity_id,
    target_entity_id: edge.target_entity_id,
    target_name: edge.target_name,
    relation_type: edge.relation_type,
    relation_strength: edge.relation_strength,
    is_bidirectional: edge.is_bidirectional,
    confidence: edge.confidence,
    start_chapter: null,
    end_chapter: null,
    properties: edge.properties || {},
    evidence_text: edge.evidence_text,
    status: edge.status,
    created_at: now,
    updated_at: now,
  }
}

function isSystemAnchorRelation(relation: EntityRelation) {
  return relation.relation_type === 'story_anchor'
    && relation.properties?.system === true
    && relation.properties?.graph_usage === 'protagonist_hub'
}

function RelationshipStarMap({
  nodes,
  edges,
  activeEntityId,
  onSelectEntity,
}: {
  nodes: StarNode[]
  edges: StarEdge[]
  activeEntityId?: string
  onSelectEntity: (entityId: string) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const projectedRef = useRef<ProjectedNode[]>([])
  const rotationRef = useRef({ x: -0.3, y: 0.55 })
  const zoomRef = useRef(1)
  const dragRef = useRef<{ x: number; y: number; moved: number } | null>(null)

  const activeNode = useMemo(
    () => nodes.find(node => node.entityId === activeEntityId || node.id === activeEntityId),
    [activeEntityId, nodes],
  )

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const width = Math.max(1, rect.width)
    const height = Math.max(1, rect.height)
    const dpr = window.devicePixelRatio || 1
    const nextWidth = Math.floor(width * dpr)
    const nextHeight = Math.floor(height * dpr)
    if (canvas.width !== nextWidth || canvas.height !== nextHeight) {
      canvas.width = nextWidth
      canvas.height = nextHeight
    }

    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, width, height)

    ctx.fillStyle = '#12100e'
    ctx.fillRect(0, 0, width, height)

    const fieldSeed = hashString(`${nodes.length}:${edges.length}:${activeEntityId || 'none'}`)
    ctx.save()
    for (let i = 0; i < 90; i += 1) {
      const seed = hashString(`${fieldSeed}:${i}`)
      const x = (seed % 1000) / 1000 * width
      const y = ((seed >> 10) % 1000) / 1000 * height
      const alpha = 0.12 + ((seed >> 20) % 100) / 1000
      ctx.fillStyle = `rgba(245, 232, 198, ${alpha})`
      ctx.fillRect(x, y, seed % 7 === 0 ? 1.6 : 1, seed % 7 === 0 ? 1.6 : 1)
    }
    ctx.restore()

    const rotation = rotationRef.current
    const zoom = zoomRef.current
    const sinX = Math.sin(rotation.x)
    const cosX = Math.cos(rotation.x)
    const sinY = Math.sin(rotation.y)
    const cosY = Math.cos(rotation.y)
    const perspective = 620
    const projected = nodes.map(node => {
      const y1 = node.y * cosX - node.z * sinX
      const z1 = node.y * sinX + node.z * cosX
      const x2 = node.x * cosY + z1 * sinY
      const z2 = -node.x * sinY + z1 * cosY
      const scale = clamp(perspective / (perspective - z2), 0.38, 1.78)
      return {
        ...node,
        sx: width / 2 + x2 * scale * zoom,
        sy: height / 2 + y1 * scale * zoom,
        depth: z2,
        scale,
        drawRadius: clamp(node.radius * scale * zoom, 3.2, node.active ? 18 : 13),
      }
    })
    projectedRef.current = projected

    const byId = new Map(projected.map(node => [node.id, node]))
    const edgeRows = edges
      .map(edge => {
        const source = byId.get(edge.sourceId)
        const target = byId.get(edge.targetId)
        return source && target ? { edge, source, target, depth: (source.depth + target.depth) / 2 } : null
      })
      .filter((item): item is { edge: StarEdge; source: ProjectedNode; target: ProjectedNode; depth: number } => Boolean(item))
      .sort((a, b) => a.depth - b.depth)

    edgeRows.forEach(({ edge, source, target }) => {
      const alpha = edge.direct ? 0.72 : 0.2
      ctx.beginPath()
      ctx.moveTo(source.sx, source.sy)
      ctx.lineTo(target.sx, target.sy)
      ctx.lineWidth = edge.direct ? 1.55 : 0.72
      ctx.strokeStyle = edge.status === 'active'
        ? `rgba(219, 196, 140, ${alpha})`
        : `rgba(159, 165, 168, ${alpha * 0.75})`
      ctx.stroke()
    })

    projected
      .slice()
      .sort((a, b) => a.depth - b.depth)
      .forEach(node => {
        const halo = node.active ? 18 : node.direct ? 12 : 7
        ctx.save()
        ctx.shadowColor = node.color
        ctx.shadowBlur = node.active ? 18 : node.direct ? 10 : 4
        ctx.beginPath()
        ctx.arc(node.sx, node.sy, node.drawRadius + halo * 0.16, 0, Math.PI * 2)
        ctx.fillStyle = node.active ? 'rgba(255, 244, 205, 0.18)' : 'rgba(255, 255, 255, 0.05)'
        ctx.fill()
        ctx.beginPath()
        ctx.arc(node.sx, node.sy, node.drawRadius, 0, Math.PI * 2)
        ctx.fillStyle = node.color
        ctx.fill()
        ctx.lineWidth = node.active ? 2.2 : node.direct ? 1.5 : 1
        ctx.strokeStyle = node.active ? '#fff0b6' : 'rgba(255, 255, 255, 0.64)'
        ctx.stroke()
        ctx.restore()

        if (node.active || node.direct || node.scale > 1.15) {
          ctx.save()
          ctx.font = `${node.active ? 13 : 11}px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
          ctx.textAlign = 'center'
          ctx.textBaseline = 'top'
          const label = truncateLabel(node.name, node.active ? 18 : 10)
          const labelY = node.sy + node.drawRadius + 8
          const textWidth = ctx.measureText(label).width
          ctx.fillStyle = 'rgba(18, 16, 14, 0.72)'
          ctx.fillRect(node.sx - textWidth / 2 - 5, labelY - 2, textWidth + 10, node.active ? 20 : 17)
          ctx.fillStyle = node.active ? '#fff3c9' : 'rgba(245, 239, 224, 0.88)'
          ctx.fillText(label, node.sx, labelY)
          ctx.restore()
        }
      })
  }, [activeEntityId, edges, nodes])

  useEffect(() => {
    draw()
    const canvas = canvasRef.current
    if (!canvas) return undefined
    const observer = new ResizeObserver(() => draw())
    observer.observe(canvas)
    return () => observer.disconnect()
  }, [draw])

  function canvasPoint(event: ReactPointerEvent<HTMLCanvasElement> | ReactWheelEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current
    const rect = canvas?.getBoundingClientRect()
    return {
      x: event.clientX - (rect?.left || 0),
      y: event.clientY - (rect?.top || 0),
    }
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLCanvasElement>) {
    const point = canvasPoint(event)
    dragRef.current = { ...point, moved: 0 }
    event.currentTarget.setPointerCapture(event.pointerId)
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLCanvasElement>) {
    const drag = dragRef.current
    if (!drag) return
    const point = canvasPoint(event)
    const dx = point.x - drag.x
    const dy = point.y - drag.y
    drag.x = point.x
    drag.y = point.y
    drag.moved += Math.abs(dx) + Math.abs(dy)
    rotationRef.current = {
      x: clamp(rotationRef.current.x + dy * 0.006, -1.35, 1.35),
      y: rotationRef.current.y + dx * 0.006,
    }
    draw()
  }

  function handlePointerUp(event: ReactPointerEvent<HTMLCanvasElement>) {
    const drag = dragRef.current
    dragRef.current = null
    event.currentTarget.releasePointerCapture(event.pointerId)
    if (!drag || drag.moved > 7) return
    const point = canvasPoint(event)
    const hit = projectedRef.current
      .filter(node => node.entityId)
      .map(node => ({
        node,
        distance: Math.hypot(node.sx - point.x, node.sy - point.y),
      }))
      .filter(item => item.distance <= item.node.drawRadius + 10)
      .sort((a, b) => a.distance - b.distance)[0]
    if (hit?.node.entityId) onSelectEntity(hit.node.entityId)
  }

  function handleWheel(event: ReactWheelEvent<HTMLCanvasElement>) {
    event.preventDefault()
    zoomRef.current = clamp(zoomRef.current * (event.deltaY > 0 ? 0.92 : 1.08), 0.62, 1.76)
    draw()
  }

  function resetView() {
    rotationRef.current = { x: -0.3, y: 0.55 }
    zoomRef.current = 1
    draw()
  }

  function zoomIn() {
    zoomRef.current = clamp(zoomRef.current * 1.12, 0.62, 1.76)
    draw()
  }

  function zoomOut() {
    zoomRef.current = clamp(zoomRef.current * 0.88, 0.62, 1.76)
    draw()
  }

  if (!nodes.length) {
    return <div className={`${styles.starMapPanel} ${styles.starEmpty}`}>暂无实体</div>
  }

  return (
    <section className={styles.starMapPanel}>
      <div className={styles.starHeader}>
        <div>
          <div className={styles.starTitle}>3D 关系星图</div>
          <div className={styles.starMeta}>
            <span>{activeNode?.name || '未选择中心'}</span>
            <span>{nodes.length} 星点</span>
            <span>{edges.length} 轨道</span>
          </div>
        </div>
        <Space size={6}>
          <Tooltip title="放大">
            <Button size="small" type="text" icon={<ZoomInOutlined />} onClick={zoomIn} />
          </Tooltip>
          <Tooltip title="缩小">
            <Button size="small" type="text" icon={<ZoomOutOutlined />} onClick={zoomOut} />
          </Tooltip>
          <Tooltip title="重置视角">
            <Button size="small" type="text" icon={<AimOutlined />} onClick={resetView} />
          </Tooltip>
        </Space>
      </div>
      <canvas
        ref={canvasRef}
        className={styles.starCanvas}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={() => {
          dragRef.current = null
        }}
        onWheel={handleWheel}
      />
      <div className={styles.starLegend}>
        {Object.entries(ENTITY_TYPE_COLORS).filter(([type]) => type !== 'external').map(([type, color]) => (
          <span key={type}>
            <i style={{ background: color }} />
            {ENTITY_TYPE_LABELS[type] || type}
          </span>
        ))}
      </div>
    </section>
  )
}

export default function RelationshipNetworkPage() {
  const { currentNovel, characters } = useAppStore()
  const [entities, setEntities] = useState<StoryEntity[]>([])
  const [relations, setRelations] = useState<EntityRelation[]>([])
  const [activeEntityId, setActiveEntityId] = useState<string | undefined>()
  const [query, setQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<string>('all')
  const [mentions, setMentions] = useState<EntityMention[]>([])
  const [events, setEvents] = useState<EntityEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [relationOpen, setRelationOpen] = useState(false)
  const [savingRelation, setSavingRelation] = useState(false)
  const [relationForm] = Form.useForm()

  useEffect(() => {
    void loadNetwork()
  }, [currentNovel?.id])

  useEffect(() => {
    void loadEntityDetails(activeEntityId)
  }, [currentNovel?.id, activeEntityId])

  async function loadNetwork(preferredEntityId?: string) {
    if (!currentNovel) return
    setLoading(true)
    try {
      let graphData = await api.entities.graphData(currentNovel.id)
      if (!graphData.nodes.length) {
        await api.entities.bootstrapGraph(currentNovel.id).catch(() => null)
        graphData = await api.entities.graphData(currentNovel.id)
      }
      const entityList = await api.entities.list(currentNovel.id)
      const graphNodeById = new Map(graphData.nodes.map(node => [node.id, node]))
      const mergedEntities = entityList.map(entity => {
        const graphNode = graphNodeById.get(entity.id)
        return graphNode
          ? {
              ...entity,
              graph_role: graphNode.graph_role,
              importance: graphNode.importance,
              graph_layer: graphNode.graph_layer,
              graph_position: graphNode.graph_position || entity.graph_position || {},
            }
          : entity
      })
      const knownEntityIds = new Set(mergedEntities.map(entity => entity.id))
      const graphOnlyEntities = graphData.nodes
        .filter(node => !knownEntityIds.has(node.id))
        .map(node => graphNodeToEntity(currentNovel.id, node))
      const nextEntities = [...mergedEntities, ...graphOnlyEntities]
      const nextRelations = graphData.edges.map(edge => graphEdgeToRelation(currentNovel.id, edge))
      setEntities(nextEntities)
      setRelations(nextRelations)
      const protagonistName = characters.find(item => item.role === '主角')?.name
      const protagonist = protagonistName
        ? nextEntities.find(item => item.entity_type === 'character' && item.name === protagonistName)
        : null
      setActiveEntityId(
        preferredEntityId
        || graphData.center_entity_id
        || protagonist?.id
        || nextEntities.find(item => item.entity_type === 'character')?.id
        || nextEntities[0]?.id,
      )
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '关系网加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function loadEntityDetails(entityId?: string) {
    if (!currentNovel || !entityId) {
      setMentions([])
      setEvents([])
      return
    }
    setDetailLoading(true)
    try {
      const [nextMentions, nextEvents] = await Promise.all([
        api.entities.mentions(currentNovel.id, entityId),
        api.entities.events(currentNovel.id, entityId),
      ])
      setMentions(nextMentions)
      setEvents(nextEvents)
    } catch {
      setMentions([])
      setEvents([])
    } finally {
      setDetailLoading(false)
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

  function openRelationDialog() {
    if (!activeEntityId) {
      message.warning('请先选择中心实体')
      return
    }
    relationForm.resetFields()
    relationForm.setFieldsValue({
      source_entity_id: activeEntityId,
      relation_type: '关联',
      status: 'active',
    })
    setRelationOpen(true)
  }

  function closeRelationDialog() {
    setRelationOpen(false)
    relationForm.resetFields()
  }

  async function createRelation(values: Record<string, any>) {
    if (!currentNovel) return
    const sourceEntityId = values.source_entity_id || activeEntityId
    const targetEntityId = values.target_entity_id || undefined
    const targetName = String(values.target_name || '').trim()
    if (!sourceEntityId) {
      message.warning('请先选择源实体')
      return
    }
    if (!targetEntityId && !targetName) {
      message.warning('请选择目标实体，或填写未入库目标名称')
      return
    }
    setSavingRelation(true)
    try {
      const created = await api.entities.createRelation(currentNovel.id, {
        source_entity_id: sourceEntityId,
        target_entity_id: targetEntityId,
        target_name: targetEntityId ? undefined : targetName,
        relation_type: values.relation_type || '关联',
        start_chapter: values.start_chapter || undefined,
        end_chapter: values.end_chapter || undefined,
        evidence_text: values.evidence_text || undefined,
        status: values.status || 'active',
        properties: {
          description: values.description || undefined,
          source: 'manual_relationship_network',
        },
      })
      setRelations(prev => [created, ...prev])
      setActiveEntityId(sourceEntityId)
      closeRelationDialog()
      message.success('关系已补记')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '关系补记失败')
    } finally {
      setSavingRelation(false)
    }
  }

  async function deleteRelation(relationId: string) {
    if (!currentNovel) return
    const relation = relations.find(item => item.id === relationId)
    if (relation && (relation.id.startsWith('implicit:') || isSystemAnchorRelation(relation))) {
      message.info('主角星图弱连接由系统维护，不需要手动删除')
      return
    }
    try {
      await api.entities.deleteRelation(currentNovel.id, relationId)
      setRelations(prev => prev.filter(item => item.id !== relationId))
      message.success('关系已删除')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除关系失败')
    }
  }

  const activeEntity = entities.find(item => item.id === activeEntityId) || null
  const visibleEntities = useMemo(() => {
    const nonItemNames = new Set(
      entities
        .filter(entity => entity.entity_type !== 'item')
        .map(entity => entity.name),
    )
    return entities.filter(entity => {
      if (entity.entity_type !== 'item') return true
      if (!nonItemNames.has(entity.name)) return true
      return Boolean(entity.summary || entity.body_md || Object.keys(entity.current_state || {}).length)
    })
  }, [entities])
  const entityById = useMemo(() => new Map(visibleEntities.map(entity => [entity.id, entity])), [visibleEntities])
  const entityTypeOptions = useMemo(() => {
    const types = Array.from(new Set(visibleEntities.map(entity => entity.entity_type))).sort()
    return [
      { value: 'all', label: '全部类型' },
      ...types.map(type => ({ value: type, label: ENTITY_TYPE_LABELS[type] || type })),
    ]
  }, [visibleEntities])
  const filteredEntities = visibleEntities.filter(entity => {
    const keyword = query.trim()
    if (typeFilter !== 'all' && entity.entity_type !== typeFilter) return false
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
  const stateEntries = Object.entries(activeEntity?.current_state || {}).filter(([, value]) => value !== undefined && value !== null && String(value).trim())
  const starGraph = useMemo(() => {
    const nodeMap = new Map<string, Omit<StarNode, 'x' | 'y' | 'z' | 'radius' | 'color' | 'active' | 'direct'>>()
    visibleEntities.forEach(entity => {
      nodeMap.set(entity.id, {
        id: entity.id,
        entityId: entity.id,
        name: entity.name,
        entityType: entity.entity_type,
        summary: entity.summary,
        status: entity.status,
        degree: 0,
        external: false,
      })
    })
    relations.forEach(relation => {
      if (!nodeMap.has(relation.source_entity_id)) return
      if (!relation.target_entity_id && relation.target_name?.trim()) {
        const externalId = `external:${relation.id}`
        nodeMap.set(externalId, {
          id: externalId,
          name: relation.target_name.trim(),
          entityType: 'external',
          summary: '未入库目标',
          status: relation.status,
          degree: 0,
          external: true,
        })
      }
    })

    const rawEdges: StarEdge[] = []
    const degree = new Map<string, number>()
    relations.forEach(relation => {
      const sourceId = relation.source_entity_id
      const targetId = relation.target_entity_id || (relation.target_name?.trim() ? `external:${relation.id}` : '')
      if (!targetId || !nodeMap.has(sourceId) || !nodeMap.has(targetId)) return
      rawEdges.push({
        id: relation.id,
        sourceId,
        targetId,
        relationType: relation.relation_type,
        status: relation.status,
        direct: Boolean(activeEntityId && (sourceId === activeEntityId || targetId === activeEntityId)),
      })
      degree.set(sourceId, (degree.get(sourceId) || 0) + 1)
      degree.set(targetId, (degree.get(targetId) || 0) + 1)
    })

    const directIds = new Set<string>()
    rawEdges.forEach(edge => {
      if (!edge.direct) return
      if (edge.sourceId !== activeEntityId) directIds.add(edge.sourceId)
      if (edge.targetId !== activeEntityId) directIds.add(edge.targetId)
    })

    const baseNodes = Array.from(nodeMap.values()).map(node => ({
      ...node,
      degree: degree.get(node.id) || 0,
    }))
    const activeNodes = baseNodes.filter(node => node.entityId === activeEntityId)
    const directNodes = baseNodes.filter(node => node.entityId !== activeEntityId && directIds.has(node.id))
    const outerNodes = baseNodes.filter(node => node.entityId !== activeEntityId && !directIds.has(node.id))
    const positioned: StarNode[] = []

    activeNodes.forEach(node => {
      positioned.push({
        ...node,
        active: true,
        direct: false,
        x: 0,
        y: 0,
        z: 0,
        radius: 9.5,
        color: '#fff0b6',
      })
    })

    directNodes.forEach((node, index) => {
      const count = Math.max(1, directNodes.length)
      const seed = hashString(node.id)
      const angle = (Math.PI * 2 * index) / count + (seed % 100) / 500
      const ring = 168 + (seed % 42)
      positioned.push({
        ...node,
        active: false,
        direct: true,
        x: Math.cos(angle) * ring,
        y: Math.sin(angle) * ring * 0.76,
        z: ((index % 5) - 2) * 44,
        radius: 6.7 + Math.min(3, node.degree) * 0.45,
        color: ENTITY_TYPE_COLORS[node.entityType] || ENTITY_TYPE_COLORS.custom,
      })
    })

    outerNodes.forEach((node, index) => {
      const count = Math.max(1, outerNodes.length)
      const seed = hashString(node.id)
      const golden = Math.PI * (3 - Math.sqrt(5))
      const phi = Math.acos(1 - (2 * (index + 0.5)) / count)
      const theta = golden * index + (seed % 360) * Math.PI / 180
      const radius = 285 + (seed % 135)
      positioned.push({
        ...node,
        active: false,
        direct: false,
        x: Math.cos(theta) * Math.sin(phi) * radius,
        y: Math.cos(phi) * radius * 0.72,
        z: Math.sin(theta) * Math.sin(phi) * radius,
        radius: node.external ? 4.6 : 4.8 + Math.min(3, node.degree) * 0.36,
        color: ENTITY_TYPE_COLORS[node.entityType] || ENTITY_TYPE_COLORS.custom,
      })
    })

    if (!activeNodes.length && positioned.length) {
      positioned[0] = {
        ...positioned[0],
        active: true,
        x: 0,
        y: 0,
        z: 0,
        radius: 9.5,
        color: '#fff0b6',
      }
    }

    return { nodes: positioned, edges: rawEdges }
  }, [activeEntityId, relations, visibleEntities])

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
            <span>{visibleEntities.length} 个实体{visibleEntities.length !== entities.length ? ` · 已隐藏 ${entities.length - visibleEntities.length} 个重复索引` : ''}</span>
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
          <Button type="primary" icon={<PlusOutlined />} onClick={openRelationDialog} disabled={!activeEntityId}>
            补关系
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
            value={typeFilter}
            onChange={setTypeFilter}
            options={entityTypeOptions}
          />
          <Select
            value={activeEntityId}
            onChange={setActiveEntityId}
            showSearch
            optionFilterProp="label"
            placeholder="选择中心实体"
            options={visibleEntities.map(entity => ({ value: entity.id, label: entityLabel(entity) }))}
          />
          <div className={styles.entityList}>
            {filteredEntities.map(entity => (
              <button
                type="button"
                key={entity.id}
                className={`${styles.entityItem} ${entity.id === activeEntityId ? styles.active : ''}`}
                onClick={() => setActiveEntityId(entity.id)}
              >
                <div>
                  <strong>{entity.name}</strong>
                  <small>{entity.summary || entity.body_md || '暂无摘要'}</small>
                </div>
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
              <div className={styles.centerTags}>
                {activeEntity ? <Tag>{ENTITY_TYPE_LABELS[activeEntity.entity_type] || activeEntity.entity_type}</Tag> : null}
                {activeEntity?.first_appearance_chapter ? <Tag>首次出现：第{activeEntity.first_appearance_chapter}章</Tag> : null}
                {activeEntity ? <Tag color={activeEntity.status === 'active' ? 'green' : 'default'}>{activeEntity.status}</Tag> : null}
              </div>
            </div>
          </section>

          <RelationshipStarMap
            nodes={starGraph.nodes}
            edges={starGraph.edges}
            activeEntityId={activeEntityId}
            onSelectEntity={setActiveEntityId}
          />

          <div className={styles.detailGrid}>
            <section className={styles.relationRows}>
              <div className={styles.panelTitle}>直接关系</div>
              {focusedRelations.map(relation => {
                const source = entityById.get(relation.source_entity_id)
                const target = relation.target_entity_id ? entityById.get(relation.target_entity_id) : null
                return (
                  <div key={relation.id} className={styles.relationRow}>
                    <button type="button" onClick={() => source && setActiveEntityId(source.id)}>{source?.name || '未知'}</button>
                    <strong>{relation.relation_type}</strong>
                    <button type="button" onClick={() => target && setActiveEntityId(target.id)}>{target?.name || relation.target_name || '未入库对象'}</button>
                    <Tag color={relation.status === 'active' ? 'green' : 'default'}>{RELATION_STATUS_LABELS[relation.status] || relation.status}</Tag>
                    {relation.id.startsWith('implicit:') || isSystemAnchorRelation(relation) ? (
                      <Tooltip title="系统星图弱连接，不代表剧情强关系">
                        <Tag>星图锚点</Tag>
                      </Tooltip>
                    ) : (
                      <Popconfirm title="删除这条关系？" okText="删除" cancelText="取消" onConfirm={() => deleteRelation(relation.id)}>
                        <Button size="small" type="text" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    )}
                    {relation.start_chapter ? <p>起始章节：第{relation.start_chapter}章{relation.end_chapter ? `；结束章节：第${relation.end_chapter}章` : ''}</p> : null}
                    {relation.evidence_text ? <p>证据：{relation.evidence_text}</p> : null}
                    {relation.properties?.description ? <p>备注：{String(relation.properties.description)}</p> : null}
                  </div>
                )
              })}
              {!focusedRelations.length ? (
                <div className={styles.emptyRelations}>暂无关系。章节定稿和设定补录后，这里会逐步形成主角为中心的多对多网络。</div>
              ) : null}
            </section>

            <aside className={styles.factPane}>
              <div className={styles.panelTitle}>状态与证据</div>
              {detailLoading ? <Spin size="small" /> : null}
              <div className={styles.factBlock}>
                <strong>当前状态</strong>
                {stateEntries.length ? (
                  <div className={styles.stateList}>
                    {stateEntries.map(([key, value]) => <Tag key={key}>{key}：{formatStateValue(value)}</Tag>)}
                  </div>
                ) : <span>暂无状态节点</span>}
              </div>
              <div className={styles.factBlock}>
                <strong>出现章节</strong>
                {mentions.slice(0, 8).map(item => (
                  <div key={item.id} className={styles.factItem}>
                    <b>第{item.chapter_number || '?'}章</b>
                    <span>{item.evidence_text || item.mention_text}</span>
                  </div>
                ))}
                {!mentions.length ? <span>暂无出现记录</span> : null}
              </div>
              <div className={styles.factBlock}>
                <strong>变化历史</strong>
                {events.slice(0, 8).map(item => (
                  <div key={item.id} className={styles.factItem}>
                    <b>{item.chapter_number ? `第${item.chapter_number}章` : '未标章节'} · {item.title || item.event_type}</b>
                    <span>{item.evidence_text || item.reason || '无证据摘录'}</span>
                  </div>
                ))}
                {!events.length ? <span>暂无变化事件</span> : null}
              </div>
            </aside>
          </div>
        </main>
      </div>

      <Modal
        title={`补记关系${activeEntity ? `：${activeEntity.name}` : ''}`}
        open={relationOpen}
        onCancel={closeRelationDialog}
        onOk={() => relationForm.submit()}
        okText="确认补记"
        cancelText="取消"
        width={760}
        confirmLoading={savingRelation}
        destroyOnHidden
        forceRender
      >
        <Form form={relationForm} layout="vertical" onFinish={createRelation}>
          <div className={styles.formGrid}>
            <Form.Item name="source_entity_id" label="源实体" rules={[{ required: true, message: '请选择源实体' }]}>
              <Select
                showSearch
                optionFilterProp="label"
                options={visibleEntities.map(entity => ({ value: entity.id, label: entityLabel(entity) }))}
              />
            </Form.Item>
            <Form.Item name="target_entity_id" label="目标实体">
              <Select
                allowClear
                showSearch
                optionFilterProp="label"
                placeholder="选择已入库实体"
                options={visibleEntities.filter(entity => entity.id !== relationForm.getFieldValue('source_entity_id')).map(entity => ({ value: entity.id, label: entityLabel(entity) }))}
              />
            </Form.Item>
          </div>
          <Form.Item name="target_name" label="未入库目标名称">
            <Input placeholder="如果目标还没入库，写名称；已选择目标实体时可留空" />
          </Form.Item>
          <div className={styles.formGrid}>
            <Form.Item name="relation_type" label="关系类型" rules={[{ required: true, message: '请输入关系类型' }]}>
              <Input placeholder="例如：盟友、持有、敌对、位于、曾经归属" />
            </Form.Item>
            <Form.Item name="status" label="状态">
              <Select options={[
                { value: 'active', label: '生效' },
                { value: 'inactive', label: '失效' },
                { value: 'ended', label: '已结束' },
                { value: 'disputed', label: '待核' },
              ]} />
            </Form.Item>
          </div>
          <div className={styles.formGrid}>
            <Form.Item name="start_chapter" label="开始章节">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="end_chapter" label="结束章节">
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item name="description" label="关系备注">
            <Input.TextArea rows={2} placeholder="简短描述关系，例如：林羽当前持有混沌灵珠，但来源尚未查明。" />
          </Form.Item>
          <Form.Item name="evidence_text" label="证据摘录">
            <Input.TextArea rows={3} placeholder="摘录正文或设定里的依据，方便后面查连续性。" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
