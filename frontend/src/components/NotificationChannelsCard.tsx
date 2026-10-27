import ChatIcon from "@mui/icons-material/ChatBubbleOutline";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import { Alert, Box, Button, Chip, Stack, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { MaxLink, NotificationSettings } from "../api/types";
import { FONT_MONO } from "../theme";
import { Async, Section, useGet, useInvalidate } from "./common";
import { useToast } from "./Toast";

const SETTINGS = "/me/notification-settings";
const WHAT = "Сюда приходят: открытие регистрации, статус заявок, протоколы, решения по разрядам и категориям, напоминания о сроках.";

/** Внешний канал уведомлений — мессенджер MAX. Уведомления в кабинете работают всегда. */
export function NotificationChannelsCard() {
  const [waitingMax, setWaitingMax] = useState(false);
  // пока пользователь открывает ссылку в MAX, опрашиваем настройки: привязка придёт от бота
  const q = useGet<NotificationSettings>(SETTINGS, undefined, { refetchInterval: waitingMax ? 3000 : undefined });

  return (
    <Section title="Уведомления в мессенджере MAX">
      <Async q={q}>
        {(s) => (
          <Stack spacing={2.5}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip size="small" color="success" label="Личный кабинет — включён" />
              <Chip size="small" color={s.max_bound ? "success" : "default"} icon={<ChatIcon />} label={s.max_bound ? "MAX привязан" : "MAX не привязан"} />
            </Stack>
            <MaxBlock s={s} waiting={waitingMax} setWaiting={setWaitingMax} />
          </Stack>
        )}
      </Async>
    </Section>
  );
}

function MaxBlock({ s, waiting, setWaiting }: { s: NotificationSettings; waiting: boolean; setWaiting: (v: boolean) => void }) {
  const toast = useToast();
  const invalidate = useInvalidate();
  const [link, setLink] = useState<MaxLink | null>(null);

  useEffect(() => {
    if (s.max_bound && waiting) {
      setWaiting(false);
      setLink(null);
      toast.success("MAX привязан — бот прислал подтверждение");
    }
  }, [s.max_bound, waiting, setWaiting, toast]);

  const issue = useMutation({
    mutationFn: () => api<MaxLink>("/me/max/link", { method: "POST" }),
    onSuccess: (l) => {
      setLink(l);
      setWaiting(true);
      if (l.link) window.open(l.link, "_blank", "noopener");
    },
    onError: toast.error,
  });
  const unbind = useMutation({
    mutationFn: () => api<NotificationSettings>("/me/max", { method: "DELETE" }),
    onSuccess: async () => {
      toast.info("MAX отвязан");
      await invalidate(SETTINGS);
    },
    onError: toast.error,
  });

  return (
    <Box>
      {!s.max_bot_configured ? (
        <Alert severity="info">Бот MAX на этом стенде не подключён администратором (MAX_BOT_TOKEN). Уведомления приходят в личный кабинет — значок колокольчика в шапке.</Alert>
      ) : s.max_bound ? (
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
          <Typography variant="body2" sx={{ flex: 1 }}>{WHAT}</Typography>
          <Button color="error" onClick={() => unbind.mutate()} disabled={unbind.isPending}>Отвязать</Button>
        </Stack>
      ) : (
        <Stack spacing={1.5}>
          <Typography variant="body2" color="text.secondary">
            Нажмите «Подключить MAX»: откроется чат с ботом{s.max_bot_username ? ` @${s.max_bot_username}` : ""}, нажмите в нём «Начать». Вводить номера и ID не нужно.
          </Typography>
          <Box>
            <Button variant="contained" startIcon={<ChatIcon />} onClick={() => issue.mutate()} disabled={issue.isPending}>
              {link ? "Получить новую ссылку" : "Подключить MAX"}
            </Button>
          </Box>
          {link && (
            <Alert severity="info" icon={false}>
              <Stack spacing={1}>
                {link.link && (
                  <Typography variant="body2">
                    Если чат не открылся,{" "}
                    <Button size="small" href={link.link} target="_blank" rel="noopener" endIcon={<OpenInNewIcon fontSize="small" />} sx={{ p: 0, minWidth: 0, verticalAlign: "baseline" }}>
                      откройте ссылку
                    </Button>
                    . Если диалог с ботом уже был, отправьте ему код:
                  </Typography>
                )}
                {!link.link && <Typography variant="body2">Отправьте боту MAX этот код сообщением:</Typography>}
                <Typography sx={{ fontFamily: FONT_MONO, fontSize: 18, fontWeight: 600, letterSpacing: "0.04em", userSelect: "all" }}>{link.code}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Код одноразовый, действует до {new Date(link.expires_at).toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}. Ждём подтверждения от бота…
                </Typography>
              </Stack>
            </Alert>
          )}
        </Stack>
      )}
    </Box>
  );
}
