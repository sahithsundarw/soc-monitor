import { describe, expect, it } from "vitest"

import { sensorRows } from "@/tabs/overview/sensor-table"

const counts = (good: number, corrupted = 0, retransmitted = 0, lost = 0) => ({
  good,
  corrupted,
  retransmitted,
  lost,
})

describe("sensorRows", () => {
  it("adds UDP and TCP faults, names the unknown bucket, and totals each column", () => {
    const { rows, total } = sensorRows({
      S1: { udp: counts(10, 1, 2, 0), tcp: counts(3, 1, 1, 1) },
      unknown: { udp: counts(0, 4), tcp: counts(0) },
    })
    expect(rows).toEqual([
      { name: "S1", values: [10, 3, 2, 3, 1] },
      { name: "Unreadable", values: [0, 0, 4, 0, 0] },
    ])
    expect(total).toEqual({ name: "All sensors", values: [10, 3, 6, 3, 1] })
  })
})
