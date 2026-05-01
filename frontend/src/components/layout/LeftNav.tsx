import { useEffect, useMemo, useState } from 'react'
import { Button, Tooltip, Modal, Input, Select, message, Radio, Space } from 'antd'
import {
  BookOutlined, UserOutlined, GlobalOutlined,
  PlusOutlined, UnorderedListOutlined, FileTextOutlined,
  FolderOutlined, ThunderboltOutlined,
  ReloadOutlined,
  ApartmentOutlined,
} from '@ant-design/icons'
import { api } from '../../api'
import { useAppStore } from '../../store'
import type { ModelProviderConfig, Chapter, Volume, WorkflowConfig } from '../../types'
import styles from './LeftNav.module.css'

const WORLD_SETTING_NAV = [
  { id: 'overview', label: '世界总述', icon: <GlobalOutlined /> },
  { id: 'power_system', label: '力量体系', icon: <ThunderboltOutlined /> },
  { id: 'techniques', label: '功法 / 技能', icon: <FileTextOutlined /> },
  { id: 'items', label: '道具 / 资源', icon: <BookOutlined /> },
  { id: 'geography', label: '地点 / 地图', icon: <GlobalOutlined /> },
  { id: 'factions', label: '势力 / 组织', icon: <FolderOutlined /> },
  { id: 'core_rules', label: '世界规则', icon: <FileTextOutlined /> },
]

const BUILTIN_WORLD_SECTION_IDS = new Set(WORLD_SETTING_NAV.map(item => item.id))

