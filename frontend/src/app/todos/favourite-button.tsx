"use client";

import { Star } from "lucide-react";
import { toast } from "sonner";

import { favouriteFilter } from "@/app/todos/actions";
import { Button } from "@/components/ui/button";

/** Adds a built-in filter to the favourites, or takes it off. */
export function FavouriteButton({ slug, on }: { slug: string; on: boolean }) {
  return (
    <Button
      variant="ghost"
      size="icon-lg"
      aria-label={on ? "Remove from favourites" : "Add to favourites"}
      aria-pressed={on}
      onClick={async () => {
        const { error } = await favouriteFilter(slug, !on);
        if (error) toast.error(error);
      }}
    >
      <Star className={on ? "fill-current text-primary" : "text-muted-foreground"} />
    </Button>
  );
}
