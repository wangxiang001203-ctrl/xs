export function normalizeAuthorText(text?: string | null) {
  if (!text) return ''
  return text
    .replace(/^# (.+)$/gm, '$1')
    .replace(/^## (.+)$/gm, '【$1】')
    .replace(/^### (.+)$/gm, '$1')
    .replace(/^- \*\*(.+?)\*\*[：:]\s*(.*)$/gm, '· $1：$2')
    .replace(/^- (.+)$/gm, '· $1')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}
