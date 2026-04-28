import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from 'react'
import CodeMirror from '@uiw/react-codemirror'
import type { EditorState, Extension, Range } from '@codemirror/state'
import { Decoration, EditorView, WidgetType, type DecorationSet } from '@codemirror/view'
import { redo, undo } from '@codemirror/commands'
import type { InlineSuggestion } from '../../utils/inlineDiff'
import styles from './NovelEditor.module.css'

export interface NovelEditorHandle {
  focus: () => void
  undo: () => boolean
  redo: () => boolean
}

interface Props {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  searchValue?: string
  inlineSuggestions?: InlineSuggestion[]
  onAcceptSuggestion?: (suggestion: InlineSuggestion) => void
  onRejectSuggestion?: (suggestion: InlineSuggestion) => void
}

class SuggestionWidget extends WidgetType {
  suggestion: InlineSuggestion
  onAccept: (suggestion: InlineSuggestion) => void
  onReject: (suggestion: InlineSuggestion) => void

  constructor(
    suggestion: InlineSuggestion,
    onAccept: (suggestion: InlineSuggestion) => void,
    onReject: (suggestion: InlineSuggestion) => void,
  ) {
    super()
    this.suggestion = suggestion
    this.onAccept = onAccept
    this.onReject = onReject
  }

  eq(other: SuggestionWidget) {
    return other.suggestion.id === this.suggestion.id
      && other.suggestion.originalText === this.suggestion.originalText
      && other.suggestion.suggestedText === this.suggestion.suggestedText
  }

  toDOM() {
    const wrapper = document.createElement('div')
    wrapper.className = styles.suggestionWidget

    const actions = document.createElement('div')
    actions.className = styles.suggestionActions

    const acceptButton = document.createElement('button')
    acceptButton.type = 'button'
    acceptButton.className = `${styles.suggestionButton} ${styles.suggestionAccept}`
    acceptButton.textContent = '接受'
    acceptButton.addEventListener('mousedown', event => event.preventDefault())
    acceptButton.addEventListener('click', event => {
      event.preventDefault()
      this.onAccept(this.suggestion)
    })

    const rejectButton = document.createElement('button')
    rejectButton.type = 'button'
    rejectButton.className = `${styles.suggestionButton} ${styles.suggestionReject}`
    rejectButton.textContent = '拒绝'
    rejectButton.addEventListener('mousedown', event => event.preventDefault())
    rejectButton.addEventListener('click', event => {
      event.preventDefault()
      this.onReject(this.suggestion)
    })

    actions.append(acceptButton, rejectButton)

    const label = document.createElement('span')
    label.className = styles.suggestionTitle
    label.textContent = this.suggestion.originalText ? 'AI 建议改为' : 'AI 建议新增'

    const newBlock = document.createElement('pre')
    newBlock.className = `${styles.suggestionBlock} ${styles.suggestionNew}`
    newBlock.textContent = this.suggestion.suggestedText || 'AI 建议删除这段内容'

    wrapper.append(label, newBlock, actions)
    return wrapper
  }

  ignoreEvent() {
    return false
  }
}

function buildEditorDecorations(
  state: EditorState,
  suggestions: InlineSuggestion[],
  searchValue: string,
  onAccept: (suggestion: InlineSuggestion) => void,
  onReject: (suggestion: InlineSuggestion) => void,
): DecorationSet {
  const ranges: Range<Decoration>[] = []
  const originalLineDecoration = Decoration.line({ class: styles.suggestionOriginalLine })
  const suggestionAnchorDecoration = Decoration.line({ class: styles.suggestionAnchorLine })
  const searchDecoration = Decoration.mark({ class: styles.searchMatch })

  suggestions.forEach((suggestion) => {
    if (suggestion.currentStartLine <= suggestion.currentEndLine) {
      for (let lineNo = suggestion.currentStartLine; lineNo <= suggestion.currentEndLine; lineNo += 1) {
        if (lineNo >= 1 && lineNo <= state.doc.lines) {
          const line = state.doc.line(lineNo)
          ranges.push(originalLineDecoration.range(line.from))
        }
      }
    }

    const widgetLineNo = suggestion.currentEndLine >= suggestion.currentStartLine
      ? Math.min(Math.max(suggestion.currentEndLine, 1), Math.max(state.doc.lines, 1))
      : Math.min(Math.max(suggestion.currentStartLine - 1, 1), Math.max(state.doc.lines, 1))
    const widgetLine = state.doc.line(widgetLineNo)
    const widgetPos = suggestion.currentEndLine >= suggestion.currentStartLine
      ? widgetLine.to
      : widgetLine.from
    ranges.push(suggestionAnchorDecoration.range(widgetLine.from))
    ranges.push(Decoration.widget({
      widget: new SuggestionWidget(suggestion, onAccept, onReject),
      block: true,
      side: 1,
    }).range(widgetPos))
  })

  const query = searchValue.trim()
  if (query) {
    const source = state.doc.toString()
    let from = source.indexOf(query)
    while (from !== -1) {
      ranges.push(searchDecoration.range(from, from + query.length))
      from = source.indexOf(query, from + query.length)
    }
  }

  return Decoration.set(ranges, true)
}

