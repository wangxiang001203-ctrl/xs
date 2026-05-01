import axios from 'axios'
import type {
  AIGenerationJob,
  AssistantChatResult,
  BookVolumePlan,
  Chapter,
  ChapterDraftResult,
  ChapterMemory,
  Character,
  EntityProposal,
  EntityEvent,
  EntityMention,
  EntityRelation,
  EntityGraphData,
  Novel,
  NovelGlobalState,
  Outline,
  OutlineChatResult,
  OutlineChatMessage,
  PromptSnippet,
  Synopsis,
  StoryEntity,
  Volume,
  VolumeWorkspace,
  WorkflowConfig,
  Worldbuilding,
} from '../types'

const JOB_POLL_INTERVAL_MS = 2000
const JOB_WAIT_TIMEOUT_MS = 30 * 60 * 1000

const http = axios.create({
  baseURL: '',
  timeout: 30000,
})

function sleep(ms: number) {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}

function buildJobError<T>(job: AIGenerationJob<T>) {
  const detail = job.result_payload ?? job.error_message ?? 'AI任务失败'
  const readableDetail = typeof detail === 'string'
    ? detail
    : (detail as any)?.message || (detail as any)?.reason || job.error_message || 'AI任务失败'
  const error: any = new Error(readableDetail)
  error.job = job
  error.response = { data: { detail: readableDetail, raw_detail: detail } }
  return error
}

async function waitForJob<T>(jobId: string): Promise<AIGenerationJob<T>> {
  const startedAt = Date.now()
  while (true) {
    const job = await http.get<AIGenerationJob<T>>(`/api/ai/jobs/${jobId}`).then(r => r.data)
    if (job.status === 'completed') {
      return job
    }
    if (job.status === 'failed') {
      throw buildJobError(job)
    }
    if (Date.now() - startedAt > JOB_WAIT_TIMEOUT_MS) {
      throw new Error('AI任务仍在后台处理中，请稍后刷新页面查看结果')
    }
    await sleep(JOB_POLL_INTERVAL_MS)
  }
}

async function runAiJob<TResult>(
  url: string,
  body: object,
  transform?: (payload: any) => TResult,
): Promise<TResult> {
  const job = await http.post<AIGenerationJob>(url, body).then(r => r.data)
  const finished = await waitForJob(job.id)
  const payload = finished.result_payload
  return transform ? transform(payload) : payload as TResult
}

