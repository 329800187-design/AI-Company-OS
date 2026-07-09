import { useCallback, useState } from "react"

/**
 * Generic undo/redo history hook.
 * Manages past/present/future stacks with a configurable limit.
 */

interface HistoryState<T> {
  past: T[]
  present: T
  future: T[]
}

interface UseHistoryReturn<T> {
  state: T
  set: (next: T) => void
  undo: () => void
  redo: () => void
  canUndo: boolean
  canRedo: boolean
  reset: (initial: T) => void
}

const MAX_HISTORY = 100

export function useDagHistory<T>(initialState: T, onChange?: (state: T) => void): UseHistoryReturn<T> {
  const [history, setHistory] = useState<HistoryState<T>>({
    past: [],
    present: initialState,
    future: [],
  })

  const state = history.present

  const set = useCallback(
    (next: T) => {
      setHistory((prev) => ({
        past: [...prev.past.slice(-(MAX_HISTORY - 1)), prev.present],
        present: next,
        future: [],
      }))
      onChange?.(next)
    },
    [onChange],
  )

  const undo = useCallback(() => {
    if (history.past.length === 0) return
    const previous = history.past[history.past.length - 1]
    setHistory({
      past: history.past.slice(0, -1),
      present: previous,
      future: [history.present, ...history.future],
    })
    onChange?.(previous)
  }, [history, onChange])

  const redo = useCallback(() => {
    if (history.future.length === 0) return
    const next = history.future[0]
    setHistory({
      past: [...history.past, history.present],
      present: next,
      future: history.future.slice(1),
    })
    onChange?.(next)
  }, [history, onChange])

  const reset = useCallback((initial: T) => {
    setHistory({
      past: [],
      present: initial,
      future: [],
    })
  }, [])

  return {
    state,
    set,
    undo,
    redo,
    canUndo: history.past.length > 0,
    canRedo: history.future.length > 0,
    reset,
  }
}
