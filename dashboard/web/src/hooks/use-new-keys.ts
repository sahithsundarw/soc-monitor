import { useState } from "react"

type Seen = {
  signature: string | null
  seen: Set<string> | null
  fresh: Set<string>
}

const NONE: Set<string> = new Set()

/**
 * Which keys appeared since the last change, for the whole page's lifetime.
 * The first list that arrives is the backlog, so nothing in it counts as new.
 * While `visible` is false nothing is marked seen, so everything that arrived
 * while the list was hidden counts as new when it is shown again.
 * Pass the full (unfiltered) list so changing a filter never marks rows new.
 */
export function useNewKeys(
  keys: string[] | undefined,
  visible = true
): ReadonlySet<string> {
  const signature = keys ? keys.join("\n") : null
  const [state, setState] = useState<Seen>({
    signature: null,
    seen: null,
    fresh: NONE,
  })

  // Adjusting state while rendering (not in an effect) so the new rows mount
  // with their fade class already set.
  if (!visible && state.fresh.size > 0) {
    setState({ ...state, fresh: NONE })
  } else if (visible && keys && signature !== state.signature) {
    const fresh = state.seen
      ? new Set(keys.filter((key) => !state.seen!.has(key)))
      : NONE
    setState({
      signature,
      seen: new Set([...(state.seen ?? []), ...keys]),
      fresh,
    })
  }

  return state.fresh
}
