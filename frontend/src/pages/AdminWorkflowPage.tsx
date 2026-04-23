import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Input, Skeleton, Space, message } from 'antd'
import { api } from '../api'
import type { ModelConfig } from '../types'
import styles from './AdminWorkflowPage.module.css'

type FlowNode = { id: string; name: string; next: string }

export default function AdminWorkflowPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [flow, setFlow] = useState<FlowNode[]>([])
  const [prompts, setPrompts] = useState<Record<string, string>>({})
  const [modelConfig, setModelConfig] = useState<ModelConfig | null>(null)

  useEffect(() => {
    ;(async () => {
      try {
        const data = await api.admin.getWorkflowConfig()
        setFlow(data.flow || [])
        setPrompts(data.prompts || {})
        setModelConfig(data.model_config || null)
      } catch {
        message.error('加载后台流程配置失败')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  async function saveConfig() {
    setSaving(true)
    try {
      const res = await api.admin.updateWorkflowConfig({
        flow,
        prompts,
        model_config: modelConfig || { active_provider: '', active_model: '', providers: [] },
      })
      setFlow(res.flow || [])
      setPrompts(res.prompts || {})
      setModelConfig(res.model_config || null)
      message.success('流程与提示词已保存')
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const flowPairs = useMemo(() => {
    return flow.map((node) => {
      const next = flow.find(n => n.id === node.next)
      return { node, nextName: next?.name || '' }
    })
  }, [flow])

  if (loading) {
    return <Skeleton active style={{ padding: 16 }} />
  }

  return (
    <div className={styles.page}>
      <Card className={styles.card} title="创作流程图（后台可配置）">
        <div className={styles.flowWrap}>
          {flowPairs.map(({ node, nextName }) => (
            <div key={node.id} className={styles.flowItem}>
              <div className={styles.node}>{node.name}</div>
              {nextName ? <div className={styles.arrow}>→ {nextName}</div> : <div className={styles.end}>结束</div>}
            </div>
          ))}
        </div>
      </Card>

      <Card className={styles.card} title="系统提示词配置">
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {Object.entries(prompts).map(([key, value]) => (
            <div key={key}>
              <div className={styles.promptKey}>{key}</div>
              <Input.TextArea
                value={value}
                autoSize={{ minRows: 3, maxRows: 8 }}
                onChange={(e) => setPrompts(prev => ({ ...prev, [key]: e.target.value }))}
              />
            </div>
          ))}
        </Space>
        <Alert
          type="info"
          showIcon
          className={styles.tip}
          message="修改后点击保存即可生效。当前包含：全局系统提示词、大纲生成、标题生成、简介生成。"
        />
        <Button type="primary" loading={saving} onClick={saveConfig}>
          保存后台配置
        </Button>
      </Card>

      {modelConfig && (
        <Card className={styles.card} title="当前模型配置">
          <div className={styles.promptKey}>active_provider</div>
          <div>{modelConfig.active_provider}</div>
          <div className={styles.promptKey} style={{ marginTop: 12 }}>active_model</div>
          <div>{modelConfig.active_model}</div>
          <Alert
            type="info"
            showIcon
            className={styles.tip}
            message="左侧导航已支持直接切换模型。这里主要展示当前生效配置，保存流程配置时也会一并保留模型设置。"
          />
        </Card>
      )}
    </div>
  )
}
