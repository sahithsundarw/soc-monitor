import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import type { Alert, Severity } from "@/lib/types"
import { AlertFeed } from "@/tabs/overview/alert-feed"

function alert(severity: Severity, title: string, ts = 1_700_000_000): Alert {
  return {
    ts,
    rule: title,
    source: "S1",
    severity,
    title,
    detail: `${title} detail`,
  }
}

const alerts = [
  alert("HIGH", "Brute-force login"),
  alert("MEDIUM", "Link tampering or noise", 1_700_000_001),
]
const counts = { CRITICAL: 0, HIGH: 1, MEDIUM: 1, LOW: 0 }

describe("AlertFeed", () => {
  it("lists every alert with its severity", () => {
    render(<AlertFeed alerts={alerts} counts={counts} />)
    const table = screen.getByRole("table", { name: "Recent alerts" })
    // One header row plus one row per alert.
    expect(within(table).getAllByRole("row")).toHaveLength(3)
    expect(within(table).getByText("High")).toHaveAttribute(
      "data-variant",
      "high"
    )
  })

  it("filters by severity and says when a filter is empty", async () => {
    const user = userEvent.setup()
    render(<AlertFeed alerts={alerts} counts={counts} />)
    await user.click(screen.getByRole("radio", { name: /High/ }))
    expect(screen.getByText("Brute-force login")).toBeInTheDocument()
    expect(
      screen.queryByText("Link tampering or noise")
    ).not.toBeInTheDocument()
    await user.click(screen.getByRole("radio", { name: /Critical/ }))
    expect(screen.getByText("No critical alerts")).toBeInTheDocument()
  })

  it("shows the empty state before any alert", () => {
    render(
      <AlertFeed
        alerts={[]}
        counts={{ CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 }}
      />
    )
    expect(screen.getByText("No alerts yet")).toBeInTheDocument()
  })

  it("shows skeletons while loading", () => {
    const { container } = render(
      <AlertFeed alerts={undefined} counts={undefined} />
    )
    expect(
      container.querySelectorAll("[data-slot=skeleton]").length
    ).toBeGreaterThan(0)
  })
})
