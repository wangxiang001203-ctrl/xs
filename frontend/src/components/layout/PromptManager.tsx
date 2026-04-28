import { useEffect, useState } from 'react'
import { Button, Input, List, message, Modal, Radio, Space, Tag } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'

import { api } from '../../api'
import type { Novel, PromptSnippet } from '../../types'
import styles from './PromptManager.module.css'

interface Props {
  open: boolean
  currentNovel: Novel | null
  onClose: () => void
}

export default function PromptManager({ open, currentNovel, onClose }: Props) {
  const [items, setItems] = useState<PromptSnippet[]>([])
  const [editing, setEditing] = useState<PromptSnippet | null>(null)
  const [scope, setScope] = useState<'common' | 'project'>('project')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [content, setContent] = useState('')

  useEffect(() => {
    if (!open) return
    void load()
  }, [open, currentNovel?.id])

  async function load() {
    try {
      setItems(await api.prompts.list(currentNovel?.id))
    } catch {
      message.error('加载提示词失败')
    }
  }

  function startCreate() {
    setEditing(null)
    setScope(currentNovel ? 'project' : 'common')
    setTitle('')
    setDescription('')
    setContent('')
  }

  function startEdit(item: PromptSnippet) {
    setEditing(item)
    setScope(item.scope === 'common' ? 'common' : 'project')
    setTitle(item.title)
    setDescription(item.description || '')
    setContent(item.content)
  }

  async function save() {
    if (!title.trim() || !content.trim()) {
      message.warning('提示词简称和内容不能为空')
      return
    }
    try {
      const payload = {
        scope,
        novel_id: scope === 'project' ? currentNovel?.id : null,
        title,
        description,
        content,
      }
      if (editing) {
        await api.prompts.update(editing.id, payload)
      } else {
        await api.prompts.create(payload)
      }
      message.success('提示词已保存')
      startCreate()
      await load()
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存提示词失败')
    }
  }

  async function remove(item: PromptSnippet) {
    try {
      await api.prompts.delete(item.id)
      message.success('已删除提示词')
      await load()
      if (editing?.id === item.id) startCreate()
    } catch {
      message.error('删除失败')
    }
  }

  return (
    <Modal
      title="提示词管理"
      open={open}
      onCancel={onClose}
      footer={null}
      width={980}
    >
      <div className={styles.wrap}>
        <div className={styles.list}>
          <div className={styles.listHeader}>
            <span>提示词库</span>
            <Button size="small" icon={<PlusOutlined />} onClick={startCreate}>新建</Button>
          </div>
          <List
            dataSource={items}
            locale={{ emptyText: '暂无提示词' }}
            renderItem={item => (
              <List.Item
                actions={[
                  <Button key="edit" type="text" size="small" icon={<EditOutlined />} onClick={() => startEdit(item)} />,
                  <Button key="delete" type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => remove(item)} />,
                ]}
              >
                <List.Item.Meta
                  title={<Space><span>{item.title}</span><Tag>{item.scope === 'common' ? '公用' : '本书'}</Tag></Space>}
                  description={item.description || item.content.slice(0, 42)}
                />
              </List.Item>
            )}
          />
        </div>
        <div className={styles.editor}>
          <Radio.Group value={scope} onChange={event => setScope(event.target.value)}>
            <Radio value="project" disabled={!currentNovel}>当前小说</Radio>
            <Radio value="common">公用</Radio>
          </Radio.Group>
          <Input value={title} onChange={event => setTitle(event.target.value)} placeholder="提示词简称，例如：更燃的大纲打磨" />
          <Input value={description} onChange={event => setDescription(event.target.value)} placeholder="提示词简介，可选" />
          <Input.TextArea
            value={content}
            onChange={event => setContent(event.target.value)}
            autoSize={{ minRows: 14, maxRows: 22 }}
            placeholder="提示词内容"
          />
          <Button type="primary" onClick={save}>{editing ? '保存修改' : '保存提示词'}</Button>
        </div>
      </div>
    </Modal>
  )
}
