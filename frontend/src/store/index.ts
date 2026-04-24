import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { Novel, Character, Chapter, Worldbuilding, Volume } from '../types'
import {
  buildWorkspaceTitle,
  getWorkspaceTabId,
  type WorkspaceTab,
  type WorkspaceTabType,
} from '../utils/workspace'

type MainView = WorkspaceTabType | 'synopsis'
type WorkspaceMode = 'bookshelf' | 'editor'

interface OpenTabInput {
  type: WorkspaceTabType
  novelSnapshot?: Novel | null
  chapterSnapshot?: Chapter | null
  volumeSnapshot?: Volume | null
  closable?: boolean
}

interface AppState {
  workspaceMode: WorkspaceMode
  setWorkspaceMode: (mode: WorkspaceMode) => void
  openNovelWorkspace: (novel: Novel) => void
  openAdminWorkspace: () => void

  currentNovel: Novel | null
  setCurrentNovel: (novel: Novel | null) => void

  currentChapter: Chapter | null
  setCurrentChapter: (chapter: Chapter | null) => void

  currentVolume: Volume | null
  setCurrentVolume: (volume: Volume | null) => void

  currentView: MainView
  setCurrentView: (view: MainView) => void

  characters: Character[]
  setCharacters: (chars: Character[]) => void

  worldbuilding: Worldbuilding | null
  setWorldbuilding: (wb: Worldbuilding | null) => void

  chapters: Chapter[]
  setChapters: (chapters: Chapter[]) => void

  volumes: Volume[]
  setVolumes: (volumes: Volume[]) => void

  openTabs: WorkspaceTab[]
  activeTabId: string | null
  openTab: (input: OpenTabInput) => void
  activateTab: (tabId: string) => void
  closeTab: (tabId: string) => void

  documentDrafts: Record<string, Record<string, unknown>>
  patchDocumentDraft: (docKey: string, patch: Record<string, unknown>) => void
  replaceDocumentDraft: (docKey: string, draft: Record<string, unknown>) => void
  clearDocumentDraft: (docKey: string) => void
}

function buildTab(input: OpenTabInput): WorkspaceTab {
  const novel = input.novelSnapshot ?? null
  const chapter = input.chapterSnapshot ?? null
  const volume = input.volumeSnapshot ?? null
  return {
    id: getWorkspaceTabId(input.type, novel?.id, chapter?.id, volume?.id),
    type: input.type,
    title: buildWorkspaceTitle(input.type, novel, chapter, volume),
    novelId: novel?.id,
    chapterId: chapter?.id,
    volumeId: volume?.id,
    novelSnapshot: novel,
    chapterSnapshot: chapter,
    volumeSnapshot: volume,
    closable: input.closable ?? input.type !== 'admin',
  }
}

