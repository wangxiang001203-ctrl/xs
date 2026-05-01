import { useEffect, useMemo, useState } from 'react'
import { BookOutlined, FileTextOutlined, FolderOutlined, GlobalOutlined, SettingOutlined, UnorderedListOutlined, UserOutlined } from '@ant-design/icons'
import { Dropdown } from 'antd'
import { api } from '../../api'
import { useAppStore } from '../../store'
import type { WorkspaceTab } from '../../utils/workspace'
import { buildWorkspaceTitle, getDocumentDraftKey } from '../../utils/workspace'
import styles from './WorkspaceTabs.module.css'

function tabIcon(type: string) {
  switch (type) {
    case 'outline':
      return <UnorderedListOutlined />
    case 'novel_synopsis':
      return <FileTextOutlined />
    case 'characters':
      return <UserOutlined />
    case 'worldbuilding':
      return <GlobalOutlined />
    case 'volume':
      return <FolderOutlined />
    case 'chapter':
      return <BookOutlined />
    case 'admin':
      return <SettingOutlined />
    default:
      return <FileTextOutlined />
  }
}

export default function WorkspaceTabs() {
  const {
    openTabs,
    activeTabId,
    activateTab,
    closeTab,
    closeOtherTabs,
    closeTabsToRight,
    documentDrafts,
    chapters,
    volumes,
  } = useAppStore()
  const visibleTabs = openTabs
  const novelIds = useMemo(() => (
    Array.from(new Set(visibleTabs.map(tab => tab.novelId).filter(Boolean) as string[]))
  ), [visibleTabs])
  const [outlineConfirmedMap, setOutlineConfirmedMap] = useState<Record<string, boolean>>({})
  void outlineConfirmedMap

  useEffect(() => {
    let ignore = false
    async function loadOutlineStatuses() {
      const entries = await Promise.all(novelIds.map(async (novelId) => {
        const outlines = await api.outline.list(novelId).catch(() => [])
        return [novelId, outlines.some(item => item.confirmed)] as const
      }))
      if (!ignore) setOutlineConfirmedMap(Object.fromEntries(entries))
    }
    if (novelIds.length) void loadOutlineStatuses()
    return () => {
      ignore = true
    }
  }, [novelIds.join('|')])

  useEffect(() => {
    function handleOutlineChanged() {
      if (!novelIds.length) return
      void Promise.all(novelIds.map(async (novelId) => {
        const outlines = await api.outline.list(novelId).catch(() => [])
        return [novelId, outlines.some(item => item.confirmed)] as const
      })).then(entries => setOutlineConfirmedMap(Object.fromEntries(entries)))
    }

    window.addEventListener('mobi:outline-generated', handleOutlineChanged)
    window.addEventListener('mobi:outline-confirmed', handleOutlineChanged)
    window.addEventListener('mobi:outline-reset', handleOutlineChanged)
    return () => {
      window.removeEventListener('mobi:outline-generated', handleOutlineChanged)
      window.removeEventListener('mobi:outline-confirmed', handleOutlineChanged)
      window.removeEventListener('mobi:outline-reset', handleOutlineChanged)
    }
  }, [novelIds.join('|')])

  function getTabBadge(tab: WorkspaceTab) {
    if (tab.type === 'volume') {
      const volume = volumes.find(item => item.id === tab.volumeId) || tab.volumeSnapshot
      if (!volume) return null
      return {
        label: volume.review_status === 'approved' ? '已批' : '待批',
        tone: volume.review_status === 'approved' ? 'success' : 'warning',
      }
    }
    if (tab.type === 'chapter') {
      const chapter = chapters.find(item => item.id === tab.chapterId) || tab.chapterSnapshot
      if (!chapter) return null
      if (chapter.final_approved) return { label: '已定稿', tone: 'success' }
      return { label: chapter.status === 'writing' ? '写作中' : '待定稿', tone: chapter.status === 'writing' ? 'warning' : 'default' }
    }
    return null
  }

  if (visibleTabs.length === 0) {
    return null
  }

  return (
    <div className={styles.bar}>
      <div className={styles.scroll}>
        {visibleTabs.map((tab, index) => {
          const draftKey = getDocumentDraftKey(tab)
          const dirty = draftKey ? (documentDrafts[draftKey] as { dirty?: boolean } | undefined)?.dirty === true : false
          const title = buildWorkspaceTitle(tab.type, tab.novelSnapshot, tab.chapterSnapshot, tab.volumeSnapshot, tab.worldbuildingSectionName)
          const badge = getTabBadge(tab)
          const hasClosableOthers = visibleTabs.some(item => item.id !== tab.id && item.closable !== false)
          const hasClosableRight = visibleTabs.slice(index + 1).some(item => item.closable !== false)
          const menuItems = [
            {
              key: 'close',
              label: '关闭标签页',
              disabled: tab.closable === false,
            },
            {
              key: 'closeOthers',
              label: '关闭其他标签页',
              disabled: !hasClosableOthers,
            },
            {
              key: 'closeRight',
              label: '关闭右侧所有标签页',
              disabled: !hasClosableRight,
            },
          ]
          return (
            <Dropdown
              key={tab.id}
              trigger={['contextMenu']}
              menu={{
                items: menuItems,
                onClick: ({ key }) => {
                  if (key === 'close') closeTab(tab.id)
                  if (key === 'closeOthers') closeOtherTabs(tab.id)
                  if (key === 'closeRight') closeTabsToRight(tab.id)
                },
              }}
            >
              <button
                type="button"
                className={`${styles.tab} ${tab.id === activeTabId ? styles.active : ''}`}
                onClick={() => activateTab(tab.id)}
              >
                <span className={styles.icon}>{tabIcon(tab.type)}</span>
                <span className={styles.label}>{title || tab.title}</span>
                {badge ? <span className={`${styles.badge} ${badge.tone === 'success' ? styles.badgeSuccess : badge.tone === 'warning' ? styles.badgeWarning : ''}`}>{badge.label}</span> : null}
                {dirty && <span className={styles.dot} />}
                {tab.closable !== false && (
                  <span
                    className={styles.close}
                    onClick={(event) => {
                      event.stopPropagation()
                      closeTab(tab.id)
                    }}
                  >
                    ×
                  </span>
                )}
              </button>
            </Dropdown>
          )
        })}
      </div>
    </div>
  )
}
