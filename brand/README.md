# Brand assets

The source of truth for the Unpress identity. Everything that shows a logo —
the Studio interface, the favicon, the default logo of a generated site — is
copied from here at build or install time, never redrawn.

| File | What it is | Use |
|---|---|---|
| `unpress-logo.svg` | the wordmark, `#161616` on transparent | anywhere on a light background |
| `unpress-logo-light.svg` | the same wordmark in white | dark headers, dark UI |
| `unpress-icon.svg` | the mark in a rounded square | favicon, app icon, avatars, anywhere square |

## The v15 branch does not use these

The `version-15` branch of the Builder fork is a different product with its own
identity, and it keeps its own assets. Nothing here belongs on it. An Unpress
logo showing up there means something copied more than it should have.

## Adding a size or a format

Derive it from the SVG, commit it here, and reference it from wherever it is
needed. Do not check in a one-off export that lives next to the code using
it: that is how a product ends up with four slightly different logos.
