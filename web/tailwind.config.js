/** Tailwind preset replicating the MCG platform theme (mcg-sms.austere.biz bundle, Sept 2026).
 *  Colour scales, light/dark tokens and radius match the existing portal so that the
 *  module is visually indistinguishable when mounted inside it. */
import mcgPreset from "./src/theme/mcg-tailwind-preset.js";
export default {
  presets: [mcgPreset],
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}", "../shared/src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
