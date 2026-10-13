import { describe, expect, it } from "vitest"

import { connection } from "@/lib/connection"
import type { Status } from "@/lib/types"

const status = { running: true, uptime_s: 125 } as Status

describe("connection", () => {
  it("says connecting before the first reply, disconnected after a failure", () => {
    expect(connection(undefined, null, 0, 1000).state).toBe("loading")
    expect(connection(undefined, "Failed to fetch", 0, 1000)).toEqual({
      state: "disconnected",
      text: "Disconnected",
    })
  })

  it("shows uptime while running and Stopped otherwise", () => {
    expect(connection(status, null, 1000, 1500).text).toBe("Running 2m")
    expect(
      connection({ ...status, running: false }, null, 1000, 1500).text
    ).toBe("Stopped")
  })

  it("marks numbers older than 5 s as stale, even if the server dropped", () => {
    expect(connection(status, "Failed to fetch", 1000, 8000)).toEqual({
      state: "stale",
      text: "Stale 7s",
    })
  })
})
