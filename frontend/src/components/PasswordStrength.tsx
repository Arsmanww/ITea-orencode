import CancelIcon from "@mui/icons-material/Cancel";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import { Stack, Typography } from "@mui/material";

import { PASSWORD_RULES } from "../utils/password";

/** Живой чек-лист требований к паролю: не держит пользователя в неведении, почему кнопка неактивна. */
export function PasswordStrength({ password }: { password: string }) {
  if (!password) return null;
  return (
    <Stack spacing={0.25} sx={{ mt: -1 }}>
      {PASSWORD_RULES.map((rule) => {
        const ok = rule.test(password);
        return (
          <Stack key={rule.key} direction="row" spacing={0.75} alignItems="center">
            {ok ? <CheckCircleIcon color="success" sx={{ fontSize: 15 }} /> : <CancelIcon color="disabled" sx={{ fontSize: 15 }} />}
            <Typography variant="caption" color={ok ? "success.main" : "text.secondary"}>{rule.label}</Typography>
          </Stack>
        );
      })}
    </Stack>
  );
}
