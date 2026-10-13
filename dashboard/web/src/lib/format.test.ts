import { describe, expect, it } from "vitest"

import {
  formatBytes,
  formatDuration,
  niceTop,
  rateLabel,
  splitSubject,
} from "@/lib/format"

describe("niceTop", () => {
  it("never drops below 10 so routine traffic sits low", () => {
    expect(niceTop(0)).toBe(10)
    expect(niceTop(3)).toBe(10)
  })

  it("rounds a flood peak up to an even step", () => {
    expect(niceTop(37)).toBe(40)
    expect(niceTop(150)).toBe(200)
    expect(niceTop(301)).toBe(400)
  })
})

describe("formatDuration", () => {
  it("uses seconds, minutes, then hours and padded minutes", () => {
    expect(formatDuration(42)).toBe("42s")
    expect(formatDuration(7 * 60 + 5)).toBe("7m")
    expect(formatDuration(3600 + 5 * 60)).toBe("1h 05m")
  })
})

describe("formatBytes", () => {
  it("switches to KB from 1024 bytes", () => {
    expect(formatBytes(563)).toBe("563 B")
    expect(formatBytes(7782)).toBe("7.6 KB")
  })
})

describe("splitSubject", () => {
  it("splits an alert email subject into severity and title", () => {
    expect(splitSubject("[HIGH] Brute-force login")).toEqual({
      severity: "HIGH",
      title: "Brute-force login",
    })
  })

  it("keeps unknown subjects whole", () => {
    expect(splitSubject("[NOTICE] Hello")).toEqual({
      severity: null,
      title: "[NOTICE] Hello",
    })
    expect(splitSubject("Plain")).toEqual({ severity: null, title: "Plain" })
  })
})

describe("rateLabel", () => {
  it("shows the last-minute rate only when it differs from the total", () => {
    expect(rateLabel(100, [10, 20])).toBe("+30/min")
    expect(rateLabel(30, [10, 20])).toBe("")
    expect(rateLabel(30, [0, 0])).toBe("")
  })
})
