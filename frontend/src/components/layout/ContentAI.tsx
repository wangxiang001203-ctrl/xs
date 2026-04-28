import { useEffect, useMemo, useState } from 'react'
import { Button, Checkbox, Empty, Input, Select, Space, Tag, Collapse, message, Modal, Radio } from 'antd'
import { CheckOutlined, CloseOutlined, SendOutlined, FileTextOutlined } from '@ant-design/icons'

import { api } from '../../api'
import { useAppStore } from '../../store'
import type { AIGenerationJob, AssistantContextFile, AssistantQuestion, EntityProposal, PromptSnippet } from '../../types'
import styles from './RightPanel.module.css'

interface ChatMessage {
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  metadata?: {
    logs?: AIGenerationJob[]
    proposals?: EntityProposal[]
    contextFiles?: AssistantContextFile[]
    questions?: AssistantQuestion[]
    changedFiles?: Array<AssistantContextFile & { status?: string }>
    mode?: string
  }
}

const JOB_TYPE_MAP: Record<string, string> = {
  'outline': '大纲生成',
  'titles': '标题生成',
  'book_synopsis': '作品简介生成',
  'chapter_synopsis': '章节细纲生成',
  'chapter_content': '章节正文生成',
  'volume_synopsis': '分卷细纲生成',
  'characters': '角色生成',
  'worldbuilding': '世界观生成',
  'chapter_segment': '章节片段生成',
  'chat': 'AI对话',
}

const STATUS_MAP: Record<string, string> = {
  'pending': '等待中',
  'running': '执行中',
  'completed': '已完成',
  'failed': '失败',
}

