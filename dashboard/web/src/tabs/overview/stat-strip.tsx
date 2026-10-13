import { Skeleton } from "@/components/ui/skeleton"
import { formatNumber, rateLabel } from "@/lib/format"
import { TILES, type Status, type Tile } from "@/lib/types"
import { cn } from "@/lib/utils"

const TILE_LABELS: Record<Tile, string> = {
  events: "Events received",
  alerts: "Alerts",
  corrupted: "Corrupted frames",
  retransmissions: "Retransmissions",
  firewall_blocks: "Firewall blocks",
}

/** Only good events rising is good news; every other counter rising is trouble. */
function rateClass(tile: Tile): string {
  return tile === "events" ? "text-positive" : "text-destructive"
}

export function StatStrip({ status }: { status: Status | undefined }) {
  return (
    <dl className="grid grid-cols-2 gap-y-6 md:grid-cols-5 md:divide-x">
      {TILES.map((tile) => {
        const rate = status
          ? rateLabel(status.tiles[tile], status.trends[tile])
          : ""
        return (
          <div
            key={tile}
            className="flex min-w-0 flex-col gap-2 pr-4 md:px-6 md:first:pl-0 md:last:pr-0"
          >
            <div className="flex items-baseline justify-between gap-2">
              <dt className="truncate text-sm text-muted-foreground">
                {TILE_LABELS[tile]}
              </dt>
              <span
                className={cn(
                  "text-sm font-medium tabular-nums",
                  rateClass(tile)
                )}
              >
                {rate}
              </span>
            </div>
            <dd className="text-3xl font-semibold tracking-tight tabular-nums">
              {status ? (
                formatNumber(status.tiles[tile])
              ) : (
                <Skeleton className="h-9 w-20" />
              )}
            </dd>
          </div>
        )
      })}
    </dl>
  )
}
