import { Button, Dropdown, Input, Space, Tooltip } from 'antd'
import {
  DiffOutlined,
  RedoOutlined,
  SearchOutlined,
  SaveOutlined,
  UndoOutlined,
} from '@ant-design/icons'
import type { ReactNode } from 'react'
import styles from './WritingToolbar.module.css'

interface Props {
  title?: string
  titleExtra?: ReactNode
  statusText?: string
  wordCount?: number
  searchValue: string
  searchCount?: number
  onSearchChange: (value: string) => void
  onUndo?: () => void
  onRedo?: () => void
  onSaveVersion?: () => void
  onOpenVersions?: () => void
  saveVersionDisabled?: boolean
  versionsDisabled?: boolean
  saveVersionTooltip?: string
  versionsTooltip?: string
}

export default function WritingToolbar({
  title,
  titleExtra,
  statusText,
  wordCount,
  searchValue,
  searchCount = 0,
  onSearchChange,
  onUndo,
  onRedo,
  onSaveVersion,
  onOpenVersions,
  saveVersionDisabled,
  versionsDisabled,
  saveVersionTooltip = '把当前内容存成一个可回退节点',
  versionsTooltip = '查看已保存的存档节点',
}: Props) {
  return (
    <div className={styles.toolbar}>
      <div className={styles.left}>
        {title ? <span className={styles.title}>{title}</span> : null}
        {titleExtra}
        {typeof wordCount === 'number' ? <span className={styles.count}>{wordCount} 字</span> : null}
        {statusText ? <span className={styles.statusText}>{statusText}</span> : null}
      </div>
      <Space size={4} className={styles.actions}>
        <Tooltip title="撤回">
          <Button size="small" type="text" icon={<UndoOutlined />} onClick={onUndo}>
            撤回
          </Button>
        </Tooltip>
        <Tooltip title="重做">
          <Button size="small" type="text" icon={<RedoOutlined />} onClick={onRedo}>
            重做
          </Button>
        </Tooltip>
        <Dropdown
          trigger={['click']}
          dropdownRender={() => (
            <div className={styles.searchPanel}>
              <Input
                autoFocus
                allowClear
                value={searchValue}
                onChange={event => onSearchChange(event.target.value)}
                placeholder="搜索当前文档"
              />
              <span>{searchValue ? `找到 ${searchCount} 处` : '输入关键词搜索'}</span>
            </div>
          )}
        >
          <Button size="small" type="text" icon={<SearchOutlined />}>搜索高亮</Button>
        </Dropdown>
        {onSaveVersion ? (
          <Tooltip title={saveVersionTooltip}>
            <Button
              size="small"
              type="text"
              icon={<SaveOutlined />}
              disabled={saveVersionDisabled}
              onClick={onSaveVersion}
            >
              存档
            </Button>
          </Tooltip>
        ) : null}
        {onOpenVersions ? (
          <Tooltip title={versionsTooltip}>
            <Button
              size="small"
              type="text"
              icon={<DiffOutlined />}
              disabled={versionsDisabled}
              onClick={onOpenVersions}
            >
              查看存档
            </Button>
          </Tooltip>
        ) : null}
      </Space>
    </div>
  )
}
