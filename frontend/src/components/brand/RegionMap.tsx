import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { Box, Collapse, Stack, Typography } from "@mui/material";
import { useMemo, useState } from "react";

import type { RegionPoint } from "../../api/types";
import { BRAND, FONT_MONO } from "../../theme";
import { plural } from "../../utils/format";
import { MAP_HEIGHT, MAP_WIDTH, REGION_SHAPES } from "./regionShapes";

/**
 * Карта Оренбургской области по районам и городским округам: наведение подсвечивает муниципалитет
 * и показывает, сколько человек там занимается. Границы – реальные (OpenStreetMap), см. regionShapes.ts.
 *
 * Порядок отрисовки задан в данных (от крупных к мелким), поэтому городские округа видны
 * поверх районов, внутри которых они находятся.
 *
 * Названия муниципалитетов в платформе и в OSM расходятся: у нас городские округа заведены как
 * «г. Гай», в данных OSM тот же контур называется «Гайский район».
 */
const SHAPE_BY_MUNICIPALITY: Record<string, string> = {
  "г. Оренбург": "Оренбург",
  "г. Орск": "Орск",
  "г. Новотроицк": "Новотроицк",
  "г. Бузулук": "Бузулук",
  "г. Бугуруслан": "Бугуруслан",
  "г. Медногорск": "Медногорск",
  "г. Гай": "Гайский район",
  "г. Кувандык": "Кувандыкский район",
  "г. Сорочинск": "Сорочинский район",
  "г. Абдулино": "Абдулинский район",
  "Оренбургский район": "Оренбургский район",
  "Саракташский район": "Саракташский район",
};

// плоская палитра в стилистике ФСП: заливка, граница и один акцент на выбранном муниципалитете
const LAND = "#7F8699";
const LAND_EDGE = "#2A3346";
const ACCENT = BRAND.blue;

/** Муниципалитеты с занимающимися подсвечены тем заметнее, чем больше там спортсменов. */
function landFill(athletes: number, max: number): string {
  if (athletes <= 0) return LAND;
  const weight = 0.25 + 0.55 * Math.sqrt(athletes / max);
  return `color-mix(in srgb, ${ACCENT} ${Math.round(weight * 100)}%, ${LAND})`;
}

