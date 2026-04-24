import { api } from '../api'
import type { Volume } from '../types'

export async function loadNovelWorkspaceContext(novelId: string) {
  const [characters, worldbuilding, chapters, volumes] = await Promise.all([
    api.characters.list(novelId),
    api.worldbuilding.get(novelId).catch(() => null),
    api.chapters.list(novelId),
    api.volumes.list(novelId).catch(() => [] as Volume[]),
  ])

  return { characters, worldbuilding, chapters, volumes }
}
