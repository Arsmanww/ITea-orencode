import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { Box, Button, Container, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";

import type { Competition, Navigator } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Reveal } from "../Reveal";
import { useCountUp } from "../../hooks/useCountUp";
import { useCountdown } from "../../hooks/useCountdown";
import { BRAND, FONT_MONO } from "../../theme";
import { fmtDateTime, fmtPeriod } from "../../utils/format";
import { FORMAT_LABEL, LEVEL_LABEL, ROLE_HOME } from "../../utils/labels";
import { shortTitle } from "./parts";

function Counter({ value, label }: { value: number; label: string }) {
  const shown = useCountUp(value);
  return (
    <Box>
      <Typography sx={{ fontFamily: FONT_MONO, fontWeight: 700, fontSize: { xs: 32, md: 44 }, lineHeight: 1, letterSpacing: "-0.03em", color: "#fff" }}>{shown}</Typography>
      <Typography sx={{ mt: 1, fontSize: 13.5, color: "rgba(255,255,255,0.62)" }}>{label}</Typography>
    </Box>
  );
}

function Tile({ value, unit }: { value: number; unit: string }) {
  return (
    <Box sx={{ flex: 1, textAlign: "center", py: 1.5, borderRadius: 2, bgcolor: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)" }}>
      <Typography sx={{ fontFamily: FONT_MONO, fontWeight: 700, fontSize: { xs: 24, sm: 28 }, lineHeight: 1, color: "#fff" }}>{String(value).padStart(2, "0")}</Typography>
      <Typography sx={{ fontFamily: FONT_MONO, fontSize: 10.5, letterSpacing: "0.1em", textTransform: "uppercase", color: "rgba(255,255,255,0.5)", mt: 0.75 }}>{unit}</Typography>
    </Box>
  );
}

function NextEventCard({ comp }: { comp: Competition }) {
  const countdown = useCountdown(`${comp.start_date}T10:00:00+05:00`);
  const open = comp.status === "registration_open";
  return (
    <Box
      sx={{
        position: "relative",
        p: { xs: 3, md: 4 },
        borderRadius: 5,
        border: "1px solid rgba(255,255,255,0.14)",
        background: "linear-gradient(160deg, rgba(255,255,255,0.1), rgba(255,255,255,0.03))",
        backdropFilter: "blur(10px)",
        boxShadow: "0 24px 64px -24px rgba(0,0,0,0.6)",
      }}
    >
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2.5 }}>
        <Typography sx={{ fontFamily: FONT_MONO, fontSize: 11.5, letterSpacing: "0.1em", textTransform: "uppercase", color: BRAND.cyan }}>следующее событие</Typography>
        {open && (
          <Box sx={{ px: 1.25, py: 0.5, borderRadius: 999, bgcolor: "rgba(184,243,74,0.14)", border: "1px solid rgba(184,243,74,0.4)", color: BRAND.lime, fontFamily: FONT_MONO, fontSize: 11 }}>
            приём заявок открыт
          </Box>
        )}
      </Stack>

      <Typography variant="h5" component="h2" sx={{ color: "#fff", fontSize: { xs: "1.2rem", md: "1.4rem" }, lineHeight: 1.3, mb: 1.5 }}>
        {shortTitle(comp.title)}
      </Typography>
      <Typography sx={{ color: "rgba(255,255,255,0.7)", fontSize: 14.5, mb: 3 }}>
        {LEVEL_LABEL[comp.level]} · {FORMAT_LABEL[comp.format]} · {comp.location ?? "место уточняется"}
      </Typography>

      {countdown && !countdown.reached ? (
        <Stack direction="row" spacing={1} sx={{ mb: 3 }} aria-label="Время до старта">
          <Tile value={countdown.days} unit="дней" />
          <Tile value={countdown.hours} unit="часов" />
          <Tile value={countdown.minutes} unit="минут" />
          <Tile value={countdown.seconds} unit="секунд" />
        </Stack>
      ) : (
        <Box sx={{ mb: 3, py: 1.5, textAlign: "center", borderRadius: 2, bgcolor: "rgba(184,243,74,0.12)", color: BRAND.lime, fontFamily: FONT_MONO }}>идёт прямо сейчас</Box>
      )}

      <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" alignItems={{ sm: "center" }} spacing={2}>
        <Box>
          <Typography sx={{ fontFamily: FONT_MONO, fontSize: 13, color: "#fff" }}>{fmtPeriod(comp.start_date, comp.end_date)}</Typography>
          {open && comp.registration_deadline && (
            <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12, color: "rgba(255,255,255,0.55)", mt: 0.5 }}>заявки до {fmtDateTime(comp.registration_deadline)}</Typography>
          )}
        </Box>
        <Button component={RouterLink} to={`/competitions/${comp.id}`} variant="contained" endIcon={<ArrowForwardIcon />}>
          Подробнее
        </Button>
      </Stack>

      {/* декоративный «код»: знак принадлежности к IT-тематике */}
      <Box aria-hidden sx={{ mt: 3, pt: 2, borderTop: "1px dashed rgba(255,255,255,0.16)", fontFamily: FONT_MONO, fontSize: 12, lineHeight: 1.7, color: "rgba(255,255,255,0.42)" }}>
        {"{ "}
        <Box component="span" sx={{ color: BRAND.cyan }}>"region"</Box>
        {": "}
        <Box component="span" sx={{ color: BRAND.lime }}>"56"</Box>
        {", "}
        <Box component="span" sx={{ color: BRAND.cyan }}>"disciplines"</Box>
        {": "}
        <Box component="span" sx={{ color: BRAND.lime }}>6</Box>
        {" }"}
      </Box>
    </Box>
  );
}

