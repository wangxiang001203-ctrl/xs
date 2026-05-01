import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Input, Modal, Space, Tag, message } from 'antd'
import { CheckOutlined, SaveOutlined, ThunderboltOutlined, FileTextOutlined } from '@ant-design/icons'

import { api } from '../api'
import { useAppStore } from '../store'
import type { ChapterMemory, EntityProposal, Synopsis } from '../types'
import WritingToolbar from '../components/editor/WritingToolbar'
import styles from './ChapterPage.module.css'

const { TextArea } = Input

export default function ChapterPage() {
  const {
    currentNovel,
    currentChapter,
    currentVolume,
    volumes,
    chapters,
    setCurrentChapter,
    setCurrentVolume,
    setChapters,
    openTab,
    documentDrafts,
    patchDocumentDraft,
    clearDocumentDraft,
  } = useAppStore()
  const [synopsis, setSynopsis] = useState<Synopsis | null>(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [generatingContent, setGeneratingContent] = useState(false)
  const [savingContent, setSavingContent] = useState(false)
  const [approvingChapter, setApprovingChapter] = useState(false)
  const [pendingProposals, setPendingProposals] = useState<EntityProposal[]>([])
  const [chapterMemory, setChapterMemory] = useState<ChapterMemory | null>(null)
  const [handlingProposalId, setHandlingProposalId] = useState<string | null>(null)
  const [searchValue, setSearchValue] = useState('')
  const [compareOpen, setCompareOpen] = useState(false)
  const [synopsisOpen, setSynopsisOpen] = useState(false)
  const docKey = currentChapter ? `chapter:${currentChapter.id}` : null

  useEffect(() => {
    void loadData()
  }, [currentChapter?.id])

  useEffect(() => {
    if (!docKey) return
    patchDocumentDraft(docKey, { content })
  }, [docKey, content])

  async function loadData(ignoreDraft = false) {
    if (!currentNovel || !currentChapter) return
    setLoading(true)
    try {
      const draft = (ignoreDraft || !docKey ? null : documentDrafts[docKey]) as { content?: string } | null
      const chapterData = await api.chapters.get(currentNovel.id, currentChapter.id)
      syncChapter(chapterData)
      setContent(draft?.content ?? chapterData.content ?? '')
      try {
        const loadedSynopsis = await api.chapters.getSynopsis(currentNovel.id, currentChapter.id)
        setSynopsis(loadedSynopsis)
      } catch {
        setSynopsis(null)
      }
      await refreshReviewState(chapterData.id)
    } finally {
      setLoading(false)
    }
  }

  async function refreshReviewState(chapterId = currentChapter?.id) {
    if (!currentNovel || !chapterId) return
    const [proposals, memory] = await Promise.all([
      api.review.listProposals(currentNovel.id, { status: 'pending', chapterId }).catch(() => []),
      api.review.getChapterMemory(currentNovel.id, chapterId).catch(() => null),
    ])
    setPendingProposals(proposals)
    setChapterMemory(memory)
  }

  const activeVolume = useMemo(() => {
    if (!currentChapter?.volume_id) return null
    if (currentVolume?.id === currentChapter.volume_id) return currentVolume
    return volumes.find(volume => volume.id === currentChapter.volume_id) || null
  }, [currentChapter?.volume_id, currentVolume?.id, volumes])

  const gateWarnings = [
    !activeVolume ? '当前章节还没有归属分卷，请先在分卷细纲中规划这一章。' : null,
    activeVolume && activeVolume.plan_data?.book_plan_status !== 'approved' ? `《${activeVolume.title}》卷级规划尚未审批，正文暂不允许推进。` : null,
    activeVolume && activeVolume.review_status !== 'approved' ? `《${activeVolume.title}》本卷章节细纲尚未审批，正文暂不允许推进。` : null,
    !synopsis ? '当前章节还没有细纲，请先在分卷细纲页生成。' : null,
    synopsis && synopsis.review_status !== 'approved' ? '当前章节细纲尚未审批，请先回到本卷页面审批整卷细纲。' : null,
  ].filter(Boolean) as string[]

  const canGenerateContent = gateWarnings.length === 0
  const locked = gateWarnings.length > 0
  const searchCount = useMemo(() => {
    if (!searchValue.trim()) return 0
    return content.split(searchValue.trim()).length - 1
  }, [content, searchValue])

  function syncChapter(chapterData: NonNullable<typeof currentChapter>) {
    setCurrentChapter(chapterData)
    const exists = chapters.some(item => item.id === chapterData.id)
    setChapters(exists ? chapters.map(item => (item.id === chapterData.id ? chapterData : item)) : [...chapters, chapterData])
  }

  async function generateChapter() {
    if (!currentNovel || !currentChapter) return
    if (!canGenerateContent) {
      message.warning(gateWarnings[0] || '当前不满足生成正文的条件')
      return
    }
    setGeneratingContent(true)
    try {
      const generated = await api.ai.generateChapterDraft(currentNovel.id, currentChapter.id)
      setContent(generated.content || '')
      if (docKey) {
        patchDocumentDraft(docKey, {
          content: generated.content || '',
          updatedAt: new Date().toISOString(),
        })
      }
      message.success('AI 正文草稿已放入编辑器，确认后再保存或定稿')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '生成失败')
    } finally {
      setGeneratingContent(false)
    }
  }

  async function saveContent() {
    if (!currentNovel || !currentChapter) return
    setSavingContent(true)
    try {
      const updated = await api.chapters.update(currentNovel.id, currentChapter.id, { content })
      syncChapter(updated)
      if (docKey) clearDocumentDraft(docKey)
      message.success('正文已保存')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存失败')
    } finally {
      setSavingContent(false)
    }
  }

  async function approveChapter() {
    if (!currentNovel || !currentChapter) return
    if (pendingProposals.length > 0) {
      message.warning('本章还有设定更新提案，请先逐条处理')
      return
    }
    setApprovingChapter(true)
    try {
      if ((currentChapter.content || '') !== content) {
        const updated = await api.chapters.update(currentNovel.id, currentChapter.id, { content })
        syncChapter(updated)
        if (docKey) clearDocumentDraft(docKey)
      }
      const approved = await api.review.approveFinalChapter(currentNovel.id, currentChapter.id)
      syncChapter(approved)
      await refreshReviewState(currentChapter.id)
      if (approved.final_approved) {
        message.success('本章已定稿，下一章已解锁')
      } else {
        message.warning(approved.final_approval_note || '已生成设定更新提案，处理完后本章会自动定稿')
      }
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '定稿失败')
    } finally {
      setApprovingChapter(false)
    }
  }

  async function handleProposal(proposal: EntityProposal, action: 'approve' | 'reject') {
    if (!currentNovel || !currentChapter) return
    setHandlingProposalId(proposal.id)
    try {
      if (action === 'approve') {
        await api.review.approveProposal(currentNovel.id, proposal.id)
        message.success('已批准这条设定更新')
      } else {
        await api.review.rejectProposal(currentNovel.id, proposal.id)
        message.success('已拒绝这条设定更新')
      }
      const refreshed = await api.chapters.get(currentNovel.id, currentChapter.id)
      syncChapter(refreshed)
      await refreshReviewState(currentChapter.id)
      if (refreshed.final_approved) {
        message.success('本章设定提案已处理完，章节已自动定稿')
      }
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '处理失败')
    } finally {
      setHandlingProposalId(null)
    }
  }

  function proposalTitle(proposal: EntityProposal) {
    const actionMap: Record<string, string> = {
      create: '新增设定',
      update: '更新设定',
      record_event: '记录事件',
      record_relation: '写入关系',
    }
    const typeMap: Record<string, string> = {
      character: '人物',
      event: '事件',
      relation: '关系',
      item: '道具',
      artifact: '道具',
      location: '地点',
      faction: '势力',
    }
    return `${actionMap[proposal.action] || proposal.action} · ${typeMap[proposal.entity_type] || proposal.entity_type} · ${proposal.entity_name}`
  }

  function proposalDiffText(proposal: EntityProposal) {
    const payload = proposal.payload || {}
    const before = payload.before ? JSON.stringify(payload.before, null, 2) : ''
    const after = payload.after ? JSON.stringify(payload.after, null, 2) : ''
    const event = payload.event?.evidence_text || payload.relation?.evidence_text || ''
    return [
      event ? `证据：${event}` : '',
      before && before !== '{}' ? `原状态：\n${before}` : '',
      after && after !== '{}' ? `新状态：\n${after}` : '',
    ].filter(Boolean).join('\n\n') || '暂无结构化差异'
  }

  function backToVolumePlan() {
    if (!currentNovel || !activeVolume) return
    setCurrentVolume(activeVolume)
    setCurrentChapter(null)
    openTab({ type: 'volume', novelSnapshot: currentNovel, volumeSnapshot: activeVolume })
  }

  if (!currentNovel || !currentChapter) return <div className={styles.empty}>请选择章节正文</div>

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div>
          <div className={styles.chapterTitle}>{currentChapter.title || `第${currentChapter.chapter_number}章`}</div>
          <div className={styles.meta}>
            <Tag color={synopsis?.review_status === 'approved' ? 'green' : 'orange'}>
              {synopsis?.review_status === 'approved' ? '细纲已批' : '细纲待批'}
            </Tag>
            <Tag color={activeVolume?.review_status === 'approved' ? 'green' : 'orange'}>
              {!activeVolume ? '未分卷' : activeVolume.review_status === 'approved' ? '本卷已批' : '本卷待批'}
            </Tag>
            <Tag color={currentChapter.final_approved ? 'green' : 'default'}>
              {currentChapter.final_approved ? '已定稿' : '未定稿'}
            </Tag>
            <span>{content.length || 0} 字</span>
          </div>
        </div>
        {locked ? (
          <Space className={styles.headerActions} wrap>
            <Button icon={<FileTextOutlined />} onClick={backToVolumePlan} disabled={!activeVolume}>
              回到本卷细纲
            </Button>
          </Space>
        ) : (
          <Space className={styles.headerActions} wrap>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={generateChapter}
              loading={generatingContent}
              disabled={!canGenerateContent}
            >
              生成整章正文
            </Button>
            <Button icon={<FileTextOutlined />} onClick={() => setSynopsisOpen(true)} disabled={!synopsis}>
              查看细纲
            </Button>
            <Button icon={<SaveOutlined />} onClick={saveContent} loading={savingContent}>
              保存正文
            </Button>
            <Button
              danger
              icon={<CheckOutlined />}
              onClick={approveChapter}
              loading={approvingChapter}
              disabled={!content.trim() || !canGenerateContent || pendingProposals.length > 0}
            >
              提交定稿检查
            </Button>
          </Space>
        )}
      </div>

      {locked ? (
        <section className={styles.lockedPanel}>
          <div className={styles.lockedTitle}>正文暂未开放</div>
          <div className={styles.lockedText}>
            正文页只负责写已经审批通过的章节。当前章节还在分卷/细纲阶段，请先回到本卷页面一次性生成并审批整卷章节细纲。
          </div>
          <div className={styles.lockedReasons}>
            {gateWarnings.map((warning) => (
              <div key={warning} className={styles.lockedReason}>{warning}</div>
            ))}
          </div>
          <Button type="primary" icon={<FileTextOutlined />} onClick={backToVolumePlan} disabled={!activeVolume}>
            回到本卷细纲
          </Button>
        </section>
      ) : (
        <>
          {currentChapter.final_approval_note && !currentChapter.final_approved && (
            <Alert className={styles.alert} type="info" showIcon message={currentChapter.final_approval_note} />
          )}
          {pendingProposals.length > 0 && (
            <section className={styles.reviewPanel}>
              <div className={styles.reviewHeader}>
                <div>
                  <div className={styles.reviewTitle}>本章设定更新待审批</div>
                  <div className={styles.reviewMeta}>逐条确认后才会写入人物、事件、道具、地点和关系网；全部处理完会自动定稿。</div>
                </div>
                <Tag color="orange">{pendingProposals.length} 条待处理</Tag>
              </div>
              <div className={styles.proposalList}>
                {pendingProposals.map(proposal => (
                  <article key={proposal.id} className={styles.proposalItem}>
                    <div className={styles.proposalTopline}>
                      <div className={styles.proposalTitle}>{proposalTitle(proposal)}</div>
                      <Space>
                        <Button
                          size="small"
                          type="primary"
                          loading={handlingProposalId === proposal.id}
                          onClick={() => handleProposal(proposal, 'approve')}
                        >
                          批准
                        </Button>
                        <Button
                          size="small"
                          loading={handlingProposalId === proposal.id}
                          onClick={() => handleProposal(proposal, 'reject')}
                        >
                          拒绝
                        </Button>
                      </Space>
                    </div>
                    {proposal.reason && <div className={styles.proposalReason}>{proposal.reason}</div>}
                    <pre className={styles.proposalPayload}>{proposalDiffText(proposal)}</pre>
                  </article>
                ))}
              </div>
              {chapterMemory && (
                <div className={styles.memorySummary}>
                  <div className={styles.memoryTitle}>AI 章节记忆</div>
                  <div>{chapterMemory.summary || '暂无摘要'}</div>
                </div>
              )}
            </section>
          )}

          <div className={styles.main}>
            <section className={styles.editorShell}>
              <WritingToolbar
                title="正文"
                wordCount={content.length}
                searchValue={searchValue}
                searchCount={searchCount}
                onSearchChange={setSearchValue}
                onUndo={() => document.execCommand('undo')}
                onRedo={() => document.execCommand('redo')}
                onOpenVersions={() => setCompareOpen(true)}
                versionsDisabled={!currentChapter.content && !content}
              />
              <TextArea
                value={content}
                onChange={event => setContent(event.target.value)}
                className={styles.editor}
                autoSize={false}
                placeholder={loading ? '正在加载正文...' : '这里就是正文区。先在分卷细纲里确认本章要写什么，再回到这里手写或让 AI 生成整章。'}
              />
            </section>
          </div>
        </>
      )}

      <Modal
        title={
          <Space>
            <span>本章细纲</span>
            {synopsis ? (
              <Tag color={synopsis.review_status === 'approved' ? 'green' : 'orange'}>
                {synopsis.review_status === 'approved' ? '已批准' : '待审批'}
              </Tag>
            ) : null}
          </Space>
        }
        open={synopsisOpen}
        onCancel={() => setSynopsisOpen(false)}
        footer={null}
        width={860}
      >
        {synopsis ? (
          <SynopsisContent synopsis={synopsis} />
        ) : (
          <div className={styles.emptySynopsis}>本章还没有细纲。</div>
        )}
      </Modal>

      <Modal
        title="正文版本对比"
        open={compareOpen}
        onCancel={() => setCompareOpen(false)}
        footer={null}
        width={980}
      >
        <div className={styles.compareGrid}>
          <div>
            <div className={styles.compareTitle}>已保存版本</div>
            <pre className={styles.compareContent}>{currentChapter.content || '还没有保存过正文'}</pre>
          </div>
          <div>
            <div className={styles.compareTitle}>当前编辑区</div>
            <pre className={styles.compareContent}>{content || '当前没有内容'}</pre>
          </div>
        </div>
      </Modal>
    </div>
  )
}

