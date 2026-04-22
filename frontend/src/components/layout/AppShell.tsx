import React from 'react'
import { Layout } from 'antd'
import LeftNav from './LeftNav'
import RightPanel from './RightPanel'
import styles from './AppShell.module.css'

const { Sider, Content } = Layout

interface Props {
  children: React.ReactNode
}

export default function AppShell({ children }: Props) {
  return (
    <Layout className={styles.shell}>
      {/* 左侧导航 */}
      <Sider width={220} className={styles.sider}>
        <LeftNav />
      </Sider>

      {/* 主编辑区 */}
      <Content className={styles.main}>
        {children}
      </Content>

      {/* 右侧上下文面板 */}
      <Sider width={240} className={styles.right}>
        <RightPanel />
      </Sider>
    </Layout>
  )
}
