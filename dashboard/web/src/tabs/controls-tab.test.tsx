import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it } from "vitest"

import type { LinkSettings, Meta } from "@/lib/types"
import { ControlsTab } from "@/tabs/controls-tab"

const meta: Meta = {
  sensors: ["S1", "S2", "S3"],
  methods: ["character", "bit"],
  crc_types: ["CRC-12", "CRC-16", "CRC-CCITT"],
  ftp_address: "127.0.0.1:2121",
}

const settings = (error_rate: number): LinkSettings => ({
  method: "bit",
  crc_type: "CRC-16",
  error_rate,
})

describe("ControlsTab", () => {
  it("never lets the poll overwrite a slider value that was not applied", async () => {
    const user = userEvent.setup()
    const onChanged = async () => true
    const { rerender } = render(
      <ControlsTab settings={settings(0.1)} meta={meta} onChanged={onChanged} />
    )
    expect(screen.getByText("10%")).toBeInTheDocument()
    screen.getByRole("slider").focus()
    await user.keyboard("{ArrowRight}{ArrowRight}")
    expect(screen.getByText("12%")).toBeInTheDocument()
    // A new status poll arrives with the server's (unchanged) value.
    rerender(
      <ControlsTab settings={settings(0.1)} meta={meta} onChanged={onChanged} />
    )
    expect(screen.getByText("12%")).toBeInTheDocument()
  })

  it("shows the live framing method and CRC as selected", () => {
    render(
      <ControlsTab
        settings={settings(0)}
        meta={meta}
        onChanged={async () => true}
      />
    )
    expect(screen.getByRole("radio", { name: "Bit stuffing" })).toHaveAttribute(
      "data-state",
      "on"
    )
    expect(screen.getByRole("radio", { name: "CRC-16" })).toHaveAttribute(
      "data-state",
      "on"
    )
  })
})
