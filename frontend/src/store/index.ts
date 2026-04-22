import { create } from 'zustand'
import type { Novel, Character, Chapter, Worldbuilding, Volume } from '../types'

interface AppState {
  // 当前选中的小说
  currentNovel: Novel | null
  setCurrentNovel: (novel: Novel | null) => void

  // 当前选中的章节
  currentChapter: Chapter | null
  setCurrentChapter: (chapter: Chapter | null) => void

  // 当前视图
  currentView: 'outline' | 'characters' | 'worldbuilding' | 'chapter' | 'synopsis' | 'admin'
  setCurrentView: (view: AppState['currentView']) => void

  // 角色列表缓存（用于细纲校验）
  characters: Character[]
  setCharacters: (chars: Character[]) => void

  // 世界观缓存
  worldbuilding: Worldbuilding | null
  setWorldbuilding: (wb: Worldbuilding | null) => void

  // 章节列表
  chapters: Chapter[]
  setChapters: (chapters: Chapter[]) => void

  // 卷列表
  volumes: Volume[]
  setVolumes: (volumes: Volume[]) => void
}

export const useAppStore = create<AppState>((set) => ({
  currentNovel: null,
  setCurrentNovel: (novel) => set({ currentNovel: novel }),

  currentChapter: null,
  setCurrentChapter: (chapter) => set({ currentChapter: chapter }),

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
}))
