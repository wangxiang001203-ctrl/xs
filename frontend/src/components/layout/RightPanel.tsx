import { useEffect, useMemo, useState } from 'react'
import { Button, Divider, Empty, Input, List, Segmented, Space, Spin, Tag, Typography, message } from 'antd'
import { CheckOutlined, CloseOutlined, SendOutlined } from '@ant-design/icons'

import { api } from '../../api'
import { useAppStore } from '../../store'
import type { AIGenerationJob, EntityProposal } from '../../types'
import styles from './RightPanel.module.css'

type PanelMode = 'context' | 'review' | 'logs' | 'chat'

interface ChatEntry {
  role: 'user' | 'assistant'
  content: string
}

export default function RightPanel() {
  const {
    currentNovel,
    currentChapter,
    currentVolume,
    volumes,
    openTab,
    currentView,
  } = useAppStore()
  const [mode, setMode] = useState<PanelMode>('context')
  const [loading, setLoading] = useState(false)
  const [proposals, setProposals] = useState<EntityProposal[]>([])
  const [jobs, setJobs] = useState<AIGenerationJob[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatEntry[]>([])
  const [chatting, setChatting] = useState(false)

  const activeVolume = useMemo(() => {
    if (currentVolume) return currentVolume
    if (!currentChapter?.volume_id) return null
    return volumes.find(volume => volume.id === currentChapter.volume_id) || null
  }, [currentVolume?.id, currentChapter?.id, currentChapter?.volume_id, volumes])

  useEffect(() => {
    if (!currentNovel) return
    setLoading(true)
    void Promise.all([
      api.review.listProposals(currentNovel.id, {
        status: 'pending',
        chapterId: currentChapter?.id,
        volumeId: activeVolume?.id,
      }).catch(() => [] as EntityProposal[]),
      api.ai.listJobs(currentNovel.id, 12).catch(() => [] as AIGenerationJob[]),
    ]).then(([proposalList, jobList]) => {
      setProposals(proposalList)
      setJobs(jobList)
    }).finally(() => setLoading(false))
  }, [currentNovel?.id, currentChapter?.id, activeVolume?.id])

  async function handleProposal(proposalId: string, action: 'approve' | 'reject') {
    if (!currentNovel) return
    try {
      const handler = action === 'approve' ? api.review.approveProposal : api.review.rejectProposal
      await handler(currentNovel.id, proposalId)
      const next = await api.review.listProposals(currentNovel.id, {
        status: 'pending',
        chapterId: currentChapter?.id,
        volumeId: activeVolume?.id,
      })
      setProposals(next)
      message.success(action === 'approve' ? '提案已通过' : '提案已拒绝')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '处理失败')
    }
  }

  async function sendChat() {
    if (!currentNovel || !chatInput.trim()) return
    const historyMessages = [...chatMessages]
    const nextMessages = [...historyMessages, { role: 'user' as const, content: chatInput.trim() }]
    setChatMessages(nextMessages)
    setChatting(true)
    const currentInput = chatInput.trim()
    setChatInput('')
    try {
      const contextType = currentChapter
        ? 'chapter'
        : currentView === 'characters'
          ? 'characters'
          : currentView === 'worldbuilding'
            ? 'worldbuilding'
            : 'outline'
      const result = await api.ai.chat({
        novel_id: currentNovel.id,
        context_type: contextType,
        context_id: currentChapter?.id ?? null,
        messages: historyMessages.map(item => ({ role: item.role, content: item.content })),
        user_message: currentInput,
      })
      setChatMessages(prev => [...prev, { role: 'assistant', content: result.message }])
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'AI 对话失败')
    } finally {
      setChatting(false)
    }
  }

  function openContextTarget(kind: string) {
    if (!currentNovel) return
    switch (kind) {
      case 'outline':
        openTab({ type: 'outline', novelSnapshot: currentNovel })
        return
      case 'synopsis':
        openTab({ type: 'novel_synopsis', novelSnapshot: currentNovel })
        return
      case 'characters':
        openTab({ type: 'characters', novelSnapshot: currentNovel })
        return
      case 'worldbuilding':
        openTab({ type: 'worldbuilding', novelSnapshot: currentNovel })
        return
      case 'volume':
        if (activeVolume) openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: activeVolume })
        return
      case 'chapter_content':
        if (currentChapter) openTab({ type: 'chapter', novelSnapshot: currentNovel, chapterSnapshot: currentChapter })
        return
      default:
        return
    }
  }

  const contextFiles = useMemo(() => {
    if (!currentNovel) return []
    const items = [
      { id: 'outline', label: 'outline/outline.md', desc: '总大纲', action: 'outline' },
      { id: 'synopsis', label: 'book/synopsis.md', desc: '作品简介', action: 'synopsis' },
      { id: 'characters', label: 'characters/characters.json', desc: '角色库', action: 'characters' },
      { id: 'worldbuilding', label: 'world/worldbuilding.json', desc: '世界观', action: 'worldbuilding' },
    ]
    if (activeVolume) {
      items.push({
        id: 'volume',
        label: `volumes/volume_${String(activeVolume.volume_number).padStart(2, '0')}/plan.md`,
        desc: '当前卷细纲文件',
        action: 'volume',
      })
    }
    if (currentChapter) {
      items.push({
        id: 'chapter-plot',
        label: `plots/chapter_${String(currentChapter.chapter_number).padStart(3, '0')}.md`,
        desc: '当前章主线提炼',
        action: activeVolume ? 'volume' : 'chapter_content',
      })
      items.push({
        id: 'chapter-content',
        label: `chapters/chapter_${String(currentChapter.chapter_number).padStart(3, '0')}/content.md`,
        desc: '当前章正文',
        action: 'chapter_content',
      })
      items.push({
        id: 'chapter-memory',
        label: `chapters/chapter_${String(currentChapter.chapter_number).padStart(3, '0')}/memory.json`,
        desc: '当前章动态记忆',
        action: 'chapter_content',
      })
    }
    return items
  }, [currentNovel?.id, activeVolume?.id, currentChapter?.id])

  if (!currentNovel) {
    return (
      <div className={styles.empty}>
        <span>选择小说后显示 AI 工作台</span>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>AI 工作台</div>
      <div className={styles.toolbar}>
        <Segmented
          size="small"
          value={mode}
          onChange={(value) => setMode(value as PanelMode)}
          options={[
            { label: '上下文', value: 'context' },
            { label: '待审阅', value: 'review' },
            { label: '日志', value: 'logs' },
            { label: '对话', value: 'chat' },
          ]}
        />
      </div>

      {loading ? (
        <div className={styles.loading}><Spin size="small" /></div>
      ) : null}

      {mode === 'context' ? (
        <div className={styles.sectionBody}>
          <Typography.Text className={styles.muted}>本次创作读取的真实依赖</Typography.Text>
          <List
            size="small"
            dataSource={contextFiles}
            renderItem={(item) => (
              <List.Item
                className={styles.listItem}
                actions={[
                  <Button key="open" type="link" size="small" onClick={() => openContextTarget(item.action)}>
                    打开
                  </Button>,
                ]}
              >
                <List.Item.Meta title={<span className={styles.fileName}>{item.label}</span>} description={item.desc} />
              </List.Item>
            )}
          />
          <Divider className={styles.divider} />
          <Typography.Text className={styles.muted}>当前门禁</Typography.Text>
          <div className={styles.gates}>
            <Tag color={activeVolume?.review_status === 'approved' ? 'green' : 'orange'}>
              {activeVolume ? (activeVolume.review_status === 'approved' ? '分卷已审批' : '分卷待审批') : '未选分卷'}
            </Tag>
            <Tag color={currentChapter?.final_approved ? 'green' : 'default'}>
              {currentChapter ? (currentChapter.final_approved ? '本章已定稿' : '本章未定稿') : '未选章节'}
            </Tag>
          </div>
        </div>
      ) : null}

      {mode === 'review' ? (
        <div className={styles.sectionBody}>
          {proposals.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="当前没有待审阅提案" />
          ) : (
            <List
              size="small"
              dataSource={proposals}
              renderItem={(item) => (
                <List.Item className={styles.reviewItem}>
                  <div className={styles.reviewHeader}>
                    <Tag>{item.entity_type}</Tag>
                    <span className={styles.reviewName}>{item.entity_name}</span>
                  </div>
                  <div className={styles.reviewReason}>{item.reason || '等待作者确认是否入库'}</div>
                  <Space size={8}>
                    <Button size="small" type="primary" icon={<CheckOutlined />} onClick={() => handleProposal(item.id, 'approve')}>
                      通过
                    </Button>
                    <Button size="small" icon={<CloseOutlined />} onClick={() => handleProposal(item.id, 'reject')}>
                      拒绝
                    </Button>
                  </Space>
                </List.Item>
              )}
            />
          )}
        </div>
      ) : null}

      {mode === 'logs' ? (
        <div className={styles.sectionBody}>
          <List
            size="small"
            dataSource={jobs}
            locale={{ emptyText: '暂无 AI 日志' }}
            renderItem={(job) => (
              <List.Item className={styles.logItem}>
                <div className={styles.logHeader}>
                  <span>{job.job_type}</span>
                  <Tag color={job.status === 'completed' ? 'green' : job.status === 'failed' ? 'red' : 'blue'}>
                    {job.status}
                  </Tag>
                </div>
                <div className={styles.logMessage}>{job.progress_message || '无进度信息'}</div>
                {job.error_message ? <div className={styles.logError}>{job.error_message}</div> : null}
              </List.Item>
            )}
          />
        </div>
      ) : null}

      {mode === 'chat' ? (
        <div className={styles.chatPane}>
          <div className={styles.chatList}>
            {chatMessages.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="可以直接要求 AI 检查节奏、润色正文或核对设定" />
            ) : (
              chatMessages.map((item, index) => (
                <div key={`${item.role}-${index}`} className={item.role === 'user' ? styles.userBubble : styles.assistantBubble}>
                  {item.content}
                </div>
              ))
            )}
          </div>
          <div className={styles.chatComposer}>
            <Input.TextArea
              rows={3}
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="例如：检查这一章是否违反已确认设定，若有请指出需要修改的文件。"
            />
            <Button type="primary" icon={<SendOutlined />} onClick={sendChat} loading={chatting}>
              发送
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
