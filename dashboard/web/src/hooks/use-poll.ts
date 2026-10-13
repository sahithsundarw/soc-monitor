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

/**
 * GET `path` now and then every `intervalMs` (plain HTTP polling, no
 * websockets). The next request starts only after the previous one finished,
 * so a slow server never piles requests up. With `once`, polling stops after
 * the first success (for lists that never change while the demo runs).
 */
export function usePoll<T>(
  path: string,
  intervalMs: number,
  { once = false }: { once?: boolean } = {}
): Poll<T> {
  const [data, setData] = useState<T>()
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState(0)
  const alive = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const next = await api<T>(path)
      if (!alive.current) return false
      setData(next)
      setError(null)
      setLastUpdate(Date.now())
      return true
    } catch (failure) {
      if (alive.current) {
        setError(failure instanceof Error ? failure.message : String(failure))
      }
      return false
    }
  }, [path])

  useEffect(() => {
    alive.current = true
    let timer: ReturnType<typeof setTimeout> | undefined
    const tick = async () => {
      const succeeded = await refresh()
      if (alive.current && !(once && succeeded)) {
        timer = setTimeout(tick, intervalMs)
      }
    }
    tick()
    return () => {
      alive.current = false
      clearTimeout(timer)
    }
  }, [refresh, intervalMs, once])

  return { data, error, lastUpdate, refresh }
}
