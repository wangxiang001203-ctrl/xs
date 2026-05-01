// 类型定义

export interface Novel {
  id: string
  title: string
  genre: string
  idea?: string
  synopsis?: string
  status: 'draft' | 'writing' | 'completed'
  created_at: string
  updated_at: string
}

export interface Outline {
  id: string
  novel_id: string
  title?: string
  synopsis?: string
  selling_points?: string
  main_plot?: string
  content?: string
  ai_generated: boolean
  confirmed: boolean
  version: number
  version_note?: string | null
  created_at: string
}

export interface OutlineDraft {
  title?: string
  synopsis?: string
  selling_points?: string
  main_plot?: string
  content?: string
  base_outline_id?: string | null
  base_version?: number
  target_version?: number
  mode?: 'revise' | 'rewrite' | string
}

export interface OutlineChatResult {
  saved: boolean
  outline?: Outline
  draft_outline?: OutlineDraft
}

export interface OutlineChatMessage {
  id: string
  novel_id: string
  outline_id?: string | null
  role: 'user' | 'assistant' | 'system'
  content: string
  metadata?: Record<string, any>
  created_at: string
}

export interface Character {
  id: string
  novel_id: string
  name: string
  aliases?: string[]
  role?: string
  importance?: number
  gender?: string
  age?: number
  race?: string
  realm?: string
  realm_level: number
  faction?: string
  techniques?: string[]
  artifacts?: ArtifactRef[]
  appearance?: string
  personality?: string
  background?: string
  golden_finger?: string
  motivation?: string
  profile_md?: string
  relationships?: Relationship[]
  status: 'alive' | 'dead' | 'unknown'
  first_appearance_chapter?: number
  last_updated_chapter?: number
  created_at: string
  updated_at: string
}

export interface ArtifactRef {
  name: string
  grade?: string
  owner_id?: string
  desc?: string
}

export interface Relationship {
  target_id: string
  target_name: string
  relation: string
  desc?: string
}

export interface Worldbuilding {
  id: string
  novel_id: string
  overview?: string
  sections?: WorldbuildingSection[]
  power_system?: Record<string, any>[]
  factions?: Record<string, any>[]
  geography?: Record<string, any>[]
  core_rules?: Record<string, any>[]
  items?: Record<string, any>[]
}

export interface WorldbuildingSection {
  id?: string
  name: string
  description?: string
  generation_hint?: string
  content?: string
  entries: WorldbuildingEntry[]
}

export interface WorldbuildingEntry {
  id?: string
  name: string
  summary?: string
  details?: string
  tags?: string[]
  attributes?: Record<string, any>
}

export interface RealmSystem {
  name: string
  levels: RealmLevel[]
}

export interface RealmLevel {
  name: string
  level: number
  sub_levels?: number
  desc?: string
}

export interface Currency {
  name: string
  units: string[]
  exchange_rate: number[]
  note?: string
}

export interface WorldArtifact {
  id?: string
  name: string
  grade: string
  type?: string
  desc?: string
}

export interface WorldTechnique {
  id?: string
  name: string
  grade?: string
  type?: string
  desc?: string
}

export interface Faction {
  id?: string
  name: string
  type?: string
  desc?: string
  location?: string
}

export interface Geography {
  id?: string
  name: string
  type?: string
  desc?: string
}

export interface CustomRule {
  name: string
  desc: string
}

export interface Volume {
  id: string
  novel_id: string
  volume_number: number
  title: string
  description?: string
  target_words: number
  planned_chapter_count: number
  main_line?: string
  character_arc?: string
  ending_hook?: string
  plan_markdown?: string
  plan_data?: Record<string, any>
  synopsis_generated: boolean
  review_status: string
  approved_at?: string | null
  created_at: string
  chapter_count?: number
}

export interface BookVolumePlan {
  book_plan_markdown: string
  approved: boolean
  volumes: Volume[]
}

