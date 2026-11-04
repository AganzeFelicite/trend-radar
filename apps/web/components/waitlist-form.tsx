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
    return <p className="rounded-xl bg-white/15 px-4 py-3 font-semibold">✓ You&apos;re on the list. See you tomorrow morning.</p>;
  }
  return (
    <form action={submit} className="space-y-2">
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="email" className="sr-only">Email</label>
        <input id="email" name="email" type="email" required autoComplete="email" placeholder="you@example.com"
               className="min-w-0 flex-1 rounded-xl border-0 bg-white px-4 py-3 text-base text-neutral-900 outline-none placeholder:text-neutral-400 focus:ring-4 focus:ring-white/40" />
        <button disabled={state === "sending"}
                className="rounded-xl bg-neutral-950 px-5 py-3 font-semibold text-white transition hover:bg-neutral-800 disabled:opacity-60">
          {state === "sending" ? "Joining…" : "Join the waitlist"}
        </button>
      </div>
      {state !== "idle" && state !== "sending" && <p role="alert" className="text-sm font-semibold text-white">⚠ {state}</p>}
    </form>
  );
}
