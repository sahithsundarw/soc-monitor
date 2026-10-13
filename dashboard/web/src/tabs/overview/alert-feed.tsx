import { useState } from "react"
import { BellIcon } from "lucide-react"

import { Panel, Section } from "@/components/page"
import { PanelEmpty } from "@/components/panel-empty"
import { SeverityBadge } from "@/components/severity-badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { formatNumber, formatTime, SEVERITY_NAMES, sum } from "@/lib/format"
import { SEVERITIES, type Alert, type Severity } from "@/lib/types"
import { cn } from "@/lib/utils"

type Filter = "ALL" | Severity

export function filterAlerts(alerts: Alert[], filter: Filter): Alert[] {
  return filter === "ALL"
    ? alerts
    : alerts.filter((alert) => alert.severity === filter)
}

function alertKey(alert: Alert): string {
  return `${alert.ts}|${alert.rule}|${alert.source}`
}

function SeverityFilter({
  filter,
  onChange,
  counts,
}: {
  filter: Filter
  onChange: (filter: Filter) => void
  counts: Record<Severity, number> | undefined
}) {
  return (
    <div className="max-w-full overflow-x-auto">
      <ToggleGroup
        type="single"
        variant="outline"
        spacing={0}
        value={filter}
        onValueChange={(value: string) => value && onChange(value as Filter)}
        aria-label="Filter alerts by severity"
      >
        <ToggleGroupItem value="ALL">
          All
          <span className="tabular-nums opacity-60">
            {formatNumber(counts ? sum(Object.values(counts)) : 0)}
          </span>
        </ToggleGroupItem>
        {SEVERITIES.map((severity) => (
          <ToggleGroupItem key={severity} value={severity}>
            {SEVERITY_NAMES[severity]}
            <span className="tabular-nums opacity-60">
              {formatNumber(counts?.[severity] ?? 0)}
            </span>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
    </div>
  )
}

function AlertTable({
  alerts,
  openedAt,
}: {
  alerts: Alert[]
  openedAt: number
}) {
  return (
    <ScrollArea className="[&>[data-slot=scroll-area-viewport]]:max-h-[26rem]">
      <Table aria-label="Recent alerts">
        <TableHeader className="sticky top-0 z-[1] bg-card">
          <TableRow>
            <TableHead className="w-24 max-sm:hidden">Time</TableHead>
            <TableHead className="w-28">Severity</TableHead>
            <TableHead>Alert</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {alerts.map((alert) => (
            <TableRow
              key={alertKey(alert)}
              // Only alerts raised after the page opened fade in; the backlog just appears.
              className={cn(
                alert.ts > openedAt && "animate-in duration-700 fade-in"
              )}
            >
              <TableCell className="align-top font-mono text-muted-foreground tabular-nums max-sm:hidden">
                {formatTime(alert.ts)}
              </TableCell>
              <TableCell className="align-top">
                <div className="flex flex-col items-start gap-1">
                  <SeverityBadge severity={alert.severity} />
                  <span className="font-mono text-muted-foreground tabular-nums sm:hidden">
                    {formatTime(alert.ts)}
                  </span>
                </div>
              </TableCell>
              <TableCell className="whitespace-normal">
                <div className="font-medium">{alert.title}</div>
                <div className="text-muted-foreground">{alert.detail}</div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </ScrollArea>
  )
}

export function AlertFeed({
  alerts,
  counts,
  className,
}: {
  alerts: Alert[] | undefined
  counts: Record<Severity, number> | undefined
  className?: string
}) {
  const [filter, setFilter] = useState<Filter>("ALL")
  const [openedAt] = useState(() => Date.now() / 1000)
  const shown = alerts ? filterAlerts(alerts, filter) : []

  return (
    <Section
      title="Alerts"
      className={className}
      actions={
        <SeverityFilter filter={filter} onChange={setFilter} counts={counts} />
      }
    >
      <Panel>
        {!alerts ? (
          <div className="flex flex-col gap-3 p-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-3/4" />
          </div>
        ) : shown.length === 0 ? (
          <PanelEmpty
            icon={BellIcon}
            title={
              alerts.length === 0
                ? "No alerts yet"
                : `No ${SEVERITY_NAMES[filter as Severity].toLowerCase()} alerts`
            }
            description={
              alerts.length === 0
                ? "Launch an attack from Controls to raise one."
                : undefined
            }
          />
        ) : (
          <AlertTable alerts={shown} openedAt={openedAt} />
        )}
      </Panel>
    </Section>
  )
}
