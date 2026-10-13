import { useCallback, useEffect, useRef, useState } from "react"

import { api } from "@/lib/api"

export type Poll<T> = {
  data: T | undefined
  /** Message of the latest failed request, cleared by the next success. */
  error: string | null
  /** Date.now() of the latest successful request, 0 before the first. */
  lastUpdate: number
  /** Fetch again right away (after an action changed something). */
  refresh: () => Promise<boolean>
}

type Options = {
  /** Stop after the first success (lists that never change during the demo). */
  once?: boolean
  /** Poll only while true, e.g. while the tab is visible; data is kept. */
  enabled?: boolean
}

/**
 * GET `path` now and then every `intervalMs` (plain HTTP polling, no
 * websockets). The next request starts only after the previous one finished,
 * so a slow server never piles requests up.
 */
export function usePoll<T>(
  path: string,
  intervalMs: number,
  { once = false, enabled = true }: Options = {}
): Poll<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState(0)
  // Guards manual refresh() calls that finish after the component unmounted.
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  const fetchOnce = useCallback(
    async (isLive: () => boolean) => {
      try {
        const next = await api<T>(path)
        if (!isLive()) return false
        setData(next)
        setError(null)
        setLastUpdate(Date.now())
        return true
      } catch (failure) {
        if (isLive()) {
          setError(failure instanceof Error ? failure.message : String(failure))
        }
        return false
      }
    },
    [path]
  )

  const refresh = useCallback(
    () => fetchOnce(() => mounted.current),
    [fetchOnce]
  )

  useEffect(() => {
    if (!enabled) return
    // Each run of this effect owns its own loop, so a cleanup (StrictMode,
    // or the tab being hidden) always stops exactly that loop.
    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | undefined
    const tick = async () => {
      const succeeded = await fetchOnce(() => !cancelled)
      if (!cancelled && !(once && succeeded)) {
        timer = setTimeout(tick, intervalMs)
      }
    }
    tick()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [fetchOnce, intervalMs, once, enabled])

  return { data, error, lastUpdate, refresh }
}
