import { PageBody, PageHeader } from "@/components/page"
import { Separator } from "@/components/ui/separator"
import type { Status } from "@/lib/types"
import { AlertFeed } from "@/tabs/overview/alert-feed"
import { SensorTable } from "@/tabs/overview/sensor-table"
import { StatStrip } from "@/tabs/overview/stat-strip"
import { TokenBucketChart } from "@/tabs/overview/token-bucket-chart"

export function OverviewTab({
  status,
  active,
}: {
  status: Status | undefined
  active: boolean
}) {
  return (
    <>
      <PageHeader title="Overview" />
      <PageBody>
        <StatStrip status={status} />
        <Separator />
        <div className="grid gap-8 xl:grid-cols-5">
          <AlertFeed
            alerts={status?.alerts}
            counts={status?.severity_counts}
            visible={active}
            className="xl:col-span-3"
          />
          {/* A hidden chart has no size to draw in, so it is drawn only when shown. */}
          {active && (
            <TokenBucketChart
              timeline={status?.qos.timeline}
              className="xl:col-span-2"
            />
          )}
        </div>
        <Separator />
        <SensorTable status={status} />
      </PageBody>
    </>
  )
}
