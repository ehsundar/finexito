import { Filter } from "lucide-react";

import { FavouriteButton } from "@/app/todos/favourite-button";
import { LabelRows } from "@/app/todos/label-rows";
import { AppBar, Screen } from "@/components/app/frame";
import { List, ListRow } from "@/components/app/list";
import { sessionApi } from "@/lib/auth/current-user";

export const metadata = { title: "Filters & labels" };

export default async function FiltersPage() {
  const api = await sessionApi();
  const [{ data: filters = [] }, { data: labels = [] }] = await Promise.all([
    api.GET("/api/v1/todos/filters/"),
    api.GET("/api/v1/todos/labels/"),
  ]);
  return (
    <>
      <AppBar title="Filters & labels" back="/todos/browse" />
      <Screen>
        <List title="Filters">
          {filters.map((f) => (
            <ListRow
              key={f.slug}
              href={`/todos/filters/${f.slug}`}
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
