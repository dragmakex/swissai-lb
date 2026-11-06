import { afterEach, describe, expect, it, vi } from "vitest";

import { buildCsv, downloadCsv } from "@/utils/csv";

afterEach(() => vi.unstubAllGlobals());

describe("CSV metadata export", () => {
  it("preserves unknowns and zeroes and quotes separators, quotes and newlines", () => {
    expect(buildCsv([[null, undefined, 0, false, "a,b", 'say "hi"', "a\nb"]]))
      .toBe(',,0,false,"a,b","say ""hi""","a\nb"');
  });

  it.each(["=1+1", "+cmd", "-cmd", "@SUM(A1)", " \t=cmd", "\u0000=cmd"])(
    "makes spreadsheet formula %j literal", value => {
      expect(buildCsv([[value]])).toBe(`'${value}`);
    },
  );

  it("does not modify trusted numeric values", () => {
    expect(buildCsv([[-1, 0, 1]])).toBe("-1,0,1");
  });

  it("releases its object URL even when the browser rejects the download", () => {
    const revoke = vi.fn();
    vi.stubGlobal("URL", class extends URL {
      static createObjectURL = vi.fn(() => "blob:csv-test");
      static revokeObjectURL = revoke;
    });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {
      throw new Error("download blocked");
    });
    try {
      expect(() => downloadCsv("test.csv", [["safe"]])).toThrow("download blocked");
      expect(revoke).toHaveBeenCalledOnce();
      expect(revoke).toHaveBeenCalledWith("blob:csv-test");
    } finally {
      click.mockRestore();
    }
  });
});
