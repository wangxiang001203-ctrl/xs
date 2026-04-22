import { useAppStore } from '../../store'
import styles from './RightPanel.module.css'

export default function RightPanel() {
  const { currentNovel, currentChapter, characters, worldbuilding } = useAppStore()

  if (!currentNovel) {
    return (
      <div className={styles.empty}>
        <span>选择小说后显示上下文</span>
      </div>
    )
  }

  return (
    <div className={styles.panel}>
      <div className={styles.header}>上下文</div>

      {/* 世界观速览 */}
      {worldbuilding?.realm_system && (
        <Section title="境界体系">
          <div className={styles.realmList}>
            {worldbuilding.realm_system.levels?.map((l, i) => (
              <span key={i} className={styles.realmTag}>
                {typeof l === 'string' ? l : l.name}
              </span>
            ))}
          </div>
        </Section>
      )}

      {/* 当前章节出场角色 */}
      {currentChapter && (
        <Section title={`第${currentChapter.chapter_number}章 出场角色`}>
          {characters.length === 0 ? (
            <span className={styles.empty}>暂无角色</span>
          ) : (
            characters.slice(0, 8).map(c => (
              <div key={c.id} className={styles.charRow}>
                <span className={styles.charName}>{c.name}</span>
                <span className={styles.charRealm}>{c.realm || '—'}</span>
              </div>
            ))
          )}
        </Section>
      )}

      {/* 角色总览 */}
      {!currentChapter && characters.length > 0 && (
        <Section title={`角色（${characters.length}）`}>
          {characters.map(c => (
            <div key={c.id} className={styles.charRow}>
              <span className={styles.charName}>{c.name}</span>
              <span className={styles.charRealm}>{c.realm || '—'}</span>
            </div>
          ))}
        </Section>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>{title}</div>
      <div className={styles.sectionBody}>{children}</div>
    </div>
  )
}
