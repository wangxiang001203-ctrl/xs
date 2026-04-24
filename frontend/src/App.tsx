import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import BookshelfPage from './pages/bookshelf/BookshelfPage'
import EditorPage from './pages/editor/EditorPage'
import { antdTheme } from './styles/antdTheme'
import './styles/global.css'

export default function App() {
  return (
    <ConfigProvider theme={antdTheme} locale={zhCN}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/bookshelf" replace />} />
          <Route path="/bookshelf" element={<BookshelfPage />} />
          <Route path="/editor/admin" element={<EditorPage />} />
          <Route path="/editor/:novelId/*" element={<EditorPage />} />
          <Route path="*" element={<Navigate to="/bookshelf" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  )
}
