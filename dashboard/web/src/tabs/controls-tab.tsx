import { useState, type ReactNode } from "react"

import { PageBody, PageHeader, Panel, Section } from "@/components/page"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldTitle,
} from "@/components/ui/field"
import { Slider } from "@/components/ui/slider"
import { Spinner } from "@/components/ui/spinner"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
} from "@/components/ui/table"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { useAction } from "@/hooks/use-action"
import { api } from "@/lib/api"
import { METHOD_NAMES } from "@/lib/format"
import type { LinkSettings, Meta } from "@/lib/types"

const ATTACK_NAMES: Record<string, string> = {
  brute_force: "Brute force",
  port_scan: "Port scan",
  beacon: "Malware beacon",
}

function LinkLayerCard({
  settings,
  meta,
  onChanged,
}: {
  settings: LinkSettings | undefined
  meta: Meta | undefined
  onChanged: () => Promise<unknown>
}) {
  const { pending, run } = useAction()
  // An unapplied slider value is never overwritten by the poll.
  const [edited, setEdited] = useState<number | null>(null)
  const noise = edited ?? Math.round((settings?.error_rate ?? 0) * 100)

  const applyNoise = async () => {
    const done = await run(
      "noise",
      () => api("/api/noise", { error_rate: noise / 100 }),
      `Line noise set to ${noise}% per link`
    )
    if (done) {
      // Let the status poll catch up first, so the slider never jumps back.
      await onChanged()
      setEdited(null)
    }
  }

  const change = async (field: "method" | "crc_type", value: string) => {
    if (!value || value === settings?.[field]) return
    const message =
      field === "method"
        ? `Framing switched to ${(METHOD_NAMES[value] ?? value).toLowerCase()}`
        : `CRC switched to ${value}`
    if (
      await run(field, () => api("/api/settings", { [field]: value }), message)
    )
      onChanged()
  }

  return (
    <Section title="Link layer">
      <Panel className="p-4 md:p-6">
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="noise-slider">Line noise per link</FieldLabel>
            <div className="flex items-center gap-4">
              <Slider
                id="noise-slider"
                min={0}
                max={50}
                step={1}
                value={[noise]}
                onValueChange={([value]) => setEdited(value)}
                aria-label="Line noise per link, percent"
                disabled={!settings}
              />
              <output
                htmlFor="noise-slider"
                className="w-12 text-right font-mono tabular-nums"
              >
                {noise}%
              </output>
              <Button
                onClick={applyNoise}
                disabled={!settings || pending.has("noise")}
              >
                {pending.has("noise") && <Spinner data-icon="inline-start" />}
                Apply
              </Button>
            </div>
          </Field>
          <Field>
            <FieldTitle id="framing-label">Framing</FieldTitle>
            <ToggleGroup
              type="single"
              variant="outline"
              spacing={0}
              value={settings?.method ?? ""}
              onValueChange={(value: string) => change("method", value)}
              aria-labelledby="framing-label"
              disabled={!settings || pending.has("method")}
            >
              {(meta?.methods ?? []).map((method) => (
                <ToggleGroupItem key={method} value={method}>
                  {METHOD_NAMES[method] ?? method}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </Field>
          <Field>
            <FieldTitle id="crc-label">CRC</FieldTitle>
            <ToggleGroup
              type="single"
              variant="outline"
              spacing={0}
              value={settings?.crc_type ?? ""}
              onValueChange={(value: string) => change("crc_type", value)}
              aria-labelledby="crc-label"
              disabled={!settings || pending.has("crc_type")}
            >
              {(meta?.crc_types ?? []).map((crc) => (
                <ToggleGroupItem key={crc} value={crc} className="font-mono">
                  {crc}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </Field>
        </FieldGroup>
      </Panel>
    </Section>
  )
}

function ActionRow({
  name,
  description,
  children,
}: {
  name: string
  description: ReactNode
  children: ReactNode
}) {
  return (
    <TableRow>
      <TableHead scope="row" className="h-auto py-3 font-medium">
        {name}
      </TableHead>
      <TableCell className="whitespace-normal text-muted-foreground">
        {description}
      </TableCell>
      <TableCell className="py-2 text-right">{children}</TableCell>
    </TableRow>
  )
}

function TrafficCard({ sensors }: { sensors: string[] }) {
  const { pending, busy, run } = useAction()
  const [floodSensor, setFloodSensor] = useState("S1")

  const button = (
    key: string,
    label: string,
    ariaLabel: string,
    onClick: () => void
  ) => (
    <Button
      variant="outline"
      disabled={busy}
      aria-label={ariaLabel}
      onClick={onClick}
    >
      {pending.has(key) && <Spinner data-icon="inline-start" />}
      {label}
    </Button>
  )

  const attack = (kind: string) => () =>
    run(
      kind,
      () =>
        api<{ attack: string; sensor: string }>("/api/attack", {
          attack: kind,
        }),
      (data) => `${ATTACK_NAMES[data.attack]} launched from ${data.sensor}`
    )

  const flood = (spoof: boolean) => () =>
    run(
      spoof ? "spoof" : "flood",
      () =>
        api<{ sensor: string; frames: number }>("/api/flood", {
          sensor: floodSensor,
          spoof,
        }),
      (data) =>
        spoof
          ? `Sent ${data.frames} spoofed frames via ${data.sensor}`
          : `Flooding ${data.frames} frames from ${data.sensor}`
    )

  return (
    <Section title="Traffic">
      <Panel>
        <Table>
          <TableBody>
            <ActionRow
              name="Brute force"
              description="8 failed SSH logins for root from 192.168.1.55, via S3"
            >
              {button(
                "brute_force",
                "Launch",
                "Launch brute force",
                attack("brute_force")
              )}
            </ActionRow>
            <ActionRow
              name="Port scan"
              description="16 ports probed by 198.51.100.23, via S2"
            >
              {button(
                "port_scan",
                "Launch",
                "Launch port scan",
                attack("port_scan")
              )}
            </ActionRow>
            <ActionRow
              name="Malware beacon"
              description="6 calls to 198.51.100.77, one per second, via S2"
            >
              {button(
                "beacon",
                "Start",
                "Start malware beacon",
                attack("beacon")
              )}
            </ActionRow>
            <ActionRow
              name="Flood"
              description={
                <span className="flex flex-wrap items-center gap-3">
                  150 frames at once from
                  <ToggleGroup
                    type="single"
                    variant="outline"
                    spacing={0}
                    value={floodSensor}
                    onValueChange={(value: string) =>
                      value && setFloodSensor(value)
                    }
                    aria-label="Sensor to send from"
                  >
                    {sensors.map((id) => (
                      <ToggleGroupItem
                        key={id}
                        value={id}
                        className="font-mono"
                      >
                        {id}
                      </ToggleGroupItem>
                    ))}
                  </ToggleGroup>
                </span>
              }
            >
              {button("flood", "Flood", "Flood from sensor", flood(false))}
            </ActionRow>
            <ActionRow
              name="Unknown source"
              description="10 frames spoofed from 203.0.113.66 via the same sensor"
            >
              {button("spoof", "Send", "Send from unknown IP", flood(true))}
            </ActionRow>
          </TableBody>
        </Table>
      </Panel>
    </Section>
  )
}

export function ControlsTab({
  settings,
  meta,
  onChanged,
}: {
  settings: LinkSettings | undefined
  meta: Meta | undefined
  onChanged: () => Promise<unknown>
}) {
  return (
    <>
      <PageHeader title="Controls" />
      <PageBody>
        <div className="grid items-start gap-8 lg:grid-cols-2">
          <LinkLayerCard
            settings={settings}
            meta={meta}
            onChanged={onChanged}
          />
          <TrafficCard sensors={meta?.sensors ?? []} />
        </div>
      </PageBody>
    </>
  )
}
