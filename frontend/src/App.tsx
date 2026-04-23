import { useEffect } from 'react'
import { ConfigProvider, Spin } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import AppShell from './components/layout/AppShell'
import { useAppStore } from './store'
import OutlinePage from './pages/OutlinePage'
import CharactersPage from './pages/CharactersPage'
import WorldbuildingPage from './pages/WorldbuildingPage'
import ChapterPage from './pages/ChapterPage'
import AdminWorkflowPage from './pages/AdminWorkflowPage'
import NovelSynopsisPage from './pages/NovelSynopsisPage'
import WorkspaceTabs from './components/layout/WorkspaceTabs'
import { api } from './api'
import { antdTheme } from './styles/antdTheme'
import './styles/global.css'

function MainContent() {
  const {
    openTabs,
    activeTabId,
    currentView,
    currentNovel,
    setCurrentNovel,
    setCurrentChapter,
    setCharacters,
    setWorldbuilding,
    setChapters,
    setVolumes,
  } = useAppStore()
  const activeTab = openTabs.find(tab => tab.id === activeTabId) || null

  useEffect(() => {
    if (!activeTab || activeTab.type === 'admin' || !activeTab.novelId) {
      return
    }

    let ignore = false
    void (async () => {
      const [novel, chars, wb, chs, vols] = await Promise.all([
        api.novels.get(activeTab.novelId!),
        api.characters.list(activeTab.novelId!),
        api.worldbuilding.get(activeTab.novelId!).catch(() => null),
        api.chapters.list(activeTab.novelId!),
        api.volumes.list(activeTab.novelId!).catch(() => []),
      ])

      if (ignore) return
      setCurrentNovel(novel)
      setCharacters(chars)
      setWorldbuilding(wb)
      setChapters(chs)
      setVolumes(vols)
      if (activeTab.chapterId) {
        const matched = chs.find(ch => ch.id === activeTab.chapterId) || activeTab.chapterSnapshot || null
        setCurrentChapter(matched)
      } else {
        setCurrentChapter(null)
      }
    })().catch(() => undefined)

    return () => {
      ignore = true
    }
  }, [activeTabId])

  if (activeTab?.type === 'admin' || currentView === 'admin') {
    return <AdminWorkflowPage />
  }

  if (!activeTab) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100%', flexDirection: 'column', gap: 12,
        color: 'var(--text-muted)', fontSize: 13,
      }}>
        <div style={{ fontSize: 32, color: 'var(--accent)' }}>墨笔</div>
        <div>从左侧结构里打开一个文档开始创作</div>
      </div>
    )
  }

  if (!currentNovel) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
        <Spin size="small" />
      </div>
    )
  }

  switch (activeTab.type) {
    case 'outline': return <OutlinePage />
    case 'novel_synopsis': return <NovelSynopsisPage />
    case 'characters': return <CharactersPage />
    case 'worldbuilding': return <WorldbuildingPage />
    case 'chapter': return <ChapterPage />
    default: return null
  }
}

export default function App() {
  return (
    <ConfigProvider theme={antdTheme} locale={zhCN}>
      <AppShell>
        <WorkspaceTabs />
        <div style={{ flex: 1, minHeight: 0 }}>
          <MainContent />
        </div>
      </AppShell>
    </ConfigProvider>
  )
}
