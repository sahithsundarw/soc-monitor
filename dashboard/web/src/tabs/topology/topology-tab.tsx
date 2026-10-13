import { useState } from "react"

import { PageBody, PageHeader, Panel, Section } from "@/components/page"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useAction } from "@/hooks/use-action"
import { usePoll } from "@/hooks/use-poll"
import { api } from "@/lib/api"
import { routeText } from "@/lib/format"
import type { Link, Topology } from "@/lib/types"
import { GraphLegend, NetworkGraph } from "@/tabs/topology/network-graph"

const POLL_MS = 1000

function LinksTable({
  links,
  onChanged,
}: {
  links: Link[]
  onChanged: () => void
}) {
  const { pending, run } = useAction()

  const toggle = async (link: Link) => {
    const action = link.up ? "fail" : "restore"
    const done = await run(
      `${link.a}-${link.b}`,
      () => api(`/api/links/${action}`, { a: link.a, b: link.b }),
      `Link ${link.a}-${link.b} ${link.up ? "failed" : "restored"}. Routes recomputed.`
    )
    if (done) onChanged()
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Link</TableHead>
          <TableHead className="text-right">Cost</TableHead>
          <TableHead>State</TableHead>
          <TableHead className="text-right">
            <span className="sr-only">Action</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {links.map((link) => {
          const key = `${link.a}-${link.b}`
          const verb = link.up ? "Fail" : "Restore"
          return (
            <TableRow key={key}>
              <TableCell className="font-mono">
                {link.a} – {link.b}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {link.cost}
              </TableCell>
              <TableCell
                className={
                  link.up
                    ? "text-muted-foreground"
                    : "font-medium text-destructive"
                }
              >
                {link.up ? "Up" : "Down"}
              </TableCell>
              <TableCell className="py-2 text-right">
                <Button
                  variant={link.up ? "outline" : "default"}
                  disabled={pending !== null}
                  onClick={() => toggle(link)}
                  aria-label={`${verb} link ${key}`}
                >
                  {pending === key && <Spinner data-icon="inline-start" />}
                  {verb}
                </Button>
              </TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}

function ForwardingTables({ topology }: { topology: Topology }) {
  return (
    <Table aria-label="Next hop from each router (rows) to each destination (columns)">
      <TableHeader>
        <TableRow>
          <TableHead>Router</TableHead>
          {topology.destinations.map((destination) => (
            <TableHead key={destination} className="font-mono">
              {destination}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {Object.entries(topology.tables).map(([router, nextHops]) => (
          <TableRow key={router}>
            <TableCell className="font-mono font-medium">{router}</TableCell>
            {topology.destinations.map((destination) => (
              <TableCell
                key={destination}
                className={
                  destination === router ? "text-muted-foreground" : "font-mono"
                }
              >
                {destination === router ? "—" : (nextHops[destination] ?? "-")}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function RoutePicker({
  sensors,
  sensor,
  onChange,
  label,
}: {
  sensors: string[]
  sensor: string
  onChange: (sensor: string) => void
  label: string
}) {
  return (
    <>
      <span className="text-sm text-muted-foreground">Route from</span>
      <ToggleGroup
        type="single"
        variant="outline"
        spacing={0}
        value={sensor}
        onValueChange={(value: string) => value && onChange(value)}
        aria-label="Show the route from a sensor"
      >
        {sensors.map((id) => (
          <ToggleGroupItem key={id} value={id} className="font-mono">
            {id}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <span className="min-w-56 font-mono text-sm" aria-live="polite">
        {label}
      </span>
    </>
  )
}

export function TopologyTab({ sensors }: { sensors: string[] }) {
  const poll = usePoll<Topology>("/api/topology", POLL_MS)
  const [sensor, setSensor] = useState("S1")
  const topology = poll.data
  const route = topology?.routes[sensor] ?? { path: [], cost: null }
  const routeLabel = !topology
    ? ""
    : route.path.length
      ? `${routeText(route.path)}, cost ${route.cost}`
      : "no route to the SOC"

  return (
    <>
      <PageHeader
        title="Topology"
        actions={
          <RoutePicker
            sensors={sensors}
            sensor={sensor}
            onChange={setSensor}
            label={routeLabel}
          />
        }
      />
      <PageBody>
        <Section title="Network" actions={<GraphLegend />}>
          <Panel className="p-4 md:p-6">
            {topology ? (
              <NetworkGraph topology={topology} route={route} />
            ) : (
              <Skeleton className="aspect-[776/336] w-full" />
            )}
          </Panel>
        </Section>
        <Separator />
        <div className="grid gap-8 lg:grid-cols-12">
          <Section title="Links" className="lg:col-span-5">
            <Panel>
              {topology ? (
                <LinksTable links={topology.links} onChanged={poll.refresh} />
              ) : (
                <Skeleton className="m-4 h-48" />
              )}
            </Panel>
          </Section>
          <Section title="Forwarding tables" className="lg:col-span-7">
            <Panel>
              {topology ? (
                <ForwardingTables topology={topology} />
              ) : (
                <Skeleton className="m-4 h-48" />
              )}
            </Panel>
          </Section>
        </div>
      </PageBody>
    </>
  )
}
