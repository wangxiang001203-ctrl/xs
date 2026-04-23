import axios from 'axios'
import type {
  AIGenerationJob,
  Chapter,
  Character,
  Novel,
  Outline,
  Synopsis,
  Volume,
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
  const error: any = new Error(typeof detail === 'string' ? detail : job.error_message || 'AI任务失败')
  error.job = job
  error.response = { data: { detail } }
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
  },

  outline: {
    list: (novelId: string) => http.get<Outline[]>(`/api/projects/${novelId}/outline`).then(r => r.data),
    latest: (novelId: string) => http.get<Outline>(`/api/projects/${novelId}/outline/latest`).then(r => r.data),
    create: (novelId: string, data: Partial<Outline>) => http.post<Outline>(`/api/projects/${novelId}/outline`, data).then(r => r.data),
    update: (novelId: string, outlineId: string, data: Partial<Outline>) =>
      http.patch<Outline>(`/api/projects/${novelId}/outline/${outlineId}`, data).then(r => r.data),
  },

  characters: {
    list: (novelId: string) => http.get<Character[]>(`/api/projects/${novelId}/characters`).then(r => r.data),
    create: (novelId: string, data: Partial<Character>) =>
      http.post<Character>(`/api/projects/${novelId}/characters`, data).then(r => r.data),
    update: (novelId: string, charId: string, data: Partial<Character>) =>
      http.patch<Character>(`/api/projects/${novelId}/characters/${charId}`, data).then(r => r.data),
    delete: (novelId: string, charId: string) =>
      http.delete(`/api/projects/${novelId}/characters/${charId}`).then(r => r.data),
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
      options?: { outlineId?: string; extraInstruction?: string; currentWorldbuilding?: Partial<Worldbuilding> },
    ) =>
      runAiJob<Worldbuilding>('/api/ai/generate/worldbuilding', {
        novel_id: novelId,
        outline_id: options?.outlineId,
        extra_instruction: options?.extraInstruction,
        current_worldbuilding: options?.currentWorldbuilding,
      }),
    generateCharactersFromOutline: (novelId: string, outlineId?: string) =>
      runAiJob<Character[]>(
        '/api/ai/generate/characters',
        { novel_id: novelId, outline_id: outlineId },
        (payload) => payload?.characters || [],
      ),
    generateSynopsis: (payload: { novel_id: string; chapter_id: string; chapter_number: number; extra_instruction?: string }) =>
      runAiJob<{ status: string; auto_created_characters?: string[] }>('/api/ai/generate/synopsis', payload),
    validateCharacters: (novelId: string, names: string[]) =>
      http.post<{ valid: boolean; missing: string[] }>('/api/ai/validate/synopsis-characters', {
        novel_id: novelId,
        characters_in_synopsis: names,
      }).then(r => r.data),
    createMissingCharacters: (novelId: string, missingNames: string[]) =>
      http.post<{ created: string[] }>('/api/ai/synopsis/create-missing-characters', {
        novel_id: novelId,
        missing_names: missingNames,
      }).then(r => r.data),
    generateTitles: (novelId: string, extraInstruction?: string) =>
      runAiJob<{ titles: string[] }>('/api/ai/generate/titles', {
        novel_id: novelId,
        extra_instruction: extraInstruction,
      }),
    generateBookSynopsis: (novelId: string, extraInstruction?: string) =>
      runAiJob<{ synopsis: string }>('/api/ai/generate/book-synopsis', {
        novel_id: novelId,
        extra_instruction: extraInstruction,
      }),
    generateVolumeSynopsis: (novelId: string, volumeId: string, extraInstruction?: string) =>
      runAiJob<{ status: string; chapter_count?: number; auto_created_characters?: string[] }>('/api/ai/generate/volume-synopsis', {
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
    ) =>
      runAiJob<{ content: string; full_content: string }>('/api/ai/generate/chapter-segment', {
        novel_id: novelId,
        chapter_id: chapterId,
        segment,
        prev_segment_text: prevSegmentText,
        extra_instruction: extraInstruction,
      }),
    getJob: <T = any>(jobId: string) =>
      http.get<AIGenerationJob<T>>(`/api/ai/jobs/${jobId}`).then(r => r.data),
  },

  volumes: {
    list: (novelId: string) => http.get<Volume[]>(`/api/projects/${novelId}/volumes/`).then(r => r.data),
    create: (novelId: string, data: { title: string; volume_number: number; description?: string }) =>
      http.post<Volume>(`/api/projects/${novelId}/volumes/`, data).then(r => r.data),
    update: (novelId: string, volumeId: string, data: Partial<Volume>) =>
      http.patch<Volume>(`/api/projects/${novelId}/volumes/${volumeId}`, data).then(r => r.data),
    delete: (novelId: string, volumeId: string) =>
      http.delete(`/api/projects/${novelId}/volumes/${volumeId}`).then(r => r.data),
    assignChapter: (novelId: string, volumeId: string, chapterId: string) =>
      http.post(`/api/projects/${novelId}/volumes/${volumeId}/assign-chapter/${chapterId}`).then(r => r.data),
  },

  admin: {
    getWorkflowConfig: () =>
      http.get<WorkflowConfig>('/api/admin/workflow-config').then(r => r.data),
    updateWorkflowConfig: (data: WorkflowConfig) =>
      http.put<WorkflowConfig>('/api/admin/workflow-config', data).then(r => r.data),
  },
}
