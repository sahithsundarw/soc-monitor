import { AppSidebar } from "@/components/app-sidebar"
import { TopBar } from "@/components/top-bar"
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { usePoll } from "@/hooks/use-poll"
import { useStoredState } from "@/hooks/use-stored-state"
import type { Meta, Status } from "@/lib/types"
import { isTabId, TABS, type TabId } from "@/lib/tabs"
import { ControlsTab } from "@/tabs/controls-tab"
import { DiagnosticsTab } from "@/tabs/diagnostics-tab"
import { EmailsTab } from "@/tabs/emails-tab"
import { InspectorTab } from "@/tabs/inspector/inspector-tab"
import { OverviewTab } from "@/tabs/overview/overview-tab"
import { ReportsTab } from "@/tabs/reports-tab"
import { TopologyTab } from "@/tabs/topology/topology-tab"

const POLL_MS = 1000

/** Only the visible tab is mounted, so only its endpoints are polled. */
function ActiveTab({
  tab,
  status,
  meta,
  refreshStatus,
}: {
  tab: TabId
  status: Status | undefined
  meta: Meta | undefined
  refreshStatus: () => void
}) {
  switch (tab) {
    case "overview":
      return <OverviewTab status={status} />
    case "topology":
      return <TopologyTab sensors={meta?.sensors ?? []} />
    case "inspector":
      return <InspectorTab />
    case "controls":
      return (
        <ControlsTab
          settings={status?.settings}
          meta={meta}
          onChanged={refreshStatus}
        />
      )
    case "diagnostics":
      return <DiagnosticsTab />
    case "reports":
      return <ReportsTab ftpAddress={meta?.ftp_address} />
    case "emails":
      return <EmailsTab />
  }
}

export function App() {
  const [tab, setTab] = useStoredState<TabId>("tab", "overview", isTabId)
  const status = usePoll<Status>("/api/status", POLL_MS)
  const meta = usePoll<Meta>("/api/meta", 2000, { once: true })
  const current = TABS.find((item) => item.id === tab) ?? TABS[0]

  return (
    <TooltipProvider>
      <SidebarProvider>
        <AppSidebar
          tab={tab}
          onTabChange={setTab}
          emailCount={status.data?.email_count ?? 0}
          settings={status.data?.settings}
        />
        <SidebarInset className="min-w-0">
          <TopBar section={current.group} title={current.title} poll={status} />
          <main className="flex min-w-0 flex-col">
            <ActiveTab
              tab={tab}
              status={status.data}
              meta={meta.data}
              refreshStatus={status.refresh}
            />
          </main>
        </SidebarInset>
      </SidebarProvider>
      <Toaster position="bottom-right" />
    </TooltipProvider>
  )
}

export default App
