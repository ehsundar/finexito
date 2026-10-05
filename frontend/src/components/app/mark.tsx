/**
 * The brand's mark, a door left open: drawn here once, for the header and the
 * app's icons (app/brand-icon.tsx). Its colours default to the theme's
 * (colours.css), so it follows the palette and dark mode.
 */
export function Mark({
  frame = "var(--mark-frame)",
  door = "var(--mark-door)",
  knob = "var(--mark-knob)",
  ...props
}: { frame?: string; door?: string; knob?: string } & React.ComponentProps<"svg">) {
  return (
    <svg viewBox="30 18 60 88" aria-hidden {...props}>
      <path d="M40 94 V26 H80 V94" fill="none" stroke={frame} strokeWidth="7" strokeLinejoin="round" />
      <polygon points="40,26 62,34 62,100 40,94" fill={door} />
      <circle cx="57" cy="66" r="2.6" fill={knob} />
    </svg>
  );
}
