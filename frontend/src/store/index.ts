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

interface OpenTabInput {
  type: WorkspaceTabType
  novelSnapshot?: Novel | null
  chapterSnapshot?: Chapter | null
  closable?: boolean
}

interface AppState {
  currentNovel: Novel | null
  setCurrentNovel: (novel: Novel | null) => void

  currentChapter: Chapter | null
  setCurrentChapter: (chapter: Chapter | null) => void

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
  return {
    id: getWorkspaceTabId(input.type, novel?.id, chapter?.id),
    type: input.type,
    title: buildWorkspaceTitle(input.type, novel, chapter),
    novelId: novel?.id,
    chapterId: chapter?.id,
    novelSnapshot: novel,
    chapterSnapshot: chapter,
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
                  title: buildWorkspaceTitle(tab.type, novel, tab.chapterSnapshot ?? null),
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
                  title: buildWorkspaceTitle(tab.type, tab.novelSnapshot ?? state.currentNovel, chapter),
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
            currentChapter: tab.type === 'chapter' ? tab.chapterSnapshot ?? state.currentChapter : null,
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
            currentChapter: tab.type === 'chapter' ? tab.chapterSnapshot ?? state.currentChapter : null,
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
              currentChapter: null,
            }
          }
          return {
            openTabs: result.remaining,
            activeTabId: result.nextTab.id,
            currentView: result.nextTab.type,
            currentNovel: result.nextTab.novelSnapshot ?? state.currentNovel,
            currentChapter: result.nextTab.type === 'chapter' ? result.nextTab.chapterSnapshot ?? state.currentChapter : null,
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
        currentView: state.currentView,
        openTabs: state.openTabs,
        activeTabId: state.activeTabId,
        documentDrafts: state.documentDrafts,
      }),
    },
  ),
)
