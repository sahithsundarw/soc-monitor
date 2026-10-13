import { render } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import type { Topology } from "@/lib/types"
import { NetworkGraph, routeLinks } from "@/tabs/topology/network-graph"

const node = (id: string, x: number) => ({
  id,
  name: id,
  role: "router",
  sim_ip: "10.0.0.1",
  x,
  y: 100,
})

const topology: Topology = {
  nodes: [node("S1", 0), node("R2", 100), node("SOC", 200), node("R4", 150)],
  links: [
    { a: "S1", b: "R2", cost: 1, up: true },
    { a: "R2", b: "SOC", cost: 1, up: true },
    { a: "R4", b: "SOC", cost: 2, up: false },
  ],
  routes: {},
  tables: {},
  destinations: [],
}

describe("routeLinks", () => {
  it("keys each hop independently of direction", () => {
    expect(routeLinks(["S1", "R2", "SOC"])).toEqual(
      new Set(["R2-S1", "R2-SOC"])
    )
  })
})

describe("NetworkGraph", () => {
  it("highlights only the links on the route and labels down links", () => {
    const { container } = render(
      <NetworkGraph
        topology={topology}
        route={{ path: ["S1", "R2", "SOC"], cost: 2 }}
      />
    )
    expect(container.querySelectorAll("line[data-route]")).toHaveLength(2)
    expect(container).toHaveTextContent("down")
  })
})