export default function LeftNav() {
  const {
    currentNovel,
    setCurrentNovel,
    currentView,
    currentChapter, setCurrentChapter,
    currentVolume,
    setCurrentVolume,
    chapters, volumes,
    worldbuilding,
    activeWorldbuildingSectionId,
    setActiveWorldbuildingSectionId,
    openTab,
  } = useAppStore()

  const [workflowConfig, setWorkflowConfig] = useState<WorkflowConfig | null>(null)
  const [savingModelConfig, setSavingModelConfig] = useState(false)
  const [titleModalOpen, setTitleModalOpen] = useState(false)
  const [titlePrompt, setTitlePrompt] = useState('')
  const [titleOptions, setTitleOptions] = useState<string[]>([])
  const [selectedTitle, setSelectedTitle] = useState('')
  const [generatingTitles, setGeneratingTitles] = useState(false)
  const [applyingTitle, setApplyingTitle] = useState(false)
  const [outlineConfirmed, setOutlineConfirmed] = useState(false)

  useEffect(() => {
    loadWorkflowConfig()
  }, [])

  useEffect(() => {
    void loadOutlineStatus()
  }, [currentNovel?.id])

  useEffect(() => {
    function handleOutlineChanged() {
      void loadOutlineStatus()
    }

    window.addEventListener('mobi:outline-generated', handleOutlineChanged)
    window.addEventListener('mobi:outline-confirmed', handleOutlineChanged)
    return () => {
      window.removeEventListener('mobi:outline-generated', handleOutlineChanged)
      window.removeEventListener('mobi:outline-confirmed', handleOutlineChanged)
    }
  }, [currentNovel?.id])

  async function loadWorkflowConfig() {
    try {
      const config = await api.admin.getWorkflowConfig()
      setWorkflowConfig(config)
    } catch {
      message.error('加载模型配置失败')
    }
  }

  async function loadOutlineStatus() {
    if (!currentNovel) {
      setOutlineConfirmed(false)
      return
    }
    try {
      const outlines = await api.outline.list(currentNovel.id)
      setOutlineConfirmed(outlines.some(item => item.confirmed))
    } catch {
      setOutlineConfirmed(false)
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
    if (!outlineConfirmed) {
      message.warning('请先确认大纲')
      return
    }
    const activeVolume = chapter.volume_id ? volumes.find(volume => volume.id === chapter.volume_id) || null : null
    if (!activeVolume) {
      message.warning('请先在分卷细纲中规划这一章，再进入正文写作')
      return
    }
    if (!isBookPlanApproved(activeVolume)) {
      message.warning('本书卷级规划尚未审批，请先到"全书分卷"审批')
      return
    }
    if (activeVolume.review_status !== 'approved') {
      message.warning('本卷章节细纲尚未整卷审批，正文入口暂不开放')
      return
    }
    try {
      const synopsis = await api.chapters.getSynopsis(currentNovel.id, chapter.id)
      if (!synopsis.content_md?.trim() || synopsis.review_status !== 'approved') {
        message.warning('本章细纲尚未审批，请先回到本卷页面审批整卷细纲')
        return
      }
    } catch {
      message.warning('本章还没有细纲，请先从分卷细纲页生成')
      return
    }
    const nextChapter = activeVolume ? { ...chapter, volume_id: activeVolume.id } : chapter
    if (activeVolume) setCurrentVolume(activeVolume)
    setCurrentChapter(nextChapter)
    openTab({ type: 'chapter', novelSnapshot: currentNovel, chapterSnapshot: nextChapter })
  }

  function isBookPlanApproved(volume: Volume) {
    return volume.plan_data?.book_plan_status === 'approved'
  }

  function openBookVolumes() {
    if (!currentNovel) return
    openTab({ type: 'book_volumes', novelSnapshot: currentNovel })
    setCurrentChapter(null)
  }

  function openRelationshipNetwork() {
    if (!currentNovel) return
    openTab({ type: 'relationship_network', novelSnapshot: currentNovel })
    setCurrentChapter(null)
  }

  function openVolumeDetail(volume: Volume) {
    if (!currentNovel) return
    if (!outlineConfirmed) {
      message.warning('请先确认大纲')
      return
    }
    if (!isBookPlanApproved(volume)) {
      message.warning('请先到“全书分卷”审批整本书的卷级规划')
      return
    }
    setCurrentVolume(volume)
    openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: volume })
    setCurrentChapter(null)
  }

  const orderedChapters = useMemo(() => [...chapters].sort((a, b) => a.chapter_number - b.chapter_number), [chapters])
  const orderedVolumes = useMemo(() => [...volumes].sort((a, b) => a.volume_number - b.volume_number), [volumes])
  const bookPlanApproved = orderedVolumes.length > 0 && orderedVolumes.every(isBookPlanApproved)
  const chaptersByVolume = useMemo(() => {
    const map = new Map<string, Chapter[]>()
    for (const chapter of orderedChapters) {
      if (!chapter.volume_id) continue
      const list = map.get(chapter.volume_id) || []
      list.push(chapter)
      map.set(chapter.volume_id, list)
    }
    return map
  }, [orderedChapters])

  function openTitleModal() {
    if (!outlineConfirmed) {
      message.warning('请先确认大纲')
      return
    }
    setTitlePrompt('')
    setTitleOptions([])
    setSelectedTitle('')
    setTitleModalOpen(true)
  }

  function closeTitleModal() {
    setTitleModalOpen(false)
    setTitlePrompt('')
    setTitleOptions([])
    setSelectedTitle('')
  }

  async function generateTitles() {
    if (!currentNovel) return
    setGeneratingTitles(true)
    try {
      const res = await api.ai.generateTitles(currentNovel.id, titlePrompt.trim() || undefined)
      if (!res.titles?.length) {
        message.warning('未生成可用书名，请调整提示后重试')
        return
      }
      setTitleOptions(res.titles)
      setSelectedTitle(res.titles[0])
      message.success('已生成10个候选书名')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '生成书名失败，请先确认大纲')
    } finally {
      setGeneratingTitles(false)
    }
  }

  async function applySelectedTitle() {
    if (!currentNovel || !selectedTitle) return
    setApplyingTitle(true)
    try {
      const updated = await api.novels.update(currentNovel.id, { title: selectedTitle })
      setCurrentNovel(updated)
      closeTitleModal()
      message.success('书名已替换')
    } catch {
      message.error('书名更新失败')
    } finally {
      setApplyingTitle(false)
    }
  }

  function openWorldSetting(sectionId: string, sectionName: string) {
    if (!currentNovel) return
    setActiveWorldbuildingSectionId(sectionId)
    openTab({
      type: 'worldbuilding',
      novelSnapshot: currentNovel,
      worldbuildingSectionId: sectionId,
      worldbuildingSectionName: sectionName,
    })
    setCurrentChapter(null)
  }

  function createCustomSetting() {
    openWorldSetting('__new_custom__', '新建设定')
  }

  const customSections = (worldbuilding?.sections || []).filter(section =>
    section.id && !BUILTIN_WORLD_SECTION_IDS.has(section.id),
  )

  return (
    <div className={styles.nav}>
      {/* 顶部 */}
      <div className={styles.header}>
        <div className={styles.bookIdentity}>
          <span className={styles.bookLabel}>当前作品</span>
          <span className={styles.bookTitle}>{currentNovel?.title || '未选择作品'}</span>
        </div>
        {currentNovel && (
          <Tooltip title="重新生成书名">
            <Button
              size="small"
              type="text"
              icon={<ReloadOutlined />}
              onClick={openTitleModal}
              disabled={!outlineConfirmed}
            >
              换名
            </Button>
          </Tooltip>
        )}
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

      {/* 当前小说导航 */}
      {currentNovel && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>作品结构</div>

          <NavItem
            icon={<UnorderedListOutlined />}
            label="大纲"
            tag={outlineConfirmed ? undefined : '待确认'}
            tagTone="warning"
            active={currentView === 'outline'}
            onClick={() => { openTab({ type: 'outline', novelSnapshot: currentNovel }); setCurrentChapter(null) }}
          />
          <NavItem
            icon={<FileTextOutlined />}
            label="简介"
            active={currentView === 'novel_synopsis'}
            disabled={!outlineConfirmed}
            onClick={() => { openTab({ type: 'novel_synopsis', novelSnapshot: currentNovel }); setCurrentChapter(null) }}
          />
          <NavItem
            icon={<FolderOutlined />}
            label="全书分卷"
            tag={bookPlanApproved ? undefined : '待审批'}
            tagTone="warning"
            active={currentView === 'book_volumes'}
            disabled={!outlineConfirmed}
            onClick={openBookVolumes}
          />

          <div className={styles.sectionTitle}>通用设定</div>
          <NavItem
            icon={<UserOutlined />}
            label="角色库"
            active={currentView === 'characters'}
            disabled={!outlineConfirmed}
            onClick={() => { openTab({ type: 'characters', novelSnapshot: currentNovel }); setCurrentChapter(null) }}
          />
          <NavItem
            icon={<ApartmentOutlined />}
            label="关系网"
            active={currentView === 'relationship_network'}
            disabled={!outlineConfirmed}
            onClick={openRelationshipNetwork}
          />
          <NavItem
            icon={<GlobalOutlined />}
            label="世界观"
            active={currentView === 'worldbuilding' && activeWorldbuildingSectionId === 'overview'}
            disabled={!outlineConfirmed}
            onClick={() => openWorldSetting('overview', '世界总述')}
          />

          <div className={styles.sectionSubGroup}>
            {WORLD_SETTING_NAV.filter(item => item.id !== 'overview').map(item => (
              <NavItem
                key={item.id}
                icon={item.icon}
                label={item.label}
                active={currentView === 'worldbuilding' && activeWorldbuildingSectionId === item.id}
                disabled={!outlineConfirmed}
                onClick={() => openWorldSetting(item.id, item.label)}
              />
            ))}
          </div>

          {/* 自定义设定折叠在世界观下 */}
          {customSections.length > 0 && (
            <div className={styles.sectionSubGroup}>
              <div className={styles.customSectionHeader}>
                <span className={styles.customSectionLabel}>自定义</span>
                <Tooltip title="新建设定">
                  <Button type="text" size="small" icon={<PlusOutlined />} disabled={!outlineConfirmed} onClick={createCustomSetting} />
                </Tooltip>
              </div>
              {customSections.map(section => (
                <NavItem
                  key={section.id}
                  icon={<FileTextOutlined />}
                  label={section.name || '未命名'}
                  active={currentView === 'worldbuilding' && activeWorldbuildingSectionId === section.id}
                  disabled={!outlineConfirmed}
                  onClick={() => openWorldSetting(section.id || 'overview', section.name || '自定义')}
                />
              ))}
            </div>
          )}

          {/* 正文卷树 */}
          <div className={styles.chapterSection}>
            <div className={styles.chapterHeader}>
              <span>正文</span>
            </div>

            {orderedVolumes.length === 0 ? (
              <div className={styles.emptyTreeHint}>{outlineConfirmed ? '先到“全书分卷”由 AI 生成卷级规划。正文不能直接新建章节。' : '确认大纲后解锁正文流程。'}</div>
            ) : null}

            {orderedVolumes.map(vol => {
              const volumeChapters = chaptersByVolume.get(vol.id) || []
              const volumeApproved = vol.review_status === 'approved'
              const volumeBookApproved = isBookPlanApproved(vol)
              const statusText = !volumeBookApproved ? '全书待批' : volumeApproved ? '可写' : '待细纲审批'
              return (
                <div key={vol.id} className={styles.volumeGroup}>
                  <div className={`${styles.volumeHeader} ${currentView === 'volume' && currentVolume?.id === vol.id ? styles.activeVolumeHeader : ''}`} onClick={() => openVolumeDetail(vol)}>
                    <FolderOutlined className={styles.volumeToggle} />
                    <span className={styles.volumeTitle}>第{vol.volume_number}卷 {vol.title}</span>
                    <span className={`${styles.itemTag} ${volumeBookApproved ? styles.tagSuccess : styles.tagWarning}`}>
                      {statusText}
                    </span>
                  </div>
                  {bookPlanApproved && !volumeApproved ? (
                    <div className={styles.emptyTreeHint}>打开本卷，生成并审批整卷章节细纲后，正文入口才会出现。</div>
                  ) : null}
                  {bookPlanApproved && volumeApproved ? volumeChapters.map(ch => (
                    <ChapterContentItem
                      key={ch.id}
                      ch={ch}
                      active={currentView === 'chapter' && currentChapter?.id === ch.id}
                      disabled={!outlineConfirmed}
                      onOpenContent={() => openChapterContent(ch)}
                    />
                  )) : null}
                </div>
              )
            })}
          </div>
        </div>
      )}

      <Modal
        title="重新生成书名"
        open={titleModalOpen}
        onCancel={closeTitleModal}
        footer={null}
        destroyOnHidden
      >
        <div className={styles.titleModalBody}>
          <Input.TextArea
            value={titlePrompt}
            onChange={event => setTitlePrompt(event.target.value)}
            placeholder="可选：输入书名偏好，例如“更短、更燃、带修仙感，避免生僻字”"
            autoSize={{ minRows: 3, maxRows: 5 }}
          />
          <Space>
            <Button type="primary" loading={generatingTitles} onClick={generateTitles}>
              生成10个书名
            </Button>
            <Button
              disabled={!selectedTitle}
              loading={applyingTitle}
              onClick={applySelectedTitle}
            >
              选中并替换
            </Button>
          </Space>
          {!!titleOptions.length && (
            <Radio.Group
              value={selectedTitle}
              onChange={event => setSelectedTitle(event.target.value)}
              className={styles.titleOptions}
            >
              <Space direction="vertical">
                {titleOptions.map(title => (
                  <Radio key={title} value={title}>{title}</Radio>
                ))}
              </Space>
            </Radio.Group>
          )}
        </div>
      </Modal>
    </div>
  )
}

