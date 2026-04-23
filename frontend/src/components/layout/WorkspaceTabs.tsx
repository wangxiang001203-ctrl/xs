import { BookOutlined, FileTextOutlined, GlobalOutlined, SettingOutlined, UnorderedListOutlined, UserOutlined } from '@ant-design/icons'
import { useAppStore } from '../../store'
import { getDocumentDraftKey } from '../../utils/workspace'
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

  if (openTabs.length === 0) {
    return null
  }

  return (
    <div className={styles.bar}>
      <div className={styles.scroll}>
        {openTabs.map((tab) => {
          const draftKey = getDocumentDraftKey(tab)
          const dirty = draftKey ? (documentDrafts[draftKey] as { dirty?: boolean } | undefined)?.dirty === true : false
          return (
            <button
              key={tab.id}
              type="button"
              className={`${styles.tab} ${tab.id === activeTabId ? styles.active : ''}`}
              onClick={() => activateTab(tab.id)}
            >
              <span className={styles.icon}>{tabIcon(tab.type)}</span>
              <span className={styles.label}>{tab.title}</span>
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
