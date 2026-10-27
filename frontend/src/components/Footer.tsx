import { Box, Container, Link, Skeleton, Stack, Typography } from "@mui/material";

import type { Navigator } from "../api/types";
import { BRAND, FONT_MONO } from "../theme";
import { BrandMark } from "./brand/BrandMark";
import { RegionMap } from "./brand/RegionMap";
import { useGet } from "./common";

const eyebrow = { fontFamily: FONT_MONO, fontSize: 12, letterSpacing: "0.1em", textTransform: "uppercase" } as const;

function Placeholder({ label }: { label: string }) {
  // ПЛЕЙСХОЛДЕР под логотип партнёра: замените на <img src="/brand/<partner>.svg" alt="…" />
  return (
    <Box
      aria-label={`Место под логотип: ${label}`}
      sx={{ height: 48, px: 2, display: "inline-flex", alignItems: "center", borderRadius: 2, border: "1px dashed rgba(255,255,255,0.22)", color: "rgba(255,255,255,0.55)", fontFamily: FONT_MONO, fontSize: 12 }}
    >
      {label}
    </Box>
  );
}

export function Footer() {
  const q = useGet<Navigator>("/public/navigator", undefined, { retry: false });

  return (
    <Box component="footer" sx={{ bgcolor: BRAND.ink, color: "#fff", mt: 8, position: "relative", overflow: "hidden" }}>
      <Box sx={{ height: "1px", background: `linear-gradient(90deg, transparent, ${BRAND.cyan}99, ${BRAND.blue}99, transparent)` }} />
      <Container maxWidth="lg" sx={{ pt: 8, pb: 4 }}>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0, 340px) minmax(0, 1fr)" }, gap: { xs: 6, md: 8 } }}>
          <Box>
            <Stack direction="row" spacing={1.5} alignItems="center" sx={{ mb: 2 }}>
              <BrandMark size={44} />
              <Typography sx={{ fontWeight: 800, fontSize: 20 }}>
                ФСП <Box component="span" sx={{ color: BRAND.cyan }}>Оренбург</Box>
              </Typography>
            </Stack>
            <Typography sx={{ color: "rgba(255,255,255,0.66)", fontSize: 14.5, lineHeight: 1.7, mb: 4 }}>
              Региональное отделение Федерации спортивного программирования Оренбургской области: турниры, разряды, рейтинг и сборная региона в одной платформе.
            </Typography>

            {/* ПЛЕЙСХОЛДЕР: реальные контакты региональной федерации */}
            <Typography sx={{ ...eyebrow, color: BRAND.cyan, mb: 1.5 }}>Контакты</Typography>
            <Stack spacing={1}>
              <Typography sx={{ color: "rgba(255,255,255,0.72)", fontSize: 14.5 }}>г. Оренбург, адрес уточняется</Typography>
              <Typography sx={{ color: "rgba(255,255,255,0.72)", fontSize: 14.5, fontFamily: FONT_MONO }}>info@fsp-orenburg.example</Typography>
              <Typography sx={{ color: "rgba(255,255,255,0.72)", fontSize: 14.5, fontFamily: FONT_MONO }}>+7 (000) 000-00-00</Typography>
            </Stack>
          </Box>

          <Box>
            <Typography sx={{ ...eyebrow, color: BRAND.cyan, mb: 0.5 }}>Регион на карте</Typography>
            <Typography sx={{ color: "rgba(255,255,255,0.6)", fontSize: 14, mb: 2.5 }}>
              Где занимаются спортивным программированием в Оренбургской области. Наведите на муниципалитет.
            </Typography>
            {q.isLoading && <Skeleton variant="rounded" height={320} sx={{ bgcolor: "rgba(255,255,255,0.06)", borderRadius: 4 }} />}
            {q.data && <RegionMap regions={q.data.regions} />}
          </Box>
        </Box>

        <Box sx={{ mt: 7, pt: 4, borderTop: "1px solid rgba(255,255,255,0.1)" }}>
          <Typography sx={{ ...eyebrow, color: "rgba(255,255,255,0.5)", mb: 2 }}>Партнёры и организаторы</Typography>
          <Stack direction="row" spacing={2} flexWrap="wrap" useFlexGap>
            <Placeholder label="ФСП России" />
            <Placeholder label="Минспорта Оренбургской области" />
            <Placeholder label="Партнёр хакатона" />
            <Placeholder label="Спонсор" />
          </Stack>
        </Box>

        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1} sx={{ mt: 6, color: "rgba(255,255,255,0.5)", fontSize: 13 }}>
          <Typography variant="body2" sx={{ color: "inherit" }}>© 2026 ФСП Оренбургской области · ОренКод</Typography>
          <Typography variant="body2" sx={{ color: "inherit", fontFamily: FONT_MONO }}>
            демо-версия · данные вымышленные ·{" "}
            <Link href="https://rusada.ru" target="_blank" rel="noreferrer" sx={{ color: "inherit" }}>
              РУСАДА ↗
            </Link>
          </Typography>
        </Stack>
      </Container>
    </Box>
  );
}