function SynopsisContent({ synopsis }: { synopsis: Synopsis }) {
  return (
    <div className={styles.synopsisContent}>
      {synopsis.summary_line && (
        <div className={styles.synopsisSection}>
          <div className={styles.synopsisLabel}>本章摘要</div>
          <div className={styles.synopsisText}>{synopsis.summary_line}</div>
        </div>
      )}
      {synopsis.opening_scene && (
        <div className={styles.synopsisSection}>
          <div className={styles.synopsisLabel}>开场场景</div>
          <div className={styles.synopsisText}>{synopsis.opening_scene}</div>
        </div>
      )}
      {synopsis.opening_hook && (
        <div className={styles.synopsisSection}>
          <div className={styles.synopsisLabel}>开场钩子</div>
          <div className={styles.synopsisText}>{synopsis.opening_hook}</div>
        </div>
      )}
      {synopsis.development_events && synopsis.development_events.length > 0 && (
        <div className={styles.synopsisSection}>
          <div className={styles.synopsisLabel}>发展事件</div>
          <ul className={styles.synopsisList}>
            {synopsis.development_events.map((event: any, idx: number) => (
              <li key={idx}>{typeof event === 'string' ? event : event.description || JSON.stringify(event)}</li>
            ))}
          </ul>
        </div>
      )}
      {synopsis.ending_resolution && (
        <div className={styles.synopsisSection}>
          <div className={styles.synopsisLabel}>结尾收束</div>
          <div className={styles.synopsisText}>{synopsis.ending_resolution}</div>
        </div>
      )}
      {synopsis.ending_cliffhanger && (
        <div className={styles.synopsisSection}>
          <div className={styles.synopsisLabel}>章末悬念</div>
          <div className={styles.synopsisText}>{synopsis.ending_cliffhanger}</div>
        </div>
      )}
      {synopsis.content_md && (
        <div className={styles.synopsisSection}>
          <div className={styles.synopsisLabel}>完整细纲</div>
          <pre className={styles.synopsisMarkdown}>{synopsis.content_md}</pre>
        </div>
      )}
    </div>
  )
}
