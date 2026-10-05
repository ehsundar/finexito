"use client";

import { LogOut, SunMoon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Pending } from "@/components/app/pending";
import { Avatar } from "@/components/app/avatar";
import { List, ListRow } from "@/components/app/list";
import { ActionSheet, PromptSheet } from "@/components/app/sheet";
import { THEMES, useProfileTheme } from "@/components/app/theme";
import { api, errorMessage, revalidate, signOut, useQuery } from "@/lib/api/client";

/**
 * Who's signed in, and the way out: the top of every mini app's "Me" tab. The
 * app's own settings go in `children`, between the two.
 */
export function Account({ children }: { children?: React.ReactNode }) {
  const router = useRouter();
  const { data: me, error } = useQuery("/api/v1/auth/me/");
  const { data: profile } = useQuery("/api/v1/profiles/me/");
  const [renaming, setRenaming] = useState(false);
  const [theming, setTheming] = useState(false);
  const { theme, choose } = useProfileTheme();
  if (!me) return <Pending error={error} />;
  const name = profile?.display_name || me.email.split("@")[0];

  return (
    <>
      <section className="flex flex-col items-center gap-2 pt-4 text-center">
        <Avatar person={{ name, avatar_url: profile?.avatar_url }} className="size-20 text-2xl" />
        <div>
          <h2 className="text-lg font-medium">{name}</h2>
          <p className="text-muted-foreground text-sm">Signed in as {me.email}</p>
        </div>
      </section>
      <List title="Profile">
        <ListRow onClick={() => setRenaming(true)} detail={profile?.display_name || "Not set"}>
          Name
        </ListRow>
        <ListRow detail={profile?.timezone}>Time zone</ListRow>
        <ListRow icon={<SunMoon />} onClick={() => setTheming(true)} detail={THEMES.find((t) => t.value === theme)?.label}>
          Appearance
        </ListRow>
      </List>
      {children}
      <List>
        <ListRow
          icon={<LogOut />}
          destructive
          onClick={async () => {
            await signOut();
            router.replace("/");
          }}
        >
          Sign out
        </ListRow>
      </List>
      <ActionSheet
        open={theming}
        onOpenChange={setTheming}
        title="Appearance"
        description="System follows this device's setting."
        actions={THEMES.map((t) => ({ label: t.label, checked: t.value === theme, onSelect: () => choose(t.value) }))}
      />
      <PromptSheet
        open={renaming}
        onOpenChange={setRenaming}
        title="Your name"
        description="As others see you in shared projects."
        initial={profile?.display_name}
        maxLength={150}
        onSubmit={async (display_name) => {
          const { error } = await api.PATCH("/api/v1/profiles/me/", { body: { display_name } });
          if (error) toast.error(errorMessage(error));
          revalidate();
          return !error;
        }}
      />
    </>
  );
}