export function Hero({ nav }: { nav: Navigator }) {
  const { me } = useAuth();
  const next = nav.upcoming[0];

  return (
    <Box
      sx={{
        position: "relative",
        overflow: "hidden",
        color: "#fff",
        bgcolor: BRAND.ink,
        backgroundImage: [
          "radial-gradient(60% 80% at 82% 0%, rgba(43,89,255,0.5), transparent 62%)",
          "radial-gradient(40% 50% at 0% 100%, rgba(34,211,238,0.2), transparent 62%)",
          "linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px)",
          "linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px)",
        ].join(","),
        backgroundSize: "auto, auto, 48px 48px, 48px 48px",
      }}
    >
      <Container maxWidth="lg" sx={{ position: "relative", py: { xs: 7, md: 12 } }}>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "minmax(0, 7fr) minmax(0, 5fr)" }, gap: { xs: 6, md: 8 }, alignItems: "center" }}>
          <Reveal shift={16}>
            <Box sx={{ display: "inline-flex", alignItems: "center", gap: 1, px: 1.75, py: 0.75, mb: 3, borderRadius: 999, border: "1px solid rgba(255,255,255,0.16)", bgcolor: "rgba(255,255,255,0.05)", fontFamily: FONT_MONO, fontSize: 12, letterSpacing: "0.06em", color: "rgba(255,255,255,0.8)" }}>
              <Box component="span" sx={{ color: BRAND.cyan }}>{"{ }"}</Box> ФСП · Оренбургская область
            </Box>
            <Typography variant="h1" sx={{ fontSize: { xs: "2.25rem", sm: "3rem", md: "3.75rem" }, mb: 3 }}>
              Спортивное программирование{" "}
              <Box component="span" sx={{ display: "inline-block", background: `linear-gradient(90deg, ${BRAND.cyan}, #7C9BFF)`, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>
                в вашем регионе
              </Box>
            </Typography>
            <Typography sx={{ fontSize: { xs: 16, md: 18 }, lineHeight: 1.65, color: "rgba(255,255,255,0.72)", maxWidth: 560, mb: 4 }}>
              Турниры, заявки, протоколы, разряды и рейтинг в одной платформе – для школьников, студентов, тренеров и судей Оренбургской области.
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2} sx={{ mb: 6 }}>
              {me ? (
                <Button size="large" variant="contained" component={RouterLink} to={ROLE_HOME[me.active_role]} endIcon={<ArrowForwardIcon />}>
                  Перейти в кабинет
                </Button>
              ) : (
                <>
                  <Button size="large" variant="contained" component={RouterLink} to="/register" endIcon={<ArrowForwardIcon />}>
                    Быстрая регистрация
                  </Button>
                  <Button size="large" variant="outlined" component={RouterLink} to="/login" sx={{ color: "#fff", borderColor: "rgba(255,255,255,0.3)", "&:hover": { borderColor: "#fff", bgcolor: "rgba(255,255,255,0.06)" } }}>
                    Войти
                  </Button>
                </>
              )}
              <Button size="large" component={RouterLink} to="/calendar" sx={{ color: "rgba(255,255,255,0.8)" }}>
                Календарь турниров
              </Button>
            </Stack>
            <Stack direction="row" spacing={{ xs: 3, sm: 6 }} sx={{ pt: 4, borderTop: "1px solid rgba(255,255,255,0.12)" }}>
              <Counter value={nav.stats.athletes} label="занимающихся" />
              <Counter value={nav.stats.organizations} label="организаций" />
              <Counter value={nav.stats.competitions_this_year} label="турниров в году" />
            </Stack>
          </Reveal>

          {next && (
            <Reveal shift={16} delay={160}>
              <NextEventCard comp={next} />
            </Reveal>
          )}
        </Box>
      </Container>
    </Box>
  );
}
