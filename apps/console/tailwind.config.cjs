// CONTENT COVERS BOTH TREES. The classes live in our ui/ kit's components as much as in this
// app's own, and a content path that lists only src/ ships a stylesheet missing every class the
// library uses — which renders as an unstyled page rather than as an error.
module.exports = {
  presets: [require('../../ui/packages/ui/tailwind-preset.cjs')],
  content: [
    './index.html',
    './src/**/*.{ts,tsx}',
    '../../ui/packages/ui/src/**/*.{ts,tsx}',
  ],
};
