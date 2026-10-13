import { useCallback, useState } from "react"

function read(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null // storage can be off (private mode); nothing is remembered then
  }
}

function write(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Same as above: the choice just isn't remembered across reloads.
  }
}

/** A string state remembered in localStorage, ignoring stored values that
 * are no longer valid (for example a tab that was renamed). */
export function useStoredState<T extends string>(
  key: string,
  initial: T,
  isValid: (value: string) => value is T
): [T, (value: T) => void] {
  const [value, setValue] = useState<T>(() => {
    const stored = read(key)
    return stored !== null && isValid(stored) ? stored : initial
  })
  const update = useCallback(
    (next: T) => {
      write(key, next)
      setValue(next)
    },
    [key]
  )
  return [value, update]
}
