import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { Suspense, lazy } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { antdTheme } from './styles/antdTheme'
import './styles/global.css'

const BookshelfPage = lazy(() => import('./pages/bookshelf/BookshelfPage'))
const EditorPage = lazy(() => import('./pages/editor/EditorPage'))
const PortalHomePage = lazy(() => import('./pages/portal/PortalHomePage'))

function RouteFallback() {
  return (
    <div
      style={{
        display: 'grid',
        minHeight: '100%',
        placeItems: 'center',
        background: '#061015',
        color: '#f7e7b4',
        fontSize: 15,
        letterSpacing: '0.12em',
      }}
    >
      仙途载入中
    </div>
  )
}

export default function App() {
  return (
    <ConfigProvider theme={antdTheme} locale={zhCN}>
      <BrowserRouter>
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<PortalHomePage />} />
            <Route path="/portal" element={<PortalHomePage />} />
            <Route path="/bookshelf" element={<BookshelfPage />} />
            <Route path="/editor/admin" element={<EditorPage />} />
            <Route path="/editor/:novelId/*" element={<EditorPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ConfigProvider>
  )
}
