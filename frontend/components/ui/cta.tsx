import { ArrowRight } from "lucide-react";

// One button system shared by the landing page and auth screens.
// Flat brand violet, shared radius and timing; translate animations only
// when motion is allowed.
export const BTN_PRIMARY =
  "rounded-xl px-6 font-medium bg-violet-500 text-white " +
  "transition-all duration-200 hover:bg-violet-400 " +
  "motion-safe:hover:-translate-y-px active:translate-y-0 active:bg-violet-600 " +
  "focus-visible:ring-2 focus-visible:ring-violet-400/60 " +
  "focus-visible:ring-offset-2 focus-visible:ring-offset-black";

export const BTN_SECONDARY =
  "rounded-xl px-6 font-medium bg-transparent dark:bg-transparent " +
  "border-white/15 dark:border-white/15 text-zinc-200 " +
  "transition-all duration-200 " +
  "hover:border-white/30 dark:hover:border-white/30 " +
  "hover:bg-white/5 dark:hover:bg-white/5 hover:text-zinc-100";

/** trailing arrow that nudges right on button hover */
export function CtaArrow() {
  return (
    <ArrowRight className="size-4 transition-transform duration-200 motion-safe:group-hover/button:translate-x-[3px]" />
  );
}