export interface Chapter {
  id: string
  novel_id: string
  volume_id?: string | null
  chapter_number: number
  title?: string
  content?: string
  word_count: number
  plot_summary?: string
  status: 'draft' | 'writing' | 'completed'
  final_approved: boolean
  final_approval_note?: string
  final_approved_at?: string | null
  created_at: string
  updated_at: string
}

export interface ChapterDraftResult {
  chapter_id: string
  chapter_number: number
  title?: string
  content: string
  word_count: number
  dry_run: boolean
  proposals_created?: number
  pending_proposals?: EntityProposal[]
}

export interface Synopsis {
  id: string
  chapter_id: string
  novel_id: string
  summary_line?: string
  content_md?: string
  opening_scene?: string
  opening_mood?: string
  opening_hook?: string
  opening_characters: string[]
  development_events: string[]
  development_conflicts: string[]
  development_characters: string[]
  ending_resolution?: string
  ending_cliffhanger?: string
  ending_next_hook?: string
  all_characters: string[]
  word_count_target: number
  hard_constraints?: string[]
  referenced_entities?: Record<string, string[]>
  review_status?: string
  approved_at?: string | null
  plot_summary_update?: string
}

export interface ChapterMemory {
  id: string
  novel_id: string
  chapter_id: string
  chapter_number: number
  summary?: string
  key_events: string[]
  state_changes: string[]
  inventory_changes: string[]
  proposed_entities: Array<{ type: string; name: string }>
  open_threads: string[]
  source_excerpt?: string
  created_at: string
  updated_at: string
}

export interface StoryEntity {
  id: string
  novel_id: string
  entity_type: string
  name: string
  aliases?: string[]
  summary?: string
  body_md?: string
  tags?: string[]
  current_state?: Record<string, any>
  status: string
  graph_role?: 'protagonist' | 'core' | 'supporting' | 'background' | string
  importance?: number
  graph_layer?: number
  graph_position?: Record<string, any>
  first_appearance_chapter?: number | null
  created_at: string
  updated_at: string
}

export interface EntityMention {
  id: string
  novel_id: string
  entity_id: string
  chapter_id?: string | null
  chapter_number?: number | null
  mention_text: string
  source: 'exact_match' | 'alias_match' | 'ai_inferred' | 'manual' | string
  confidence: number
  evidence_text?: string | null
  created_at: string
}

