import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import EmojiEventsIcon from "@mui/icons-material/EmojiEvents";
import { Box, Button, Card, CardActionArea, Chip, MenuItem, Skeleton, Stack, TextField, Typography } from "@mui/material";
import { useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";

import type { FeedItem, LeaderRow, Navigator, RegistrationOptions } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { BRAND, FONT_MONO } from "../../theme";
import { fmtDate, plural } from "../../utils/format";
import { FORMAT_LABEL, LEVEL_LABEL, ORG_TYPE_LABEL, ROLE_HOME } from "../../utils/labels";
import { DisciplineIcon } from "../brand/DisciplineIcon";
import { EmptyState, useGet } from "../common";
import { Reveal } from "../Reveal";
import { HomeSection, capitalize, hiddenScrollbar, shortTitle } from "./parts";

/* ---------- 6 дисциплин ---------- */
export function DisciplineGrid({ nav }: { nav: Navigator }) {
  return (
    <HomeSection eyebrow="дисциплины" title="Шесть направлений вида спорта" subtitle="Учёт, календарь, разряды и отчёты работают одинаково для всех дисциплин.">
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)" }, gap: 3 }}>
        {nav.disciplines.map((d, i) => (
          <Reveal key={d.id} delay={i * 70} sx={{ height: "100%" }}>
          <Card sx={{ height: "100%", p: 3, transition: "border-color .2s, transform .2s, box-shadow .2s", "&:hover": { borderColor: BRAND.blue, transform: "translateY(-2px)", boxShadow: "0 12px 32px -16px rgba(43,89,255,0.45)" } }}>
            <Stack direction="row" justifyContent="space-between" alignItems="flex-start" sx={{ mb: 2.5 }}>
              <DisciplineIcon code={d.code} size={36} />
              <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12, color: "text.secondary" }}>{String(i + 1).padStart(2, "0")}</Typography>
            </Stack>
            <Typography variant="h6" sx={{ mb: 1, lineHeight: 1.3 }}>
              {capitalize(d.name.replace("Программирование ", ""))}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ minHeight: 64, mb: 2 }}>
              {d.description}
            </Typography>
            <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12.5, color: BRAND.blue }}>
              {d.athletes} {plural(d.athletes, ["спортсмен", "спортсмена", "спортсменов"])}
            </Typography>
          </Card>
          </Reveal>
        ))}
      </Box>
    </HomeSection>
  );
}

