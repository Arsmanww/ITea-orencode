import { alpha, createTheme } from "@mui/material/styles";

/**
 * Дизайн-токены ФСП Оренбург (подробности – docs/design-system.md).
 * Светлая база для рабочих экранов, тёмные «обложки» (hero, футер) для техно-акцента.
 * Шаг сетки – 8 px (theme.spacing(1) = 8).
 */
export const BRAND = {
  blue: "#2B59FF", // электрик: основной акцент, кнопки, ссылки
  blueDark: "#1B3BD1",
  cyan: "#22D3EE", // техно-акцент: фокус, живые индикаторы, градиенты
  lime: "#B8F34A", // «live»: открытая регистрация, пульсирующая точка
  red: "#E5303A", // фирменный красный ФСП: только точечный акцент
  ink: "#0A0F1F", // тёмный фон hero и футера
  inkSoft: "#111936",
  panel: "#18224A",
  bg: "#F5F7FC",
  border: "#E1E7F3",
  text: "#0E1630",
  muted: "#5A6788",
} as const;

export const FONT_SANS = '"Inter Variable", "Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif';
/** Моноширинный: теги, даты, таймеры, счётчики, очки. */
export const FONT_MONO = '"JetBrains Mono Variable", ui-monospace, "Cascadia Code", Consolas, monospace';

export const SHADOW = {
  card: "0 1px 2px rgba(14, 22, 48, 0.04), 0 8px 24px -12px rgba(14, 22, 48, 0.12)",
  glow: "0 8px 24px -8px rgba(43, 89, 255, 0.55)",
};

export const theme = createTheme({
  palette: {
    primary: { main: BRAND.blue, dark: BRAND.blueDark, contrastText: "#fff" },
    secondary: { main: BRAND.red, contrastText: "#fff" },
    info: { main: BRAND.cyan },
    background: { default: BRAND.bg, paper: "#fff" },
    text: { primary: BRAND.text, secondary: BRAND.muted },
    divider: BRAND.border,
  },
  shape: { borderRadius: 12 },
  typography: {
    fontFamily: FONT_SANS,
    h1: { fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 1.08 },
    h2: { fontWeight: 800, letterSpacing: "-0.025em", lineHeight: 1.12 },
    h3: { fontWeight: 750, letterSpacing: "-0.02em" },
    h4: { fontWeight: 750, letterSpacing: "-0.02em" },
    h5: { fontWeight: 700, letterSpacing: "-0.015em" },
    h6: { fontWeight: 700, letterSpacing: "-0.01em" },
    button: { textTransform: "none", fontWeight: 600, letterSpacing: 0 },
    overline: { fontFamily: FONT_MONO, fontWeight: 600, letterSpacing: "0.08em", fontSize: "0.72rem" },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { fontFeatureSettings: '"cv11", "ss03"', WebkitFontSmoothing: "antialiased", MozOsxFontSmoothing: "grayscale" },
        "::selection": { background: alpha(BRAND.blue, 0.22) },
        "a:focus-visible, button:focus-visible, [role='tab']:focus-visible, [role='combobox']:focus-visible": {
          outline: `2px solid ${BRAND.cyan}`,
          outlineOffset: 2,
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 10, minHeight: 40, transition: "transform .15s ease, box-shadow .15s ease, background-color .15s ease" },
        sizeLarge: { minHeight: 48, paddingInline: 24 },
        containedPrimary: { boxShadow: SHADOW.glow, "&:hover": { boxShadow: "0 10px 28px -8px rgba(43,89,255,0.7)", transform: "translateY(-1px)" } },
      },
    },
    MuiPaper: { styleOverrides: { root: { backgroundImage: "none" } } },
    MuiCard: {
      defaultProps: { variant: "outlined" },
      // overflow: hidden – без него подсветка CardActionArea при наведении/клике рисуется прямым
      // прямоугольником и торчит острыми углами за скруглённой рамкой карточки.
      styleOverrides: { root: { borderColor: BRAND.border, borderRadius: 16, boxShadow: "0 1px 2px rgba(14,22,48,0.03)", overflow: "hidden" } },
    },
    MuiChip: { styleOverrides: { root: { fontWeight: 600, borderRadius: 999 } } },
    MuiTableCell: {
      styleOverrides: {
        head: { fontWeight: 700, fontSize: 12, letterSpacing: "0.02em", backgroundColor: "#EEF2FC", color: BRAND.text, whiteSpace: "nowrap" },
        root: { borderColor: BRAND.border },
      },
    },
    MuiTextField: { defaultProps: { size: "small", fullWidth: true } },
    MuiOutlinedInput: { styleOverrides: { root: { borderRadius: 10, backgroundColor: "#fff" } } },
    MuiTabs: { styleOverrides: { indicator: { height: 3, borderRadius: "3px 3px 0 0" } } },
    MuiTab: { styleOverrides: { root: { textTransform: "none", fontWeight: 600, minHeight: 48 } } },
    MuiAlert: { styleOverrides: { root: { borderRadius: 12 } } },
    MuiDialog: { styleOverrides: { paper: { borderRadius: 20 } } },
  },
});
