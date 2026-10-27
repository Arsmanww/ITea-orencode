import { Box } from "@mui/material";

/**
 * Знак «ФСП Оренбург»: фигурные скобки { } (код) вокруг условного контура области.
 *
 * ПЛЕЙСХОЛДЕР: контур — стилизованный силуэт, а не картографически точная граница.
 * Для финальной айдентики замените содержимое <svg> на утверждённый логотип ФСП и герб/контур
 * области (SVG), сохранив размеры viewBox и подписи aria.
 */
export function BrandMark({ size = 40, onDark = true }: { size?: number; onDark?: boolean }) {
  const frame = onDark ? "rgba(255,255,255,0.08)" : "#0A0F1F";
  return (
    <Box
      component="svg"
      viewBox="0 0 48 48"
      role="img"
      aria-label="ФСП Оренбург"
      sx={{ width: size, height: size, flexShrink: 0, display: "block" }}
    >
      <defs>
        <linearGradient id="fsp-mark-glow" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#22D3EE" />
          <stop offset="1" stopColor="#2B59FF" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="12" fill={frame} stroke={onDark ? "rgba(255,255,255,0.16)" : "none"} />
      {/* скобки */}
      <path d="M16 10c-4 0-5.5 2-5.5 5.5V19c0 2.8-1.2 4.4-4 5 2.8.6 4 2.2 4 5v3.5c0 3.5 1.5 5.5 5.5 5.5" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M32 10c4 0 5.5 2 5.5 5.5V19c0 2.8 1.2 4.4 4 5-2.8.6-4 2.2-4 5v3.5c0 3.5-1.5 5.5-5.5 5.5" fill="none" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
      {/* условный контур области */}
      <path d="M18.5 25.2l2.2-3.6 4.4-1.4 4.6 1.2 1.8 3.2-1.4 3.6-4.2 2.4-4.6-.6z" fill="url(#fsp-mark-glow)" />
      <circle cx="24.5" cy="25.4" r="1.4" fill="#0A0F1F" />
    </Box>
  );
}
