import { describe, expect, it } from "vitest";

import { addDays, dayName, dueText } from "@/app/todos/due";

// Wednesday.
const today = "2026-10-07";

describe("dayName", () => {
  it("names the days around today", () => {
    expect(dayName(today, today)).toBe("Today");
    expect(dayName("2026-10-08", today)).toBe("Tomorrow");
    expect(dayName("2026-10-06", today)).toBe("Yesterday");
  });

  it("gives the weekday within the week, then the date", () => {
    expect(dayName("2026-10-09", today)).toBe("Friday");
    expect(dayName("2026-10-13", today)).toBe("Tuesday");
    expect(dayName("2026-10-14", today)).toBe("14 Oct");
    expect(dayName("2026-10-01", today)).toBe("1 Oct");
  });

  it("adds the year when it isn't this one", () => {
    expect(dayName("2027-01-05", today)).toBe("5 Jan 2027");
  });
});

describe("addDays", () => {
  it("crosses months, years and changes of clocks", () => {
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(addDays("2026-10-24", 2)).toBe("2026-10-26");
    expect(addDays("2026-10-07", -7)).toBe("2026-09-30");
  });
});

describe("dueText", () => {
  it("adds the time without seconds", () => {
    expect(dueText("2030-01-05", "09:30:00")).toBe("5 Jan 2030 09:30");
    expect(dueText("2030-01-05")).toBe("5 Jan 2030");
  });
});
