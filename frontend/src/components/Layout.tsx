import LogoutIcon from "@mui/icons-material/Logout";
import MenuIcon from "@mui/icons-material/Menu";
import {
  AppBar,
  Avatar,
  Box,
  Button,
  Chip,
  Container,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  MenuItem,
  Select,
  Stack,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from "@mui/material";
import { useEffect, useState } from "react";
import { Link as RouterLink, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import type { Navigator, Role } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { BRAND, FONT_MONO } from "../theme";
import { ROLE_HOME, ROLE_LABEL } from "../utils/labels";
import { BrandMark } from "./brand/BrandMark";
import { RegionBadge } from "./brand/RegionBadge";
import { Footer } from "./Footer";
import { NotificationsBell } from "./NotificationsBell";
import { scrollToTop, useGet } from "./common";
import { useToast } from "./Toast";

interface NavItem { to: string; label: string }

function navFor(role: Role | null): NavItem[] {
  if (!role) {
    return [
      { to: "/", label: "Навигатор" },
      { to: "/calendar", label: "Календарь" },
      { to: "/rating", label: "Рейтинг" },
    ];
  }
  const common: NavItem[] = [
    { to: "/calendar", label: "Календарь" },
    { to: "/rating", label: "Рейтинг" },
  ];
  const cabinet: Record<Role, NavItem[]> = {
    federation: [{ to: "/federation", label: "Кабинет" }, { to: "/registry", label: "Реестр" }, ...common, { to: "/reports", label: "Отчёты" }],
    athlete: [{ to: "/athlete", label: "Мой кабинет" }, ...common],
    coach: [{ to: "/coach", label: "Кабинет" }, ...common],
    judge: [{ to: "/judge", label: "Кабинет" }, ...common],
    ministry: common,
  };
  return [...cabinet[role], { to: "/", label: "Навигатор" }];
}

const ROLE_COLOR: Record<Role, string> = { federation: BRAND.red, athlete: "#12A36B", coach: "#E08A00", judge: "#7C4DDB", ministry: "#546E7A" };

function initials(last: string, first: string) {
  return `${last[0] ?? ""}${first[0] ?? ""}`.toUpperCase();
}

/** Плашка «живого» статуса: сколько турниров сейчас принимают заявки. */
function LiveStatus({ from }: { from: "lg" | "xl" }) {
  const q = useGet<Navigator>("/public/navigator", undefined, { retry: false });
  const open = q.data?.stats.open_registrations ?? 0;
  if (!q.data) return null;
  return (
    <Box
      component={RouterLink}
      to={open ? "/calendar?status=registration_open" : "/calendar"}
      sx={{
        display: { xs: "none", [from]: "inline-flex" },
        alignItems: "center",
        whiteSpace: "nowrap",
        flexShrink: 0,
        gap: 1,
        px: 1.5,
        height: 32,
        borderRadius: 999,
        border: "1px solid rgba(255,255,255,0.14)",
        bgcolor: "rgba(255,255,255,0.05)",
        color: "#fff",
        textDecoration: "none",
        fontFamily: FONT_MONO,
        fontSize: 12,
        letterSpacing: "0.02em",
        "&:hover": { bgcolor: "rgba(255,255,255,0.1)" },
      }}
    >
      <Box
        sx={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          bgcolor: open ? BRAND.lime : "rgba(255,255,255,0.4)",
          boxShadow: open ? `0 0 0 0 ${BRAND.lime}` : "none",
          animation: open ? "fspPulse 2s infinite" : "none",
          "@keyframes fspPulse": {
            "0%": { boxShadow: "0 0 0 0 rgba(184,243,74,0.6)" },
            "70%": { boxShadow: "0 0 0 8px rgba(184,243,74,0)" },
            "100%": { boxShadow: "0 0 0 0 rgba(184,243,74,0)" },
          },
          "@media (prefers-reduced-motion: reduce)": { animation: "none" },
        }}
      />
      {open ? `приём заявок: ${open}` : "приём заявок закрыт"}
    </Box>
  );
}

export function Layout() {
  const { me, switchRole, logout } = useAuth();
  const theme = useTheme();
  const mobile = useMediaQuery(theme.breakpoints.down("md"));
  const [drawer, setDrawer] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const items = navFor(me?.active_role ?? null);
  // в кабинете федерации пунктов больше: подпись логотипа и плашка статуса появляются только на широких экранах
  const crowded = items.length > 5;
  const home = location.pathname === "/";

  // SPA сохраняет позицию прокрутки от прежней страницы – на новой это выглядит как «бросило вниз».
  // Повтор после отрисовки нужен для страниц, которые догружаются лениво уже после смены маршрута.
  useEffect(() => {
    scrollToTop();
    const frame = requestAnimationFrame(scrollToTop);
    return () => cancelAnimationFrame(frame);
  }, [location.pathname]);

  const onSwitch = async (role: Role) => {
    try {
      await switchRole(role);
      toast.success(`Активная роль: ${ROLE_LABEL[role]}`);
      navigate(ROLE_HOME[role]);
    } catch (e) {
      toast.error(e);
    }
  };

  const roleSelect =
    me &&
    (me.roles.length < 2 ? (
      <Chip label={ROLE_LABEL[me.active_role]} sx={{ bgcolor: ROLE_COLOR[me.active_role], color: "#fff", fontWeight: 700 }} />
    ) : (
      <Select
        size="small"
        value={me.active_role}
        onChange={(e) => onSwitch(e.target.value as Role)}
        inputProps={{ "aria-label": "Активная роль" }}
        sx={{
          color: "#fff",
          minWidth: 144,
          borderRadius: 999,
          bgcolor: "rgba(255,255,255,0.08)",
          "& .MuiOutlinedInput-notchedOutline": { borderColor: "rgba(255,255,255,0.28)" },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: "#fff" },
          "& .MuiSvgIcon-root": { color: "#fff" },
        }}
      >
        {me.roles.map((r) => (
          <MenuItem key={r} value={r}>
            {ROLE_LABEL[r]}
          </MenuItem>
        ))}
      </Select>
    ));

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", flexDirection: "column", bgcolor: "background.default" }}>
      <AppBar
        position="sticky"
        elevation={0}
        sx={{
          bgcolor: "rgba(10,15,31,0.86)",
          backdropFilter: "blur(14px)",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          "&::after": { content: '""', position: "absolute", left: 0, right: 0, bottom: -1, height: "1px", background: `linear-gradient(90deg, transparent, ${BRAND.cyan}88, ${BRAND.blue}88, transparent)` },
        }}
      >
        <Toolbar sx={{ gap: 2, minHeight: { xs: 56, md: 64 }, flexWrap: "nowrap" }}>
          {mobile && (
            <IconButton color="inherit" edge="start" onClick={() => setDrawer(true)} aria-label="Меню">
              <MenuIcon />
            </IconButton>
          )}
          <Box component={RouterLink} to="/" sx={{ display: "flex", alignItems: "center", gap: 1.5, color: "#fff", textDecoration: "none", mr: 1 }}>
            <BrandMark size={mobile ? 36 : 40} />
            <Box sx={{ display: { xs: "none", sm: "block", md: "none", [crowded ? "xl" : "lg"]: "block" }, lineHeight: 1.1, whiteSpace: "nowrap" }}>
              <Typography sx={{ fontWeight: 800, fontSize: 17, letterSpacing: "-0.01em" }}>
                ФСП <Box component="span" sx={{ color: BRAND.cyan }}>Оренбург</Box>
              </Typography>
              <Typography sx={{ fontFamily: FONT_MONO, fontSize: 10.5, letterSpacing: "0.1em", textTransform: "uppercase", opacity: 0.6, mt: 0.25 }}>
                спортивное программирование
              </Typography>
            </Box>
          </Box>

          {!mobile && (
            <Stack direction="row" spacing={0.5} sx={{ flexGrow: 1 }}>
              {items.map((i) => (
                <Button
                  key={i.to + i.label}
                  component={NavLink}
                  to={i.to}
                  end={i.to === "/"}
                  color="inherit"
                  sx={{ color: "rgba(255,255,255,0.72)", borderRadius: 999, px: crowded ? 1.5 : 2, whiteSpace: "nowrap", minWidth: 0, "&:hover": { color: "#fff", bgcolor: "rgba(255,255,255,0.08)" }, "&.active": { color: "#fff", bgcolor: "rgba(255,255,255,0.12)" } }}
                >
                  {i.label}
                </Button>
              ))}
            </Stack>
          )}
          {mobile && <Box sx={{ flexGrow: 1 }} />}

          {!crowded && <RegionBadge />}
          <LiveStatus from={crowded ? "xl" : "lg"} />

          {me ? (
            <Stack direction="row" spacing={1.5} alignItems="center">
              <NotificationsBell />
              {!mobile && (
                <Stack
                  component={RouterLink}
                  to="/profile"
                  direction="row"
                  spacing={1}
                  alignItems="center"
                  title="Мой профиль"
                  sx={{ color: "#fff", textDecoration: "none", px: 1, py: 0.5, borderRadius: 999, "&:hover": { bgcolor: "rgba(255,255,255,0.1)" } }}
                >
                  <Avatar sx={{ width: 32, height: 32, bgcolor: ROLE_COLOR[me.active_role], fontSize: 13, fontWeight: 700 }}>{initials(me.user.last_name, me.user.first_name)}</Avatar>
                  <Box sx={{ lineHeight: 1.15, maxWidth: 168, display: { md: "none", lg: "block" } }}>
                    <Typography noWrap sx={{ fontSize: 13.5, fontWeight: 700 }}>
                      {me.user.last_name} {me.user.first_name[0]}.
                    </Typography>
                    <Typography noWrap sx={{ fontFamily: FONT_MONO, fontSize: 11, opacity: 0.65, display: { lg: "none", xl: "block" } }}>
                      {me.user.email}
                    </Typography>
                  </Box>
                </Stack>
              )}
              {!mobile && roleSelect}
              <IconButton color="inherit" onClick={() => { logout(); navigate("/"); }} aria-label="Выйти" title="Выйти">
                <LogoutIcon />
              </IconButton>
            </Stack>
          ) : (
            <Stack direction="row" spacing={1}>
              <Button color="inherit" component={RouterLink} to="/login" sx={{ borderRadius: 999 }}>
                Войти
              </Button>
              {!mobile && (
                <Button variant="contained" component={RouterLink} to="/register" sx={{ borderRadius: 999 }}>
                  Регистрация
                </Button>
              )}
            </Stack>
          )}
        </Toolbar>
      </AppBar>

      <Drawer anchor="left" open={drawer} onClose={() => setDrawer(false)} PaperProps={{ sx: { bgcolor: BRAND.ink, color: "#fff", width: 296 } }}>
        <Box role="presentation">
          <Stack direction="row" spacing={1.5} alignItems="center" sx={{ p: 2.5 }}>
            <BrandMark size={40} />
            <Typography sx={{ fontWeight: 800 }}>
              ФСП <Box component="span" sx={{ color: BRAND.cyan }}>Оренбург</Box>
            </Typography>
          </Stack>
          {me && (
            <Box sx={{ px: 2.5, pb: 2.5 }}>
              <Box component={RouterLink} to="/profile" onClick={() => setDrawer(false)} sx={{ color: "#fff", textDecoration: "none", display: "block" }}>
                <Typography fontWeight={700}>
                  {me.user.last_name} {me.user.first_name}
                </Typography>
                <Typography sx={{ fontFamily: FONT_MONO, fontSize: 12, opacity: 0.65 }}>{me.user.email}</Typography>
                <Typography sx={{ fontSize: 12.5, color: BRAND.cyan, mb: 1.5 }}>Мой профиль →</Typography>
              </Box>
              {me.roles.length > 1 ? <Box>{roleSelect}</Box> : <Chip size="small" label={`Роль: ${ROLE_LABEL[me.active_role]}`} sx={{ bgcolor: ROLE_COLOR[me.active_role], color: "#fff" }} />}
            </Box>
          )}
          <Divider sx={{ borderColor: "rgba(255,255,255,0.1)" }} />
          <List sx={{ p: 1 }}>
            {items.map((i) => (
              <ListItemButton key={i.to + i.label} component={NavLink} to={i.to} end={i.to === "/"} onClick={() => setDrawer(false)} sx={{ borderRadius: 2, "&.active": { bgcolor: "rgba(255,255,255,0.1)" } }}>
                <ListItemText primary={i.label} />
              </ListItemButton>
            ))}
          </List>
          {!me && (
            <Stack sx={{ p: 2.5 }} spacing={1}>
              <Button variant="contained" component={RouterLink} to="/register" onClick={() => setDrawer(false)}>
                Регистрация
              </Button>
            </Stack>
          )}
        </Box>
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1 }}>
        {home ? (
          <Outlet />
        ) : (
          <Container maxWidth="lg" sx={{ py: { xs: 3, md: 5 } }}>
            <Outlet />
          </Container>
        )}
      </Box>

      <Footer />
    </Box>
  );
}
