import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts"

import { Section } from "@/components/page"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart"
import { Skeleton } from "@/components/ui/skeleton"
import { formatTime, niceTop } from "@/lib/format"
import type { QosSecond } from "@/lib/types"

const chartConfig = {
  allowed: { label: "Allowed", color: "var(--chart-1)" },
  dropped: { label: "Dropped", color: "var(--chart-2)" },
} satisfies ChartConfig

type Point = QosSecond & { ago: number }

/** Seconds before now, so the x axis reads "45s ago … now". */
export function withAge(timeline: QosSecond[]): Point[] {
  return timeline.map((second, index) => ({
    ...second,
    ago: timeline.length - 1 - index,
  }))
}

function Legend() {
  return (
    <div className="flex gap-4 text-sm text-muted-foreground">
      {Object.entries(chartConfig).map(([key, item]) => (
        <span key={key} className="flex items-center gap-2">
          <span
            aria-hidden
            className="size-2.5 rounded-[2px]"
            style={{ background: item.color }}
          />
          {item.label}
        </span>
      ))}
    </div>
  )
}

function Gradient({ id, color }: { id: string; color: string }) {
  return (
    <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
      <stop offset="5%" stopColor={color} stopOpacity={0.35} />
      <stop offset="95%" stopColor={color} stopOpacity={0.02} />
    </linearGradient>
  )
}

/** Allowed vs dropped frames per second over the last minute (QoS policing). */
export function TokenBucketChart({
  timeline,
  className,
}: {
  timeline: QosSecond[] | undefined
  className?: string
}) {
  const top = niceTop(
    Math.max(0, ...(timeline ?? []).flatMap((s) => [s.allowed, s.dropped]))
  )

  return (
    <Section title="Token bucket" className={className} actions={<Legend />}>
      <span className="-mb-2 text-sm text-muted-foreground">
        frames per second
      </span>
      {timeline ? (
        <ChartContainer
          config={chartConfig}
          className="aspect-auto h-72 w-full text-sm"
          aria-label="Frames per second allowed and dropped by the token bucket, last 60 seconds"
        >
          <AreaChart
            data={withAge(timeline)}
            margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
          >
            <defs>
              <Gradient id="fill-allowed" color="var(--color-allowed)" />
              <Gradient id="fill-dropped" color="var(--color-dropped)" />
            </defs>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="ago"
              type="number"
              reversed
              domain={[0, timeline.length - 1]}
              ticks={[45, 30, 15, 0]}
              tickFormatter={(value: number) =>
                value === 0 ? "now" : `${value}s ago`
              }
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              tick={{ fontSize: 14 }}
            />
            <YAxis
              domain={[0, top]}
              ticks={[0, top / 2, top]}
              interval={0}
              width={40}
              tickLine={false}
              axisLine={false}
              tick={{ fontSize: 14 }}
            />
            <ChartTooltip
              cursor
              content={
                <ChartTooltipContent
                  indicator="line"
                  labelFormatter={(_, payload) =>
                    payload?.[0]
                      ? formatTime((payload[0].payload as Point).t)
                      : ""
                  }
                />
              }
            />
            <Area
              dataKey="allowed"
              type="monotone"
              stroke="var(--color-allowed)"
              strokeWidth={2}
              fill="url(#fill-allowed)"
              isAnimationActive={false}
            />
            <Area
              dataKey="dropped"
              type="monotone"
              stroke="var(--color-dropped)"
              strokeWidth={2}
              fill="url(#fill-dropped)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ChartContainer>
      ) : (
        <Skeleton className="h-72 w-full" />
      )}
    </Section>
  )
}
