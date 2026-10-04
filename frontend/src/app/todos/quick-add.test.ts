import { describe, expect, it } from "vitest";

import { markDate, parse } from "@/app/todos/quick-add";
import type { Label, Project, Section } from "@/app/todos/shell";

const projects = [
  { id: "inbox", name: "Inbox", is_inbox: true },
  { id: "home", name: "Home" },
  { id: "home-office", name: "Home office" },
] as Project[];
const labels = [{ id: "urgent", name: "urgent" }] as Label[];
const sections = [{ id: "kitchen", name: "Kitchen", project: "home" }] as Section[];
const sectionsOf = (project: Project | null) => sections.filter((s) => s.project === project?.id);

const read = (text: string) => parse(text, projects, labels, sectionsOf);

describe("quick add", () => {
  it("takes the longest project name, a section in it, and the priority", () => {
    const parsed = read("Fix tap #Home office p2");
    expect(parsed.project?.id).toBe("home-office");
    expect(parsed.priority).toBe(2);
    expect(parsed.content).toBe("Fix tap");

    const inKitchen = read("Fix tap #Home /Kitchen");
    expect(inKitchen.project?.id).toBe("home");
    expect(inKitchen.section).toEqual(sections[0]);
  });

  it("knows labels, and names new ones and new sections", () => {
    const parsed = read("Call #urgent #later /Garden");
    expect(parsed.labels).toEqual([labels[0], "later"]);
    expect(parsed.section).toBe("Garden");
    expect(parsed.content).toBe("Call");
  });

  it("keeps escaped tokens as text", () => {
    const parsed = read("Buy \\#Home \\p1");
    expect(parsed.project).toBeNull();
    expect(parsed.priority).toBeNull();
    expect(parsed.content).toBe("Buy #Home p1");
  });

  it("marks the date the server found, splitting the text around it", () => {
    const text = "Pay rent every month #Home";
    const parts = markDate(read(text).parts, [9, 20]);
    expect(parts).toEqual([
      { text: "Pay rent ", kind: "text" },
      { text: "every month", kind: "date" },
      { text: " ", kind: "text" },
      { text: "#Home", kind: "project", created: false },
    ]);
  });
});