/* ---------- Интерактивная сетка турниров ---------- */
export function TournamentGrid({ nav }: { nav: Navigator }) {
  const [filter, setFilter] = useState("all");
  const disciplines = useMemo(() => Array.from(new Map(nav.upcoming.map((c) => [c.discipline.code, c.discipline.name])).entries()), [nav.upcoming]);
  const list = nav.upcoming.filter((c) => filter === "all" || c.discipline.code === filter);

  return (
    <HomeSection
      tone="white"
      eyebrow="календарь"
      title="Ближайшие турниры"
      subtitle="Региональные, межрегиональные и всероссийские соревнования. Формат этапов – онлайн, очно или смешанный."
      actions={
        <Button component={RouterLink} to="/calendar" endIcon={<ArrowForwardIcon />}>
          Весь календарь
        </Button>
      }
    >
      <Stack direction="row" spacing={1} sx={{ mb: 4, pb: 0.5, ...hiddenScrollbar }} role="group" aria-label="Фильтр по дисциплине">
        <Chip label="Все" clickable onClick={() => setFilter("all")} color={filter === "all" ? "primary" : "default"} variant={filter === "all" ? "filled" : "outlined"} />
        {disciplines.map(([code, name]) => (
          <Chip key={code} label={capitalize(name.replace("Программирование ", ""))} clickable onClick={() => setFilter(code)} color={filter === code ? "primary" : "default"} variant={filter === code ? "filled" : "outlined"} sx={{ flexShrink: 0 }} />
        ))}
      </Stack>
      {list.length === 0 ? (
        <EmptyState title="По этой дисциплине ближайших турниров нет" hint="Выберите другую дисциплину или откройте полный календарь" />
      ) : (
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" }, gap: 3 }}>
          {list.map((c, i) => {
            const d = new Date(`${c.start_date}T00:00:00`);
            const open = c.status === "registration_open";
            return (
              <Reveal key={c.id} delay={i * 70} sx={{ height: "100%" }}>
              <Card sx={{ height: "100%", transition: "border-color .2s, transform .2s, box-shadow .2s", "&:hover": { borderColor: BRAND.blue, transform: "translateY(-2px)", boxShadow: "0 12px 32px -16px rgba(43,89,255,0.45)" } }}>
                <CardActionArea component={RouterLink} to={`/competitions/${c.id}`} sx={{ p: 3, height: "100%", display: "flex", gap: 2.5, alignItems: "flex-start", justifyContent: "flex-start" }}>
                  <Box sx={{ minWidth: 64, py: 1.25, textAlign: "center", borderRadius: 3, bgcolor: BRAND.ink, color: "#fff" }}>
                    <Typography sx={{ fontFamily: FONT_MONO, fontWeight: 700, fontSize: 24, lineHeight: 1 }}>{String(d.getDate()).padStart(2, "0")}</Typography>
                    <Typography sx={{ fontFamily: FONT_MONO, fontSize: 11, letterSpacing: "0.1em", textTransform: "uppercase", color: BRAND.cyan, mt: 0.5 }}>
                      {d.toLocaleDateString("ru-RU", { month: "short" }).replace(".", "")}
                    </Typography>
                  </Box>
                  <Box sx={{ minWidth: 0 }}>
                    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                      <Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: open ? "#52C41A" : "#B0B8CC" }} />
                      <Typography sx={{ fontFamily: FONT_MONO, fontSize: 11.5, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                        {open ? "приём заявок" : "скоро"}
                      </Typography>
                    </Stack>
                    <Typography fontWeight={700} sx={{ lineHeight: 1.35, mb: 1 }}>
                      {shortTitle(c.title)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
                      {c.location ?? "место уточняется"}
                    </Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      <Chip size="small" label={FORMAT_LABEL[c.format]} variant="outlined" color={c.format === "offline" ? "secondary" : "primary"} />
                      <Chip size="small" label={LEVEL_LABEL[c.level]} variant="outlined" />
                    </Stack>
                  </Box>
                </CardActionArea>
              </Card>
              </Reveal>
            );
          })}
        </Box>
      )}
    </HomeSection>
  );
}

/* ---------- Лидерборд региона с фильтром по городам ---------- */
const medal = (place: number) =>
  place === 1 ? { bg: "#FFF3C4", fg: "#8A6500" } : place === 2 ? { bg: "#E9EDF5", fg: "#4B5878" } : place === 3 ? { bg: "#FFE3D1", fg: "#9A4A1C" } : { bg: "#F1F4FA", fg: "#5A6788" };

export function Leaderboard({ nav }: { nav: Navigator }) {
  const [discipline, setDiscipline] = useState("algorithmic");
  const [cityId, setCityId] = useState<number | null>(null);
  const options = useGet<RegistrationOptions>("/public/options");
  const q = useGet<LeaderRow[]>("/public/leaderboard", { discipline, municipality_id: cityId, limit: 8 });

  const cities = useMemo(() => {
    const ids = new Map((options.data?.municipalities ?? []).map((m) => [m.name, m.id]));
    return nav.regions
      .filter((r) => r.athletes > 0 && ids.has(r.name))
      .sort((a, b) => b.athletes - a.athletes)
      .slice(0, 6)
      .map((r) => ({ id: ids.get(r.name) as number, name: r.name.replace("г. ", "") }));
  }, [nav.regions, options.data]);

  return (
    <HomeSection
      eyebrow="лидерборд"
      title="Рейтинг сезона по городам области"
      subtitle="Очки за призовые места по уровню турнира, коэффициент стабильности ×1,2. Имена сокращены для публичного показа."
      actions={
        <Button component={RouterLink} to="/rating" endIcon={<ArrowForwardIcon />}>
          Полный рейтинг
        </Button>
      }
    >
      <Card sx={{ p: { xs: 2, md: 3 } }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} justifyContent="space-between" sx={{ mb: 3 }}>
          <Stack direction="row" spacing={1} sx={{ pb: 0.5, ...hiddenScrollbar }} role="group" aria-label="Фильтр по городам">
            <Chip label="Весь регион" clickable onClick={() => setCityId(null)} color={cityId === null ? "primary" : "default"} variant={cityId === null ? "filled" : "outlined"} sx={{ flexShrink: 0 }} />
            {cities.map((c) => (
              <Chip key={c.id} label={c.name} clickable onClick={() => setCityId(c.id)} color={cityId === c.id ? "primary" : "default"} variant={cityId === c.id ? "filled" : "outlined"} sx={{ flexShrink: 0 }} />
            ))}
          </Stack>
          <TextField select label="Дисциплина" value={discipline} onChange={(e) => setDiscipline(e.target.value)} sx={{ maxWidth: { md: 280 } }}>
            {nav.disciplines.map((d) => (
              <MenuItem key={d.code} value={d.code}>{capitalize(d.name.replace("Программирование ", ""))}</MenuItem>
            ))}
          </TextField>
        </Stack>

        {q.isLoading && (
          <Stack spacing={1}>
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} variant="rounded" height={56} />)}
          </Stack>
        )}
        {q.data && q.data.length === 0 && <EmptyState title="В этом городе пока нет результатов сезона" hint="Попробуйте другую дисциплину или «Весь регион»" />}
        {q.data && q.data.length > 0 && (
          <Box component="ol" sx={{ listStyle: "none", m: 0, p: 0 }}>
            {q.data.map((r) => {
              const m = medal(r.place);
              return (
                <Box component="li" key={`${r.place}-${r.name}`} sx={{ display: "grid", gridTemplateColumns: { xs: "40px 1fr auto", sm: "48px 1fr 120px auto" }, gap: 2, alignItems: "center", py: 1.5, px: 1, borderBottom: `1px solid ${BRAND.border}`, "&:last-of-type": { borderBottom: "none" } }}>
                  <Box sx={{ width: 40, height: 40, borderRadius: 2, display: "grid", placeItems: "center", bgcolor: m.bg, color: m.fg, fontFamily: FONT_MONO, fontWeight: 700 }}>{r.place}</Box>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography fontWeight={700} noWrap>{r.name}</Typography>
                    <Typography variant="body2" color="text.secondary" noWrap>
                      {r.organization ?? r.municipality ?? "–"}
                    </Typography>
                  </Box>
                  <Chip size="small" icon={<EmojiEventsIcon />} label={`${r.prizes} ${plural(r.prizes, ["приз", "приза", "призов"])}`} sx={{ display: { xs: "none", sm: "inline-flex" }, justifySelf: "end" }} />
                  <Typography sx={{ fontFamily: FONT_MONO, fontWeight: 700, fontSize: 18, color: BRAND.blue }}>{Number(r.points).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}</Typography>
                </Box>
              );
            })}
          </Box>
        )}
      </Card>
    </HomeSection>
  );
}

