import { useEffect, useMemo, useState } from 'react'
import { Button, Form, Modal, Select, Spin, Tag, message } from 'antd'
import { BookOutlined, PlusOutlined, SettingOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'

import { api } from '../../api'
import { useAppStore } from '../../store'
import { loadNovelWorkspaceContext } from '../../services/workspaceLoader'
import type { Novel } from '../../types'
import styles from './BookshelfPage.module.css'

export default function BookshelfPage() {
  const navigate = useNavigate()
  const {
    currentNovel,
    openNovelWorkspace,
    openAdminWorkspace,
    setCharacters,
    setWorldbuilding,
    setChapters,
    setVolumes,
  } = useAppStore()
  const [novels, setNovels] = useState<Novel[]>([])
  const [loading, setLoading] = useState(false)
  const [openingNovelId, setOpeningNovelId] = useState<string | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    void loadNovels()
  }, [])

  useEffect(() => {
    if (!currentNovel) return
    setNovels(prev => prev.map(novel => (novel.id === currentNovel.id ? { ...novel, ...currentNovel } : novel)))
  }, [currentNovel?.id, currentNovel?.title, currentNovel?.synopsis, currentNovel?.updated_at])

  const stats = useMemo(() => {
    const drafting = novels.filter(novel => novel.status === 'draft').length
    const writing = novels.filter(novel => novel.status === 'writing').length
    const completed = novels.filter(novel => novel.status === 'completed').length
    return { drafting, writing, completed }
  }, [novels])

  async function loadNovels() {
    setLoading(true)
    try {
      const list = await api.novels.list()
      setNovels(list)
    } catch {
      message.error('书架加载失败')
    } finally {
      setLoading(false)
    }
  }

  async function openNovel(novel: Novel) {
    setOpeningNovelId(novel.id)
    try {
      const context = await loadNovelWorkspaceContext(novel.id)
      setOpeningNovelId(null)
      openNovelWorkspace(novel)
      setCharacters(context.characters)
      setWorldbuilding(context.worldbuilding)
      setChapters(context.chapters)
      setVolumes(context.volumes)
      navigate(`/editor/${novel.id}`)
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '进入作品失败')
      setOpeningNovelId(null)
    }
  }

  function openAdmin() {
    openAdminWorkspace()
    navigate('/editor/admin')
  }

  function getNextDefaultTitle() {
    const used = new Set<number>()
    novels.forEach((novel) => {
      const match = /^默认书名(\d+)$/.exec(novel.title.trim())
      if (match) used.add(Number(match[1]))
    })

    let next = 1
    while (used.has(next)) next += 1
    return `默认书名${next}`
  }

  async function createNovel(values: { genre: string }) {
    setCreating(true)
    try {
      const defaultTitle = getNextDefaultTitle()
      const novel = await api.novels.create({ ...values, title: defaultTitle })
      setNovels(prev => [novel, ...prev])
      setCreateOpen(false)
      form.resetFields()
      setCreating(false)
      await openNovel(novel)
    } catch {
      message.error('创建失败')
      setCreating(false)
    }
  }

  function formatDate(value?: string) {
    if (!value) return '未更新'
    return new Date(value).toLocaleDateString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className={styles.page}>
      <nav className={styles.topNav}>
        <div className={styles.navBrand}>
          <span>墨笔</span>
          <small>书架</small>
        </div>
        <div className={styles.navActions}>
          <Button icon={<SettingOutlined />} onClick={openAdmin}>
            后台流程配置
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
            新建作品
          </Button>
        </div>
      </nav>

      <header className={styles.hero}>
        <div>
          <div className={styles.brand}>墨笔书架</div>
          <h1>先选一本书，再进入编辑器。</h1>
          <p>书架只管理作品，编辑器只处理单本书的创作结构，后面扩展封面、分类、搜索都会更干净。</p>
        </div>
      </header>

      <section className={styles.stats}>
        <div className={styles.statCard}>
          <span>全部作品</span>
          <strong>{novels.length}</strong>
        </div>
        <div className={styles.statCard}>
          <span>草稿</span>
          <strong>{stats.drafting}</strong>
        </div>
        <div className={styles.statCard}>
          <span>连载中</span>
          <strong>{stats.writing}</strong>
        </div>
        <div className={styles.statCard}>
          <span>已完结</span>
          <strong>{stats.completed}</strong>
        </div>
      </section>

      <main className={styles.shelf}>
        <div className={styles.sectionHeader}>
          <div>
            <h2>作品书架</h2>
            <span>每次只进入一本书的编辑工作区，避免多书标签混在一起。</span>
          </div>
          <Button onClick={loadNovels} loading={loading}>刷新</Button>
        </div>

        {loading ? (
          <div className={styles.loading}>
            <Spin size="small" />
          </div>
        ) : null}

        {!loading && novels.length === 0 ? (
          <div className={styles.empty}>
            <BookOutlined />
            <h3>书架还是空的</h3>
            <p>先创建第一本小说，然后进入编辑器生成大纲和分卷细纲。</p>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              新建作品
            </Button>
          </div>
        ) : null}

        <div className={styles.grid}>
          {novels.map(novel => (
            <button
              key={novel.id}
              type="button"
              className={styles.bookCard}
              onClick={() => openNovel(novel)}
              disabled={openingNovelId === novel.id}
            >
              <div className={styles.cover}>
                <BookOutlined />
              </div>
              <div className={styles.bookBody}>
                <div className={styles.bookTopline}>
                  <Tag color={novel.status === 'completed' ? 'green' : novel.status === 'writing' ? 'blue' : 'orange'}>
                    {novel.status === 'completed' ? '已完结' : novel.status === 'writing' ? '连载中' : '草稿'}
                  </Tag>
                  <span>{novel.genre}</span>
                </div>
                <h3>{novel.title}</h3>
                <p>{novel.synopsis || novel.idea || '还没有简介。进入编辑器后，可以先生成标题、简介和大纲。'}</p>
                <div className={styles.bookFooter}>
                  <span>更新 {formatDate(novel.updated_at)}</span>
                  <strong>{openingNovelId === novel.id ? '进入中...' : '进入编辑'}</strong>
                </div>
              </div>
            </button>
          ))}
        </div>
      </main>

      <Modal
        title="新建作品"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => form.submit()}
        okText="创建并进入"
        cancelText="取消"
        confirmLoading={creating}
      >
        <Form form={form} layout="vertical" onFinish={createNovel}>
          <Form.Item name="genre" label="类型" initialValue="玄幻修仙">
            <Select options={[
              { value: '玄幻修仙', label: '玄幻修仙' },
              { value: '都市', label: '都市' },
              { value: '科幻', label: '科幻' },
              { value: '历史', label: '历史' },
            ]} />
          </Form.Item>
          <p style={{ fontSize: '12px', color: '#999', marginTop: '-8px' }}>
            书名将自动生成为“默认书名1”“默认书名2”等，生成大纲时不会参考这个临时书名。
          </p>
        </Form>
      </Modal>
    </div>
  )
}
