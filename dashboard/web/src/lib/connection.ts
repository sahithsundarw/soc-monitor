import { formatDuration } from "@/lib/format"
import type { Status } from "@/lib/types"

export const STALE_AFTER_MS = 5000

export type ConnectionState =
  "loading" | "running" | "stopped" | "disconnected" | "stale"

/** What the status cell in the top bar says. Only a failed request means
 * "disconnected"; numbers older than 5 s are marked stale. */
export function connection(
  status: Status | undefined,
  error: string | null,
  lastUpdate: number,
  now: number
): { state: ConnectionState; text: string } {
  if (!lastUpdate || !status) {
    return error
      ? { state: "disconnected", text: "Disconnected" }
      : { state: "loading", text: "Connecting…" }
  }
  const age = now - lastUpdate
  if (age > STALE_AFTER_MS) {
    return { state: "stale", text: `Stale ${Math.round(age / 1000)}s` }
  }
  if (!status.running) return { state: "stopped", text: "Stopped" }
  return {
    state: "running",
    text:
      status.uptime_s === null
        ? "Running"
        : `Running ${formatDuration(status.uptime_s)}`,
  }
}
