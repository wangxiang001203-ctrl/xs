import type { Chapter, Novel, Volume } from '../types'

export type WorkspaceTabType =
  | 'outline'
  | 'novel_synopsis'
  | 'characters'
  | 'worldbuilding'
  | 'volume'
  | 'chapter_synopsis'
  | 'chapter'
  | 'admin'

export interface WorkspaceTab {
  id: string
  type: WorkspaceTabType
  title: string
  novelId?: string
  chapterId?: string
  volumeId?: string
  worldbuildingSectionId?: string
  worldbuildingSectionName?: string
  novelSnapshot?: Novel | null
  chapterSnapshot?: Chapter | null
  volumeSnapshot?: Volume | null
  closable?: boolean
}

export function getWorkspaceTabId(type: WorkspaceTabType, novelId?: string, chapterId?: string, volumeId?: string, worldbuildingSectionId?: string) {
  if (type === 'admin') return 'admin'
  if (type === 'chapter') return `chapter:${chapterId || 'unknown'}`
  if (type === 'chapter_synopsis') return `chapter_synopsis:${chapterId || 'unknown'}`
  if (type === 'volume') return `volume:${volumeId || 'unknown'}`
  if (type === 'worldbuilding') return `worldbuilding:${novelId || 'global'}:${worldbuildingSectionId || 'overview'}`
  return `${type}:${novelId || 'global'}`
}

export function buildWorkspaceTitle(type: WorkspaceTabType, novel?: Novel | null, chapter?: Chapter | null, volume?: Volume | null, worldbuildingSectionName?: string | null) {
  void novel
  switch (type) {
    case 'outline':
      return '大纲'
    case 'novel_synopsis':
      return '简介'
    case 'characters':
      return '角色'
    case 'worldbuilding':
      return worldbuildingSectionName || '世界观'
    case 'volume':
      if (!volume) return '分卷'
      return `分卷 · ${volume.title}`
    case 'chapter_synopsis':
      if (!chapter) return '细纲'
      return `细纲 · ${chapter.title || `第${chapter.chapter_number}章`}`
    case 'chapter':
      if (!chapter) return '章节'
      return `正文 · ${chapter.title || `第${chapter.chapter_number}章`}`
    case 'admin':
      return '后台流程'
    default:
      return '文档'
  }
}

export function getDocumentDraftKey(tab: Pick<WorkspaceTab, 'type' | 'novelId' | 'chapterId' | 'volumeId'>) {
  switch (tab.type) {
    case 'outline':
      return tab.novelId ? `outline:${tab.novelId}` : null
    case 'novel_synopsis':
      return tab.novelId ? `novel_synopsis:${tab.novelId}` : null
    case 'worldbuilding':
      return tab.novelId ? `worldbuilding:${tab.novelId}` : null
    case 'volume':
      return tab.volumeId ? `volume:${tab.volumeId}` : null
    case 'chapter_synopsis':
      return tab.chapterId ? `chapter_synopsis:${tab.chapterId}` : null
    case 'chapter':
      return tab.chapterId ? `chapter:${tab.chapterId}` : null
    default:
      return null
  }
}
