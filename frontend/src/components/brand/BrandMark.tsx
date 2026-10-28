import { Box } from "@mui/material";

/**
 * Знак «ФСП Оренбург»: фигурные скобки { } (код) вокруг растущих столбиков результата –
 * «спортивное программирование» как есть: код снаружи, соревновательный рейтинг внутри.
 *
 * ПЛЕЙСХОЛДЕР: для финальной айдентики замените содержимое <svg> на утверждённый логотип ФСП
 * (SVG), сохранив размеры viewBox и подписи aria.
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
      {/* растущие столбики: результат, рейтинг, прогресс */}
      <rect x="17.5" y="24" width="4" height="9" rx="1.3" fill="url(#fsp-mark-glow)" />
      <rect x="22.5" y="19" width="4" height="14" rx="1.3" fill="url(#fsp-mark-glow)" />
      <rect x="27.5" y="14" width="4" height="19" rx="1.3" fill="url(#fsp-mark-glow)" />
    </Box>
  );
}
