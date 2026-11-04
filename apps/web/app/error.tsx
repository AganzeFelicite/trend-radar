"use client";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="space-y-3 pt-10 text-center">
      <h1 className="text-xl font-semibold">Scores are temporarily unavailable</h1>
      <p className="text-neutral-500">We&apos;re probably mid-update. Try again in a minute.</p>
      <button onClick={reset} className="rounded-xl bg-emerald-600 px-4 py-2 font-semibold text-white">Try again</button>
    </div>
  );
}