export default function ContentAI() {
  const {
    currentNovel,
    currentChapter,
    currentVolume,
    volumes,
    openTab,
  } = useAppStore()
  const [chatInput, setChatInput] = useState('')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatting, setChatting] = useState(false)
  const [selectedFiles, setSelectedFiles] = useState<string[]>([])
  const [showFileSelector, setShowFileSelector] = useState(false)
  const [prompts, setPrompts] = useState<PromptSnippet[]>([])
  const [savePromptOpen, setSavePromptOpen] = useState(false)
  const [promptScope, setPromptScope] = useState<'common' | 'project'>('project')
  const [promptTitle, setPromptTitle] = useState('')
  const [promptDesc, setPromptDesc] = useState('')
  const [promptContent, setPromptContent] = useState('')

  useEffect(() => {
    if (!currentNovel) return
    void api.prompts.list(currentNovel.id).then(setPrompts).catch(() => setPrompts([]))
  }, [currentNovel?.id])

  const activeVolume = useMemo(() => {
    if (currentVolume) return currentVolume
    if (!currentChapter?.volume_id) return null
    return volumes.find(volume => volume.id === currentChapter.volume_id) || null
  }, [currentVolume?.id, currentChapter?.id, currentChapter?.volume_id, volumes])

  // 可选的上下文文件（仅章节相关）
  const availableFiles = useMemo(() => {
    if (!currentNovel) return []
    const files = [
      { id: 'outline', label: '总大纲', path: 'outline/outline.md' },
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

  // 默认上下文文件（章节写作必需）
  const defaultContextFiles = useMemo(() => {
    const defaults: string[] = []
    if (currentChapter) {
      defaults.push('chapter-synopsis', 'chapter-content', 'characters', 'worldbuilding')
      if (activeVolume) defaults.push('volume')
    }
    return defaults
  }, [currentChapter?.id, activeVolume?.id])

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
        context_type: 'chapter',
        context_id: currentChapter?.id ?? null,
        messages: chatMessages
          .filter(m => m.role !== 'system')
          .map(item => ({ role: item.role, content: item.content })),
        user_message: currentInput,
        context_files: finalContextFiles,
      })

      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: result.message,
        timestamp: new Date(),
        metadata: {
          logs: jobs,
          proposals: result.pending_proposals || proposals,
          contextFiles: result.context_files || [],
          questions: result.questions || [],
          changedFiles: result.changed_files || [],
          mode: result.mode,
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

  function chooseQuestionOption(option: string) {
    setChatInput(prev => (prev.trim() ? `${prev.trim()}；${option}` : option))
  }

  function insertPrompt(promptId: string) {
    const prompt = prompts.find(item => item.id === promptId)
    if (!prompt) return
    setChatInput(prev => (prev.trim() ? `${prev.trim()}\n\n${prompt.content}` : prompt.content))
  }

  function startSavePrompt(content: string) {
    setPromptContent(content)
    setPromptTitle(content.slice(0, 16) || '新提示词')
    setPromptDesc('')
    setPromptScope(currentNovel ? 'project' : 'common')
    setSavePromptOpen(true)
  }

  async function savePrompt() {
    if (!promptTitle.trim() || !promptContent.trim()) {
      message.warning('提示词简称和内容不能为空。')
      return
    }
    try {
      await api.prompts.create({
        scope: promptScope,
        novel_id: promptScope === 'project' ? currentNovel?.id : null,
        title: promptTitle,
        description: promptDesc,
        content: promptContent,
      })
      setSavePromptOpen(false)
      if (currentNovel) setPrompts(await api.prompts.list(currentNovel.id))
      message.success('提示词已保存')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存提示词失败')
    }
  }

  function openChangedFile(file: AssistantContextFile) {
    if (!currentNovel) return
    if (file.kind === 'synopsis' || file.path.includes('synopsis')) {
      openTab({ type: 'chapter_synopsis', novelSnapshot: currentNovel, chapterSnapshot: currentChapter || undefined })
      return
    }
    if (file.kind === 'characters' || file.path.includes('characters')) {
      openTab({ type: 'characters', novelSnapshot: currentNovel })
      return
    }
    if (file.kind.startsWith('worldbuilding') || file.path.includes('world')) {
      openTab({ type: 'worldbuilding', novelSnapshot: currentNovel })
      return
    }
    if (file.kind === 'volume' && activeVolume) {
      openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: activeVolume })
      return
    }
    if (currentChapter) {
      openTab({ type: 'chapter', novelSnapshot: currentNovel, chapterSnapshot: currentChapter })
    }
  }

  function formatProposalPayload(value: unknown) {
    if (!value) return ''
    if (typeof value === 'string') return value
    if (typeof value !== 'object') return String(value)
    return Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== null && item !== undefined && String(item).trim() !== '')
      .map(([key, item]) => `${key}: ${Array.isArray(item) ? item.join('、') : String(item)}`)
      .join('\n')
  }

  if (!currentNovel) {
    return (
      <div className={styles.empty}>
        <span>选择小说后显示 AI 助手</span>
      </div>
    )
  }

  if (!currentChapter) {
    return (
      <div className={styles.empty}>
        <span>选择章节后显示正文 AI</span>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <span>正文 AI</span>
        <Button
          size="small"
          type="text"
          icon={<FileTextOutlined />}
          onClick={() => setShowFileSelector(!showFileSelector)}
        >
          选择参考文件
        </Button>
      </div>

      {showFileSelector && (
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
            description="可以要求 AI 检查节奏、润色正文或核对设定"
          />
        ) : (
          chatMessages.map((msg, index) => (
            <div key={index} className={styles.messageWrapper}>
              <div
                className={msg.role === 'user' ? styles.userBubble : msg.role === 'system' ? styles.systemBubble : styles.assistantBubble}
                onContextMenu={(event) => {
                  event.preventDefault()
                  startSavePrompt(msg.content)
                }}
              >
                <div className={styles.messageContent}>{msg.content}</div>
                <div className={styles.messageTime}>
                  {msg.timestamp.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </div>
              </div>

              {/* 显示日志和提案 */}
              {msg.metadata && (msg.metadata.logs?.length || msg.metadata.proposals?.length || msg.metadata.contextFiles?.length || msg.metadata.questions?.length || msg.metadata.changedFiles?.length) ? (
                <Collapse
                  size="small"
                  className={styles.metadata}
                  items={[
                    ...(msg.metadata.questions?.length ? [{
                      key: 'questions',
                      label: `需要确认 (${msg.metadata.questions.length})`,
                      children: (
                        <div className={styles.logs}>
                          {msg.metadata.questions.map((item, questionIndex) => (
                            <div key={`${item.question}-${questionIndex}`} className={styles.logItem}>
                              <strong>{item.question}</strong>
                              <div className={styles.contextFiles}>
                                {item.options.map(option => (
                                  <Tag key={option} className={styles.contextTag} onClick={() => chooseQuestionOption(option)}>
                                    {option}
                                  </Tag>
                                ))}
                              </div>
                            </div>
                          ))}
                        </div>
                      ),
                    }] : []),
                    ...(msg.metadata.contextFiles?.length ? [{
                      key: 'context',
                      label: `参考文件 (${msg.metadata.contextFiles.length})`,
                      children: (
                        <div className={styles.contextFiles}>
                          {msg.metadata.contextFiles.map(file => (
                            <Tag
                              key={`${file.id}-${file.path}`}
                              className={styles.contextTag}
                              style={{ cursor: 'pointer' }}
                              onClick={() => {
                                message.info(`文件路径: ${file.path}`)
                              }}
                            >
                              {file.label}
                            </Tag>
                          ))}
                        </div>
                      ),
                    }] : []),
                    ...(msg.metadata.changedFiles?.length ? [{
                      key: 'changed',
                      label: `改动文件 (${msg.metadata.changedFiles.length})`,
                      children: (
                        <div className={styles.contextFiles}>
                          {msg.metadata.changedFiles.map(file => (
                            <Button key={`${file.kind}-${file.id}`} size="small" onClick={() => openChangedFile(file)}>
                              {file.label}{file.status === 'pending' ? ' · 待确认' : ''}
                            </Button>
                          ))}
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
                                {STATUS_MAP[job.status] || job.status}
                              </Tag>
                              <span>{JOB_TYPE_MAP[job.job_type] || job.job_type}</span>
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
                              <div className={styles.proposalDiff}>
                                <div className={styles.proposalSide}>
                                  <div className={styles.proposalSideTitle}>修改前</div>
                                  <pre className={styles.proposalPre}>
                                    {formatProposalPayload(proposal.payload?.before) || '新增卡片，暂无旧内容'}
                                  </pre>
                                </div>
                                <div className={styles.proposalSide}>
                                  <div className={styles.proposalSideTitle}>修改后</div>
                                  <pre className={styles.proposalPre}>
                                    {formatProposalPayload(proposal.payload?.after || proposal.payload?.entry) || '等待 AI 补全内容'}
                                  </pre>
                                </div>
                              </div>
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
          placeholder="例如：检查这一章是否违反设定 / 润色这段正文"
        />
        <div className={styles.composerFooter}>
          <Select
            size="small"
            placeholder="选择提示词"
            popupMatchSelectWidth={false}
            style={{ minWidth: 150 }}
            options={prompts.map(item => ({
              value: item.id,
              label: `${item.scope === 'common' ? '公用' : '本书'} · ${item.title}`,
            }))}
            onChange={insertPrompt}
            value={undefined}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={sendChat} loading={chatting}>
            发送
          </Button>
        </div>
      </div>
      <Modal
        title="保存为提示词"
        open={savePromptOpen}
        onCancel={() => setSavePromptOpen(false)}
        onOk={savePrompt}
        okText="保存"
        cancelText="取消"
      >
        <Space direction="vertical" size={10} style={{ width: '100%' }}>
          <Radio.Group value={promptScope} onChange={event => setPromptScope(event.target.value)}>
            <Radio value="project">当前小说</Radio>
            <Radio value="common">公用</Radio>
          </Radio.Group>
          <Input value={promptTitle} onChange={event => setPromptTitle(event.target.value)} placeholder="提示词简称" />
          <Input value={promptDesc} onChange={event => setPromptDesc(event.target.value)} placeholder="提示词简介，可选" />
          <Input.TextArea
            value={promptContent}
            onChange={event => setPromptContent(event.target.value)}
            autoSize={{ minRows: 6, maxRows: 12 }}
            placeholder="提示词内容"
          />
        </Space>
      </Modal>
    </div>
  )
}
