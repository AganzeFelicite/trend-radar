"use client";

import { useState } from "react";

const MESSAGES: Record<number, string> = {
  422: "That doesn't look like an email address.",
  429: "Too many tries from your network. Try again in an hour.",
};

export function WaitlistForm() {
  const [state, setState] = useState<"idle" | "sending" | "done" | string>("idle");

  async function submit(form: FormData) {
    setState("sending");
    const res = await fetch("/api/waitlist", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: form.get("email") }),
    }).catch(() => null);
    setState(res?.ok ? "done" : (res && MESSAGES[res.status]) || "Something went wrong. Try again.");
  }

  if (state === "done") {
    return <p className="font-medium text-emerald-700 dark:text-emerald-400">You&apos;re on the list. See you tomorrow morning.</p>;
  }
  return (
    <form action={submit} className="space-y-2">
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="email" className="sr-only">Email</label>
        <input id="email" name="email" type="email" required autoComplete="email" placeholder="you@example.com"
               className="min-w-0 flex-1 rounded-xl border border-neutral-300 bg-white px-4 py-3 text-base outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/30 dark:border-neutral-700 dark:bg-neutral-950" />
        <button disabled={state === "sending"}
                className="rounded-xl bg-emerald-600 px-5 py-3 font-semibold text-white hover:bg-emerald-700 disabled:opacity-60">
          {state === "sending" ? "Joining…" : "Join the waitlist"}
        </button>
      </div>
      {state !== "idle" && state !== "sending" && <p role="alert" className="text-sm text-rose-700 dark:text-rose-400">{state}</p>}
    </form>
  );
}
