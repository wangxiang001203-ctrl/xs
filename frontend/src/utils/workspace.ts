import type { Chapter, Novel } from '../types'

export type WorkspaceTabType =
  | 'outline'
  | 'novel_synopsis'
  | 'characters'
  | 'worldbuilding'
  | 'chapter'
  | 'admin'

export interface WorkspaceTab {
  id: string
  type: WorkspaceTabType
  title: string
  novelId?: string
  chapterId?: string
  novelSnapshot?: Novel | null
  chapterSnapshot?: Chapter | null
  closable?: boolean
}

export function getWorkspaceTabId(type: WorkspaceTabType, novelId?: string, chapterId?: string) {
  if (type === 'admin') return 'admin'
  if (type === 'chapter') return `chapter:${chapterId || 'unknown'}`
  return `${type}:${novelId || 'global'}`
}

export function buildWorkspaceTitle(type: WorkspaceTabType, novel?: Novel | null, chapter?: Chapter | null) {
  switch (type) {
    case 'outline':
      return novel ? `大纲 · ${novel.title}` : '大纲'
    case 'novel_synopsis':
      return novel ? `简介 · ${novel.title}` : '简介'
    case 'characters':
      return novel ? `角色 · ${novel.title}` : '角色'
    case 'worldbuilding':
      return novel ? `世界观 · ${novel.title}` : '世界观'
    case 'chapter':
      if (!chapter) return '章节'
      return chapter.title || `第${chapter.chapter_number}章`
    case 'admin':
      return '后台流程'
    default:
      return '文档'
  }
}

export function getDocumentDraftKey(tab: Pick<WorkspaceTab, 'type' | 'novelId' | 'chapterId'>) {
  switch (tab.type) {
    case 'outline':
      return tab.novelId ? `outline:${tab.novelId}` : null
    case 'novel_synopsis':
      return tab.novelId ? `novel_synopsis:${tab.novelId}` : null
    case 'worldbuilding':
      return tab.novelId ? `worldbuilding:${tab.novelId}` : null
    case 'chapter':
      return tab.chapterId ? `chapter:${tab.chapterId}` : null
    default:
      return null
  }
}
