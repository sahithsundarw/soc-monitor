import { act, renderHook } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { toast } from "sonner"

import { useAction } from "@/hooks/use-action"

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: Error) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe("useAction", () => {
  beforeEach(() => {
    vi.mocked(toast.success).mockClear()
    vi.mocked(toast.error).mockClear()
  })

  it("keeps each action pending until its own request finishes", async () => {
    const noise = deferred<string>()
    const crc = deferred<string>()
    const { result } = renderHook(() => useAction())
    let noiseDone!: Promise<unknown>
    let crcDone!: Promise<unknown>
    act(() => {
      noiseDone = result.current.run("noise", () => noise.promise, "Noise set")
      crcDone = result.current.run("crc", () => crc.promise, "CRC set")
    })
    expect([...result.current.pending].sort()).toEqual(["crc", "noise"])
    await act(async () => {
      noise.resolve("ok")
      await noiseDone
    })
    // The CRC request is still running, so it stays pending.
    expect([...result.current.pending]).toEqual(["crc"])
    expect(result.current.busy).toBe(true)
    await act(async () => {
      crc.reject(new Error("Unknown CRC type"))
      await crcDone
    })
    expect(result.current.busy).toBe(false)
    expect(toast.success).toHaveBeenCalledWith("Noise set")
    expect(toast.error).toHaveBeenCalledWith("Unknown CRC type")
  })

  it("returns the data, or null after a failure", async () => {
    const { result } = renderHook(() => useAction())
    let ok: unknown
    let failed: unknown
    await act(async () => {
      ok = await result.current.run(
        "a",
        async () => ({ sensor: "S1" }),
        (d) => `From ${d.sensor}`
      )
      failed = await result.current.run(
        "b",
        async () => Promise.reject(new Error("down")),
        "x"
      )
    })
    expect(ok).toEqual({ sensor: "S1" })
    expect(failed).toBeNull()
    expect(toast.success).toHaveBeenCalledWith("From S1")
  })
})
