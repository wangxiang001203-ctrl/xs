import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import AppShell from './components/layout/AppShell'
import { useAppStore } from './store'
import OutlinePage from './pages/OutlinePage'
import CharactersPage from './pages/CharactersPage'
import WorldbuildingPage from './pages/WorldbuildingPage'
import ChapterPage from './pages/ChapterPage'
import { antdTheme } from './styles/antdTheme'
import './styles/global.css'

function MainContent() {
  const { currentView, currentNovel } = useAppStore()

  if (!currentNovel) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        height: '100%', flexDirection: 'column', gap: 12,
        color: 'var(--text-muted)', fontSize: 13,
      }}>
        <div style={{ fontSize: 32, color: 'var(--accent)' }}>墨笔</div>
        <div>从左侧选择或新建小说开始创作</div>
      </div>
    )
  }

  switch (currentView) {
    case 'outline': return <OutlinePage />
    case 'characters': return <CharactersPage />
    case 'worldbuilding': return <WorldbuildingPage />
    case 'chapter':
    case 'synopsis': return <ChapterPage />
    default: return null
  }
}

export default function App() {
  return (
    <ConfigProvider theme={antdTheme} locale={zhCN}>
      <AppShell>
        <MainContent />
      </AppShell>
    </ConfigProvider>
  )
}
