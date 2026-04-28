import { useEffect } from 'react'
import { Spin } from 'antd'
import { useParams } from 'react-router-dom'

import AppShell from '../../components/layout/AppShell'
import WorkspaceTabs from '../../components/layout/WorkspaceTabs'
import { api } from '../../api'
import { useAppStore } from '../../store'
import { loadNovelWorkspaceContext } from '../../services/workspaceLoader'
import OutlinePage from '../OutlinePage'
import CharactersPage from '../CharactersPage'
import WorldbuildingPage from '../WorldbuildingPage'
import ChapterPage from '../ChapterPage'
import VolumePage from '../VolumePage'
import AdminWorkflowPage from '../AdminWorkflowPage'
import NovelSynopsisPage from '../NovelSynopsisPage'
import BookVolumesPage from '../BookVolumesPage'
import RelationshipNetworkPage from '../RelationshipNetworkPage'

function EditorContent() {
  const { novelId } = useParams()
  const {
    openTabs,
    activeTabId,
    currentView,
    currentNovel,
    openNovelWorkspace,
    setCurrentNovel,
    setCurrentChapter,
    setCurrentVolume,
    setCharacters,
    setWorldbuilding,
    setChapters,
    setVolumes,
    openTab,
  } = useAppStore()
  const activeTab = openTabs.find(tab => tab.id === activeTabId) || null

  useEffect(() => {
    if (!novelId || (currentNovel?.id === novelId && activeTab?.novelId === novelId)) return

    let ignore = false
    void (async () => {
      const [novel, context] = await Promise.all([
        api.novels.get(novelId),
        loadNovelWorkspaceContext(novelId),
      ])

      if (ignore) return
      openNovelWorkspace(novel)
      setCharacters(context.characters)
      setWorldbuilding(context.worldbuilding)
      setChapters(context.chapters)
      setVolumes(context.volumes)
    })().catch(() => undefined)

    return () => {
      ignore = true
    }
  }, [novelId, currentNovel?.id])

  useEffect(() => {
    if (!activeTab || activeTab.type === 'admin' || !activeTab.novelId) {
      return
    }

    let ignore = false
    void (async () => {
      const [novel, context] = await Promise.all([
        api.novels.get(activeTab.novelId!),
        loadNovelWorkspaceContext(activeTab.novelId!),
      ])

      if (ignore) return
      setCurrentNovel(novel)
      setCharacters(context.characters)
      setWorldbuilding(context.worldbuilding)
      setChapters(context.chapters)
      setVolumes(context.volumes)
      if (activeTab.chapterId) {
        const matched = context.chapters.find(ch => ch.id === activeTab.chapterId) || activeTab.chapterSnapshot || null
        const chapterVolume = matched?.volume_id ? context.volumes.find(vol => vol.id === matched.volume_id) || null : null
        if (activeTab.type === 'chapter_synopsis') {
          if (chapterVolume) {
            openTab({ type: 'volume', novelSnapshot: novel, volumeSnapshot: chapterVolume })
          } else if (matched) {
            openTab({ type: 'chapter', novelSnapshot: novel, chapterSnapshot: matched })
          }
          return
        }
        setCurrentVolume(chapterVolume)
        setCurrentChapter(matched)
      } else if (activeTab.volumeId) {
        const matchedVolume = context.volumes.find(vol => vol.id === activeTab.volumeId) || activeTab.volumeSnapshot || null
        setCurrentVolume(matchedVolume)
        setCurrentChapter(null)
      } else {
        setCurrentVolume(null)
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
    case 'book_volumes': return <BookVolumesPage />
    case 'characters': return <CharactersPage />
    case 'relationship_network': return <RelationshipNetworkPage />
    case 'worldbuilding': return <WorldbuildingPage />
    case 'volume': return <VolumePage />
    case 'chapter_synopsis': return currentNovel ? <VolumePage /> : null
    case 'chapter': return <ChapterPage />
    default: return null
  }
}

export default function EditorPage() {
  return (
    <AppShell>
      <WorkspaceTabs />
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <EditorContent />
      </div>
    </AppShell>
  )
}
