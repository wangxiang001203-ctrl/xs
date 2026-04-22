import { useEffect, useState } from 'react'
import { Button, Tooltip, Modal, Form, Input, Select, message, Spin, Popconfirm } from 'antd'
import {
  BookOutlined, UserOutlined, GlobalOutlined,
  PlusOutlined, UnorderedListOutlined, FileTextOutlined,
  FolderOutlined, ThunderboltOutlined, DownOutlined, RightOutlined,
} from '@ant-design/icons'
import { api, streamVolumeSynopsis } from '../../api'
import { useAppStore } from '../../store'
import type { Novel, Chapter, Volume } from '../../types'
import styles from './LeftNav.module.css'

export default function LeftNav() {
  const {
    currentNovel, setCurrentNovel,
    currentView, setCurrentView,
    currentChapter, setCurrentChapter,
    setCharacters, setWorldbuilding, setChapters,
    chapters, volumes, setVolumes,
  } = useAppStore()

  const [novels, setNovels] = useState<Novel[]>([])
  const [loading, setLoading] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [volumeOpen, setVolumeOpen] = useState(false)
  const [assignOpen, setAssignOpen] = useState<{ volumeId: string } | null>(null)
  const [collapsedVolumes, setCollapsedVolumes] = useState<Set<string>>(new Set())
  const [generatingVolume, setGeneratingVolume] = useState<string | null>(null)
  const [form] = Form.useForm()
  const [volumeForm] = Form.useForm()

  useEffect(() => {
    loadNovels()
  }, [])

  async function loadNovels() {
    setLoading(true)
    try {
      const list = await api.novels.list()
      setNovels(list)
    } finally {
      setLoading(false)
    }
  }

  async function selectNovel(novel: Novel) {
    setCurrentNovel(novel)
    setCurrentView('outline')
    setCurrentChapter(null)
    const [chars, wb, chs, vols] = await Promise.all([
      api.characters.list(novel.id),
      api.worldbuilding.get(novel.id).catch(() => null),
      api.chapters.list(novel.id),
      api.volumes.list(novel.id).catch(() => [] as Volume[]),
    ])
    setCharacters(chars)
    setWorldbuilding(wb)
    setChapters(chs)
    setVolumes(vols)
  }

  async function createNovel(values: { title: string; genre: string }) {
    try {
      const novel = await api.novels.create(values)
      setNovels(prev => [novel, ...prev])
      setCreateOpen(false)
      form.resetFields()
      selectNovel(novel)
    } catch {
      message.error('创建失败')
    }
  }

  async function addChapter(volumeId?: string) {
    if (!currentNovel) return
    const nextNum = chapters.length + 1
    try {
      const ch = await api.chapters.create(currentNovel.id, {
        chapter_number: nextNum,
        title: `第${nextNum}章`,
      })
      if (volumeId) {
        await api.volumes.assignChapter(currentNovel.id, volumeId, ch.id)
        const updated = { ...ch, volume_id: volumeId }
        setChapters([...chapters, updated])
        setCurrentChapter(updated)
      } else {
        setChapters([...chapters, ch])
        setCurrentChapter(ch)
      }
      setCurrentView('synopsis')
    } catch {
      message.error('创建章节失败')
    }
  }

  async function createVolume(values: { title: string; description?: string }) {
    if (!currentNovel) return
    try {
      const vol = await api.volumes.create(currentNovel.id, {
        title: values.title,
        volume_number: volumes.length + 1,
        description: values.description,
      })
      setVolumes([...volumes, vol])
      setVolumeOpen(false)
      volumeForm.resetFields()
    } catch {
      message.error('创建卷失败')
    }
  }

  async function deleteVolume(volumeId: string) {
    if (!currentNovel) return
    try {
      await api.volumes.delete(currentNovel.id, volumeId)
      setVolumes(volumes.filter(v => v.id !== volumeId))
    } catch {
      message.error('删除失败')
    }
  }

  function generateVolumeSynopsis(volume: Volume) {
    if (!currentNovel) return
    setGeneratingVolume(volume.id)
    streamVolumeSynopsis(
      currentNovel.id, volume.id, undefined,
      () => {},
      async () => {
        setGeneratingVolume(null)
        message.success(`《${volume.title}》细纲生成完成`)
        // 刷新卷状态
        const vols = await api.volumes.list(currentNovel.id)
        setVolumes(vols)
      },
      err => { setGeneratingVolume(null); message.error(`生成失败：${err}`) },
    )
  }

  function toggleVolume(volumeId: string) {
    setCollapsedVolumes(prev => {
      const next = new Set(prev)
      if (next.has(volumeId)) next.delete(volumeId)
      else next.add(volumeId)
      return next
    })
  }

  // 未分卷章节
  const unassignedChapters = chapters.filter(c => !c.volume_id)

  return (
    <div className={styles.nav}>
      {/* 顶部 */}
      <div className={styles.header}>
        <span className={styles.logo}>墨笔</span>
        <Tooltip title="新建小说">
          <Button
            type="text" size="small" icon={<PlusOutlined />}
            className={styles.addBtn}
            onClick={() => setCreateOpen(true)}
          />
        </Tooltip>
      </div>

      {/* 小说列表 */}
      <div className={styles.novelList}>
        {loading ? <Spin size="small" style={{ margin: '12px auto', display: 'block' }} /> : null}
        {novels.map(n => (
          <div
            key={n.id}
            className={`${styles.novelItem} ${currentNovel?.id === n.id ? styles.active : ''}`}
            onClick={() => selectNovel(n)}
          >
            <BookOutlined className={styles.novelIcon} />
            <span className={styles.novelTitle}>{n.title}</span>
          </div>
        ))}
      </div>

      {/* 当前小说导航 */}
      {currentNovel && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>{currentNovel.title}</div>

          <NavItem
            icon={<UnorderedListOutlined />}
            label="大纲"
            active={currentView === 'outline'}
            onClick={() => { setCurrentView('outline'); setCurrentChapter(null) }}
          />
          <NavItem
            icon={<UserOutlined />}
            label="角色"
            active={currentView === 'characters'}
            onClick={() => { setCurrentView('characters'); setCurrentChapter(null) }}
          />
          <NavItem
            icon={<GlobalOutlined />}
            label="世界观设定"
            active={currentView === 'worldbuilding'}
            onClick={() => { setCurrentView('worldbuilding'); setCurrentChapter(null) }}
          />

          {/* 卷列表 */}
          <div className={styles.chapterSection}>
            <div className={styles.chapterHeader}>
              <span>章节</span>
              <div style={{ display: 'flex', gap: 2 }}>
                <Tooltip title="新建卷">
                  <Button type="text" size="small" icon={<FolderOutlined />} onClick={() => setVolumeOpen(true)} />
                </Tooltip>
                <Tooltip title="新建章节（不分卷）">
                  <Button type="text" size="small" icon={<PlusOutlined />} onClick={() => addChapter()} />
                </Tooltip>
              </div>
            </div>

            {/* 各卷 */}
            {volumes.map(vol => {
              const volChapters = chapters.filter(c => c.volume_id === vol.id)
              const collapsed = collapsedVolumes.has(vol.id)
              return (
                <div key={vol.id} className={styles.volumeGroup}>
                  <div className={styles.volumeHeader}>
                    <span className={styles.volumeToggle} onClick={() => toggleVolume(vol.id)}>
                      {collapsed ? <RightOutlined /> : <DownOutlined />}
                    </span>
                    <span className={styles.volumeTitle} onClick={() => toggleVolume(vol.id)}>
                      {vol.title}
                    </span>
                    <div className={styles.volumeActions}>
                      <Tooltip title="生成本卷细纲">
                        <Button
                          type="text" size="small"
                          icon={<ThunderboltOutlined />}
                          loading={generatingVolume === vol.id}
                          onClick={() => generateVolumeSynopsis(vol)}
                        />
                      </Tooltip>
                      <Tooltip title="新建章节">
                        <Button type="text" size="small" icon={<PlusOutlined />} onClick={() => addChapter(vol.id)} />
                      </Tooltip>
                      <Popconfirm title="删除此卷？章节不会删除" onConfirm={() => deleteVolume(vol.id)} okText="删除" cancelText="取消">
                        <Button type="text" size="small" danger style={{ fontSize: 10 }}>×</Button>
                      </Popconfirm>
                    </div>
                  </div>
                  {!collapsed && volChapters.map(ch => (
                    <ChapterItem
                      key={ch.id}
                      ch={ch}
                      active={currentChapter?.id === ch.id}
                      onClick={() => { setCurrentChapter(ch); setCurrentView('chapter') }}
                    />
                  ))}
                </div>
              )
            })}

            {/* 未分卷章节 */}
            {unassignedChapters.map(ch => (
              <ChapterItem
                key={ch.id}
                ch={ch}
                active={currentChapter?.id === ch.id}
                onClick={() => { setCurrentChapter(ch); setCurrentView('chapter') }}
              />
            ))}
          </div>
        </div>
      )}

      {/* 新建小说弹窗 */}
      <Modal
        title="新建小说"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={createNovel}>
          <Form.Item name="title" label="书名" rules={[{ required: true }]}>
            <Input placeholder="请输入书名" />
          </Form.Item>
          <Form.Item name="genre" label="类型" initialValue="玄幻修仙">
            <Select options={[
              { value: '玄幻修仙', label: '玄幻修仙' },
              { value: '都市', label: '都市' },
              { value: '科幻', label: '科幻' },
              { value: '历史', label: '历史' },
            ]} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 新建卷弹窗 */}
      <Modal
        title="新建卷"
        open={volumeOpen}
        onCancel={() => setVolumeOpen(false)}
        onOk={() => volumeForm.submit()}
        okText="创建"
        cancelText="取消"
      >
        <Form form={volumeForm} layout="vertical" onFinish={createVolume}>
          <Form.Item name="title" label="卷名" rules={[{ required: true }]}>
            <Input placeholder="如：第一卷 凡人修仙" />
          </Form.Item>
          <Form.Item name="description" label="简介">
            <Input.TextArea rows={2} placeholder="本卷剧情简介（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

function NavItem({ icon, label, active, onClick }: {
  icon: React.ReactNode
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <div
      className={`${styles.navItem} ${active ? styles.active : ''}`}
      onClick={onClick}
    >
      <span className={styles.navIcon}>{icon}</span>
      <span>{label}</span>
    </div>
  )
}

function ChapterItem({ ch, active, onClick }: { ch: Chapter; active: boolean; onClick: () => void }) {
  return (
    <div
      className={`${styles.chapterItem} ${active ? styles.active : ''}`}
      onClick={onClick}
    >
      <FileTextOutlined className={styles.chapterIcon} />
      <span className={styles.chapterTitle}>
        {ch.title || `第${ch.chapter_number}章`}
      </span>
      <span className={`${styles.chapterStatus} ${styles[`status_${ch.status}`]}`} />
    </div>
  )
}
