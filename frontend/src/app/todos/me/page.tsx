"use client";

import { Bell, CalendarDays } from "lucide-react";
import { useState } from "react";

import { GoogleCalendarSheet, useGoogleCalendar } from "@/app/todos/google-calendar";
import { NotificationSettingsSheet } from "@/app/todos/reminders";
import { Account } from "@/components/app/account";
import { AppBar, Screen } from "@/components/app/frame";
import { List, ListRow } from "@/components/app/list";

/** Who's signed in, and the todos settings. */
export default function MePage() {
  const [sheet, setSheet] = useState<"notifications" | "calendar" | null>(null);
  // Absent where the deployment leaves Google Calendar out.
  const { data: google } = useGoogleCalendar();
  const close = (open: boolean) => !open && setSheet(null);

  return (
    <>
      <AppBar title="Me" />
      <Screen>
        <Account>
          <List title="Todos">
            <ListRow icon={<Bell />} onClick={() => setSheet("notifications")}>
              Notifications
            </ListRow>
            {google && (
              <ListRow
                icon={<CalendarDays />}
                onClick={() => setSheet("calendar")}
                detail={google.status === "connected" ? "On" : google.status === "disconnected" ? "Disconnected" : "Off"}
              >
                Google Calendar
              </ListRow>
            )}
          </List>
        </Account>
      </Screen>
      <NotificationSettingsSheet open={sheet === "notifications"} onOpenChange={close} />
      {google && <GoogleCalendarSheet open={sheet === "calendar"} onOpenChange={close} />}
    </>
  );
}
