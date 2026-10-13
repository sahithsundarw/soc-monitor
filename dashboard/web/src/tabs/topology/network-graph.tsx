import type { Route, Topology } from "@/lib/types"
import { cn } from "@/lib/utils"

const NODE_WIDTH = 132
const NODE_HEIGHT = 50

function linkKey(a: string, b: string): string {
  return a < b ? `${a}-${b}` : `${b}-${a}`
}

/** The links a path walks over, as order-independent keys. */
export function routeLinks(path: string[]): Set<string> {
  const keys = new Set<string>()
  for (let i = 0; i + 1 < path.length; i += 1)
    keys.add(linkKey(path[i], path[i + 1]))
  return keys
}

/** The weighted graph Dijkstra runs on, with the chosen sensor's route drawn
 * in the accent colour and failed links dashed. */
export function NetworkGraph({
  topology,
  route,
}: {
  topology: Topology
  route: Route
}) {
  const onRoute = routeLinks(route.path)
  const position = new Map(topology.nodes.map((node) => [node.id, node]))

  return (
    <svg
      viewBox="12 44 776 336"
      role="img"
      aria-label={`Network topology. Current route ${route.path.join(" to ") || "none"}.`}
      className="mx-auto block h-auto max-h-[26rem] w-full"
    >
      {topology.links.map((link) => {
        const a = position.get(link.a)
        const b = position.get(link.b)
        if (!a || !b) return null
        const isRoute = link.up && onRoute.has(linkKey(link.a, link.b))
        const midX = (a.x + b.x) / 2
        const midY = (a.y + b.y) / 2
        const label = link.up ? String(link.cost) : "down"
        const labelWidth = label.length * 8 + 12
        return (
          <g key={linkKey(link.a, link.b)}>
            <line
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              data-route={isRoute || undefined}
              className={cn(
                "stroke-link-idle",
                !link.up && "[stroke-dasharray:6_6]",
                isRoute && "animate-route-pulse stroke-primary"
              )}
              strokeWidth={isRoute ? 4 : 2}
            />
            <rect
              x={midX - labelWidth / 2}
              y={midY - 10}
              width={labelWidth}
              height={18}
              rx={4}
              className="fill-card"
            />
            <text
              x={midX}
              y={midY + 4}
              textAnchor="middle"
              className={cn(
                "font-mono text-[13px]",
                link.up ? "fill-muted-foreground" : "fill-destructive"
              )}
            >
              {label}
            </text>
          </g>
        )
      })}
      {topology.nodes.map((node) => {
        const isRoute = route.path.includes(node.id)
        return (
          <g key={node.id} transform={`translate(${node.x} ${node.y})`}>
            <rect
              x={-NODE_WIDTH / 2}
              y={-NODE_HEIGHT / 2}
              width={NODE_WIDTH}
              height={NODE_HEIGHT}
              rx={8}
              className={cn(
                "fill-card",
                isRoute ? "stroke-primary" : "stroke-link-idle"
              )}
              strokeWidth={isRoute ? 2 : 1.5}
            />
            <text
              x={-52}
              y={-3}
              className="fill-foreground text-sm font-medium"
            >
              {node.id}
              {node.role === "sensor" && (
                <tspan dx={6} className="fill-muted-foreground font-normal">
                  {node.name}
                </tspan>
              )}
            </text>
            <text
              x={-52}
              y={15}
              className="fill-muted-foreground font-mono text-xs"
            >
              {node.sim_ip}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function LegendLine({
  className,
  dashed,
  width = 2,
}: {
  className: string
  dashed?: boolean
  width?: number
}) {
  return (
    <svg viewBox="0 0 28 8" aria-hidden className="h-2 w-7">
      <line
        x1={1}
        y1={4}
        x2={27}
        y2={4}
        className={cn(className, dashed && "[stroke-dasharray:6_6]")}
        strokeWidth={width}
      />
    </svg>
  )
}

export function GraphLegend() {
  return (
    <ul
      aria-label="Legend"
      className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted-foreground"
    >
      <li className="flex items-center gap-2">
        <LegendLine className="stroke-primary" width={4} />
        Current route
      </li>
      <li className="flex items-center gap-2">
        <LegendLine className="stroke-link-idle" />
        Link up, with cost
      </li>
      <li className="flex items-center gap-2">
        <LegendLine className="stroke-link-idle" dashed />
        Link down
      </li>
    </ul>
  )
}