/* ---------- Лента недавних результатов ---------- */
export function ActivityFeed() {
  const q = useGet<FeedItem[]>("/public/feed", { limit: 4 });
  return (
    <HomeSection tone="white" eyebrow="лента" title="Недавние результаты" subtitle="Опубликованные протоколы региональных и выездных соревнований.">
      {q.isLoading && <Skeleton variant="rounded" height={220} />}
      {q.data && (
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(2, 1fr)" }, gap: 3 }}>
          {q.data.map((f) => (
            <Card key={f.competition_id} sx={{ height: "100%" }}>
              <CardActionArea component={RouterLink} to={`/competitions/${f.competition_id}`} sx={{ p: 3, height: "100%" }}>
                <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12, color: "text.secondary", mb: 1.5 }}>{fmtDate(f.published_at)} · {f.discipline.replace("Программирование ", "")}</Typography>
                <Typography fontWeight={700} sx={{ lineHeight: 1.35, mb: 2 }}>{shortTitle(f.title)}</Typography>
                <Stack direction="row" spacing={1.5} alignItems="center">
                  <EmojiEventsIcon sx={{ color: "#D49A00" }} />
                  <Typography variant="body2">{f.winner ? <>Победитель: <b>{f.winner}</b></> : "Протокол опубликован"}</Typography>
                  <Typography sx={{ ml: "auto", fontFamily: FONT_MONO, fontSize: 12, color: "text.secondary" }}>{f.participants} уч.</Typography>
                </Stack>
              </CardActionArea>
            </Card>
          ))}
        </Box>
      )}
    </HomeSection>
  );
}

