import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ImageResponse } from "next/og";

import { Mark } from "@/components/app/mark";

/**
 * The app's icon at `size` pixels, as a PNG (app/brand/[icon]/route.tsx): the mark on a tile, in the
 * `--icon-*` colours of colours.css. Drawn when the app is built, so a new
 * palette brings new icons. iOS rounds its own, so `square` leaves the corners.
 */
export function brandIcon(size: number, { square = false } = {}) {
  const css = readFileSync(join(process.cwd(), "src/app/colours.css"), "utf8");
  // The palette and the light theme: everything before `.dark`.
  const vars = new Map(
    [...css.slice(0, css.indexOf(".dark")).matchAll(/--([\w-]+):\s*([^;]+);/g)].map((m) => [m[1], m[2].trim()]),
  );
  const colour = (name: string): string => {
    const value = vars.get(name) ?? "";
    const ref = value.match(/^var\(--([\w-]+)\)$/);
    return ref ? colour(ref[1]) : value;
  };

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: colour("icon-tile"),
          borderRadius: square ? 0 : "23%",
        }}
      >
        <Mark
          frame={colour("icon-frame")}
          door={colour("icon-door")}
          knob={colour("icon-knob")}
          width={size * 0.5}
          height={size * 0.73}
        />
      </div>
    ),
    { width: size, height: size },
  );
}
