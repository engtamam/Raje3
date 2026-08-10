// CONTENT COVERS BOTH TREES. The classes live in platform/ui's components as much as in ours, and
// a content path that lists only src/ ships a stylesheet missing every class the library uses —
// which renders as an unstyled page rather than as an error.
module.exports = {
  presets: [require('../../platform/ui/packages/ui/tailwind-preset.cjs')],
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
    '../../platform/ui/packages/ui/src/**/*.{ts,tsx}',
  ],
};
