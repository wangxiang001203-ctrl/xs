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
  created_at: string
}

export interface Character {
  id: string
  novel_id: string
  name: string
  role?: string
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
  synopsis_generated: boolean
  created_at: string
}

export interface Chapter {
  id: string
  novel_id: string
  volume_id?: string
  chapter_number: number
  title?: string
  content?: string
  word_count: number
  plot_summary?: string
  status: 'draft' | 'writing' | 'completed'
  created_at: string
  updated_at: string
}

export interface Synopsis {
  id: string
  chapter_id: string
  novel_id: string
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
  plot_summary_update?: string
}

export interface ModelCatalogItem {
  id: string
  name: string
}

export interface ModelProviderConfig {
  id: string
  name: string
  api_base: string
  api_key_source: string
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
