export interface InlineSuggestion {
  id: string
  signature: string
  currentStartLine: number
  currentEndLine: number
  originalText: string
  suggestedText: string
}

type DiffOp =
  | { kind: 'equal'; line: string; currentLine: number; draftLine: number }
  | { kind: 'delete'; line: string; currentLine: number }
  | { kind: 'insert'; line: string; draftLine: number }

function splitLines(text: string) {
  return text.length ? text.split('\n') : []
}

export function getSuggestionSignature(originalText: string, suggestedText: string) {
  let hash = 5381
  const source = `${originalText}\n---ai-suggestion---\n${suggestedText}`
  for (let index = 0; index < source.length; index += 1) {
    hash = ((hash << 5) + hash) ^ source.charCodeAt(index)
  }
  return `sg-${(hash >>> 0).toString(36)}`
}

function buildDiffOps(currentLines: string[], draftLines: string[]) {
  const dp = Array.from({ length: currentLines.length + 1 }, () =>
    Array(draftLines.length + 1).fill(0) as number[],
  )

  for (let i = currentLines.length - 1; i >= 0; i -= 1) {
    for (let j = draftLines.length - 1; j >= 0; j -= 1) {
      dp[i][j] = currentLines[i] === draftLines[j]
        ? dp[i + 1][j + 1] + 1
        : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }

  const ops: DiffOp[] = []
  let currentIndex = 0
  let draftIndex = 0
  while (currentIndex < currentLines.length || draftIndex < draftLines.length) {
    if (
      currentIndex < currentLines.length
      && draftIndex < draftLines.length
      && currentLines[currentIndex] === draftLines[draftIndex]
    ) {
      ops.push({
        kind: 'equal',
        line: currentLines[currentIndex],
        currentLine: currentIndex + 1,
        draftLine: draftIndex + 1,
      })
      currentIndex += 1
      draftIndex += 1
    } else if (
      draftIndex < draftLines.length
      && (currentIndex >= currentLines.length || dp[currentIndex][draftIndex + 1] >= dp[currentIndex + 1][draftIndex])
    ) {
      ops.push({ kind: 'insert', line: draftLines[draftIndex], draftLine: draftIndex + 1 })
      draftIndex += 1
    } else {
      ops.push({ kind: 'delete', line: currentLines[currentIndex], currentLine: currentIndex + 1 })
      currentIndex += 1
    }
  }

  return ops
}

export function buildInlineSuggestions(currentText: string, draftText: string): InlineSuggestion[] {
  if (currentText === draftText) return []

  const currentLines = splitLines(currentText)
  const draftLines = splitLines(draftText)
  const ops = buildDiffOps(currentLines, draftLines)
  const suggestions: InlineSuggestion[] = []

  let deletedLines: string[] = []
  let insertedLines: string[] = []
  let currentStartLine: number | null = null
  let currentEndLine: number | null = null
  let lastEqualCurrentLine = 0

  function flushSuggestion() {
    if (!deletedLines.length && !insertedLines.length) return
    const insertionLine = currentStartLine ?? lastEqualCurrentLine + 1
    const originalText = deletedLines.join('\n')
    const suggestedText = insertedLines.join('\n')
    const signature = getSuggestionSignature(originalText, suggestedText)
    suggestions.push({
      id: `${signature}-${suggestions.length}`,
      signature,
      currentStartLine: insertionLine,
      currentEndLine: currentEndLine ?? insertionLine - 1,
      originalText,
      suggestedText,
    })
    deletedLines = []
    insertedLines = []
    currentStartLine = null
    currentEndLine = null
  }

  ops.forEach((op) => {
    if (op.kind === 'equal') {
      flushSuggestion()
      lastEqualCurrentLine = op.currentLine
      return
    }

    if (op.kind === 'delete') {
      currentStartLine = currentStartLine ?? op.currentLine
      currentEndLine = op.currentLine
      deletedLines.push(op.line)
      return
    }

    insertedLines.push(op.line)
  })
  flushSuggestion()

  return suggestions
}

export function applyInlineSuggestion(text: string, suggestion: InlineSuggestion) {
  const lines = splitLines(text)
  const startIndex = Math.max(0, suggestion.currentStartLine - 1)
  const deleteCount = Math.max(0, suggestion.currentEndLine - suggestion.currentStartLine + 1)
  const replacementLines = splitLines(suggestion.suggestedText)
  lines.splice(startIndex, deleteCount, ...replacementLines)
  return lines.join('\n')
}
