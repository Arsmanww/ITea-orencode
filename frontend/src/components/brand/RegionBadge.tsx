import { Box, Tooltip } from "@mui/material";

import { BRAND, FONT_MONO } from "../../theme";
import { MAP_HEIGHT, MAP_WIDTH, REGION_SILHOUETTE } from "./regionShapes";

/** Силуэт Оренбургской области и код региона – опознавательный знак в шапке. */
export function RegionBadge() {
  return (
    <Tooltip title="Оренбургская область, 56 регион">
      <Box
        sx={{
          display: { xs: "none", lg: "inline-flex" },
          alignItems: "center",
          gap: 1,
          flexShrink: 0,
          px: 1.25,
          height: 32,
          borderRadius: 999,
          border: "1px solid rgba(255,255,255,0.14)",
          bgcolor: "rgba(255,255,255,0.05)",
        }}
      >
        <Box
          component="svg"
          viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
          aria-hidden
          sx={{ width: 26, height: 26 * (MAP_HEIGHT / MAP_WIDTH), display: "block" }}
        >
          <path d={REGION_SILHOUETTE} fill={BRAND.cyan} fillRule="nonzero" />
        </Box>
        <Box component="span" sx={{ fontFamily: FONT_MONO, fontSize: 12, color: "rgba(255,255,255,0.85)", letterSpacing: "0.02em" }}>
          56
        </Box>
      </Box>
    </Tooltip>
  );
}
