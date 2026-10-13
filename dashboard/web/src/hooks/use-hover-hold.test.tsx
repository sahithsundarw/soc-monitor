import { act, renderHook } from "@testing-library/react"
import { describe, expect, it } from "vitest"

import { useHoverHold } from "@/hooks/use-hover-hold"

describe("useHoverHold", () => {
  it("freezes the list while hovered and catches up on leave", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useHoverHold(value),
      {
        initialProps: { value: ["a"] },
      }
    )
    act(() => result.current.holdProps.onMouseEnter())
    rerender({ value: ["b", "a"] })
    expect(result.current.shown).toEqual(["a"])
    act(() => result.current.holdProps.onMouseLeave())
    expect(result.current.shown).toEqual(["b", "a"])
  })
})
