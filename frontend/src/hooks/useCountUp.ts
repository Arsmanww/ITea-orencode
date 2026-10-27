import { useEffect, useState } from "react";

const reduceMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Плавно «накручивает» число до target. При prefers-reduced-motion показывает итог сразу. */
export function useCountUp(target: number, durationMs = 1100): number {
  const [value, setValue] = useState(() => (reduceMotion() ? target : 0));

  useEffect(() => {
    if (reduceMotion() || target === 0) {
      setValue(target);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      setValue(Math.round(target * (1 - Math.pow(1 - t, 3)))); // ease-out cubic
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, durationMs]);

  return value;
}
