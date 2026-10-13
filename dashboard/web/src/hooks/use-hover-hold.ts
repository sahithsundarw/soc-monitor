import { useState } from "react"

/**
 * A live list holds still while the pointer is on it, so new rows arriving
 * from the poll never shift the row someone is about to click.
 */
export function useHoverHold<T>(value: T) {
  const [held, setHeld] = useState<{ value: T } | null>(null)
  return {
    shown: held ? held.value : value,
    holdProps: {
      onMouseEnter: () => setHeld({ value }),
      onMouseLeave: () => setHeld(null),
    },
  }
}
