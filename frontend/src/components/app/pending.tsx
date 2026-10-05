"use client";

import { CloudAlert, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { errorMessage, revalidate, type ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

/**
 * What stands in for data that isn't here yet: a spinner while it loads, or,
 * when the call failed, why and a way to try again. A 404 shows `missing`.
 */
export function Pending({ error, missing, className }: { error?: unknown; missing?: string; className?: string }) {
  if (!error) {
    return (
      <div role="status" aria-label="Loading" className={cn("flex flex-1 items-center justify-center p-8", className)}>
        <Loader2 className="text-muted-foreground size-6 animate-spin" />
      </div>
    );
  }
  if (missing && (error as ApiError).error?.code === "not_found") {
    return (
      <Empty className={cn("flex-1", className)}>
        <EmptyHeader>
          <EmptyTitle>{missing}</EmptyTitle>
        </EmptyHeader>
      </Empty>
    );
  }
  return (
    <Empty className={cn("flex-1", className)}>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <CloudAlert />
        </EmptyMedia>
        <EmptyTitle>Couldn’t load this</EmptyTitle>
        <EmptyDescription>{errorMessage(error)}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button size="lg" onClick={revalidate}>
          Try again
        </Button>
      </EmptyContent>
    </Empty>
  );
}
