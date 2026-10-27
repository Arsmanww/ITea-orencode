import { Box, Stack, Typography } from "@mui/material";
import { useMemo, useState } from "react";

import type { RegionPoint } from "../../api/types";
import { BRAND, FONT_MONO } from "../../theme";
import { plural } from "../../utils/format";

/**
 * Схематичная карта Оренбургской области с городами подготовки.
 * Размер точки — число занимающихся, данные приходят с платформы (/public/navigator → regions).
 *
 * ПЛЕЙСХОЛДЕР: контур области нарисован по ~28 опорным точкам и передаёт форму, но не является
 * картографически точной границей. Для финальной версии подставьте GeoJSON/SVG из официального
 * источника в OUTLINE (формат [долгота, широта]) — проекция и точки городов подстроятся сами.
 */
const OUTLINE: [number, number][] = [
  [50.9, 52.7], [51.4, 53.4], [52.0, 53.8], [52.6, 54.5], [53.4, 54.95], [54.3, 54.6], [55.0, 54.0], [55.9, 54.1], [56.8, 53.6],
  [57.4, 52.9], [58.4, 52.4], [59.2, 52.5], [60.2, 52.0], [60.9, 52.2], [61.7, 51.6], [61.3, 51.0], [60.1, 50.8], [59.0, 50.7],
  [58.0, 51.0], [57.0, 50.9], [56.0, 51.0], [55.2, 50.8], [54.0, 51.2], [52.9, 51.0], [51.8, 51.4], [51.2, 51.9], [50.8, 52.3],
];

interface City {
  lat: number;
  lon: number;
  short: string;
  /** смещение подписи относительно точки, px (в координатах viewBox) */
  dx: number;
  dy: number;
  anchor: "start" | "middle" | "end";
}

const CITIES: Record<string, City> = {
  "г. Оренбург": { lat: 51.77, lon: 55.1, short: "Оренбург", dx: 0, dy: 34, anchor: "middle" },
  "г. Орск": { lat: 51.2, lon: 58.57, short: "Орск", dx: 16, dy: 5, anchor: "start" },
  "г. Новотроицк": { lat: 51.2, lon: 58.33, short: "Новотроицк", dx: 4, dy: 30, anchor: "start" },
  "г. Гай": { lat: 51.46, lon: 58.45, short: "Гай", dx: 12, dy: -10, anchor: "start" },
  "г. Медногорск": { lat: 51.4, lon: 57.6, short: "Медногорск", dx: -2, dy: 30, anchor: "end" },
  "г. Кувандык": { lat: 51.48, lon: 57.37, short: "Кувандык", dx: -10, dy: -10, anchor: "end" },
  "Саракташский район": { lat: 51.83, lon: 56.12, short: "Саракташ", dx: 0, dy: -14, anchor: "middle" },
  "Оренбургский район": { lat: 52.0, lon: 54.6, short: "Оренбургский р-н", dx: -12, dy: 4, anchor: "end" },
  "г. Сорочинск": { lat: 52.43, lon: 53.15, short: "Сорочинск", dx: -12, dy: 4, anchor: "end" },
  "г. Бузулук": { lat: 52.78, lon: 52.26, short: "Бузулук", dx: -12, dy: 4, anchor: "end" },
  "г. Бугуруслан": { lat: 53.66, lon: 52.44, short: "Бугуруслан", dx: -12, dy: 4, anchor: "end" },
  "г. Абдулино": { lat: 53.68, lon: 53.65, short: "Абдулино", dx: 12, dy: 4, anchor: "start" },
};

// проекция: градус широты = U px, долгота сжата косинусом средней широты
const U = 82;
const KX = 0.616;
const LON0 = 50.4;
const LAT1 = 55.2;
const PAD = 28;
const W = Math.round(PAD * 2 + (61.9 - LON0) * KX * U);
const H = Math.round(PAD * 2 + (LAT1 - 50.6) * U);
const px = (lon: number) => PAD + (lon - LON0) * KX * U;
const py = (lat: number) => PAD + (LAT1 - lat) * U;
const OUTLINE_PATH = OUTLINE.map(([lon, lat], i) => `${i ? "L" : "M"}${px(lon).toFixed(1)} ${py(lat).toFixed(1)}`).join(" ") + " Z";

const radius = (athletes: number) => Math.min(18, 5 + Math.sqrt(athletes) * 1.7);