/* ---------- Как это работает ---------- */
export function HowItWorks() {
  const steps = [
    { n: "01", t: "Регистрация", d: "Профиль, дисциплины и согласие на обработку персональных данных. Для несовершеннолетних – данные законного представителя." },
    { n: "02", t: "Заявка на турнир", d: "Платформа сама проверит возраст и дисциплину. Если у вас есть тренер, заявку подаёт он." },
    { n: "03", t: "Результат и разряд", d: "Протокол формируется автоматически, результат попадает в историю, а по нему можно подать заявку на разряд." },
  ];
  return (
    <HomeSection eyebrow="как это работает" title="От регистрации до разряда за три шага">
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(3, 1fr)" }, gap: 3 }}>
        {steps.map((s, i) => (
          <Reveal key={s.n} delay={i * 90} sx={{ height: "100%" }}>
          <Card sx={{ height: "100%", p: 4, position: "relative", overflow: "hidden" }}>
            <Typography sx={{ fontFamily: FONT_MONO, fontWeight: 700, fontSize: 56, lineHeight: 1, color: "#E3EAFF", letterSpacing: "-0.04em", mb: 2 }}>{s.n}</Typography>
            <Typography variant="h6" sx={{ mb: 1 }}>{s.t}</Typography>
            <Typography variant="body2" color="text.secondary">{s.d}</Typography>
          </Card>
          </Reveal>
        ))}
      </Box>
    </HomeSection>
  );
}

/* ---------- Где заниматься ---------- */
export function Organizations({ nav }: { nav: Navigator }) {
  return (
    <HomeSection tone="white" eyebrow="организации" title="Где заниматься в области" subtitle="Школы, колледжи, вузы, спортивные школы и клубы по городам.">
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "repeat(2, 1fr)", lg: "repeat(3, 1fr)" }, gap: 3 }}>
        {nav.municipalities.map((m, i) => (
          <Reveal key={m.municipality} delay={i * 70} sx={{ height: "100%" }}>
          <Card sx={{ height: "100%", p: 3 }}>
            <Stack direction="row" justifyContent="space-between" alignItems="baseline" sx={{ mb: 2 }}>
              <Typography variant="h6">{m.municipality}</Typography>
              <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12, color: "text.secondary" }}>{m.organizations.length} орг.</Typography>
            </Stack>
            <Stack spacing={1.25}>
              {m.organizations.map((o) => (
                <Box key={o.id}>
                  <Typography variant="body2" fontWeight={600}>{o.name}</Typography>
                  <Typography sx={{ fontFamily: FONT_MONO, fontSize: 11.5, color: "text.secondary" }}>{ORG_TYPE_LABEL[o.type] ?? o.type}</Typography>
                </Box>
              ))}
            </Stack>
          </Card>
          </Reveal>
        ))}
      </Box>
    </HomeSection>
  );
}

/* ---------- Финальный призыв ---------- */
export function CtaBand() {
  const { me } = useAuth();
  return (
    <Box sx={{ py: { xs: 7, md: 10 } }}>
      <Box sx={{ maxWidth: 1200, mx: "auto", px: { xs: 2, sm: 3 } }}>
        <Reveal
          sx={{
            position: "relative",
            overflow: "hidden",
            p: { xs: 4, md: 8 },
            borderRadius: 6,
            color: "#fff",
            textAlign: "center",
            background: `radial-gradient(70% 120% at 80% 0%, rgba(34,211,238,0.35), transparent 60%), linear-gradient(135deg, ${BRAND.blue}, #1B2F9E 70%, ${BRAND.ink})`,
          }}
        >
          <Typography variant="h3" component="h2" sx={{ fontSize: { xs: "1.75rem", md: "2.5rem" }, mb: 2 }}>
            Готовы выйти на старт?
          </Typography>
          <Typography sx={{ maxWidth: 520, mx: "auto", color: "rgba(255,255,255,0.8)", mb: 4 }}>
            Создайте профиль за минуту, выберите дисциплину и подайте заявку на ближайший турнир.
          </Typography>
          <Button size="large" variant="contained" component={RouterLink} to={me ? ROLE_HOME[me.active_role] : "/register"} sx={{ bgcolor: "#fff", color: BRAND.blueDark, boxShadow: "none", "&:hover": { bgcolor: "#EEF2FF", boxShadow: "none" } }}>
            {me ? "Перейти в кабинет" : "Зарегистрироваться"}
          </Button>
        </Reveal>
      </Box>
    </Box>
  );
}
