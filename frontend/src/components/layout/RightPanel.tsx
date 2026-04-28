import { useMemo, useState } from 'react'
import { Button, Checkbox, Empty, Input, Space, Tag, Collapse, message } from 'antd'
import { CheckOutlined, CloseOutlined, SendOutlined, FileTextOutlined } from '@ant-design/icons'

import { api } from '../../api'
import { useAppStore } from '../../store'
import type { AIGenerationJob, EntityProposal } from '../../types'
import styles from './RightPanel.module.css'

interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  metadata?: {
    logs?: AIGenerationJob[]
    proposals?: EntityProposal[]
    contextFiles?: string[]
  }
}

export default function RightPanel() {
  const {
    currentNovel,
    currentChapter,
    currentVolume,
    volumes,
    currentView,
  } = useAppStore()
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatting, setChatting] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<string[]>([])
  const [showFileSelector, setShowFileSelector] = useState(false)

  const activeVolume = useMemo(() => {
    if (currentVolume) return currentVolume
    if (!currentChapter?.volume_id) return null
    return volumes.find(volume => volume.id === currentChapter.volume_id) || null
  }, [currentVolume?.id, currentChapter?.id, currentChapter?.volume_id, volumes])

  // 可选的上下文文件
  const availableFiles = useMemo(() => {
    if (!currentNovel) return []
    const files = [
      { id: 'outline', label: '总大纲', path: 'outline/outline.md' },
      { id: 'synopsis', label: '作品简介', path: 'book/synopsis.md' },
      { id: 'characters', label: '角色库', path: 'characters/characters.json' },
      { id: 'worldbuilding', label: '世界观', path: 'world/worldbuilding.json' },
    ]
    if (activeVolume) {
      files.push({
        id: 'volume',
        label: `第${activeVolume.volume_number}卷细纲`,
        path: `volumes/volume_${String(activeVolume.volume_number).padStart(2, '0')}/plan.md`,
      })
    }
    if (currentChapter) {
      files.push({
        id: 'chapter-synopsis',
        label: `第${currentChapter.chapter_number}章细纲`,
        path: `chapters/chapter_${String(currentChapter.chapter_number).padStart(3, '0')}/synopsis.json`,
      })
      files.push({
        id: 'chapter-content',
        label: `第${currentChapter.chapter_number}章正文`,
        path: `chapters/chapter_${String(currentChapter.chapter_number).padStart(3, '0')}/content.md`,
      })
      files.push({
        id: 'chapter-memory',
        label: `第${currentChapter.chapter_number}章记忆`,
        path: `chapters/chapter_${String(currentChapter.chapter_number).padStart(3, '0')}/memory.json`,
      })
    }
    return files
  }, [currentNovel?.id, activeVolume?.id, currentChapter?.id])

  // 默认上下文文件（根据当前页面自动选择）
  const defaultContextFiles = useMemo(() => {
    const defaults: string[] = []
    if (currentView === 'outline') {
      defaults.push('outline')
    } else if (currentView === 'characters') {
      defaults.push('characters', 'outline')
    } else if (currentView === 'worldbuilding') {
      defaults.push('worldbuilding', 'outline')
    } else if (currentChapter) {
      defaults.push('chapter-synopsis', 'chapter-content', 'characters', 'worldbuilding')
      if (activeVolume) defaults.push('volume')
    }
    return defaults
  }, [currentView, currentChapter?.id, activeVolume?.id])

  // 根据当前页面显示不同的提示
  const placeholder = useMemo(() => {
    if (currentView === 'outline') {
      return '输入你的小说想法，例如："我想写一个修仙小说，主角是个废柴逆袭的故事"'
    } else if (currentView === 'synopsis') {
      return '例如：帮我重新生成一个更吸引人的简介'
    } else if (currentChapter) {
      return '例如：生成大纲 / 检查这一章是否违反设定 / 润色这段正文'
    }
    return '例如：生成大纲 / 检查节奏 / 润色正文'
  }, [currentView, currentChapter])

  // 根据当前页面决定是否显示文件选择器
  const shouldShowFileSelector = useMemo(() => {
    // 大纲页面和简介页面不显示文件选择器
    return currentView !== 'outline' && currentView !== 'synopsis'
  }, [currentView])

  async function sendChat() {
    if (!currentNovel || !chatInput.trim()) return

    const userMessage: ChatMessage = {
      role: 'user',
      content: chatInput.trim(),
      timestamp: new Date(),
    }

    setChatMessages(prev => [...prev, userMessage])
    setChatting(true)
    const currentInput = chatInput.trim()
    setChatInput('')

    try {
      // 合并默认文件和用户选择的文件，去重
      const finalContextFiles = Array.from(new Set([...defaultContextFiles, ...selectedFiles]))

      const contextType = currentChapter
        ? 'chapter'
        : currentView === 'characters'
          ? 'characters'
          : currentView === 'worldbuilding'
            ? 'worldbuilding'
            : 'outline'

      // 获取最新的日志和提案
      const [jobs, proposals] = await Promise.all([
        api.ai.listJobs(currentNovel.id, 5).catch(() => [] as AIGenerationJob[]),
        api.review.listProposals(currentNovel.id, {
          status: 'pending',
          chapterId: currentChapter?.id,
          volumeId: activeVolume?.id,
        }).catch(() => [] as EntityProposal[]),
      ])

      const result = await api.ai.chat({
        novel_id: currentNovel.id,
        context_type: contextType,
        context_id: currentChapter?.id ?? null,
        messages: chatMessages
          .filter(m => m.role !== 'system')
          .map(item => ({ role: item.role, content: item.content })),
        user_message: currentInput,
      })

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: result.message,
        timestamp: new Date(),
        metadata: {
          logs: jobs,
          proposals: proposals,
          contextFiles: finalContextFiles,
        },
      }

      setChatMessages(prev => [...prev, assistantMessage])
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'AI 对话失败')
      const errorMessage: ChatMessage = {
        role: 'system',
        content: `错误: ${err?.response?.data?.detail || 'AI 对话失败'}`,
        timestamp: new Date(),
      }
      setChatMessages(prev => [...prev, errorMessage])
    } finally {
      setChatting(false)
    }
  }

  async function handleProposal(proposalId: string, action: 'approve' | 'reject') {
    if (!currentNovel) return
    try {
      const handler = action === 'approve' ? api.review.approveProposal : api.review.rejectProposal
      await handler(currentNovel.id, proposalId)
      message.success(action === 'approve' ? '提案已通过' : '提案已拒绝')

      // 刷新对话中的提案状态
      setChatMessages(prev => prev.map(msg => {
        if (msg.metadata?.proposals) {
          return {
            ...msg,
            metadata: {
              ...msg.metadata,
              proposals: msg.metadata.proposals.filter(p => p.id !== proposalId),
            },
          }
        }
        return msg
      }))
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '处理失败')
    }
  }

  if (!currentNovel) {
    return (
      <div className={styles.empty}>
        <span>选择小说后显示 AI 助手</span>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span>AI 助手</span>
        {shouldShowFileSelector && (
          <Button
            size="small"
            type="text"
            icon={<FileTextOutlined />}
            onClick={() => setShowFileSelector(!showFileSelector)}
          >
            选择参考文件
          </Button>
        )}
      </div>

      {showFileSelector && shouldShowFileSelector && (
        <div className={styles.fileSelector}>
          <div className={styles.fileSelectorTitle}>额外参考文件（默认已包含必要文件）</div>
          <Checkbox.Group
            value={selectedFiles}
            onChange={(values) => setSelectedFiles(values as string[])}
          >
            <Space direction="vertical" size={4}>
              {availableFiles.map(file => (
                <Checkbox key={file.id} value={file.id}>
                  <span className={styles.fileName}>{file.label}</span>
                  <span className={styles.filePath}>{file.path}</span>
                </Checkbox>
              ))}
            </Space>
          </Checkbox.Group>
        </div>
      )}

      <div className={styles.chatList}>
        {chatMessages.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              currentView === 'outline'
                ? '输入你的小说想法，AI 会帮你生成完整大纲'
                : '可以直接要求 AI 生成大纲、检查节奏、润色正文或核对设定'
            }
          />
        ) : (
          chatMessages.map((msg, index) => (
            <div key={index} className={styles.messageWrapper}>
              <div className={msg.role === 'user' ? styles.userBubble : msg.role === 'system' ? styles.systemBubble : styles.assistantBubble}>
                <div className={styles.messageContent}>{msg.content}</div>
                <div className={styles.messageTime}>
                  {msg.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>

              {/* 显示日志和提案 */}
              {msg.metadata && (msg.metadata.logs?.length || msg.metadata.proposals?.length || msg.metadata.contextFiles?.length) ? (
                <Collapse
                  size="small"
                  className={styles.metadata}
                  items={[
                    ...(msg.metadata.contextFiles?.length ? [{
                      key: 'context',
                      label: `参考文件 (${msg.metadata.contextFiles.length})`,
                      children: (
                        <div className={styles.contextFiles}>
                          {msg.metadata.contextFiles.map(fileId => {
                            const file = availableFiles.find(f => f.id === fileId)
                            return file ? (
                              <Tag key={fileId} className={styles.contextTag}>
                                {file.label}
                              </Tag>
                            ) : null
                          })}
                        </div>
                      ),
                    }] : []),
                    ...(msg.metadata.logs?.length ? [{
                      key: 'logs',
                      label: `AI 日志 (${msg.metadata.logs.length})`,
                      children: (
                        <div className={styles.logs}>
                          {msg.metadata.logs.map(job => (
                            <div key={job.id} className={styles.logItem}>
                              <Tag color={job.status === 'completed' ? 'green' : job.status === 'failed' ? 'red' : 'blue'}>
                                {job.status}
                              </Tag>
                              <span>{job.job_type}</span>
                              {job.progress_message && <div className={styles.logMessage}>{job.progress_message}</div>}
                            </div>
                          ))}
                        </div>
                      ),
                    }] : []),
                    ...(msg.metadata.proposals?.length ? [{
                      key: 'proposals',
                      label: `待审阅 (${msg.metadata.proposals.length})`,
                      children: (
                        <div className={styles.proposals}>
                          {msg.metadata.proposals.map(proposal => (
                            <div key={proposal.id} className={styles.proposalItem}>
                              <div className={styles.proposalHeader}>
                                <Tag>{proposal.entity_type}</Tag>
                                <span className={styles.proposalName}>{proposal.entity_name}</span>
                              </div>
                              <div className={styles.proposalReason}>{proposal.reason || '等待作者确认'}</div>
                              <Space size={8}>
                                <Button
                                  size="small"
                                  type="primary"
                                  icon={<CheckOutlined />}
                                  onClick={() => handleProposal(proposal.id, 'approve')}
                                >
                                  通过
                                </Button>
                                <Button
                                  size="small"
                                  icon={<CloseOutlined />}
                                  onClick={() => handleProposal(proposal.id, 'reject')}
                                >
                                  拒绝
                                </Button>
                              </Space>
                            </div>
                          ))}
                        </div>
                      ),
                    }] : []),
                  ]}
                />
              ) : null}
            </div>
          ))
        )}
      </div>

      <div className={styles.chatComposer}>
        <Input.TextArea
          rows={3}
          value={chatInput}
          onChange={(event) => setChatInput(event.target.value)}
          onPressEnter={(e) => {
            if (e.shiftKey) return
            e.preventDefault()
            void sendChat()
          }}
          placeholder={placeholder}
        />
        <Button type="primary" icon={<SendOutlined />} onClick={sendChat} loading={chatting}>
          发送
        </Button>
      </div>
    </div>
  )
}
