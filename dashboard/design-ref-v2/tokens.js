// ZenOS · Zen Ink design tokens (v2 — B-only, deepened)
window.ZEN_INK = {
  name: "Zen Ink",
  tagline: "墨白禪意 · Sumi-e",
  modes: {
    light: {
      // 宣紙 → 墨 gradient of neutrals
      paper:       "#F4EFE4",   // outer page (slightly warmer than surface)
      paperWarm:   "#EFE9DB",   // elevated tint for section bands
      surface:     "#FBF8F1",   // cards
      surfaceHi:   "#FFFFFF",   // inset / active
      ink:         "#141210",   // 墨
      inkSoft:     "#3A342C",
      inkMuted:    "#5E574B",
      inkFaint:    "#8A8373",
      inkHair:     "rgba(20, 18, 16, 0.10)",   // hairline
      inkHairBold: "rgba(20, 18, 16, 0.22)",
      vermillion:  "#B63A2C",   // 朱砂 · accent
      vermSoft:    "rgba(182, 58, 44, 0.08)",
      vermLine:    "rgba(182, 58, 44, 0.30)",
      seal:        "#9C2E1F",   // deeper seal red for chops
      jade:        "#5F7A45",   // success — 青竹
      ocher:       "#B48432",   // warn — 赭石
    },
    dark: {
      paper:       "#0D0C0A",
      paperWarm:   "#141210",
      surface:     "#17140F",
      surfaceHi:   "#1F1B14",
      ink:         "#ECE5D3",
      inkSoft:     "#C8C1B0",
      inkMuted:    "#928B7D",
      inkFaint:    "#605A4F",
      inkHair:     "rgba(236, 229, 211, 0.10)",
      inkHairBold: "rgba(236, 229, 211, 0.20)",
      vermillion:  "#E8614E",
      vermSoft:    "rgba(232, 97, 78, 0.12)",
      vermLine:    "rgba(232, 97, 78, 0.32)",
      seal:        "#D24B3E",
      jade:        "#A8C087",
      ocher:       "#D9A35A",
    },
  },
  // Type pairing: serif for heads (reads as eastern/editorial), sans for body.
  fontHead: '"Noto Serif TC", "Songti TC", "Source Han Serif TC", "Times New Roman", serif',
  fontBody: '"Helvetica Neue", Helvetica, "Noto Sans TC", "PingFang TC", system-ui, sans-serif',
  fontMono: 'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace',
  radius: 2,
  // 24 solar terms — for seasonal timestamping
  solarTerm: { name: "穀雨", en: "Grain Rain", line: "雨生百穀，萬物萌發。", ord: 6 },
};

window.useInk = (mode) => {
  const t = window.ZEN_INK;
  const c = t.modes[mode] || t.modes.light;
  return { ...t, mode, c };
};
