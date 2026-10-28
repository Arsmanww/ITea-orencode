import EmojiEventsIcon from "@mui/icons-material/EmojiEvents";
import GavelIcon from "@mui/icons-material/Gavel";
import GroupsIcon from "@mui/icons-material/Groups";
import { Alert, Avatar, Box, Button, Chip, Link, Stack, Typography } from "@mui/material";
import { Link as RouterLink } from "react-router-dom";

import type { MyProfile } from "../api/types";
import { Async, EmptyState, KeyValue, PageTitle, Section, ValidityAlert, useGet } from "../components/common";
import { BRAND } from "../theme";
import { daysText, fmtDate } from "../utils/format";
import { ROLE_HOME, ROLE_LABEL, STAGE_LABEL } from "../utils/labels";

const ROLE_COLOR: Record<string, string> = { federation: BRAND.red, athlete: "#12A36B", coach: "#E08A00", judge: "#7C4DDB", ministry: "#546E7A" };
const GENDER_LABEL: Record<string, string> = { male: "мужской", female: "женский" };

function short(name: string) {
  return name.replace("Программирование ", "");
}

/** Карточка «кто я»: общие данные аккаунта и блок по каждой роли (у мульти-аккаунта – несколько). */
export function ProfilePage() {
  const q = useGet<MyProfile>("/me/profile");
  return (
    <Box>
      <Async q={q}>
        {(p) => (
          <>
            <PageTitle
              title="Мой профиль"
              subtitle="Основные данные аккаунта. Изменить их можно в кабинете или обратившись в федерацию"
              actions={<Button variant="contained" component={RouterLink} to={ROLE_HOME[p.active_role]}>Перейти в кабинет</Button>}
            />

            <Section>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={3} alignItems={{ sm: "center" }} sx={{ mb: 3 }}>
                <Avatar sx={{ width: 72, height: 72, bgcolor: ROLE_COLOR[p.active_role], fontSize: 26, fontWeight: 700 }}>
                  {`${p.user.last_name[0] ?? ""}${p.user.first_name[0] ?? ""}`.toUpperCase()}
                </Avatar>
                <Box sx={{ flexGrow: 1 }}>
                  <Typography variant="h5" sx={{ mb: 1 }}>{p.full_name}</Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {p.roles.map((r) => (
                      <Chip
                        key={r}
                        size="small"
                        label={r === p.active_role ? `${ROLE_LABEL[r]} · активная роль` : ROLE_LABEL[r]}
                        sx={r === p.active_role ? { bgcolor: ROLE_COLOR[r], color: "#fff", fontWeight: 700 } : undefined}
                        variant={r === p.active_role ? "filled" : "outlined"}
                      />
                    ))}
                  </Stack>
                </Box>
              </Stack>
              <KeyValue
                items={[
                  ["Email", p.user.email],
                  ["Дата рождения", `${fmtDate(p.user.birth_date)} · ${p.age} лет`],
                  ["Пол", GENDER_LABEL[p.user.gender] ?? p.user.gender],
                  ["Телефон", p.user.phone],
                  ["Муниципалитет", p.municipality],
                  ["На платформе с", fmtDate(p.registered_at)],
                  [
                    "Согласие на обработку ПДн",
                    p.consent.accepted ? (
                      <Stack key="c" direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                        <Chip size="small" color="success" label="принято" />
                        {p.consent.has_scan ? <Chip size="small" variant="outlined" label="скан загружен" /> : <Chip size="small" color="warning" variant="outlined" label="скан не загружен" />}
                        {p.consent.signed_by && (
                          <Typography variant="body2" color="text.secondary">
                            {p.consent.is_guardian ? "законный представитель: " : "подписал: "}{p.consent.signed_by}
                          </Typography>
                        )}
                      </Stack>
                    ) : (
                      <Chip key="c" size="small" color="warning" label="не найдено" />
                    ),
                  ],
                  ["Уведомления на почту", <Chip key="m" size="small" color={p.email_notifications_enabled ? "success" : "default"} label={p.email_notifications_enabled ? "включены" : "выключены"} />],
                ]}
              />
            </Section>

            {p.athlete && (
              <Section title="Спортсмен">
                <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
                  <Chip label={`Стартов: ${p.athlete.starts}`} />
                  <Chip color="warning" icon={<EmojiEventsIcon />} label={`Призовых мест: ${p.athlete.prizes}`} />
                  <Chip variant="outlined" label={`Дисциплин: ${p.athlete.disciplines.length}`} />
                </Stack>
                {p.athlete.disciplines.map((d) => <ValidityAlert key={d.discipline.id} info={d.rank} what={`Разряд (${short(d.discipline.name)})`} />)}
                {p.athlete.disciplines.length === 0 ? (
                  <EmptyState title="Занятия не оформлены" hint="Обратитесь в федерацию, чтобы вас внесли в реестр по дисциплине" />
                ) : (
                  <Stack spacing={1.5}>
                    {p.athlete.disciplines.map((d) => (
                      <Stack key={d.discipline.id} direction={{ xs: "column", sm: "row" }} spacing={1} alignItems={{ sm: "center" }}
                        sx={{ p: 1.5, borderRadius: 2, bgcolor: "#F7F9FD", border: "1px solid", borderColor: "divider" }}>
                        <Box sx={{ flexGrow: 1 }}>
                          <Typography fontWeight={700}>{short(d.discipline.name)}</Typography>
                          <Typography variant="body2" color="text.secondary">
                            {d.organization ?? "Без организации"} · с {fmtDate(d.since)}
                            {d.training_stage ? ` · ${STAGE_LABEL[d.training_stage] ?? d.training_stage}` : ""}
                          </Typography>
                        </Box>
                        {d.rank ? (
                          <Chip
                            size="small"
                            color={d.rank.expired ? "error" : d.rank.warning ? "warning" : "primary"}
                            variant={d.rank.warning ? "filled" : "outlined"}
                            label={d.rank.valid_until ? `${d.rank.name} · до ${fmtDate(d.rank.valid_until)}` : d.rank.name}
                          />
                        ) : (
                          <Chip size="small" variant="outlined" label="разряда нет" />
                        )}
                        <Chip size="small" variant="outlined" color={d.coach ? "primary" : "default"} label={d.coach ? `Тренер: ${d.coach}` : "Без тренера"} />
                      </Stack>
                    ))}
                  </Stack>
                )}
                <Box sx={{ mt: 2 }}>
                  {p.athlete.antidoping_course_date ? (
                    <Alert severity="success">
                      Антидопинговый курс РУСАДА пройден {fmtDate(p.athlete.antidoping_course_date)}.
                      {p.athlete.antidoping_cert_url && <> <Link href={p.athlete.antidoping_cert_url} target="_blank" rel="noreferrer">Сертификат</Link></>}
                    </Alert>
                  ) : (
                    <Alert severity="warning">Отметка о прохождении онлайн-курса РУСАДА не указана – добавьте её в кабинете спортсмена.</Alert>
                  )}
                </Box>
                {p.athlete.guardian_name && (
                  <Typography variant="body2" color="text.secondary" sx={{ mt: 1.5 }}>
                    Законный представитель: {p.athlete.guardian_name}{p.athlete.guardian_phone ? `, ${p.athlete.guardian_phone}` : ""}
                  </Typography>
                )}
              </Section>
            )}

            {p.coach && (
              <Section title="Тренер">
                <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap" useFlexGap>
                  <Chip icon={<GroupsIcon />} label={`Подопечных: ${p.coach.athletes}`} />
                  {p.coach.organization && <Chip variant="outlined" label={p.coach.organization} />}
                </Stack>
                {p.coach.disciplines.length === 0 ? (
                  <EmptyState title="Подопечных пока нет" hint="Отправьте запрос на привязку в кабинете тренера" />
                ) : (
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {p.coach.disciplines.map((d) => <Chip key={d} size="small" color="primary" variant="outlined" label={short(d)} />)}
                  </Stack>
                )}
              </Section>
            )}

            {p.judge && (
              <Section title="Судья">
                <ValidityAlert info={p.judge.category} what="Судейская категория" />
                <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
                  <GavelIcon color={p.judge.category?.warning ? "warning" : "primary"} sx={{ fontSize: 36 }} />
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography fontWeight={700}>{p.judge.category?.name ?? "Категория не присвоена"}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {p.judge.category
                        ? p.judge.category.valid_until
                          ? `действует до ${fmtDate(p.judge.category.valid_until)} · ${daysText(p.judge.category.days_left)}`
                          : "бессрочно"
                        : "Подайте заявку на присвоение в кабинете судьи"}
                      {p.judge.organization ? ` · ${p.judge.organization}` : ""}
                    </Typography>
                  </Box>
                  <Chip label={`Назначений: ${p.judge.assignments}`} variant="outlined" />
                </Stack>
              </Section>
            )}
          </>
        )}
      </Async>
    </Box>
  );
}
