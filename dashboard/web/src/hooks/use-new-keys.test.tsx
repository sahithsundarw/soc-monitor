import { renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { useNewKeys } from "@/hooks/use-new-keys"

describe("useNewKeys", () => {
  it("treats the first list as backlog and later arrivals as new", () => {
    const { result, rerender } = renderHook(({ keys }) => useNewKeys(keys), {
      initialProps: { keys: undefined as string[] | undefined },
    })
    expect(result.current.size).toBe(0)
    rerender({ keys: ["a", "b"] })
    expect(result.current.size).toBe(0)
    rerender({ keys: ["c", "a", "b"] })
    expect([...result.current]).toEqual(["c"])
    // The next poll with nothing new clears it; a key seen before never returns as new.
    rerender({ keys: ["c", "a"] })
    expect(result.current.size).toBe(0)
    rerender({ keys: ["b", "c", "a"] })
    expect(result.current.size).toBe(0)
  })

  it("marks everything that arrived while hidden as new once shown", () => {
    const { result, rerender } = renderHook(
      ({ keys, visible }) => useNewKeys(keys, visible),
      { initialProps: { keys: ["a"], visible: true } }
    )
    rerender({ keys: ["b", "a"], visible: false })
    rerender({ keys: ["c", "b", "a"], visible: false })
    expect(result.current.size).toBe(0)
    rerender({ keys: ["c", "b", "a"], visible: true })
    expect([...result.current].sort()).toEqual(["b", "c"])
  })
})
