"use client";

import { Dialog } from "@base-ui/react/dialog";
import { Bold, Heading, Italic, Link, List, ListChecks, ListOrdered, Quote } from "lucide-react";
import { useRef, useState } from "react";

import { Markdown } from "@/components/markdown/markdown";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type Tool = { label: string; icon: React.ReactNode } & (
  | { wrap: [string, string]; sample: string }
  | { prefix: string }
);

const TOOLS: Tool[] = [
  { label: "Bold", icon: <Bold />, wrap: ["**", "**"], sample: "bold" },
  { label: "Italic", icon: <Italic />, wrap: ["_", "_"], sample: "italic" },
  { label: "Heading", icon: <Heading />, prefix: "## " },
  { label: "Bulleted list", icon: <List />, prefix: "- " },
  { label: "Numbered list", icon: <ListOrdered />, prefix: "1. " },
  { label: "Checklist", icon: <ListChecks />, prefix: "- [ ] " },
  { label: "Quote", icon: <Quote />, prefix: "> " },
  { label: "Link", icon: <Link />, wrap: ["[", "](https://)"], sample: "link text" },
];

/**
 * A full-screen editor for Markdown, with buttons for the common marks so
 * nobody has to know the syntax, and a preview of how it will read.
 * Closes when `onSave` says it worked.
 */
export function MarkdownEditor({
  open,
  onOpenChange,
  title,
  initial,
  placeholder,
  maxLength,
  onSave,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  initial: string;
  placeholder?: string;
  maxLength: number;
  onSave: (value: string) => Promise<boolean>;
}) {
  const [value, setValue] = useState(initial);
  const [preview, setPreview] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);

  function apply(tool: Tool) {
    const el = area.current;
    if (!el) return;
    el.focus();
    let { selectionStart: start, selectionEnd: end } = el;
    let text: string;
    if ("wrap" in tool) {
      const inner = value.slice(start, end) || tool.sample;
      text = tool.wrap[0] + inner + tool.wrap[1];
    } else {
      // Marks every line the selection touches.
      start = value.lastIndexOf("\n", start - 1) + 1;
      const next = value.indexOf("\n", end);
      end = next === -1 ? value.length : next;
      text = value
        .slice(start, end)
        .split("\n")
        .map((line, i) => (tool.prefix === "1. " ? `${i + 1}. ` : tool.prefix) + line)
        .join("\n");
    }
    el.setSelectionRange(start, end);
    // Keeps the browser's undo history, unlike setting the value.
    if (!document.execCommand("insertText", false, text)) {
      el.setRangeText(text, start, end, "end");
      setValue(el.value);
    }
    if ("wrap" in tool && start === end) {
      el.setSelectionRange(start + tool.wrap[0].length, start + tool.wrap[0].length + tool.sample.length);
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (next) {
          setValue(initial);
          setPreview(false);
        }
        onOpenChange(next);
      }}
    >
      <Dialog.Portal>
        <Dialog.Popup className="bg-background fixed inset-0 z-50 mx-auto flex h-dvh max-w-md flex-col pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)] outline-none sm:border-x">
          <header className="flex min-h-14 items-center gap-2 px-2">
            <Dialog.Close render={<Button variant="ghost" size="lg" />}>Cancel</Dialog.Close>
            <Dialog.Title className="flex-1 text-center font-medium">{title}</Dialog.Title>
            <Button size="lg" onClick={async () => (await onSave(value)) && onOpenChange(false)}>
              Save
            </Button>
          </header>

          <div className="flex items-center gap-1 overflow-x-auto border-y px-2 py-1.5">
            {TOOLS.map((tool) => (
              <Button
                key={tool.label}
                variant="ghost"
                size="icon-lg"
                aria-label={tool.label}
                title={tool.label}
                disabled={preview}
                // Keeps the selection: the textarea stays focused.
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => apply(tool)}
              >
                {tool.icon}
              </Button>
            ))}
            <Button
              variant="outline"
              size="lg"
              className={cn("ml-auto", preview && "bg-muted")}
              aria-pressed={preview}
              onClick={() => setPreview(!preview)}
            >
              {preview ? "Edit" : "Preview"}
            </Button>
          </div>

          {preview ? (
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {value.trim() ? <Markdown source={value} /> : <p className="text-muted-foreground">Nothing yet.</p>}
            </div>
          ) : (
            <textarea
              ref={area}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              maxLength={maxLength}
              placeholder={placeholder}
              autoFocus
              className="min-h-0 flex-1 resize-none bg-transparent p-4 text-base leading-7 outline-none"
            />
          )}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
