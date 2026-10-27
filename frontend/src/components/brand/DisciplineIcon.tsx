import { Box } from "@mui/material";

import { BRAND } from "../../theme";

/**
 * Иконки шести дисциплин в стилистике ФСП: тонкая линия основным цветом и один-два
 * сплошных акцента. Рисуются кодом, внешних наборов и картинок не требуют.
 */
const LINE = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

function Algorithmic() {
  return (
    <>
      <rect x="3" y="4" width="26" height="16" rx="3" {...LINE} />
      <path d="M11 9l-3 3 3 3M21 9l3 3-3 3M17 8l-2 8" {...LINE} />
      <circle cx="8" cy="26" r="2.4" fill={BRAND.blue} />
      <circle cx="16" cy="26" r="2.4" fill={BRAND.blue} />
      <circle cx="24" cy="26" r="2.4" fill={BRAND.blue} />
    </>
  );
}

function Product() {
  return (
    <>
      <rect x="4" y="4.5" width="8.5" height="8.5" rx="2" fill={BRAND.blue} />
      <path d="M22 4l5 5-5 5-5-5z" {...LINE} />
      <path d="M8.3 16.5v4.8a2.5 2.5 0 002.5 2.5H15" {...LINE} />
      <rect x="16.5" y="19.5" width="11.5" height="8" rx="4" {...LINE} />
    </>
  );
}

function Infosec() {
  return (
    <>
      <path d="M16 3.5l10.5 4v8.2c0 6.4-4.4 11-10.5 12.8C9.9 26.7 5.5 22.1 5.5 15.7V7.5z" {...LINE} />
      <path d="M11 15.5l3.4 3.4 6.6-7" {...LINE} />
      <circle cx="24.5" cy="21.5" r="3.5" fill={BRAND.blue} />
    </>
  );
}

function Ai() {
  return (
    <>
      <path d="M9.2 9.1L16.3 11.3M9.3 15.2L16.3 12.9M9.3 16.8L16.3 19.1M9.2 22.9L16.3 20.7M20.7 13.1L24.8 15.1M20.7 18.9L24.8 16.9" {...LINE} />
      <circle cx="7" cy="8" r="2.4" {...LINE} />
      <circle cx="7" cy="16" r="2.4" fill={BRAND.blue} />
      <circle cx="7" cy="24" r="2.4" {...LINE} />
      <circle cx="18.5" cy="12" r="2.4" {...LINE} />
      <circle cx="18.5" cy="20" r="2.4" {...LINE} />
      <circle cx="26.5" cy="16" r="2.4" fill={BRAND.blue} />
    </>
  );
}

function Robotics() {
  return (
    <>
      <path d="M16 3.5v4" {...LINE} />
      <circle cx="16" cy="3" r="1.8" fill={BRAND.blue} />
      <rect x="5" y="8" width="22" height="14" rx="6" {...LINE} />
      <circle cx="11.5" cy="15" r="2.2" fill={BRAND.blue} />
      <circle cx="20.5" cy="15" r="2.2" fill={BRAND.blue} />
      <path d="M11 26h10M3 13v4M29 13v4" {...LINE} />
    </>
  );
}

function Uas() {
  return (
    <>
      <path d="M11 11L6.5 6.5M21 11l4.5-4.5M11 21l-4.5 4.5M21 21l4.5 4.5" {...LINE} />
      <circle cx="5.5" cy="5.5" r="3.2" {...LINE} />
      <circle cx="26.5" cy="5.5" r="3.2" {...LINE} />
      <circle cx="5.5" cy="26.5" r="3.2" {...LINE} />
      <circle cx="26.5" cy="26.5" r="3.2" {...LINE} />
      <rect x="11" y="11" width="10" height="10" rx="3" fill={BRAND.blue} />
    </>
  );
}

const SHAPES: Record<string, () => JSX.Element> = {
  algorithmic: Algorithmic,
  product: Product,
  infosec: Infosec,
  ai: Ai,
  robotics: Robotics,
  uas: Uas,
};

export function DisciplineIcon({ code, size = 32, color = BRAND.text }: { code: string; size?: number; color?: string }) {
  const Shape = SHAPES[code];
  if (!Shape) return null;
  return (
    <Box component="svg" viewBox="0 0 32 32" aria-hidden sx={{ width: size, height: size, color, display: "block" }}>
      <Shape />
    </Box>
  );
}
