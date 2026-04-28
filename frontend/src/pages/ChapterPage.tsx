import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Collapse, Input, Modal, Space, Tag, message } from 'antd'
import { CheckOutlined, SaveOutlined, ThunderboltOutlined, FileTextOutlined } from '@ant-design/icons'

import { api } from '../api'
import { useAppStore } from '../store'
import type { Synopsis } from '../types'
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
    setChapters,
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
  const [searchValue, setSearchValue] = useState('')
  const [compareOpen, setCompareOpen] = useState(false)
  const docKey = currentChapter ? `chapter:${currentChapter.id}` : null

  const previousChapter = useMemo(() => {
    if (!currentChapter || currentChapter.chapter_number <= 1) return null
    return [...chapters]
      .filter(item => item.chapter_number < currentChapter.chapter_number)
      .sort((a, b) => b.chapter_number - a.chapter_number)[0] || null
  }, [chapters, currentChapter?.id, currentChapter?.chapter_number])

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
    } finally {
      setLoading(false)
    }
  }

  const activeVolume = useMemo(() => {
    if (!currentChapter?.volume_id) return null
    if (currentVolume?.id === currentChapter.volume_id) return currentVolume
    return volumes.find(volume => volume.id === currentChapter.volume_id) || null
  }, [currentChapter?.volume_id, currentVolume?.id, volumes])

  const gateWarnings = [
    !activeVolume ? '当前章节还没有归属分卷，请先在分卷细纲中规划这一章。' : null,
    activeVolume && activeVolume.review_status !== 'approved' ? `《${activeVolume.title}》分卷细纲尚未审批，正文暂不允许推进。` : null,
    !synopsis ? '当前章节还没有细纲，请先在分卷细纲页生成并确认。' : null,
    synopsis && synopsis.review_status !== 'approved' ? '当前章节细纲尚未审批通过，正文暂不允许推进。' : null,
    previousChapter && !previousChapter.final_approved ? `第${previousChapter.chapter_number}章尚未人工定稿，不能继续推进本章。` : null,
  ].filter(Boolean) as string[]

  const canGenerateContent = gateWarnings.length === 0
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
    setApprovingChapter(true)
    try {
      const approved = await api.review.approveFinalChapter(currentNovel.id, currentChapter.id)
      syncChapter(approved)
      message.success('本章已定稿，下一章已解锁')
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '定稿失败')
    } finally {
      setApprovingChapter(false)
    }
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
        <Space>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={generateChapter}
            loading={generatingContent}
            disabled={!canGenerateContent}
          >
            生成整章正文
          </Button>
          <Button icon={<SaveOutlined />} onClick={saveContent} loading={savingContent}>
            保存正文
          </Button>
          <Button
            danger
            icon={<CheckOutlined />}
            onClick={approveChapter}
            loading={approvingChapter}
            disabled={!content.trim() || !canGenerateContent}
          >
            手动定稿
          </Button>
        </Space>
      </div>

      {gateWarnings.map((warning) => (
        <Alert key={warning} className={styles.alert} type="warning" showIcon message={warning} />
      ))}

      <div className={styles.main}>
        {synopsis && (
          <aside className={styles.synopsisPanel}>
            <Collapse
              defaultActiveKey={['synopsis']}
              items={[
                {
                  key: 'synopsis',
                  label: (
                    <Space>
                      <FileTextOutlined />
                      <span>细纲参考</span>
                      <Tag color={synopsis.review_status === 'approved' ? 'green' : 'orange'} style={{ marginLeft: 8 }}>
                        {synopsis.review_status === 'approved' ? '已批准' : '待审批'}
                      </Tag>
                    </Space>
                  ),
                  children: (
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
                  ),
                },
              ]}
            />
          </aside>
        )}
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