function NavItem({ icon, label, tag, tagTone = 'default', active, disabled, onClick }: {
  icon: React.ReactNode
  label: string
  tag?: string
  tagTone?: 'success' | 'warning' | 'default'
  active: boolean
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <div
      className={`${styles.navItem} ${active ? styles.active : ''} ${disabled ? styles.disabled : ''}`}
      onClick={disabled ? undefined : onClick}
    >
      <span className={styles.navIcon}>{icon}</span>
      <span className={styles.navText}>{label}</span>
      {tag ? <span className={`${styles.itemTag} ${tagTone === 'success' ? styles.tagSuccess : tagTone === 'warning' ? styles.tagWarning : ''}`}>{tag}</span> : null}
    </div>
  )
}

function ChapterContentItem({
  ch,
  active,
  disabled,
  onOpenContent,
}: {
  ch: Chapter
  active: boolean
  disabled?: boolean
  onOpenContent: () => void
}) {
  return (
    <button
      type="button"
      className={`${styles.chapterDocItem} ${active ? styles.activeDoc : ''}`}
      onClick={onOpenContent}
      disabled={disabled}
    >
      <BookOutlined className={styles.chapterIcon} />
      <span className={styles.chapterTitle}>{ch.title || `第${ch.chapter_number}章`}</span>
      <span className={`${styles.itemTag} ${ch.final_approved ? styles.tagSuccess : ch.status === 'writing' ? styles.tagWarning : ''}`}>
        {ch.final_approved ? '已定' : ch.status === 'writing' ? '写作中' : '待写'}
      </span>
      <span className={`${styles.chapterStatus} ${styles[`status_${ch.status}`]}`} />
    </button>
  )
}
