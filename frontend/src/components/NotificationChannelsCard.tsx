import EmailIcon from "@mui/icons-material/EmailOutlined";
import { Alert, Chip, Stack, Switch, Typography } from "@mui/material";
import { useMutation } from "@tanstack/react-query";

import { api } from "../api/client";
import type { NotificationSettings } from "../api/types";
import { Async, Section, useGet, useInvalidate } from "./common";
import { useToast } from "./Toast";

const SETTINGS = "/me/notification-settings";

/**
 * Внешний канал уведомлений — почта. Адрес берётся из аккаунта (логин при регистрации),
 * отдельно привязывать ничего не нужно: пользователь может только включить/выключить канал.
 * Уведомления в личном кабинете (колокольчик) работают всегда, независимо от этого тумблера.
 */
export function NotificationChannelsCard() {
  const toast = useToast();
  const invalidate = useInvalidate();
  const q = useGet<NotificationSettings>(SETTINGS);

  const toggle = useMutation({
    mutationFn: (enabled: boolean) => api<NotificationSettings>(SETTINGS, { method: "PUT", body: { enabled } }),
    onSuccess: async (s) => {
      toast.success(s.email_notifications_enabled ? "Уведомления на почту включены" : "Уведомления на почту выключены");
      await invalidate(SETTINGS);
    },
    onError: toast.error,
  });

  return (
    <Section title="Уведомления на почту">
      <Async q={q}>
        {(s) => (
          <Stack spacing={2}>
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              <Chip size="small" color="success" label="Личный кабинет — включён" />
              <Chip size="small" color={s.email_notifications_enabled ? "success" : "default"} icon={<EmailIcon />}
                    label={s.email_notifications_enabled ? "Почта — включена" : "Почта — выключена"} />
            </Stack>
            {!s.email_notifications_configured ? (
              <Alert severity="info">Почта на этом стенде не подключена администратором (SMTP_HOST). Уведомления приходят в личный кабинет — значок колокольчика в шапке.</Alert>
            ) : (
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems={{ sm: "center" }}>
                <Stack sx={{ flex: 1 }}>
                  <Typography variant="body2">
                    Сюда приходят: открытие регистрации, статус заявок, протоколы, решения по разрядам и категориям, напоминания о сроках.
                  </Typography>
                  <Typography variant="body2" color="text.secondary">Адрес: {s.email}</Typography>
                </Stack>
                <Switch checked={s.email_notifications_enabled} disabled={toggle.isPending} onChange={(e) => toggle.mutate(e.target.checked)} />
              </Stack>
            )}
          </Stack>
        )}
      </Async>
    </Section>
  );
}
