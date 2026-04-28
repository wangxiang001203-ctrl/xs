import React, { useState } from 'react'
import { Button, Layout } from 'antd'
import { BookOutlined, FormOutlined, SettingOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import LeftNav from './LeftNav'
import SettingsAI from './SettingsAI'
import ContentAI from './ContentAI'
import PromptManager from './PromptManager'
import { useAppStore } from '../../store'
import styles from './AppShell.module.css'

const { Sider, Content } = Layout

interface Props {
  children: React.ReactNode
}

export default function AppShell({ children }: Props) {
  const { currentNovel, currentView, currentChapter, setWorkspaceMode, openAdminWorkspace } = useAppStore()
  const navigate = useNavigate()
  const [promptManagerOpen, setPromptManagerOpen] = useState(false)

  // 根据当前视图决定显示哪个AI助手
  const isContentView = currentView === 'chapter' || currentView === 'chapter_synopsis'
  const showContentAI = isContentView && currentChapter

  function backToBookshelf() {
    setWorkspaceMode('bookshelf')
    navigate('/bookshelf')
  }

  function openAdmin() {
    openAdminWorkspace()
    navigate('/editor/admin')
  }

  return (
    <div className={styles.shell}>
      <div className={styles.topNav}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>墨笔</span>
          <span className={styles.brandSub}>{currentNovel ? '创作工作台' : '后台工作台'}</span>
        </div>
        <div className={styles.topActions}>
          <Button icon={<FormOutlined />} onClick={() => setPromptManagerOpen(true)}>
            提示词管理
          </Button>
          <Button icon={<SettingOutlined />} onClick={openAdmin}>
            后台流程配置
          </Button>
          <Button icon={<BookOutlined />} onClick={backToBookshelf}>
            书架
          </Button>
        </div>
      </div>

      <Layout className={styles.workspace}>
        {/* 左侧导航 */}
        <Sider width={220} className={styles.sider}>
          <LeftNav />
        </Sider>

        {/* 主编辑区 */}
        <Content className={styles.main}>
          {children}
        </Content>

        {/* 右侧AI助手 */}
        <Sider width={320} className={styles.right}>
          {showContentAI ? <ContentAI /> : <SettingsAI />}
        </Sider>
      </Layout>
      <PromptManager
        open={promptManagerOpen}
        currentNovel={currentNovel}
        onClose={() => setPromptManagerOpen(false)}
      />
    </div>
  )
}