// ── 项目 ──────────────────────────────────────────────────────────────────────
export const api = {
  novels: {
    list: () => http.get<Novel[]>('/api/projects').then(r => r.data),
    create: (data: Partial<Novel>) => http.post<Novel>('/api/projects', data).then(r => r.data),
    get: (id: string) => http.get<Novel>(`/api/projects/${id}`).then(r => r.data),
    update: (id: string, data: Partial<Novel>) => http.patch<Novel>(`/api/projects/${id}`, data).then(r => r.data),
    delete: (id: string) => http.delete(`/api/projects/${id}`).then(r => r.data),
    globalState: (id: string) => http.get<NovelGlobalState>(`/api/projects/${id}/global-state`).then(r => r.data),
  },

  outline: {
    list: (novelId: string) => http.get<Outline[]>(`/api/projects/${novelId}/outline`).then(r => r.data),
    latest: (novelId: string) => http.get<Outline>(`/api/projects/${novelId}/outline/latest`).then(r => r.data),
    create: (novelId: string, data: Partial<Outline>) => http.post<Outline>(`/api/projects/${novelId}/outline`, data).then(r => r.data),
    update: (novelId: string, outlineId: string, data: Partial<Outline>) =>
      http.patch<Outline>(`/api/projects/${novelId}/outline/${outlineId}`, data).then(r => r.data),
    reset: (novelId: string) => http.post<{ status: string }>(`/api/projects/${novelId}/outline/reset`).then(r => r.data),
    delete: (novelId: string, outlineId: string) =>
      http.delete<{ status: string }>(`/api/projects/${novelId}/outline/${outlineId}`).then(r => r.data),
    messages: (novelId: string) =>
      http.get<OutlineChatMessage[]>('/api/ai/outline/messages', { params: { novel_id: novelId } }).then(r => r.data),
    chat: (novelId: string, message: string, mode: 'revise' | 'rewrite' = 'revise') =>
      runAiJob<OutlineChatResult>('/api/ai/outline/chat', { novel_id: novelId, message, mode }),
  },

  characters: {
    list: (novelId: string) => http.get<Character[]>(`/api/projects/${novelId}/characters`).then(r => r.data),
    create: (novelId: string, data: Partial<Character>) =>
      http.post<Character>(`/api/projects/${novelId}/characters`, data).then(r => r.data),
    update: (novelId: string, charId: string, data: Partial<Character>) =>
      http.patch<Character>(`/api/projects/${novelId}/characters/${charId}`, data).then(r => r.data),
    delete: (novelId: string, charId: string) =>
      http.delete<{ ok: boolean; archived?: boolean; character?: Character }>(`/api/projects/${novelId}/characters/${charId}`).then(r => r.data),
  },

  entities: {
    bootstrap: (novelId: string) =>
      http.post<{ created: number; created_relations: number }>(`/api/projects/${novelId}/entities/bootstrap`).then(r => r.data),
    bootstrapGraph: (novelId: string) =>
      http.post<{ center_entity_id?: string | null; entity_count: number; created_entities: number; created_relations: number }>(
        `/api/projects/${novelId}/entities/graph/bootstrap`,
      ).then(r => r.data),
    graphData: (novelId: string) =>
      http.get<EntityGraphData>(`/api/projects/${novelId}/entities/graph-data`).then(r => r.data),
    list: (novelId: string, params?: { entityType?: string; status?: string; q?: string }) =>
      http.get<StoryEntity[]>(`/api/projects/${novelId}/entities`, {
        params: {
          entity_type: params?.entityType,
          status: params?.status,
          q: params?.q,
        },
      }).then(r => r.data),
    create: (novelId: string, data: Partial<StoryEntity>) =>
      http.post<StoryEntity>(`/api/projects/${novelId}/entities`, data).then(r => r.data),
    update: (novelId: string, entityId: string, data: Partial<StoryEntity>) =>
      http.patch<StoryEntity>(`/api/projects/${novelId}/entities/${entityId}`, data).then(r => r.data),
    scan: (novelId: string, chapterId?: string | null) =>
      http.post<{ scanned_chapters: number; created_mentions: number }>(`/api/projects/${novelId}/entities/scan`, {
        chapter_id: chapterId || null,
      }).then(r => r.data),
    state: (novelId: string, entityId: string, chapterNumber?: number) =>
      http.get<{ entity_id: string; chapter_number?: number | null; state: Record<string, any> }>(
        `/api/projects/${novelId}/entities/${entityId}/state`,
        { params: { chapter_number: chapterNumber } },
      ).then(r => r.data),
    mentions: (novelId: string, entityId: string) =>
      http.get<EntityMention[]>(`/api/projects/${novelId}/entities/${entityId}/mentions`).then(r => r.data),
    events: (novelId: string, entityId: string) =>
      http.get<EntityEvent[]>(`/api/projects/${novelId}/entities/${entityId}/events`).then(r => r.data),
    createEvent: (novelId: string, entityId: string, data: Partial<EntityEvent>) =>
      http.post<EntityEvent>(`/api/projects/${novelId}/entities/${entityId}/events`, data).then(r => r.data),
    recompute: (novelId: string, entityId: string) =>
      http.post<StoryEntity>(`/api/projects/${novelId}/entities/${entityId}/recompute`).then(r => r.data),
    relations: (novelId: string, entityId?: string) =>
      http.get<EntityRelation[]>(`/api/projects/${novelId}/entities/relations`, {
        params: { entity_id: entityId },
      }).then(r => r.data),
    createRelation: (novelId: string, data: Partial<EntityRelation>) =>
      http.post<EntityRelation>(`/api/projects/${novelId}/entities/relations`, data).then(r => r.data),
    updateRelation: (novelId: string, relationId: string, data: Partial<EntityRelation>) =>
      http.patch<EntityRelation>(`/api/projects/${novelId}/entities/relations/${relationId}`, data).then(r => r.data),
    deleteRelation: (novelId: string, relationId: string) =>
      http.delete(`/api/projects/${novelId}/entities/relations/${relationId}`).then(r => r.data),
  },

  worldbuilding: {
    get: (novelId: string) => http.get<Worldbuilding>(`/api/projects/${novelId}/worldbuilding`).then(r => r.data),
    update: (novelId: string, data: Partial<Worldbuilding>) =>
      http.put<Worldbuilding>(`/api/projects/${novelId}/worldbuilding`, data).then(r => r.data),
  },

  chapters: {
    list: (novelId: string) => http.get<Chapter[]>(`/api/projects/${novelId}/chapters`).then(r => r.data),
    create: (novelId: string, data: Partial<Chapter>) =>
      http.post<Chapter>(`/api/projects/${novelId}/chapters`, data).then(r => r.data),
    get: (novelId: string, chapterId: string) =>
      http.get<Chapter>(`/api/projects/${novelId}/chapters/${chapterId}`).then(r => r.data),
    update: (novelId: string, chapterId: string, data: Partial<Chapter>) =>
      http.patch<Chapter>(`/api/projects/${novelId}/chapters/${chapterId}`, data).then(r => r.data),
    delete: (novelId: string, chapterId: string) =>
      http.delete(`/api/projects/${novelId}/chapters/${chapterId}`).then(r => r.data),
    getSynopsis: (novelId: string, chapterId: string) =>
      http.get<Synopsis>(`/api/projects/${novelId}/chapters/${chapterId}/synopsis`).then(r => r.data),
    upsertSynopsis: (novelId: string, chapterId: string, data: Partial<Synopsis>) =>
      http.put<Synopsis>(`/api/projects/${novelId}/chapters/${chapterId}/synopsis`, data).then(r => r.data),
  },

  ai: {
    generateOutline: (novelId: string, idea: string) =>
      runAiJob<Outline>('/api/ai/generate/outline', { novel_id: novelId, idea }),
    generateWorldbuilding: (
      novelId: string,
      options?: { outlineId?: string; extraInstruction?: string; currentWorldbuilding?: Partial<Worldbuilding>; dryRun?: boolean },
    ) =>
      runAiJob<Worldbuilding>('/api/ai/generate/worldbuilding', {
        novel_id: novelId,
        outline_id: options?.outlineId,
        extra_instruction: options?.extraInstruction,
        current_worldbuilding: options?.currentWorldbuilding,
        dry_run: options?.dryRun,
      }),
    generateCharactersFromOutline: (
      novelId: string,
      options?: { outlineId?: string; dryRun?: boolean },
    ) =>
      runAiJob<Partial<Character>[]>(
        '/api/ai/generate/characters',
        { novel_id: novelId, outline_id: options?.outlineId, dry_run: options?.dryRun },
        (payload) => payload?.characters || [],
      ),
    generateChapterDraft: (novelId: string, chapterId: string, extraInstruction?: string) =>
      runAiJob<ChapterDraftResult>('/api/ai/generate/chapter', {
        novel_id: novelId,
        chapter_id: chapterId,
        extra_instruction: extraInstruction,
        dry_run: true,
      }),
    generateTitles: (novelId: string, extraInstruction?: string) =>
      runAiJob<{ titles: string[] }>('/api/ai/generate/titles', {
        novel_id: novelId,
        extra_instruction: extraInstruction,
      }),
    generateBookSynopsis: (novelId: string, extraInstruction?: string, options?: { dryRun?: boolean }) =>
      runAiJob<{ synopsis: string }>('/api/ai/generate/book-synopsis', {
        novel_id: novelId,
        extra_instruction: extraInstruction,
        dry_run: options?.dryRun || false,
      }),
    generateBookVolumes: (novelId: string, extraInstruction?: string) =>
      runAiJob<{ status: string; volume_count: number; approved: boolean; book_plan_markdown: string; volumes: Volume[] }>(
        '/api/ai/generate/book-volumes',
        {
          novel_id: novelId,
          extra_instruction: extraInstruction,
        },
      ),
    generateVolumeSynopsis: (novelId: string, volumeId: string, extraInstruction?: string) =>
      runAiJob<{ status: string; chapter_count?: number; pending_proposals?: EntityProposal[] }>('/api/ai/generate/volume-synopsis', {
        novel_id: novelId,
        volume_id: volumeId,
        extra_instruction: extraInstruction,
      }),
    generateChapterSegment: (
      novelId: string,
      chapterId: string,
      segment: 'opening' | 'middle' | 'ending',
      prevSegmentText: string,
      extraInstruction?: string,
      options?: { dryRun?: boolean },
    ) =>
      runAiJob<{ content: string; full_content: string; dry_run?: boolean }>('/api/ai/generate/chapter-segment', {
        novel_id: novelId,
        chapter_id: chapterId,
        segment,
        prev_segment_text: prevSegmentText,
        extra_instruction: extraInstruction,
        dry_run: options?.dryRun || false,
      }),
    getJob: <T = any>(jobId: string) =>
      http.get<AIGenerationJob<T>>(`/api/ai/jobs/${jobId}`).then(r => r.data),
    listJobs: <T = any>(novelId: string, limit = 20) =>
      http.get<AIGenerationJob<T>[]>('/api/ai/jobs', { params: { novel_id: novelId, limit } }).then(r => r.data),
  },

  assistant: {
    run: (payload: {
      novel_id: string
      context_type: string
      context_id?: string | null
      messages: Array<{ role: string; content: string }>
      user_message: string
      current_file?: Record<string, any> | null
      context_files?: string[]
    }) =>
      runAiJob<AssistantChatResult>('/api/assistant/run', payload),
  },

  volumes: {
    list: (novelId: string) => http.get<Volume[]>(`/api/projects/${novelId}/volumes/`).then(r => r.data),
    bookPlan: (novelId: string) => http.get<BookVolumePlan>(`/api/projects/${novelId}/volumes/book-plan`).then(r => r.data),
    approveBookPlan: (novelId: string) =>
      http.post<BookVolumePlan>(`/api/projects/${novelId}/volumes/book-plan/approve`).then(r => r.data),
    create: (novelId: string, data: { title: string; volume_number: number; description?: string }) =>
      http.post<Volume>(`/api/projects/${novelId}/volumes/`, data).then(r => r.data),
    update: (novelId: string, volumeId: string, data: Partial<Volume>) =>
      http.patch<Volume>(`/api/projects/${novelId}/volumes/${volumeId}`, data).then(r => r.data),
    delete: (novelId: string, volumeId: string) =>
      http.delete(`/api/projects/${novelId}/volumes/${volumeId}`).then(r => r.data),
    assignChapter: (novelId: string, volumeId: string, chapterId: string) =>
      http.post(`/api/projects/${novelId}/volumes/${volumeId}/assign-chapter/${chapterId}`).then(r => r.data),
    workspace: (novelId: string, volumeId: string) =>
      http.get<VolumeWorkspace>(`/api/projects/${novelId}/volumes/${volumeId}/workspace`).then(r => r.data),
    approve: (novelId: string, volumeId: string) =>
      http.post<Volume>(`/api/projects/${novelId}/volumes/${volumeId}/approve`).then(r => r.data),
  },

  review: {
    listProposals: (novelId: string, params?: { status?: string; chapterId?: string; volumeId?: string }) =>
      http.get<EntityProposal[]>(`/api/projects/${novelId}/review/proposals`, {
        params: {
          status: params?.status,
          chapter_id: params?.chapterId,
          volume_id: params?.volumeId,
        },
      }).then(r => r.data),
    approveProposal: (novelId: string, proposalId: string, note?: string) =>
      http.post<EntityProposal>(`/api/projects/${novelId}/review/proposals/${proposalId}/approve`, { note }).then(r => r.data),
    rejectProposal: (novelId: string, proposalId: string, note?: string) =>
      http.post<EntityProposal>(`/api/projects/${novelId}/review/proposals/${proposalId}/reject`, { note }).then(r => r.data),
    approveSynopsis: (novelId: string, chapterId: string) =>
      http.post<Synopsis>(`/api/projects/${novelId}/review/chapters/${chapterId}/approve-synopsis`).then(r => r.data),
    approveFinalChapter: (novelId: string, chapterId: string) =>
      http.post<Chapter>(`/api/projects/${novelId}/review/chapters/${chapterId}/approve-final`).then(r => r.data),
    getChapterMemory: (novelId: string, chapterId: string) =>
      http.get<ChapterMemory>(`/api/projects/${novelId}/review/chapters/${chapterId}/memory`).then(r => r.data),
  },

  admin: {
    getWorkflowConfig: () =>
      http.get<WorkflowConfig>('/api/admin/workflow-config').then(r => r.data),
    updateWorkflowConfig: (data: WorkflowConfig) =>
      http.put<WorkflowConfig>('/api/admin/workflow-config', data).then(r => r.data),
  },

  prompts: {
    list: (novelId?: string | null, scope?: string) =>
      http.get<PromptSnippet[]>('/api/prompts', {
        params: { novel_id: novelId || undefined, scope },
      }).then(r => r.data),
    create: (data: Partial<PromptSnippet>) =>
      http.post<PromptSnippet>('/api/prompts', data).then(r => r.data),
    update: (id: string, data: Partial<PromptSnippet>) =>
      http.patch<PromptSnippet>(`/api/prompts/${id}`, data).then(r => r.data),
    delete: (id: string) =>
      http.delete<{ status: string }>(`/api/prompts/${id}`).then(r => r.data),
  },
}