function inlineReviewExtension(
  suggestions: InlineSuggestion[],
  searchValue: string,
  onAccept: (suggestion: InlineSuggestion) => void,
  onReject: (suggestion: InlineSuggestion) => void,
): Extension {
  return EditorView.decorations.compute([], state =>
    buildEditorDecorations(state, suggestions, searchValue, onAccept, onReject),
  )
}

const editorTheme = EditorView.theme({
  '&': {
    height: '100%',
    minHeight: '0',
    width: '100%',
  },
  '.cm-editor': {
    height: '100%',
    minHeight: '0',
  },
  '.cm-scroller': {
    height: '100%',
    minHeight: '0',
    overflow: 'auto',
  },
  '.cm-content': {
    minHeight: '100%',
  },
  '.cm-line': {
    color: 'var(--text-primary)',
  },
  '.cm-placeholder': {
    color: 'rgba(55, 80, 83, 0.36)',
  },
})

const NovelEditor = forwardRef<NovelEditorHandle, Props>(function NovelEditor({
  value,
  onChange,
  placeholder,
  searchValue = '',
  inlineSuggestions = [],
  onAcceptSuggestion,
  onRejectSuggestion,
}, ref) {
  const editorViewRef = useRef<EditorView | null>(null)
  const shellRef = useRef<HTMLDivElement | null>(null)
  const extensions = useMemo(() => [
    editorTheme,
    EditorView.lineWrapping,
    inlineReviewExtension(
      inlineSuggestions,
      searchValue,
      onAcceptSuggestion ?? (() => undefined),
      onRejectSuggestion ?? (() => undefined),
    ),
  ], [inlineSuggestions, onAcceptSuggestion, onRejectSuggestion, searchValue])

  useImperativeHandle(ref, () => ({
    focus: () => editorViewRef.current?.focus(),
    undo: () => (editorViewRef.current ? undo(editorViewRef.current) : false),
    redo: () => (editorViewRef.current ? redo(editorViewRef.current) : false),
  }))

  useEffect(() => {
    editorViewRef.current?.requestMeasure()
  }, [value.length])

  useEffect(() => {
    const shellNode = shellRef.current
    if (!shellNode) return undefined

    function handleWheel(event: WheelEvent) {
      const scroller = shellNode!.querySelector('.cm-scroller') as HTMLElement | null
      if (!scroller) return

      const maxScrollTop = scroller.scrollHeight - scroller.clientHeight
      if (maxScrollTop <= 0) return

      const delta = event.deltaY || event.deltaX
      if (!delta) return

      const nextScrollTop = Math.max(0, Math.min(maxScrollTop, scroller.scrollTop + delta))
      if (nextScrollTop === scroller.scrollTop) return

      scroller.scrollTop = nextScrollTop
      event.preventDefault()
      event.stopPropagation()
    }

    shellNode.addEventListener('wheel', handleWheel, { capture: true, passive: false })
    return () => shellNode.removeEventListener('wheel', handleWheel, { capture: true })
  }, [])

  return (
    <div ref={shellRef} className={styles.shell}>
      <CodeMirror
        value={value}
        height="100%"
        style={{
          width: '100%',
          height: '100%',
          minHeight: 0,
          flex: '1 1 0',
          display: 'flex',
        }}
        basicSetup={{
          lineNumbers: false,
          foldGutter: false,
          highlightActiveLine: true,
          highlightSelectionMatches: false,
        }}
        placeholder={placeholder}
        extensions={extensions}
        onCreateEditor={(view) => {
          editorViewRef.current = view
          window.requestAnimationFrame(() => view.requestMeasure())
        }}
        onChange={onChange}
      />
    </div>
  )
})

export default NovelEditor