function nextActiveContext(openTabs: WorkspaceTab[], tabId: string) {
  const closeIndex = openTabs.findIndex(tab => tab.id === tabId)
  if (closeIndex === -1) return null
  const remaining = openTabs.filter(tab => tab.id !== tabId)
  if (remaining.length === 0) return { remaining, nextTab: null as WorkspaceTab | null }
  const nextTab = remaining[Math.min(closeIndex, remaining.length - 1)]
  return { remaining, nextTab }
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      workspaceMode: 'bookshelf',
      setWorkspaceMode: (mode) => set({ workspaceMode: mode }),
      openNovelWorkspace: (novel) =>
        set(() => {
          const tab = buildTab({ type: 'outline', novelSnapshot: novel, closable: false })
          return {
            workspaceMode: 'editor',
            currentNovel: novel,
            currentChapter: null,
            currentVolume: null,
            currentView: 'outline',
            characters: [],
            worldbuilding: null,
            chapters: [],
            volumes: [],
            openTabs: [tab],
            activeTabId: tab.id,
          }
        }),
      openAdminWorkspace: () =>
        set(() => {
          const tab = buildTab({ type: 'admin', closable: false })
          return {
            workspaceMode: 'editor',
            currentNovel: null,
            currentChapter: null,
            currentVolume: null,
            currentView: 'admin',
            characters: [],
            worldbuilding: null,
            chapters: [],
            volumes: [],
            openTabs: [tab],
            activeTabId: tab.id,
          }
        }),

      currentNovel: null,
      setCurrentNovel: (novel) =>
        set((state) => ({
          currentNovel: novel,
          openTabs: novel
            ? state.openTabs.map((tab) => {
                if (tab.novelId !== novel.id) return tab
                return {
                  ...tab,
                  novelSnapshot: novel,
                  title: buildWorkspaceTitle(tab.type, novel, tab.chapterSnapshot ?? null, tab.volumeSnapshot ?? state.currentVolume),
                }
              })
            : state.openTabs,
        })),

      currentChapter: null,
      setCurrentChapter: (chapter) =>
        set((state) => ({
          currentChapter: chapter,
          openTabs: chapter
            ? state.openTabs.map((tab) => {
                if (tab.chapterId !== chapter.id) return tab
                return {
                  ...tab,
                  chapterSnapshot: chapter,
                  title: buildWorkspaceTitle(tab.type, tab.novelSnapshot ?? state.currentNovel, chapter, tab.volumeSnapshot ?? state.currentVolume),
                }
              })
            : state.openTabs,
        })),

      currentVolume: null,
      setCurrentVolume: (volume) =>
        set((state) => ({
          currentVolume: volume,
          openTabs: volume
            ? state.openTabs.map((tab) => {
                if (tab.volumeId !== volume.id) return tab
                return {
                  ...tab,
                  volumeSnapshot: volume,
                  title: buildWorkspaceTitle(tab.type, tab.novelSnapshot ?? state.currentNovel, tab.chapterSnapshot ?? state.currentChapter, volume),
                }
              })
            : state.openTabs,
        })),

      currentView: 'outline',
      setCurrentView: (view) => set({ currentView: view }),

      characters: [],
      setCharacters: (chars) => set({ characters: chars }),

      worldbuilding: null,
      setWorldbuilding: (wb) => set({ worldbuilding: wb }),

      chapters: [],
      setChapters: (chapters) => set({ chapters }),

      volumes: [],
      setVolumes: (volumes) => set({ volumes }),

      openTabs: [],
      activeTabId: null,
      openTab: (input) =>
        set((state) => {
          const tab = buildTab(input)
          const exists = state.openTabs.find(existing => existing.id === tab.id)
          const openTabs = exists
            ? state.openTabs.map(existing => (existing.id === tab.id ? { ...existing, ...tab } : existing))
            : [...state.openTabs, tab]

          return {
            openTabs,
            activeTabId: tab.id,
            currentView: tab.type,
            currentNovel: tab.novelSnapshot ?? state.currentNovel,
            currentVolume: tab.type === 'volume' ? tab.volumeSnapshot ?? state.currentVolume : state.currentVolume,
            currentChapter: tab.type === 'chapter' || tab.type === 'chapter_synopsis'
              ? tab.chapterSnapshot ?? state.currentChapter
              : null,
          }
        }),
      activateTab: (tabId) =>
        set((state) => {
          const tab = state.openTabs.find(item => item.id === tabId)
          if (!tab) return {}
          return {
            activeTabId: tab.id,
            currentView: tab.type,
            currentNovel: tab.novelSnapshot ?? state.currentNovel,
            currentVolume: tab.type === 'volume' ? tab.volumeSnapshot ?? state.currentVolume : state.currentVolume,
            currentChapter: tab.type === 'chapter' || tab.type === 'chapter_synopsis'
              ? tab.chapterSnapshot ?? state.currentChapter
              : null,
          }
        }),
      closeTab: (tabId) =>
        set((state) => {
          const result = nextActiveContext(state.openTabs, tabId)
          if (!result) return {}
          if (!result.nextTab) {
            return {
              openTabs: result.remaining,
              activeTabId: null,
              currentVolume: null,
              currentChapter: null,
            }
          }
          return {
            openTabs: result.remaining,
            activeTabId: result.nextTab.id,
            currentView: result.nextTab.type,
            currentNovel: result.nextTab.novelSnapshot ?? state.currentNovel,
            currentVolume: result.nextTab.type === 'volume' ? result.nextTab.volumeSnapshot ?? state.currentVolume : state.currentVolume,
            currentChapter: result.nextTab.type === 'chapter' || result.nextTab.type === 'chapter_synopsis'
              ? result.nextTab.chapterSnapshot ?? state.currentChapter
              : null,
          }
        }),

      documentDrafts: {},
      patchDocumentDraft: (docKey, patch) =>
        set((state) => ({
          documentDrafts: {
            ...state.documentDrafts,
            [docKey]: {
              ...(state.documentDrafts[docKey] || {}),
              ...patch,
            },
          },
        })),
      replaceDocumentDraft: (docKey, draft) =>
        set((state) => ({
          documentDrafts: {
            ...state.documentDrafts,
            [docKey]: draft,
          },
        })),
      clearDocumentDraft: (docKey) =>
        set((state) => {
          const nextDrafts = { ...state.documentDrafts }
          delete nextDrafts[docKey]
          return { documentDrafts: nextDrafts }
        }),
    }),
    {
      name: 'mobi-workspace-store',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        currentNovel: state.currentNovel,
        currentChapter: state.currentChapter,
        currentVolume: state.currentVolume,
        currentView: state.currentView,
        openTabs: state.openTabs,
        activeTabId: state.activeTabId,
        documentDrafts: state.documentDrafts,
      }),
    },
  ),
)
