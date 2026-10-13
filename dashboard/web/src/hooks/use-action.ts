import { useCallback, useState } from "react"
import { toast } from "sonner"

/**
 * Run a control action (a POST), show a confirmation toast or the server's
 * error message, and remember which action is still running so its button
 * can show a spinner.
 */
export function useAction() {
  const [pending, setPending] = useState<string | null>(null)

  const run = useCallback(
    async <T>(
      key: string,
      request: () => Promise<T>,
      success: string | ((data: T) => string)
    ): Promise<T | null> => {
      setPending(key)
      try {
        const data = await request()
        toast.success(typeof success === "function" ? success(data) : success)
        return data
      } catch (error) {
        toast.error(error instanceof Error ? error.message : String(error))
        return null
      } finally {
        setPending(null)
      }
    },
    []
  )

  return { pending, run }
}
