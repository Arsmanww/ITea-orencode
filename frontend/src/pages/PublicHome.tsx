import { Box, Container, Skeleton } from "@mui/material";

import type { Navigator } from "../api/types";
import { ErrorBox, useGet } from "../components/common";
import { Hero } from "../components/home/Hero";
import { ActivityFeed, CtaBand, DisciplineGrid, HowItWorks, Leaderboard, Organizations, TournamentGrid } from "../components/home/Sections";

/** Публичная главная («Навигатор для новичка», Д11). Доступна без авторизации. */
export function PublicHome() {
  const q = useGet<Navigator>("/public/navigator");

  if (q.error) {
    return (
      <Container maxWidth="lg" sx={{ py: 6 }}>
        <ErrorBox error={q.error} />
      </Container>
    );
  }
  if (!q.data) {
    return (
      <Box>
        <Skeleton variant="rectangular" height={560} sx={{ bgcolor: "#0A0F1F", opacity: 0.9 }} />
        <Container maxWidth="lg" sx={{ py: 8 }}>
          <Skeleton variant="rounded" height={240} />
        </Container>
      </Box>
    );
  }

  const nav = q.data;
  return (
    <Box>
      <Hero nav={nav} />
      <DisciplineGrid nav={nav} />
      <TournamentGrid nav={nav} />
      <Leaderboard nav={nav} />
      <ActivityFeed />
      <HowItWorks />
      <Organizations nav={nav} />
      <CtaBand />
    </Box>
  );
}
