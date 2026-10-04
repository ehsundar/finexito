import { cn } from "@/lib/utils";

/** Someone's picture, or the start of their name. */
export function Avatar({ person, className }: { person: { name: string; avatar_url?: string }; className?: string }) {
  const style = cn(
    "bg-secondary text-secondary-foreground inline-flex size-6 shrink-0 items-center justify-center overflow-hidden rounded-full text-[10px] font-medium uppercase",
    className,
  );
  if (person.avatar_url)
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={person.avatar_url} alt={person.name} title={person.name} className={style} />;
  return (
    <span className={style} title={person.name} aria-label={person.name}>
      {person.name.slice(0, 2)}
    </span>
  );
}
