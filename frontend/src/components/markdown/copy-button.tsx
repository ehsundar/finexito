"use client";

import { CheckIcon, CopyIcon } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Copies the code block it sits beside. It reads the text from the rendered
 * `<pre>` rather than taking it as a prop, so the code is not sent twice.
 */
export function CopyButton({ className }: { className?: string }) {
  const ref = useRef<HTMLButtonElement>(null);
  const [copied, setCopied] = useState(false);

  async function copy() {
    const code = ref.current?.parentElement?.querySelector("pre")?.textContent ?? "";
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // No clipboard access (an insecure origin, or permission denied): nothing to do.
    }
  }

  return (
    <Button
      ref={ref}
      type="button"
      variant="ghost"
      size="icon-sm"
      onClick={copy}
      aria-label={copied ? "Copied" : "Copy code"}
      className={cn("bg-muted/80 text-muted-foreground backdrop-blur", className)}
    >
      {copied ? <CheckIcon /> : <CopyIcon />}
    </Button>
  );
}
