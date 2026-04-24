import { useEffect, useState } from 'react'
import { Button, Tooltip, Modal, Form, Input, Select, message, Popconfirm } from 'antd'
import {
  BookOutlined, UserOutlined, GlobalOutlined,
  PlusOutlined, UnorderedListOutlined, FileTextOutlined,
  FolderOutlined, ThunderboltOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api'
import { useAppStore } from '../../store'
import type { ModelProviderConfig, Chapter, Volume, WorkflowConfig } from '../../types'
import styles from './LeftNav.module.css'

export default function LeftNav() {
  const navigate = useNavigate()
  const {
    currentNovel,
    currentView,
    currentChapter, setCurrentChapter,
    setCurrentVolume,
    setWorkspaceMode,
    setChapters,
    chapters, volumes, setVolumes,
    openTab,
  } = useAppStore()

  const [volumeOpen, setVolumeOpen] = useState(false)
  const [generatingVolume, setGeneratingVolume] = useState<string | null>(null)
  const [workflowConfig, setWorkflowConfig] = useState<WorkflowConfig | null>(null)
  const [savingModelConfig, setSavingModelConfig] = useState(false)
  const [volumeForm] = Form.useForm()

  useEffect(() => {
    loadWorkflowConfig()
  }, [])

  async function loadWorkflowConfig() {
    try {
      const config = await api.admin.getWorkflowConfig()
      setWorkflowConfig(config)
    } catch {
      message.error('加载模型配置失败')
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
        const volume = volumes.find(item => item.id === volumeId)
        if (volume) {
          setCurrentVolume(volume)
          openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: volume })
        }
        message.success('章节已加入分卷，请先生成或更新本卷细纲')
      } else {
        setChapters([...chapters, ch])
        setCurrentChapter(ch)
        openTab({ type: 'chapter', novelSnapshot: currentNovel, chapterSnapshot: ch })
      }
    } catch {
      message.error('创建章节失败')
    }
  }

  function canOpenChapterContent(chapter: Chapter) {
    if (chapter.chapter_number <= 1) return true
    const previous = [...chapters]
      .filter(item => item.chapter_number < chapter.chapter_number)
      .sort((a, b) => b.chapter_number - a.chapter_number)[0]
    return previous ? previous.final_approved : true
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
      setCurrentVolume(vol)
      openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: vol })
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
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败')
    }
  }

  async function generateVolumeSynopsis(volume: Volume) {
    if (!currentNovel) return
    setGeneratingVolume(volume.id)
    try {
      const result = await api.ai.generateVolumeSynopsis(currentNovel.id, volume.id)
      const [vols, chs] = await Promise.all([
        api.volumes.list(currentNovel.id),
        api.chapters.list(currentNovel.id),
      ])
      setVolumes(vols)
      setChapters(chs)
      if (result.pending_proposals && result.pending_proposals.length > 0) {
        message.warning(`《${volume.title}》细纲生成完成，但有 ${result.pending_proposals.length} 条新实体提案待审阅`)
      } else {
        message.success(`《${volume.title}》细纲生成完成，已同步 ${result.chapter_count || chs.filter(ch => ch.volume_id === volume.id).length} 章`)
      }
    } catch (err: any) {
      message.error(`生成失败：${err?.response?.data?.detail || err.message}`)
    } finally {
      setGeneratingVolume(null)
    }
  }

  async function saveModelConfig(nextProviderId: string, nextModelId: string) {
    if (!workflowConfig) return
    const previous = workflowConfig
    const nextConfig: WorkflowConfig = {
      ...workflowConfig,
      model_config: {
        ...workflowConfig.model_config,
        active_provider: nextProviderId,
        active_model: nextModelId,
      },
    }
    setWorkflowConfig(nextConfig)
    setSavingModelConfig(true)
    try {
      const saved = await api.admin.updateWorkflowConfig(nextConfig)
      setWorkflowConfig(saved)
      message.success('模型配置已切换')
    } catch {
      setWorkflowConfig(previous)
      message.error('模型配置保存失败')
    } finally {
      setSavingModelConfig(false)
    }
  }

  const providers = workflowConfig?.model_config?.providers || []
  const activeProvider = providers.find(p => p.id === workflowConfig?.model_config?.active_provider) || providers[0]
  const activeModelId = workflowConfig?.model_config?.active_model || activeProvider?.models?.[0]?.id

  function handleProviderChange(providerId: string) {
    const provider = providers.find(item => item.id === providerId)
    if (!provider) return
    const nextModelId = provider.models?.[0]?.id
    if (!nextModelId) return
    void saveModelConfig(providerId, nextModelId)
  }

  function handleModelChange(modelId: string) {
    if (!activeProvider) return
    void saveModelConfig(activeProvider.id, modelId)
  }

  async function openChapterContent(chapter: Chapter) {
    if (!currentNovel) return
    const chapterStarted = Boolean(chapter.word_count || chapter.final_approved || chapter.status !== 'draft')
    const activeVolume = chapter.volume_id ? volumes.find(volume => volume.id === chapter.volume_id) || null : null
    if (!activeVolume && !chapterStarted) {
      message.warning('请先在分卷细纲中规划这一章，再进入正文写作')
      return
    }
    if (activeVolume && activeVolume.review_status !== 'approved' && !chapterStarted) {
      message.warning('本卷细纲尚未审批，暂时不能进入正文写作')
      return
    }
    if (!chapterStarted) {
      try {
        const synopsis = await api.chapters.getSynopsis(currentNovel.id, chapter.id)
        if (!synopsis.content_md?.trim() || synopsis.review_status !== 'approved') {
          message.warning('本章细纲尚未确认，请先从分卷细纲页处理')
          return
        }
      } catch {
        message.warning('本章还没有细纲，请先从分卷细纲页生成')
        return
      }
    }
    if (!canOpenChapterContent(chapter)) {
      message.warning('上一章尚未人工定稿，暂时不能进入这一章正文')
      return
    }
    const nextChapter = activeVolume ? { ...chapter, volume_id: activeVolume.id } : chapter
    if (activeVolume) setCurrentVolume(activeVolume)
    setCurrentChapter(nextChapter)
    openTab({ type: 'chapter', novelSnapshot: currentNovel, chapterSnapshot: nextChapter })
  }

  const orderedChapters = [...chapters].sort((a, b) => a.chapter_number - b.chapter_number)

  function backToBookshelf() {
    setWorkspaceMode('bookshelf')
    navigate('/bookshelf')
  }

  return (
    <div className={styles.nav}>
      {/* 顶部 */}
      <div className={styles.header}>
        <button type="button" className={styles.shelfButton} onClick={backToBookshelf}>
          <BookOutlined />
          <span>书架</span>
        </button>
        <span className={styles.logo}>墨笔</span>
      </div>

      <div className={styles.modelConfigCard}>
        <div className={styles.modelConfigTitle}>模型配置</div>
        <Select
          size="small"
          className={styles.modelSelect}
          placeholder="选择提供商"
          value={activeProvider?.id}
          options={providers.map((provider: ModelProviderConfig) => ({
            value: provider.id,
            label: provider.name,
          }))}
          onChange={handleProviderChange}
          loading={!workflowConfig}
          disabled={savingModelConfig || !providers.length}
        />
        <Select
          size="small"
          className={styles.modelSelect}
          placeholder="选择模型"
          value={activeModelId}
          options={(activeProvider?.models || []).map(model => ({
            value: model.id,
            label: model.name,
          }))}
          onChange={handleModelChange}
          loading={savingModelConfig}
          disabled={savingModelConfig || !activeProvider}
        />
        <div className={styles.modelHint}>当前先走豆包，同一 API Key，后续可扩展更多提供商。</div>
      </div>

      <div className={styles.adminEntry}>
        <NavItem
          icon={<SettingOutlined />}
          label="后台流程配置"
          active={currentView === 'admin'}
          onClick={() => { openTab({ type: 'admin', closable: false }); setCurrentChapter(null) }}
        />
      </div>

      {/* 当前小说导航 */}
      {currentNovel && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>{currentNovel.title}</div>

          <NavItem
            icon={<UnorderedListOutlined />}
            label="大纲"
            active={currentView === 'outline'}
            onClick={() => { openTab({ type: 'outline', novelSnapshot: currentNovel }); setCurrentChapter(null) }}
          />
          <NavItem
            icon={<FileTextOutlined />}
            label="简介"
            active={currentView === 'novel_synopsis'}
            onClick={() => { openTab({ type: 'novel_synopsis', novelSnapshot: currentNovel }); setCurrentChapter(null) }}
          />
          <NavItem
            icon={<UserOutlined />}
            label="角色"
            active={currentView === 'characters'}
            onClick={() => { openTab({ type: 'characters', novelSnapshot: currentNovel }); setCurrentChapter(null) }}
          />
          <NavItem
            icon={<GlobalOutlined />}
            label="世界观设定"
            active={currentView === 'worldbuilding'}
            onClick={() => { openTab({ type: 'worldbuilding', novelSnapshot: currentNovel }); setCurrentChapter(null) }}
          />

          {/* 分卷文档树 */}
          <div className={styles.chapterSection}>
            <div className={styles.chapterHeader}>
              <span>分卷</span>
              <div style={{ display: 'flex', gap: 2 }}>
                <Tooltip title="新建卷">
                  <Button type="text" size="small" icon={<FolderOutlined />} onClick={() => setVolumeOpen(true)} />
                </Tooltip>
              </div>
            </div>

            {volumes.length === 0 ? (
              <div className={styles.emptyTreeHint}>暂无分卷。确认大纲后会自动创建分卷，也可以点上方文件夹手动新建。</div>
            ) : null}

            {/* 各卷 */}
            {volumes.map(vol => {
              return (
                <div key={vol.id} className={styles.volumeGroup}>
                  <div className={styles.volumeHeader}>
                    <FolderOutlined className={styles.volumeToggle} />
                    <span
                      className={styles.volumeTitle}
                      onClick={() => {
                        setCurrentVolume(vol)
                        openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: vol })
                      }}
                    >
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
                      <Popconfirm title="删除此卷？已开始写作的卷会被后端拦截" onConfirm={() => deleteVolume(vol.id)} okText="删除" cancelText="取消">
                        <Button type="text" size="small" danger style={{ fontSize: 10 }}>×</Button>
                      </Popconfirm>
                    </div>
                  </div>
                </div>
              )
            })}

            <div className={styles.chapterHeader}>
              <span>正文</span>
              <Tooltip title="新建章节正文">
                <Button type="text" size="small" icon={<PlusOutlined />} onClick={() => addChapter()} />
              </Tooltip>
            </div>
            {orderedChapters.map(ch => (
              <ChapterContentItem
                key={ch.id}
                ch={ch}
                active={currentView === 'chapter' && currentChapter?.id === ch.id}
                onOpenContent={() => openChapterContent(ch)}
              />
            ))}
          </div>
        </div>
      )}

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

function ChapterContentItem({
  ch,
  active,
  onOpenContent,
}: {
  ch: Chapter
  active: boolean
  onOpenContent: () => void
}) {
  return (
    <button
      type="button"
      className={`${styles.chapterDocItem} ${active ? styles.activeDoc : ''}`}
      onClick={onOpenContent}
    >
      <BookOutlined className={styles.chapterIcon} />
      <span className={styles.chapterTitle}>{ch.title || `第${ch.chapter_number}章`}</span>
      <span className={`${styles.chapterStatus} ${styles[`status_${ch.status}`]}`} />
    </button>
  )
}
