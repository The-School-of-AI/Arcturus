/* Arcturus theme — aligned with platform-frontend (tech blue / deep navy) */
const tintColorLight = 'hsl(221, 83%, 53%)'; // primary blue
const tintColorDark = 'hsl(217, 91%, 60%)';  // electric blue

export default {
  light: {
    text: 'hsl(222, 47%, 11%)',
    background: 'hsl(210, 40%, 98%)',
    tint: tintColorLight,
    tabIconDefault: 'hsl(215, 16%, 47%)',
    tabIconSelected: tintColorLight,
  },
  dark: {
    text: 'hsl(210, 40%, 98%)',
    background: 'hsl(222, 47%, 11%)',
    tint: tintColorDark,
    tabIconDefault: 'hsl(215, 20%, 65%)',
    tabIconSelected: tintColorDark,
  },
};
