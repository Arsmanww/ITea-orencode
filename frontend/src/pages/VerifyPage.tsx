import CancelIcon from "@mui/icons-material/Cancel";
import VerifiedIcon from "@mui/icons-material/Verified";
import { Box, Button, Card, CardContent, Chip, Stack, Typography } from "@mui/material";
import { Link as RouterLink, useParams } from "react-router-dom";

import type { Verification } from "../api/types";
import { KeyValue, Loading, useGet } from "../components/common";
import { fmtDate, fmtNum, fmtPeriod } from "../utils/format";
import { LEVEL_LABEL } from "../utils/labels";

/** Публичная страница, на которую ведёт QR-код справки. Доступна без авторизации. */
export function VerifyPage() {
  const { token } = useParams();
  const q = useGet<Verification>(`/public/certificates/${token}`);

  return (
    <Box sx={{ maxWidth: 680, mx: "auto" }}>
      <Typography variant="overline" color="text.secondary">
        Проверка подлинности справки об участии
      </Typography>
      {q.isLoading && <Loading label="Проверяем справку…" />}
      {q.error && (
        <Card sx={{ borderColor: "error.main", mt: 1 }}>
          <CardContent sx={{ textAlign: "center", py: 5 }}>
            <CancelIcon color="error" sx={{ fontSize: 64 }} />
            <Typography variant="h5" sx={{ mt: 1 }}>
              Справка не найдена
            </Typography>
            <Typography color="text.secondary" sx={{ mt: 1, mb: 3 }}>
              Документ с таким кодом в системе отсутствует. Возможно, QR-код повреждён или справка не выдавалась.
            </Typography>
            <Button component={RouterLink} to="/" variant="contained">
              На главную
            </Button>
          </CardContent>
        </Card>
      )}
      {q.data && (
        <Card sx={{ borderColor: q.data.valid ? "success.main" : "error.main", borderWidth: 2, mt: 1 }}>
          <CardContent sx={{ p: { xs: 2.5, sm: 4 } }}>
            <Stack direction="row" spacing={2} alignItems="center" sx={{ mb: 3 }}>
              {q.data.valid ? <VerifiedIcon color="success" sx={{ fontSize: 56 }} /> : <CancelIcon color="error" sx={{ fontSize: 56 }} />}
              <Box>
                <Typography variant="h5" component="h1">
                  {q.data.valid ? "Справка подлинная" : "Справка аннулирована"}
                </Typography>
                <Typography color="text.secondary">
                  № {q.data.number} · выдана {fmtDate(q.data.issued_at)}
                </Typography>
              </Box>
            </Stack>
            <KeyValue
              items={[
                ["Спортсмен", <b key="n">{q.data.athlete_name}</b>],
                ["Соревнование", q.data.competition_title],
                ["Дисциплина", q.data.discipline],
                ["Статус соревнования", LEVEL_LABEL[q.data.level]],
                ["Даты", fmtPeriod(q.data.start_date, q.data.end_date)],
                ["Занятое место", q.data.place ? <Chip key="p" color="primary" label={`${q.data.place} место из ${q.data.participants}`} /> : "–"],
                ["Набрано баллов", q.data.score ? fmtNum(q.data.score) : "–"],
              ]}
            />
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 3 }}>
              Данные получены из опубликованного протокола соревнования в платформе ФСП Оренбургской области. Дата рождения и контакты спортсмена не раскрываются.
            </Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
