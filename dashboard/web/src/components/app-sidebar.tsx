import { ShieldCheckIcon } from "lucide-react"

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"
import type { LinkSettings } from "@/lib/types"
import { TAB_GROUPS, TABS, type TabId } from "@/lib/tabs"

function LinkSettingsList({
  settings,
}: {
  settings: LinkSettings | undefined
}) {
  const rows = [
    [
      "Stuffing",
      settings ? (settings.method === "bit" ? "Bit" : "Character") : "–",
    ],
    ["CRC", settings?.crc_type ?? "–"],
    [
      "Line noise",
      settings ? `${Math.round(settings.error_rate * 100)}%` : "–",
    ],
  ]
  return (
    <div className="flex flex-col gap-2 rounded-lg border bg-background p-3 group-data-[collapsible=icon]:hidden">
      <span className="text-xs font-medium text-muted-foreground">
        Link layer
      </span>
      <dl
        aria-label="Live link settings"
        className="flex flex-col gap-1 text-sm"
      >
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-2">
            <dt className="text-muted-foreground">{label}</dt>
            <dd className="font-medium">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

export function AppSidebar({
  tab,
  onTabChange,
  emailCount,
  settings,
}: {
  tab: TabId
  onTabChange: (tab: TabId) => void
  emailCount: number
  settings: LinkSettings | undefined
}) {
  const { isMobile, setOpenMobile } = useSidebar()

  const choose = (next: TabId) => {
    onTabChange(next)
    if (isMobile) setOpenMobile(false)
  }

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              size="lg"
              onClick={() => choose("overview")}
              tooltip="SOC Monitor"
            >
              <div className="flex aspect-square size-8 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
                <ShieldCheckIcon />
              </div>
              <div className="grid flex-1 text-left leading-tight">
                <span className="truncate font-semibold">SOC Monitor</span>
                <span className="truncate text-xs text-muted-foreground">
                  Telemetry and routing
                </span>
              </div>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {TAB_GROUPS.map((group) => (
          <SidebarGroup key={group}>
            <SidebarGroupLabel>{group}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu aria-label={group}>
                {TABS.filter((item) => item.group === group).map((item) => (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      isActive={item.id === tab}
                      aria-current={item.id === tab ? "page" : undefined}
                      tooltip={item.title}
                      onClick={() => choose(item.id)}
                    >
                      <item.icon />
                      <span>{item.title}</span>
                    </SidebarMenuButton>
                    {item.id === "emails" && emailCount > 0 && (
                      <SidebarMenuBadge aria-label={`${emailCount} emails`}>
                        {emailCount}
                      </SidebarMenuBadge>
                    )}
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarFooter>
        <LinkSettingsList settings={settings} />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
