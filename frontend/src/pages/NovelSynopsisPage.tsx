import { useEffect, useState } from 'react'
import { Button, Input, Modal, Space, message } from 'antd'
import { api } from '../api'
import { useAppStore } from '../store'
import styles from './NovelSynopsisPage.module.css'

export default function NovelSynopsisPage() {
  const { currentNovel, setCurrentNovel, documentDrafts, patchDocumentDraft } = useAppStore()
  const [value, setValue] = useState('')
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const docKey = currentNovel ? `novel_synopsis:${currentNovel.id}` : null

  useEffect(() => {
    if (!currentNovel) return
    const draft = (docKey ? documentDrafts[docKey] : null) as { value?: string; prompt?: string } | null
    setValue(draft?.value ?? currentNovel.synopsis ?? '')
    setPrompt(draft?.prompt ?? '')
  }, [currentNovel?.id])

  useEffect(() => {
    if (!docKey) return
    patchDocumentDraft(docKey, { value, prompt })
  }, [docKey, value, prompt])

  if (!currentNovel) return <div className={styles.empty}>请先选择小说</div>

  async function saveSynopsis() {
    if (!currentNovel) return
    setSaving(true)
    try {
      const updated = await api.novels.update(currentNovel.id, { synopsis: value })
      setCurrentNovel(updated)
      message.success('简介文件已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  async function regenerateSynopsis() {
    if (!currentNovel) return
    setGenerating(true)
    try {
      const res = await api.ai.generateBookSynopsis(currentNovel.id, prompt.trim() || undefined)
      setValue(res.synopsis || '')
      const updated = await api.novels.get(currentNovel.id)
      setCurrentNovel(updated)
      setModalOpen(false)
      message.success('简介已生成并更新')
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '简介生成失败')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <div className={styles.title}>简介</div>
        <Space size={8}>
          <Button size="small" onClick={() => setModalOpen(true)}>
            重新生成简介
          </Button>
          <Button type="primary" size="small" loading={saving} onClick={saveSynopsis}>
            保存
          </Button>
        </Space>
      </div>
      <Input.TextArea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        autoSize={{ minRows: 14, maxRows: 30 }}
        placeholder="这里是读者看到的小说简介，可手动编辑。"
        className={styles.editor}
      />
      <Modal
        title="生成简介"
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Input.TextArea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="可选：输入简介偏好，例如“强调成长线与复仇线，语气更燃”"
          autoSize={{ minRows: 2, maxRows: 4 }}
        />
        <Space className={styles.modalActions}>
          <Button loading={generating} onClick={regenerateSynopsis} type="primary">
            生成简介
          </Button>
        </Space>
      </Modal>
    </div>
  )
}
