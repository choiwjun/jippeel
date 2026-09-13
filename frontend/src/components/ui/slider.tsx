import type { InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** 네이티브 range 슬라이더 — max_tokens와 집필 동시성 조절용 */
export function Slider({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      type="range"
      className={cn(
        "h-1.5 w-full cursor-pointer accent-[hsl(var(--primary))]",
        className,
      )}
      {...props}
    />
  );
}