export function RegionMap({ regions }: { regions: RegionPoint[] }) {
  const [active, setActive] = useState<string | null>(null);
  const points = useMemo(
    () => regions.filter((r) => CITIES[r.name]).map((r) => ({ ...r, ...CITIES[r.name] })).sort((a, b) => b.athletes - a.athletes),
    [regions],
  );
  const top = points[0]?.name;
  const current = points.find((p) => p.name === active);
  const total = regions.reduce((s, r) => s + r.athletes, 0);

  const list = (
    <Stack spacing={0.25} component="ul" sx={{ listStyle: "none", m: 0, p: 0 }} aria-label="Занимающиеся по городам">
      <Typography component="li" sx={{ fontFamily: FONT_MONO, fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "rgba(255,255,255,0.55)", mb: 1 }}>
        всего {total} {plural(total, ["спортсмен", "спортсмена", "спортсменов"])}
      </Typography>
      {points
        .filter((p) => p.athletes > 0)
        .slice(0, 5)
        .map((p) => (
          <Box
            component="li"
            key={p.name}
            onMouseEnter={() => setActive(p.name)}
            onMouseLeave={() => setActive(null)}
            sx={{ px: 1, py: 0.75, borderRadius: 1.5, bgcolor: active === p.name ? "rgba(255,255,255,0.1)" : "transparent", transition: "background-color .15s" }}
          >
            <Stack direction="row" justifyContent="space-between" alignItems="baseline">
              <Typography sx={{ fontSize: 13.5, color: "#fff" }}>{p.short}</Typography>
              <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12.5, color: BRAND.cyan }}>{p.athletes}</Typography>
            </Stack>
            <Box sx={{ mt: 0.5, height: "3px", borderRadius: 2, bgcolor: "rgba(255,255,255,0.1)", overflow: "hidden" }}>
              <Box sx={{ height: "100%", width: `${(p.athletes / (points[0]?.athletes || 1)) * 100}%`, borderRadius: 2, background: `linear-gradient(90deg, ${BRAND.cyan}, ${BRAND.blue})` }} />
            </Box>
          </Box>
        ))}
    </Stack>
  );

  return (
    <Box>
      <Box
        sx={{
          position: "relative",
          borderRadius: 4,
          border: "1px solid rgba(255,255,255,0.1)",
          background: "radial-gradient(80% 80% at 70% 20%, rgba(43,89,255,0.18), transparent 70%), rgba(255,255,255,0.03)",
          overflow: "hidden",
        }}
      >
        <svg viewBox={`0 0 ${W} ${H}`} role="group" aria-label="Карта Оренбургской области: города подготовки спортсменов" style={{ display: "block", width: "100%", height: "auto" }}>
          <defs>
            <pattern id="fsp-dots" width="16" height="16" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill="rgba(255,255,255,0.09)" />
            </pattern>
            <linearGradient id="fsp-dot" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor={BRAND.cyan} />
              <stop offset="1" stopColor={BRAND.blue} />
            </linearGradient>
          </defs>
          <rect width={W} height={H} fill="url(#fsp-dots)" />
          <path d={OUTLINE_PATH} fill="rgba(34,211,238,0.06)" stroke="rgba(34,211,238,0.6)" strokeWidth="1.5" strokeLinejoin="round" />

          {points.map((p) => {
            const x = px(p.lon);
            const y = py(p.lat);
            const r = radius(p.athletes);
            const on = active === p.name;
            return (
              <g
                key={p.name}
                role="button"
                tabIndex={0}
                aria-label={`${p.short}: ${p.athletes} занимающихся, организаций ${p.organizations}`}
                onMouseEnter={() => setActive(p.name)}
                onMouseLeave={() => setActive(null)}
                onFocus={() => setActive(p.name)}
                onBlur={() => setActive(null)}
                style={{ cursor: "pointer", outline: "none" }}
              >
                {p.name === top && (
                  <circle cx={x} cy={y} r={r} fill="none" stroke={BRAND.cyan} strokeOpacity="0.7" strokeWidth="1.5">
                    <animate attributeName="r" values={`${r};${r + 14}`} dur="2.4s" repeatCount="indefinite" />
                    <animate attributeName="stroke-opacity" values="0.7;0" dur="2.4s" repeatCount="indefinite" />
                  </circle>
                )}
                <circle
                  cx={x}
                  cy={y}
                  r={r + (on ? 3 : 0)}
                  fill="url(#fsp-dot)"
                  fillOpacity={p.athletes ? 0.95 : 0.35}
                  stroke="#fff"
                  strokeOpacity={on ? 1 : 0.55}
                  strokeWidth={on ? 2 : 1}
                  style={{ transition: "all .15s ease", filter: on ? `drop-shadow(0 0 8px ${BRAND.cyan})` : "none" }}
                />
                <circle cx={x} cy={y} r={Math.min(3, r / 3)} fill={BRAND.ink} />
                <text x={x + p.dx} y={y + p.dy} textAnchor={p.anchor} fill={on ? "#fff" : "rgba(255,255,255,0.82)"} fontSize="12.5" fontFamily={FONT_MONO} fontWeight={on ? 700 : 500} style={{ pointerEvents: "none" }}>
                  {p.short}
                </text>
              </g>
            );
          })}
        </svg>

        {current && (
          <Box
            sx={{
              position: "absolute",
              left: `${(px(current.lon) / W) * 100}%`,
              top: `${(py(current.lat) / H) * 100}%`,
              transform: "translate(-50%, calc(-100% - 28px))",
              pointerEvents: "none",
              px: 1.5,
              py: 1,
              borderRadius: 2,
              bgcolor: "rgba(10,15,31,0.94)",
              border: "1px solid rgba(34,211,238,0.5)",
              color: "#fff",
              whiteSpace: "nowrap",
              zIndex: 2,
            }}
          >
            <Typography sx={{ fontWeight: 700, fontSize: 13.5 }}>{current.name}</Typography>
            <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12, color: BRAND.cyan }}>
              {current.athletes} {plural(current.athletes, ["спортсмен", "спортсмена", "спортсменов"])} · орг.: {current.organizations}
            </Typography>
          </Box>
        )}

        {/* список городов лежит в свободном верхнем правом углу карты (на узких экранах — ниже карты) */}
        <Box sx={{ display: { xs: "none", md: "block" }, position: "absolute", top: 16, right: 16, width: 208, p: 1.5, borderRadius: 3, bgcolor: "rgba(10,15,31,0.72)", border: "1px solid rgba(255,255,255,0.1)", backdropFilter: "blur(6px)" }}>{list}</Box>

        <Typography sx={{ position: "absolute", left: 16, bottom: 10, fontFamily: FONT_MONO, fontSize: 10.5, letterSpacing: "0.08em", color: "rgba(255,255,255,0.38)", textTransform: "uppercase" }}>
          схематичная карта
        </Typography>
      </Box>
      <Box sx={{ display: { xs: "block", md: "none" }, mt: 2 }}>{list}</Box>
    </Box>
  );
}
