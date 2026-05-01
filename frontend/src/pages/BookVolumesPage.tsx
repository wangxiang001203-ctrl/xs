import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Space, Spin, Tag, message } from 'antd'
import { CheckOutlined, FolderOpenOutlined, ThunderboltOutlined } from '@ant-design/icons'

import { api } from '../api'
import { useAppStore } from '../store'
import type { BookVolumePlan, Volume } from '../types'
import styles from './BookVolumesPage.module.css'

function volumeBookPlanApproved(volume: Volume) {
  return volume.plan_data?.book_plan_status === 'approved'
}

export default function BookVolumesPage() {
  const {
    currentNovel,
    volumes,
    setVolumes,
    setCurrentVolume,
    openTab,
  } = useAppStore()
  const [plan, setPlan] = useState<BookVolumePlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [approving, setApproving] = useState(false)

  useEffect(() => {
    void loadPlan()
  }, [currentNovel?.id])

  async function loadPlan() {
    if (!currentNovel) return
    setLoading(true)
    try {
      const data = await api.volumes.bookPlan(currentNovel.id)
      setPlan(data)
      setVolumes(data.volumes)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '全书分卷加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function generateBookVolumes() {
    if (!currentNovel) return
    setGenerating(true)
    try {
      const result = await api.ai.generateBookVolumes(currentNovel.id)
      const data = await api.volumes.bookPlan(currentNovel.id)
      setPlan(data)
      setVolumes(data.volumes)
      message.success(`已生成 ${result.volume_count || data.volumes.length} 卷，请先整体审批`)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || err?.message || '生成全书分卷失败')
    } finally {
      setGenerating(false)
    }
  }

  async function approveBookPlan() {
    if (!currentNovel) return
    setApproving(true)
    try {
      const approved = await api.volumes.approveBookPlan(currentNovel.id)
      setPlan(approved)
      setVolumes(approved.volumes)
      message.success('全书分卷已审批，可以按卷生成章节细纲')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '审批失败')
    } finally {
      setApproving(false)
    }
  }

  function openVolume(volume: Volume) {
    if (!currentNovel) return
    if (!volumeBookPlanApproved(volume)) {
      message.warning('请先审批全书分卷，再进入单卷细纲')
      return
    }
    setCurrentVolume(volume)
    openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: volume })
  }

  const visibleVolumes = plan?.volumes.length ? plan.volumes : volumes
  const approved = useMemo(
    () => Boolean(visibleVolumes.length) && visibleVolumes.every(volumeBookPlanApproved),
    [visibleVolumes],
  )
  const bookPlanText = plan?.book_plan_markdown || ''

  if (!currentNovel) return <div className={styles.empty}>请选择作品</div>

  if (loading && !plan) {
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
          <div className={styles.title}>全书分卷</div>
          <div className={styles.meta}>
            <span>{visibleVolumes.length || 0} 卷</span>
            <span>{visibleVolumes.reduce((sum, volume) => sum + (volume.planned_chapter_count || 0), 0)} 章规划</span>
            <Tag color={approved ? 'green' : 'orange'}>{approved ? '已审批' : '待审批'}</Tag>
          </div>
        </div>
        <Space>
          <Button icon={<ThunderboltOutlined />} onClick={generateBookVolumes} loading={generating}>
            生成全书分卷
          </Button>
          <Button type="primary" icon={<CheckOutlined />} onClick={approveBookPlan} loading={approving} disabled={!visibleVolumes.length || approved}>
            审批全书分卷
          </Button>
        </Space>
      </div>

      <div className={styles.content}>
        <section className={styles.leftPane}>
          <Alert
            type="info"
            showIcon
            message="全书分卷只负责卷级推进。审批后，正文侧边栏会按卷展示；进入某一卷后再一次性生成并审批本卷所有章节细纲。"
            className={styles.alert}
          />
          <div className={styles.planDoc}>
            {bookPlanText ? (
              <pre>{bookPlanText}</pre>
            ) : (
              <div className={styles.emptyDoc}>确认大纲后，在这里生成一份全书卷级规划。</div>
            )}
          </div>
        </section>

        <aside className={styles.volumeList}>
          <div className={styles.listTitle}>卷列表</div>
          {visibleVolumes.map(volume => {
            const isApproved = volumeBookPlanApproved(volume)
            return (
              <button
                type="button"
                key={volume.id}
                className={styles.volumeItem}
                onClick={() => openVolume(volume)}
              >
                <span className={styles.volumeIcon}><FolderOpenOutlined /></span>
                <span className={styles.volumeBody}>
                  <strong>第{volume.volume_number}卷 {volume.title}</strong>
                  <span>{volume.planned_chapter_count || 0} 章 · {volume.target_words || 0} 字</span>
                </span>
                <Tag color={isApproved ? 'green' : 'orange'}>{isApproved ? '可细纲' : '待批'}</Tag>
              </button>
            )
          })}
          {!visibleVolumes.length ? (
            <div className={styles.emptyList}>还没有卷。先生成全书分卷。</div>
          ) : null}
        </aside>
      </div>
    </div>
  )
}
