import { useEffect, useState } from "react"

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"
import type { Poll } from "@/hooks/use-poll"
import { connection, type ConnectionState } from "@/lib/connection"
import { formatNumber, routeText } from "@/lib/format"
import type { Status } from "@/lib/types"
import { cn } from "@/lib/utils"

const DOT_CLASSES: Record<ConnectionState, string> = {
  loading: "bg-muted-foreground",
  running: "bg-positive",
  stopped: "bg-muted-foreground",
  disconnected: "bg-destructive",
  stale: "bg-destructive",
}

/** Re-render every second so "Stale 7s" counts up between polls. */
function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), intervalMs)
    return () => clearInterval(timer)
  }, [intervalMs])
  return now
}

function Counter({
  label,
  value,
  className,
}: {
  label: string
  value: string
  className?: string
}) {
  return (
    <div className={cn("flex items-baseline gap-2", className)}>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  )
}

export function TopBar({
  section,
  title,
  poll,
}: {
  section: string
  title: string
  poll: Poll<Status>
}) {
  const now = useNow(1000)
  const { data: status, error, lastUpdate } = poll
  const { state, text } = connection(status, error, lastUpdate, now)
  const route = status?.routes.S1
  const routeLabel = !status
    ? "–"
    : route && route.path.length
      ? routeText(route.path)
      : "no route"

  return (
    <header className="sticky top-0 z-10 flex h-16 shrink-0 items-center gap-3 border-b bg-background px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator
        orientation="vertical"
        className="data-vertical:h-5 data-vertical:self-center"
      />
      <Breadcrumb className="min-w-0">
        <BreadcrumbList>
          <BreadcrumbItem className="max-sm:hidden">{section}</BreadcrumbItem>
          <BreadcrumbSeparator className="max-sm:hidden" />
          <BreadcrumbItem>
            <BreadcrumbPage className="truncate">{title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <dl className="ml-auto flex items-center gap-6 text-sm">
        <div>
          <dt className="sr-only">Status</dt>
          <dd
            data-state={state}
            className={cn(
              "flex items-center gap-2 font-medium",
              (state === "stale" || state === "disconnected") &&
                "text-destructive"
            )}
          >
            <span
              aria-hidden
              className={cn("size-2 rounded-full", DOT_CLASSES[state])}
            />
            {text}
          </dd>
        </div>
        <Counter
          label="Events"
          value={status ? formatNumber(status.tiles.events) : "–"}
          className="max-md:hidden"
        />
        <Counter
          label="Alerts"
          value={status ? formatNumber(status.tiles.alerts) : "–"}
          className="max-md:hidden"
        />
        <Counter label="Route" value={routeLabel} className="max-xl:hidden" />
      </dl>
    </header>
  )
}
