import { Panel, Section } from "@/components/page"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { formatNumber } from "@/lib/format"
import type { Status } from "@/lib/types"
import { cn } from "@/lib/utils"

const COLUMNS = ["Good UDP", "Good TCP", "Corrupted", "Retransmitted", "Lost"]

type Row = { name: string; values: number[] }

/** One row per sensor (the "unknown" bucket is frames too damaged to read)
 * plus an "All sensors" total. */
export function sensorRows(perSensor: Status["per_sensor"]): {
  rows: Row[]
  total: Row
} {
  const totals = [0, 0, 0, 0, 0]
  const rows = Object.entries(perSensor).map(([sensor, { udp, tcp }]) => {
    const values = [
      udp.good,
      tcp.good,
      udp.corrupted + tcp.corrupted,
      udp.retransmitted + tcp.retransmitted,
      udp.lost + tcp.lost,
    ]
    values.forEach((value, index) => {
      totals[index] += value
    })
    return { name: sensor === "unknown" ? "Unreadable" : sensor, values }
  })
  return { rows, total: { name: "All sensors", values: totals } }
}

function ProtocolSplit({ protocols }: { protocols: Status["protocols"] }) {
  const total = protocols.udp + protocols.tcp
  const udpShare = total ? Math.round((protocols.udp / total) * 100) : 0
  const tcpShare = total ? 100 - udpShare : 0
  return (
    <div
      className="flex items-center gap-3 text-sm"
      aria-label="UDP and TCP share of good frames"
    >
      <span>
        UDP <span className="font-medium tabular-nums">{udpShare}%</span>{" "}
        <span className="text-muted-foreground tabular-nums">
          ({formatNumber(protocols.udp)})
        </span>
      </span>
      <span
        className="flex h-2 w-28 gap-0.5 overflow-hidden rounded-full max-sm:hidden"
        aria-hidden
      >
        <span
          className="bg-chart-1"
          style={{ width: `${total ? udpShare : 50}%` }}
        />
        <span className="flex-1 bg-chart-2" />
      </span>
      <span>
        TCP <span className="font-medium tabular-nums">{tcpShare}%</span>{" "}
        <span className="text-muted-foreground tabular-nums">
          ({formatNumber(protocols.tcp)})
        </span>
      </span>
    </div>
  )
}

function NumberCells({ values }: { values: number[] }) {
  return values.map((value, index) => (
    <TableCell
      key={COLUMNS[index]}
      className={cn(
        "text-right tabular-nums",
        !value && "text-muted-foreground"
      )}
    >
      {formatNumber(value)}
    </TableCell>
  ))
}

export function SensorTable({ status }: { status: Status | undefined }) {
  const table = status ? sensorRows(status.per_sensor) : null
  return (
    <Section
      title="Frames per sensor"
      actions={status && <ProtocolSplit protocols={status.protocols} />}
    >
      <Panel>
        {!table ? (
          <Skeleton className="m-4 h-40" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sensor</TableHead>
                {COLUMNS.map((column) => (
                  <TableHead key={column} className="text-right">
                    {column}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {table.rows.map((row) => (
                <TableRow key={row.name}>
                  <TableCell className="font-medium">{row.name}</TableCell>
                  <NumberCells values={row.values} />
                </TableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TableCell>{table.total.name}</TableCell>
                <NumberCells values={table.total.values} />
              </TableRow>
            </TableFooter>
          </Table>
        )}
      </Panel>
    </Section>
  )
}
