import { useEffect, useState } from "react"
import { FileXIcon, InboxIcon, MousePointerClickIcon } from "lucide-react"
import { toast } from "sonner"

import { PageBody, PageHeader, Panel, Section } from "@/components/page"
import { PanelEmpty } from "@/components/panel-empty"
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
import { useHoverHold } from "@/hooks/use-hover-hold"
import { usePoll } from "@/hooks/use-poll"
import { api } from "@/lib/api"
import { formatTime } from "@/lib/format"
import type { EventSummary, Layers } from "@/lib/types"
import { LayerStack } from "@/tabs/inspector/layer-stack"

const POLL_MS = 1000

function EventTable({
  events,
  selected,
  onSelect,
}: {
  events: EventSummary[]
  selected: string | null
  onSelect: (id: string) => void
}) {
  const { shown, holdProps } = useHoverHold(events)
  return (
    <ScrollArea
      className="[&>[data-slot=scroll-area-viewport]]:max-h-[36rem]"
      {...holdProps}
    >
      <Table aria-label="Recent events. Select one to inspect its frame.">
        <TableHeader className="sticky top-0 z-[1] bg-card">
          <TableRow>
            <TableHead>Time</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Sensor</TableHead>
            <TableHead>Proto</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {shown.map((event) => (
            <TableRow
              key={event.id}
              tabIndex={0}
              aria-selected={event.id === selected}
              data-state={event.id === selected ? "selected" : undefined}
              className="cursor-pointer focus-visible:bg-muted focus-visible:outline-none data-[state=selected]:font-medium"
              onClick={() => onSelect(event.id)}
              onKeyDown={(key) => {
                if (key.key === "Enter" || key.key === " ") {
                  key.preventDefault()
                  onSelect(event.id)
                }
              }}
            >
              <TableCell className="font-mono tabular-nums">
                {formatTime(event.received_at)}
              </TableCell>
              <TableCell>{event.type.replace(/_/g, " ")}</TableCell>
              <TableCell className="font-mono">{event.sensor}</TableCell>
              <TableCell className="font-mono">
                {event.protocol.toUpperCase()}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </ScrollArea>
  )
}

export function InspectorTab({ active }: { active: boolean }) {
  const poll = usePoll<EventSummary[]>("/api/events", POLL_MS, {
    enabled: active,
  })
  const [selected, setSelected] = useState<string | null>(null)
  const [layers, setLayers] = useState<Layers | null>(null)
  const [failure, setFailure] = useState<{
    id: string
    message: string
  } | null>(null)

  useEffect(() => {
    if (!selected) return
    let current = true
    api<Layers>(`/api/events/${encodeURIComponent(selected)}`)
      .then((next) => current && setLayers(next))
      .catch((error: Error) => {
        if (!current) return
        setFailure({ id: selected, message: error.message })
        toast.error(error.message)
      })
    return () => {
      current = false
    }
  }, [selected])

  const frame = !selected ? (
    <PanelEmpty
      icon={MousePointerClickIcon}
      title="No event selected"
      description="Select an event to see it at every layer."
    />
  ) : failure?.id === selected ? (
    <PanelEmpty
      icon={FileXIcon}
      title="Frame not available"
      description={failure.message}
    />
  ) : layers?.id !== selected ? (
    <div className="flex flex-col gap-4" aria-label="Loading frame">
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-24 w-full" />
    </div>
  ) : (
    <LayerStack layers={layers} />
  )

  return (
    <>
      <PageHeader title="Packet Inspector" />
      <PageBody>
        <div className="grid items-start gap-8 lg:grid-cols-12">
          <Section
            title="Recent events"
            className="lg:sticky lg:top-24 lg:col-span-5"
          >
            <Panel>
              {!poll.data ? (
                <div className="flex flex-col gap-3 p-4">
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-8 w-full" />
                </div>
              ) : poll.data.length === 0 ? (
                <PanelEmpty
                  icon={InboxIcon}
                  title="Waiting for the first event"
                  description="Events appear here as the sensors send them."
                />
              ) : (
                <EventTable
                  events={poll.data}
                  selected={selected}
                  onSelect={setSelected}
                />
              )}
            </Panel>
          </Section>
          <Section
            title="Frame"
            className="lg:col-span-7"
            actions={
              selected && (
                <span className="font-mono text-sm text-muted-foreground">
                  {selected}
                </span>
              )
            }
          >
            <Panel className="p-4 md:p-6">{frame}</Panel>
          </Section>
        </div>
      </PageBody>
    </>
  )
}
