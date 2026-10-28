import { Box, type BoxProps } from "@mui/material";
import { useEffect, useRef, useState } from "react";

const REDUCED = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/**
 * Блок проявляется, когда доходит до экрана: всплытие снизу с лёгким приближением и расфокусом.
 *
 * Анимация повторяемая, но только в одну сторону: при прокрутке вниз блок появляется заново,
 * при движении вверх уже показанный блок остаётся на месте и не мигает. Сброс происходит,
 * когда блок уходит ниже экрана, – пользователь этого не видит.
 */
export function Reveal({ delay = 0, shift = 28, children, sx, ...rest }: { delay?: number; shift?: number } & BoxProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [shown, setShown] = useState(REDUCED);

  useEffect(() => {
    const node = ref.current;
    if (REDUCED || !node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
        } else if (entry.boundingClientRect.top >= window.innerHeight) {
          // блок целиком ушёл ниже экрана – вернём в исходное состояние для следующего прохода.
          // Сверяемся именно с краем окна: сбрасывать блок, который ещё виден, нельзя – моргнёт
          setShown(false);
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <Box
      ref={ref}
      sx={{
        opacity: shown ? 1 : 0,
        transform: shown ? "none" : `translate3d(0, ${shift}px, 0) scale(0.985)`,
        filter: shown ? "none" : "blur(6px)",
        transition: [
          `opacity .65s cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms`,
          `transform .75s cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms`,
          `filter .65s ease ${delay}ms`,
        ].join(","),
        "@media (prefers-reduced-motion: reduce)": { opacity: 1, transform: "none", filter: "none", transition: "none" },
        ...sx,
      }}
      {...rest}
    >
      {children}
    </Box>
  );
}
