"use client";

import { Filter } from "lucide-react";

import { FavouriteButton } from "@/app/todos/favourite-button";
import { LabelRows } from "@/app/todos/label-rows";
import { useTodos } from "@/app/todos/shell";
import { AppBar, Screen } from "@/components/app/frame";
import { List, ListRow } from "@/components/app/list";

export default function FiltersPage() {
  const { filters, labels } = useTodos();
  return (
    <>
      <AppBar title="Filters & labels" back="/todos/browse" />
      <Screen>
        <List title="Filters">
          {filters.map((f) => (
            <ListRow
              key={f.slug}
              href={`/todos/filter?slug=${f.slug}`}
              icon={<Filter />}
              trailing={<FavouriteButton slug={f.slug} on={f.is_favourite} />}
            >
              {f.name}
            </ListRow>
          ))}
        </List>
        <LabelRows labels={labels} />
      </Screen>
    </>
  );
}
