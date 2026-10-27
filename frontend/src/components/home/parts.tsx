import { Box, Container, Stack, Typography } from "@mui/material";
import type { ReactNode } from "react";

import { BRAND, FONT_MONO } from "../../theme";

/** Секция главной: единые вертикальные отступы (кратны 8) и заголовок «моно-эйбрау + h2». */
export function HomeSection({
  eyebrow,
  title,
  subtitle,
  actions,
  tone = "light",
  children,
}: {
  eyebrow: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  tone?: "light" | "white";
  children: ReactNode;
}) {
  return (
    <Box sx={{ py: { xs: 7, md: 10 }, bgcolor: tone === "white" ? "#fff" : "transparent", borderTop: tone === "white" ? `1px solid ${BRAND.border}` : "none", borderBottom: tone === "white" ? `1px solid ${BRAND.border}` : "none" }}>
      <Container maxWidth="lg">
        <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ xs: "flex-start", sm: "flex-end" }} spacing={2} sx={{ mb: { xs: 4, md: 5 } }}>
          <Box sx={{ maxWidth: 640 }}>
            <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: BRAND.blue, mb: 1.5 }}>
              {"{ "}
              {eyebrow}
              {" }"}
            </Typography>
            <Typography variant="h3" component="h2" sx={{ fontSize: { xs: "1.75rem", md: "2.25rem" } }}>
              {title}
            </Typography>
            {subtitle && (
              <Typography color="text.secondary" sx={{ mt: 1.5, fontSize: { xs: 15, md: 16.5 } }}>
                {subtitle}
              </Typography>
            )}
          </Box>
          {actions}
        </Stack>
        {children}
      </Container>
    </Box>
  );
}

/** «алгоритмическое» → «Алгоритмическое»: названия дисциплин в чипах и фильтрах. */
export function capitalize(text: string): string {
  return text ? text[0].toUpperCase() + text.slice(1) : text;
}

/** Скрывает полосу прокрутки у горизонтальных рядов чипов (прокрутка остаётся). */
export const hiddenScrollbar = {
  overflowX: "auto",
  scrollbarWidth: "none",
  "&::-webkit-scrollbar": { display: "none" },
} as const;

/** Короткое название турнира для карточек: без повторяющегося «по спортивному программированию». */
export function shortTitle(title: string): string {
  return title.replace(" по спортивному программированию", "").replace(/, \d{4}$/, "");
}