export function RegionMap({ regions }: { regions: RegionPoint[] }) {
  const [active, setActive] = useState<string | null>(null);
  // свёрнут по умолчанию: список городов лежит ровно над восточной частью области (Орск,
  // Новотроицк, Медногорск) – развёрнутым он закрывает ту часть карты, про которую рассказывает
  const [listOpen, setListOpen] = useState(false);

  const byShape = useMemo(() => {
    const map = new Map<string, RegionPoint>();
    regions.forEach((r) => {
      const shape = SHAPE_BY_MUNICIPALITY[r.name];
      if (shape) map.set(shape, r);
    });
    return map;
  }, [regions]);

  const ranked = useMemo(() => [...regions].sort((a, b) => b.athletes - a.athletes), [regions]);
  const max = ranked[0]?.athletes || 1;
  const total = regions.reduce((sum, r) => sum + r.athletes, 0);
  const current = REGION_SHAPES.find((s) => s.name === active);
  const currentData = active ? byShape.get(active) : undefined;

  const topRows = ranked
    .filter((r) => r.athletes > 0)
    .slice(0, 5)
    .map((r) => {
      const shape = SHAPE_BY_MUNICIPALITY[r.name];
      const on = active === shape;
      return (
        <Box
          component="li"
          key={r.name}
          onMouseEnter={() => setActive(shape ?? null)}
          onMouseLeave={() => setActive(null)}
          sx={{ px: 1, py: 0.75, borderRadius: 1, bgcolor: on ? "rgba(255,255,255,0.08)" : "transparent", transition: "background-color .15s" }}
        >
          <Stack direction="row" justifyContent="space-between" alignItems="baseline">
            <Typography sx={{ fontSize: 13.5, color: "#fff" }}>{r.name.replace("г. ", "")}</Typography>
            <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12.5, color: on ? ACCENT : "rgba(255,255,255,0.7)" }}>{r.athletes}</Typography>
          </Stack>
          <Box sx={{ mt: 0.5, height: "2px", bgcolor: "rgba(255,255,255,0.12)" }}>
            <Box sx={{ height: "100%", width: `${(r.athletes / max) * 100}%`, bgcolor: on ? ACCENT : "rgba(255,255,255,0.45)", transition: "background-color .15s" }} />
          </Box>
        </Box>
      );
    });

  const countLabel = `всего ${total} ${plural(total, ["спортсмен", "спортсмена", "спортсменов"])}`;

  /** Полный список для мобильной раскладки: там он лежит под картой, а не поверх, – сворачивать нечего. */
  const list = (
    <Stack spacing={0.25} component="ul" sx={{ listStyle: "none", m: 0, p: 0 }} aria-label="Занимающиеся по муниципалитетам">
      <Typography component="li" sx={{ fontFamily: FONT_MONO, fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "rgba(255,255,255,0.5)", mb: 1 }}>
        {countLabel}
      </Typography>
      {topRows}
    </Stack>
  );

  return (
    <Box>
      <Box sx={{ position: "relative", borderRadius: 2, border: "1px solid rgba(255,255,255,0.08)", bgcolor: "rgba(255,255,255,0.02)", overflow: "hidden" }}>
        <svg
          viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
          role="group"
          aria-label="Карта Оренбургской области по муниципалитетам"
          style={{ display: "block", width: "100%", height: "auto" }}
          onMouseLeave={() => setActive(null)}
        >
          {REGION_SHAPES.map((shape) => {
            const data = byShape.get(shape.name);
            const on = active === shape.name;
            return (
              <path
                key={shape.name}
                d={shape.d}
                fill={on ? ACCENT : landFill(data?.athletes ?? 0, max)}
                stroke={on ? "#fff" : LAND_EDGE}
                strokeWidth={on ? 1.6 : 0.8}
                strokeLinejoin="round"
                role="button"
                tabIndex={0}
                aria-label={data ? `${data.name}: ${data.athletes} занимающихся, организаций ${data.organizations}` : shape.name}
                onMouseEnter={() => setActive(shape.name)}
                onFocus={() => setActive(shape.name)}
                onBlur={() => setActive(null)}
                style={{ cursor: "pointer", outline: "none", transition: "fill .15s ease" }}
              />
            );
          })}
        </svg>

        {current && (() => {
          // У края карты центрированный тултип вылезает за рамку контейнера (overflow: hidden)
          // и обрезается – поэтому у краёв меняем выравнивание на прижатое к точке региона, а не
          // центрированное на ней; места с запасом хватает, чтобы подпись не срезало.
          const cxPct = (current.cx / MAP_WIDTH) * 100;
          const cyPct = (current.cy / MAP_HEIGHT) * 100;
          const hEdge = cxPct < 18 ? "left" : cxPct > 82 ? "right" : "center";
          const vBelow = cyPct < 18;
          const x = hEdge === "left" ? "0%" : hEdge === "right" ? "-100%" : "-50%";
          const y = vBelow ? "14px" : "calc(-100% - 14px)";
          return (
          <Box
            sx={{
              position: "absolute",
              left: `${cxPct}%`,
              top: `${cyPct}%`,
              transform: `translate(${x}, ${y})`,
              pointerEvents: "none",
              px: 2,
              py: 1.5,
              borderRadius: 1.5,
              bgcolor: "#EDEDED",
              color: BRAND.text,
              whiteSpace: "nowrap",
              zIndex: 2,
            }}
          >
            <Typography sx={{ fontFamily: FONT_MONO, fontSize: 10.5, letterSpacing: "0.08em", textTransform: "uppercase", color: ACCENT, mb: 0.25 }}>
              муниципалитет
            </Typography>
            <Typography sx={{ fontWeight: 700, fontSize: 15, lineHeight: 1.2 }}>{currentData?.name ?? current.name}</Typography>
            <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12, color: BRAND.muted, mt: 0.5 }}>
              {currentData
                ? `${currentData.athletes} ${plural(currentData.athletes, ["спортсмен", "спортсмена", "спортсменов"])} · орг.: ${currentData.organizations}`
                : "занимающихся пока нет"}
            </Typography>
          </Box>
          );
        })()}

        {/* список лежит в свободном верхнем правом углу карты и по умолчанию свёрнут: развёрнутым
            он закрывает как раз ту часть области, про которую рассказывает (на узких экранах
            панель не нужна – список лежит ниже карты, см. list в конце компонента) */}
        <Box
          sx={{
            display: { xs: "none", md: "block" },
            position: "absolute",
            top: 16,
            right: 16,
            width: 208,
            borderRadius: 2,
            bgcolor: "rgba(10,15,31,0.82)",
            border: "1px solid rgba(255,255,255,0.1)",
            overflow: "hidden",
          }}
        >
          <Box
            component="button"
            type="button"
            onClick={() => setListOpen((v) => !v)}
            aria-expanded={listOpen}
            aria-controls="region-map-top-list"
            sx={{
              all: "unset",
              boxSizing: "border-box",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1,
              width: "100%",
              px: 1.5,
              py: 1.25,
              cursor: "pointer",
              "&:hover": { bgcolor: "rgba(255,255,255,0.06)" },
              "&:focus-visible": { outline: `2px solid ${BRAND.cyan}`, outlineOffset: -2 },
            }}
          >
            <Typography sx={{ fontFamily: FONT_MONO, fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: "rgba(255,255,255,0.8)" }}>
              топ городов · {total}
            </Typography>
            <ExpandMoreIcon sx={{ fontSize: 19, color: "rgba(255,255,255,0.6)", transform: listOpen ? "rotate(180deg)" : "none", transition: "transform .25s ease" }} />
          </Box>
          <Collapse in={listOpen} id="region-map-top-list">
            <Box component="ul" sx={{ listStyle: "none", m: 0, px: 1.5, pb: 1.5 }} aria-label="Занимающиеся по муниципалитетам">
              {topRows}
            </Box>
          </Collapse>
        </Box>

        <Typography sx={{ position: "absolute", left: 16, bottom: 10, fontFamily: FONT_MONO, fontSize: 10.5, letterSpacing: "0.08em", color: "rgba(255,255,255,0.35)", textTransform: "uppercase" }}>
          35 районов и городских округов · © OpenStreetMap
        </Typography>
      </Box>
      <Box sx={{ display: { xs: "block", md: "none" }, mt: 2 }}>{list}</Box>
    </Box>
  );
}