export interface EntityEvent {
  id: string
  novel_id: string
  entity_id: string
  event_type: string
  chapter_id?: string | null
  chapter_number?: number | null
  title?: string | null
  from_state?: Record<string, any>
  to_state?: Record<string, any>
  delta?: Record<string, any>
  source: string
  confidence: number
  evidence_text?: string | null
  reason?: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface EntityRelation {
  id: string
  novel_id: string
  source_entity_id: string
  target_entity_id?: string | null
  target_name?: string | null
  relation_type: string
  relation_strength?: number
  is_bidirectional?: boolean
  confidence?: number
  start_chapter?: number | null
  end_chapter?: number | null
  properties?: Record<string, any>
  evidence_text?: string | null
  status: string
  created_at: string
  updated_at: string
}

export interface EntityGraphNode {
  id: string
  name: string
  entity_type: string
  graph_role: string
  importance: number
  graph_layer: number
  status: string
  summary?: string | null
  current_state?: Record<string, any>
  graph_position?: Record<string, any>
}

export interface EntityGraphEdge {
  id: string
  source_entity_id: string
  target_entity_id?: string | null
  target_name?: string | null
  relation_type: string
  relation_strength: number
  is_bidirectional: boolean
  confidence: number
  status: string
  evidence_text?: string | null
  properties?: Record<string, any>
}

export interface EntityGraphData {
  center_entity_id?: string | null
  nodes: EntityGraphNode[]
  edges: EntityGraphEdge[]
  implicit_edge_count: number
}

export interface EntityProposal {
  id: string
  novel_id: string
  chapter_id?: string | null
  volume_id?: string | null
  entity_type: string
  action: string
  entity_name: string
  status: string
  reason?: string
  payload?: Record<string, any>
  created_at: string
  updated_at: string
  resolved_at?: string | null
}

export interface VolumeWorkspace {
  volume: Volume
  volume_synopsis_markdown?: string
  chapters: Array<{
    id: string
    chapter_number: number
    title?: string
    status: string
    final_approved: boolean
    synopsis_review_status: string
    summary_line?: string
    plot_summary_update?: string
    content_md?: string
    content_preview?: string
  }>
  pending_proposals: EntityProposal[]
}

export interface ModelCatalogItem {
  id: string
  name: string
  api_type?: string
  tools?: Record<string, any>[]
}

export interface ModelProviderConfig {
  id: string
  name: string
  api_base: string
  api_key_source: string
  api_type?: string
  models: ModelCatalogItem[]
}

export interface ModelConfig {
  active_provider: string
  active_model: string
  providers: ModelProviderConfig[]
}

export interface WorkflowConfig {
  flow: Array<{ id: string; name: string; next: string }>
  prompts: Record<string, string>
  model_config: ModelConfig
  assistant_policy?: Record<string, any>
}

export interface AIGenerationJob<T = any> {
  id: string
  novel_id: string
  chapter_id?: string | null
  volume_id?: string | null
  job_type: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress_message?: string | null
  result_payload?: T | null
  partial_text?: string | null
  error_message?: string | null
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  updated_at: string
}

export interface AssistantContextFile {
  id: string
  label: string
  path: string
  kind: string
}

export interface AssistantQuestion {
  question: string
  options: string[]
}

export interface AssistantWorkflowStep {
  id: string
  step_order: number
  title: string
  status: string
  detail?: string | null
  files?: AssistantContextFile[]
  payload?: Record<string, any>
  created_at?: string | null
  finished_at?: string | null
}

export interface AssistantChatResult {
  message: string
  mode?: 'clarify' | 'answer' | string
  questions?: AssistantQuestion[]
  context_files?: AssistantContextFile[]
  search_terms?: string[]
  changed_files?: Array<AssistantContextFile & { status?: string }>
  pending_proposals?: EntityProposal[]
  workflow_run_id?: string
  workflow_steps?: AssistantWorkflowStep[]
  intent?: string
  confidence?: number
  outline_result?: OutlineChatResult
  outline?: Outline
  draft_outline?: Record<string, any>
  synopsis_draft?: string
}

export interface PromptSnippet {
  id: string
  novel_id?: string | null
  scope: 'common' | 'project' | string
  title: string
  description?: string | null
  content: string
  created_at: string
  updated_at: string
}

// 三层记忆架构类型

// L1: 10章聚合快照
export interface ChapterSnapshot {
  id: string
  novel_id: string
  start_chapter: number
  end_chapter: number
  summary: string
  key_events: string[]
  character_arcs: string[]
  item_changes: string[]
  open_threads: string[]
  foreshadowing: string[]
  created_at: string
}

// L2: 全局知识索引
export interface GlobalCharacterStatus {
  character_id: string
  name: string
  current_realm: string
  current_location: string
  current_faction: string
  importance: number
  status: string
}

export interface GlobalItemStatus {
  item_id: string
  name: string
  grade: string
  current_holder: string
  holder_name: string
  location: string
}

export interface GlobalLocationStatus {
  location_id: string
  name: string
  type: string
  current_state: string
  significance: string
}

export interface GlobalEventEntry {
  chapter_number: number
  title: string
  event_type: string
  entities_involved: string[]
  description: string
}

export interface NovelGlobalState {
  // L0 原始数据摘要
  total_chapters: number
  total_words: number
  approved_chapters: number
  latest_chapter_number: number

  // L1 聚合快照
  snapshots: ChapterSnapshot[]

  // L2 全局知识索引
  characters: GlobalCharacterStatus[]
  items: GlobalItemStatus[]
  locations: GlobalLocationStatus[]
  event_timeline: GlobalEventEntry[]
  open_threads: string[]

  // 关键伏笔追踪
  unresolved_foreshadowing: Array<{
    thread: string
    introduced_chapter: number
    related_entities: string[]
  }>

  // 最后更新时间
  updated_at: string
}
