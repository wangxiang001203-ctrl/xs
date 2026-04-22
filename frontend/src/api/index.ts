import axios from 'axios'
import type { Novel, Outline, Character, Worldbuilding, Chapter, Synopsis, Volume } from '../types'

const http = axios.create({
  baseURL: 'http://localhost:8000',
  timeout: 30000,
})

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
    validateCharacters: (novelId: string, names: string[]) =>
      http.post<{ valid: boolean; missing: string[] }>('/api/ai/validate/synopsis-characters', {
        novel_id: novelId,
        characters_in_synopsis: names,
      }).then(r => r.data),
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
}

// SSE流式请求
export function streamRequest(
  url: string,
  body: object,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): AbortController {
  const ctrl = new AbortController()
  fetch(`http://localhost:8000${url}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: ctrl.signal,
  }).then(async res => {
    if (!res.ok) {
      onError(`HTTP ${res.status}`)
      return
    }
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const data = line.slice(6).trim()
        if (data === '[DONE]') { onDone(); return }
        try {
          const parsed = JSON.parse(data)
          if (parsed.error) { onError(parsed.error); return }
          if (parsed.text) onChunk(parsed.text)
        } catch { /* ignore */ }
      }
    }
    onDone()
  }).catch(err => {
    if (err.name !== 'AbortError') onError(err.message)
  })
  return ctrl
}

// 生成整卷细纲（SSE）
export function streamVolumeSynopsis(
  novelId: string, volumeId: string, extraInstruction: string | undefined,
  onChunk: (text: string) => void, onDone: () => void, onError: (err: string) => void,
): AbortController {
  return streamRequest(
    '/api/ai/generate/volume-synopsis',
    { novel_id: novelId, volume_id: volumeId, extra_instruction: extraInstruction },
    onChunk, onDone, onError,
  )
}

// 根据细纲生成角色（SSE）
export function streamGenerateCharacters(
  novelId: string,
  onChunk: (text: string) => void, onDone: () => void, onError: (err: string) => void,
): AbortController {
  return streamRequest(
    '/api/ai/generate/characters-from-synopsis',
    { novel_id: novelId },
    onChunk, onDone, onError,
  )
}

// 根据大纲生成世界观（SSE）
export function streamGenerateWorldbuilding(
  novelId: string,
  onChunk: (text: string) => void, onDone: () => void, onError: (err: string) => void,
): AbortController {
  return streamRequest(
    '/api/ai/generate/worldbuilding',
    { novel_id: novelId },
    onChunk, onDone, onError,
  )
}

// 分段生成正文（SSE）
export function streamChapterSegment(
  novelId: string, chapterId: string, segment: 'opening' | 'middle' | 'ending',
  prevSegmentText: string,
  onChunk: (text: string) => void, onDone: () => void, onError: (err: string) => void,
): AbortController {
  return streamRequest(
    '/api/ai/generate/chapter-segment',
    { novel_id: novelId, chapter_id: chapterId, segment, prev_segment_text: prevSegmentText },
    onChunk, onDone, onError,
  )
}

// AI对话（SSE）
export function streamChat(
  novelId: string,
  contextType: string,
  contextId: string | undefined,
  messages: { role: string; content: string }[],
  userMessage: string,
  onChunk: (text: string) => void, onDone: () => void, onError: (err: string) => void,
): AbortController {
  return streamRequest(
    '/api/ai/chat',
    { novel_id: novelId, context_type: contextType, context_id: contextId, messages, user_message: userMessage },
    onChunk, onDone, onError,
  )
}
