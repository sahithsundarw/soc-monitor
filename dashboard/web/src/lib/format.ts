// Small display helpers shared by every tab.
import type { Severity } from "@/lib/types"

export const SEVERITY_NAMES: Record<Severity, string> = {
  CRITICAL: "Critical",
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
}

export const METHOD_NAMES: Record<string, string> = {
  character: "Character stuffing",
  bit: "Bit stuffing",
}

export function formatTime(seconds: number): string {
  return new Date(seconds * 1000).toLocaleTimeString([], { hour12: false })
}

export function formatNumber(value: number): string {
  return Number(value).toLocaleString()
}

/** 42s, 7m, 1h 05m. */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`
}

export function formatBytes(size: number): string {
  return size < 1024 ? `${size} B` : `${(size / 1024).toFixed(1)} KB`
}

export function plural(count: number, word: string): string {
  return count === 1 ? word : `${word}s`
}

export function sum(values: number[]): number {
  return values.reduce((total, value) => total + value, 0)
}

export function routeText(path: string[]): string {
  return path.join(" → ")
}

export function isSeverity(value: string): value is Severity {
  return value in SEVERITY_NAMES
}

/** Alert emails have subjects like "[HIGH] Brute-force login". */
export function splitSubject(subject: string): {
  severity: Severity | null
  title: string
} {
  const match = /^\[(\w+)\]\s*(.*)$/.exec(subject)
  if (!match || !isSeverity(match[1])) return { severity: null, title: subject }
  return { severity: match[1], title: match[2] }
}

// The chart axis never drops below 10 frames/s, so routine traffic sits low and
// a flood visibly spikes instead of every second filling the plot.
const CHART_MIN_TOP = 10

/** A round axis maximum at or above `peak`, even so the midline is whole. */
export function niceTop(peak: number): number {
  const step = peak <= 10 ? 2 : peak <= 50 ? 10 : peak <= 200 ? 50 : 100
  const top = Math.ceil(peak / (2 * step)) * 2 * step
  return Math.max(CHART_MIN_TOP, top)
}

/** The per-minute rate, shown only when it says something the total does not. */
export function rateLabel(total: number, lastMinute: number[]): string {
  const minute = sum(lastMinute)
  return minute && minute !== total ? `+${formatNumber(minute)}/min` : ""
}
