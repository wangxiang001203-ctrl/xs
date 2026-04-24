import { BookOutlined, FileTextOutlined, FolderOutlined, GlobalOutlined, SettingOutlined, UnorderedListOutlined, UserOutlined } from '@ant-design/icons'
import { useAppStore } from '../../store'
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
    case 'chapter_synopsis':
      return <FileTextOutlined />
    case 'chapter':
      return <BookOutlined />
    case 'admin':
      return <SettingOutlined />
    default:
      return <FileTextOutlined />
  }
}

export default function WorkspaceTabs() {
  const { openTabs, activeTabId, activateTab, closeTab, documentDrafts } = useAppStore()
  const visibleTabs = openTabs.filter(tab => tab.type !== 'chapter_synopsis')

  if (visibleTabs.length === 0) {
    return null
  }

  return (
    <div className={styles.bar}>
      <div className={styles.scroll}>
        {visibleTabs.map((tab) => {
          const draftKey = getDocumentDraftKey(tab)
          const dirty = draftKey ? (documentDrafts[draftKey] as { dirty?: boolean } | undefined)?.dirty === true : false
          const title = buildWorkspaceTitle(tab.type, tab.novelSnapshot, tab.chapterSnapshot, tab.volumeSnapshot)
          return (
            <button
              key={tab.id}
              type="button"
              className={`${styles.tab} ${tab.id === activeTabId ? styles.active : ''}`}
              onClick={() => activateTab(tab.id)}
            >
              <span className={styles.icon}>{tabIcon(tab.type)}</span>
              <span className={styles.label}>{title || tab.title}</span>
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
          )
        })}
      </div>
    </div>
  )
}
