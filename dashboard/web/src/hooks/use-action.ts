import { useCallback, useState } from "react"
import { toast } from "sonner"

/**
 * Run control actions (POSTs), show a confirmation toast or the server's
 * error message, and track which actions are still running so their buttons
 * can show a spinner and stay disabled until their own request finishes.
 */
export function useAction() {
  const [pending, setPending] = useState<ReadonlySet<string>>(() => new Set())

  const run = useCallback(
    async <T>(
      key: string,
      request: () => Promise<T>,
      success: string | ((data: T) => string)
    ): Promise<T | null> => {
      setPending((keys) => new Set(keys).add(key))
      try {
        const data = await request()
        toast.success(typeof success === "function" ? success(data) : success)
        return data
      } catch (error) {
        toast.error(error instanceof Error ? error.message : String(error))
        return null
      } finally {
        setPending((keys) => {
          const next = new Set(keys)
          next.delete(key)
          return next
        })
      }
    },
    []
  )

  return { pending, busy: pending.size > 0, run }
}
