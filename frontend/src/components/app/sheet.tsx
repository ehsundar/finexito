"use client";

import { Drawer as DrawerPrimitive } from "@base-ui/react/drawer";
import { Check } from "lucide-react";

import { List, ListRow } from "@/components/app/list";
import { Button } from "@/components/ui/button";
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
} from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";

type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  description?: React.ReactNode;
};

/**
 * A bottom sheet, as wide as the app. When a field in it brings up the phone's
 * keyboard, the sheet keeps the field and the rows below it above the keyboard.
 */
export function Sheet({ open, onOpenChange, title, description, children }: SheetProps & { children: React.ReactNode }) {
  return (
    <Drawer open={open} onOpenChange={(next) => onOpenChange(next)} showSwipeHandle>
      <DrawerPrimitive.VirtualKeyboardProvider>
        <DrawerContent className="mx-auto max-w-md pb-[env(safe-area-inset-bottom)]">
          <DrawerHeader className="text-left">
            <DrawerTitle>{title}</DrawerTitle>
            {description && <DrawerDescription className="text-left">{description}</DrawerDescription>}
          </DrawerHeader>
          <div className="flex min-h-0 flex-col gap-3 overflow-y-auto p-4 pb-[calc(1rem+var(--drawer-keyboard-inset,0px))] transition-[padding] duration-200">
            {children}
          </div>
        </DrawerContent>
      </DrawerPrimitive.VirtualKeyboardProvider>
    </Drawer>
  );
}

export type Action = {
  label: React.ReactNode;
  icon?: React.ReactNode;
  onSelect: () => void;
  destructive?: boolean;
  /** Shows a tick: the current choice. */
  checked?: boolean;
};

/** A menu or a choice, as a sheet of rows; picking one closes it. */
export function ActionSheet({ actions, ...props }: SheetProps & { actions: Action[] }) {
  return (
    <Sheet {...props}>
      <List>
        {actions.map((action, index) => (
          <ListRow
            key={index}
            icon={action.icon}
            destructive={action.destructive}
            detail={action.checked ? <Check className="text-primary size-4" /> : undefined}
            onClick={() => {
              props.onOpenChange(false);
              action.onSelect();
            }}
          >
            {action.label}
          </ListRow>
        ))}
      </List>
      <Button variant="ghost" size="lg" onClick={() => props.onOpenChange(false)}>
        Cancel
      </Button>
    </Sheet>
  );
}

/** Asks for one line of text; closes when `onSubmit` says it worked. */
export function PromptSheet({
  initial = "",
  placeholder,
  maxLength,
  submit = "Save",
  onSubmit,
  ...props
}: SheetProps & {
  initial?: string;
  placeholder?: string;
  maxLength: number;
  submit?: string;
  onSubmit: (value: string) => Promise<boolean>;
}) {
  return (
    <Sheet {...props}>
      <form
        className="flex flex-col gap-3"
        onSubmit={async (event) => {
          event.preventDefault();
          const value = String(new FormData(event.currentTarget).get("value") ?? "").trim();
          if (value && (await onSubmit(value))) props.onOpenChange(false);
        }}
      >
        <Input
          name="value"
          defaultValue={initial}
          placeholder={placeholder}
          maxLength={maxLength}
          required
          autoFocus
          enterKeyHint="done"
          className="h-11 text-base"
        />
        <Button type="submit" size="lg" className="h-11">
          {submit}
        </Button>
      </form>
    </Sheet>
  );
}
