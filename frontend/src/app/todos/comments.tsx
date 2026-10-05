"use client";

import { Ellipsis, FileText, Paperclip, X } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { createComment, deleteComment, updateComment, uploadAttachment } from "@/app/todos/actions";
import { Avatar } from "@/app/todos/people";
import { useTodos, type Project } from "@/app/todos/shell";
import { Pending } from "@/components/app/pending";
import { ActionSheet } from "@/components/app/sheet";
import { Markdown } from "@/components/markdown/markdown";
import { Button } from "@/components/ui/button";
import { apiUrl, useQuery } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type Comment = components["schemas"]["Comment"];
type Attachment = components["schemas"]["Attachment"];

/** What storage accepts (apps/storage/formats.py). */
const ACCEPT = "image/jpeg,image/png,image/gif,image/webp,image/avif,application/pdf";

function size(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

const when = (iso: string) => new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

/** A task's comments, or a project's own, oldest first, with a box to add one. */
export function Comments({ task, project }: { task?: string; project: Project }) {
  const query = task ? { task } : { project: project.id };
  const { data: comments, error } = useQuery("/api/v1/todos/comments/", { params: { query } });
  const { data: me } = useQuery("/api/v1/auth/me/");
  const [editing, setEditing] = useState<Comment | null>(null);
  const [chosen, setChosen] = useState<Comment | null>(null);
  const { confirm } = useTodos();

  return (
    <section className="flex flex-col gap-3" aria-label="Comments">
      <h2 className="text-muted-foreground text-sm font-medium">Comments</h2>
      {!comments && <Pending error={error} />}
      {comments?.length === 0 && (
        <p className="text-muted-foreground text-sm">{task ? "No comments yet." : "No notes yet."}</p>
      )}
      <ul className="flex flex-col gap-4">
        {comments?.map((comment) => {
          const mine = comment.author.id === me?.id;
          return (
            <li key={comment.id} className="flex gap-3">
              <Avatar person={comment.author} className="size-8 text-xs" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium">{comment.author.name}</span>
                  <span className="text-muted-foreground text-xs">
                    {when(comment.created_at)}
                    {comment.edited_at && " · edited"}
                  </span>
                  {(mine || project.is_owner) && (
                    <Button variant="ghost" size="icon-sm" className="ml-auto" aria-label="Comment menu" onClick={() => setChosen(comment)}>
                      <Ellipsis />
                    </Button>
                  )}
                </div>
                {editing?.id === comment.id ? (
                  <Composer
                    initial={comment.text}
                    onCancel={() => setEditing(null)}
                    onSend={async (text) => {
                      const { error } = await updateComment(comment.id, text);
                      if (error) return toast.error(error), false;
                      setEditing(null);
                      return true;
                    }}
                  />
                ) : (
                  comment.text && (
                    <div className="text-sm">
                      <Markdown source={comment.text} />
                    </div>
                  )
                )}
                {comment.attachment && <AttachmentView file={comment.attachment} />}
              </div>
            </li>
          );
        })}
      </ul>
      <Composer
        attach
        onSend={async (text, file) => {
          let attachment_id: string | undefined;
          if (file) {
            const uploaded = await uploadAttachment(file);
            if (uploaded.error) return toast.error(uploaded.error), false;
            attachment_id = uploaded.data;
          }
          const { error } = await createComment({ ...query, text, attachment_id });
          if (error) return toast.error(error), false;
          return true;
        }}
      />
      <ActionSheet
        open={!!chosen}
        onOpenChange={(open) => !open && setChosen(null)}
        title="Comment"
        actions={[
          ...(chosen?.author.id === me?.id ? [{ label: "Edit", onSelect: () => setEditing(chosen) }] : []),
          {
            label: "Delete",
            destructive: true,
            onSelect: async () => {
              if (!chosen || !(await confirm("Delete this comment?"))) return;
              const { error } = await deleteComment(chosen.id);
              if (error) toast.error(error);
            },
          },
        ]}
      />
    </section>
  );
}

function AttachmentView({ file }: { file: Attachment }) {
  const href = apiUrl(file.url);
  if (file.content_type.startsWith("image/"))
    return (
      <a href={href} target="_blank" rel="noreferrer" className="mt-2 block">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={href} alt={file.name} className="max-h-60 rounded-lg border object-contain" />
      </a>
    );
  return (
    <a href={href} target="_blank" rel="noreferrer" className="bg-card active:bg-accent mt-2 flex items-center gap-3 rounded-lg border p-3 text-sm">
      <FileText className="text-muted-foreground size-5 shrink-0" />
      <span className="min-w-0 flex-1 truncate">{file.name}</span>
      <span className="text-muted-foreground text-xs">
        {file.content_type.split("/")[1].toUpperCase()} · {size(file.size)}
      </span>
    </a>
  );
}

/** Writes a comment, in Markdown, optionally with one file. */
function Composer({
  initial = "",
  attach = false,
  onSend,
  onCancel,
}: {
  initial?: string;
  attach?: boolean;
  onSend: (text: string, file?: File) => Promise<boolean>;
  onCancel?: () => void;
}) {
  const [text, setText] = useState(initial);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!text.trim() && !file) return;
        setBusy(true);
        const sent = await onSend(text.trim(), file ?? undefined);
        setBusy(false);
        if (sent) {
          setText("");
          setFile(null);
        }
      }}
    >
      <textarea
        value={text}
        onChange={(event) => setText(event.target.value)}
        maxLength={15000}
        rows={2}
        placeholder="Comment (Markdown)"
        aria-label="Comment"
        className="border-input bg-card field-sizing-content min-h-12 rounded-xl border p-3 text-base"
      />
      {file && (
        <div className="text-muted-foreground flex items-center gap-2 text-sm">
          <Paperclip className="size-4" />
          <span className="min-w-0 flex-1 truncate">
            {file.name} · {size(file.size)}
          </span>
          <Button type="button" variant="ghost" size="icon-sm" aria-label="Remove file" onClick={() => setFile(null)}>
            <X />
          </Button>
        </div>
      )}
      <div className="flex gap-2">
        {attach && (
          <>
            <input
              ref={picker}
              type="file"
              accept={ACCEPT}
              hidden
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                event.target.value = "";
              }}
            />
            <Button type="button" variant="outline" size="lg" aria-label="Attach a file" onClick={() => picker.current?.click()}>
              <Paperclip />
            </Button>
          </>
        )}
        {onCancel && (
          <Button type="button" variant="outline" size="lg" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" size="lg" className="flex-1" disabled={busy || (!text.trim() && !file)}>
          {busy ? "Sending…" : onCancel ? "Save" : "Comment"}
        </Button>
      </div>
    </form>
  );
}
