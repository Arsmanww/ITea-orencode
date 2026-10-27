import { useEffect, useState } from "react";

export interface Countdown {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  /** true, если момент уже наступил */
  reached: boolean;
}

function diff(target: number): Countdown {
  const ms = target - Date.now();
  if (ms <= 0) return { days: 0, hours: 0, minutes: 0, seconds: 0, reached: true };
  const total = Math.floor(ms / 1000);
  return {
    days: Math.floor(total / 86400),
    hours: Math.floor((total % 86400) / 3600),
    minutes: Math.floor((total % 3600) / 60),
    seconds: total % 60,
    reached: false,
  };
}

/** Обратный отсчёт до ISO-времени, обновляется раз в секунду. */
export function useCountdown(targetIso: string | null | undefined): Countdown | null {
  const target = targetIso ? new Date(targetIso).getTime() : NaN;
  const [state, setState] = useState<Countdown | null>(() => (Number.isNaN(target) ? null : diff(target)));

  useEffect(() => {
    if (Number.isNaN(target)) {
      setState(null);
      return;
    }
    setState(diff(target));
    const id = window.setInterval(() => setState(diff(target)), 1000);
    return () => window.clearInterval(id);
  }, [target]);

  return state;
}
