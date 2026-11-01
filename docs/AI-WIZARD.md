# The AI wizard — what it reads, and where it lives

The Studio's "Create with AI" wizard is a modal inside the Builder SPA
(`AIChatModal.vue`). There is no desk page: the Frappe desk is not part of the
product, and every desk route redirects to `/builder`.

## What the client can hand it

**One button.** A client does not think "this one is a logo upload, that one is
a content upload" — they drop what they have. `chat_attach_files` takes every
file and sorts it:

| Bucket | How it is chosen | What happens to it |
|---|---|---|
| **Logo** | filename hint (`logo`, `marque`, `wordmark`…), an SVG, or a small image on transparency — and only while the site has no logo. The wizard's `logo` step forces it. | Written to the site chrome (see below) **and read for its colours** — the two dominant non-neutral colours become `primary_color` / `secondary_color` unless the user already chose them. |
| **References** | any image while the wizard sits on its `inspiration` step — the question on screen is what disambiguates | Becomes a `Builder Site Inspiration`; its palette and style keywords are appended to the generation prompt. |
| **Photos & documents** | everything else | Becomes `Builder Content Asset` rows. Photos are placed in the generated pages by `image_matcher.match_and_apply`; documents are read and their text is injected into the page prompt by `get_content_context`. |

The point of the third one is that the site says what the business actually
says, in its own words, illustrated with its own photos — instead of generic
copy over stock images.

`chat_upload_logo` and `chat_upload_inspiration` still exist and still work —
they are the same code, reached one file at a time.

### The logo has one address

`unpress_core/branding.py` writes every logo to **`/files/logo-default.png`**,
whatever the uploaded file was called, and points the chrome
(`Website Header Footer Config`, or a `Website Header Footer Variant` when a
profile is targeted) at that path.

This is not a detail. A managed fleet references that one path on every
instance, so replacing a logo has to replace the **bytes**, never mint a new
URL. The rendered `<img>` carries `?v=<content hash>` (`_versioned` in the
chrome doctype) so a browser still sees the change.

Both doors lead there: the Theme tab's uploader calls `branding.set_logo`, the
chat calls `branding.apply_logo`. A logo dropped in the conversation *is* the
site's logo — anything else means a client uploads their brand to the assistant
and their header keeps showing someone else's.

### Why the logo drives the palette

A client's brand lives in their logo. Asking them to name a palette when they
just handed us the answer is busy-work, and the model writes better copy when
the site already looks like the brand.

Near-white, near-black and grey are discarded (`_is_neutral`): most logos sit
on a white background, so the dominant colour *by area* would otherwise be
`#ffffff`. A logo that cannot be read is never a reason to reject the logo.

### Degradation, on purpose

`get_content_context` accepts documents whose LLM pass **failed**, as long as
the text extraction succeeded — extraction happens before the model call, so a
model hiccup (or a self-host with no vision model at all) must not silently
drop what the client wrote.

Likewise image generation starts on its own once the pages exist, if and only
if a backend is configured (`_image_backend_available`). It used to wait for a
button, so self-serve sites never got real images.

## The design system: decided once, never restated

What separates a professional site from a generated one is that its pages
agree with each other. Colours and fonts were already a token layer; corners,
elevation, motion and hover were not — every block carried its own copy, and
copies drift.

Four settings in the Theme tab now drive the whole site:

| Setting | Values | Becomes |
|---|---|---|
| Corners | Sharp / Subtle / Rounded / Soft | `--radius`, `--radius-sm`, `--radius-lg` |
| Elevation | None / Soft / Strong | `--shadow-sm`, `--shadow`, `--shadow-lg` |
| Button hover | None / Darken / Lift / Grow | the single `.u-btn:hover` rule |
| Motion | None / Calm / Brisk | `--transition` |

They are consumed by a small class layer — `.u-btn` (`--primary`,
`--secondary`, `--outline`, `--ghost`), `.u-card` (`--raised`, `--flat`),
`.u-media`, `.u-input` — and by the header and footer, so the CTA in the bar
has the same corners as the CTAs in the pages.

**The generator asks for a role instead of restating the system.** The page
prompt gives it the table above and one rule: put `u-btn` in `classes` and do
not set borderRadius, boxShadow, transition or any hover on that block.
Colours stay per-block; only the *shape* is fixed. Measured on a generated
pricing page: 94 blocks, 8 carrying a role, **0 restating a system property**.

The brief decides the tokens once (`radius_style`, `shadow_style`,
`button_hover`, `motion_style` in `BRIEF_CHROME_FIELDS`), and they are written
to the site config — not repeated into the pages.

None of this locks anything: a user can still override any property in the
editor. The point is that the default is coherent.

## The site chrome the AI picks

The header and footer are **prefabs**, not a pile of switches to combine. The
design brief chooses one of each, and every site type has a deliberate default
so a generation never lands on whatever the doctype happened to hold.

| Header style | What it is | When |
|---|---|---|
| `Classic` | full-width bar | the safe default |
| `Floating` | detached rounded bar above the content, with a shadow | modern / premium |
| `Transparent` | blends into the hero, turns solid on scroll | **only** when the first section is a full-bleed image or a deep colour |
| `Minimal` | no background, no border | editorial |

`header_style` is orthogonal to `header_layout`, which only decides where the
logo goes: any style works with any layout.

The transparent one carries its own scrim (`::before`, a top-down gradient).
The style is site-wide but only the home page is guaranteed to open on a hero,
so without it white links would vanish on a pale interior page.

Footers: `Minimal` (one line), `Standard` (columns), `Extended` (columns +
newsletter), `Centered` (logo, one row of links, social underneath — for sites
with few links).

## Why the body of a generated page must carry `originalElement`

The editor recognises its root block by `originalElement === "body"`. The
generator wrote only `element`, so on every generated page the body was an
ordinary block: the resize handle appeared on it, one drag wrote a fixed pixel
width into `baseStyles`, and `getEditorStyles()`'s `width: inherit` guard —
which exists precisely to stop that — never applied. The page then stopped
filling the canvas and overflowed the preview.

Both sides are fixed (the generator stamps it, `isRoot()` also accepts
`element`), and `patches/repair_generated_page_roots` repairs pages already
written.

## Codex and images

The Codex provider drives the CLI, and three things had to be true before it
could look at a client's photo — each of which failed in a way that looked like
the model simply had nothing to say:

- **`-i FILE`.** `images=` was accepted and dropped. The model was asked about
  a picture it had never received.
- **A strict output schema.** The structured-output endpoint requires
  `additionalProperties: false` and every property listed in `required`.
  Pydantic emits neither, so any `generate_structured` call with a pydantic
  model came back HTTP 400 — surfaced as "Codex returned no answer".
  `_strict_schema` normalises it; defaults still apply on our side.
- **An absolute path.** `"/files/x.png"` is a site URL that *looks* like an
  absolute path, and frappe answers relative to the sites directory while the
  CLI runs in a scratch dir of ours. Every image was silently dropped.

## Why a slot with no description used to get a stock landscape

Image slots are filled from whatever text describes them: an `<img>`'s `alt`,
or the `text=` parameter of the `placehold.co` background URL. A hero
background usually carries **neither** — and the fallback in
`_build_image_prompt` asked, literally, for *"beautiful landscape
photography"*. That is how a yoga studio ended up with a mountain lake above
the fold while every described slot on the same site got a real studio
interior.

The fallback now describes the **business** (`_image_subject`: the session's
site description, else its name, cut on a clean break). Described slots are
untouched — they were never the problem.

## The assistant's name

`get_assistant_name()` — **Unpress AI** by default, overridable per site with
`unpress_ai_name` in `site_config.json`. Never hardcode it in a prompt or a
greeting: a fork or a host application must be able to put its own name in
front of the user without patching us.

## Extending the prompt without us knowing you exist

`unpress_core` never imports a host application. A host that wants to teach the
model about its own shortcodes or vocabulary declares itself:

```python
# in the host app's hooks.py
unpress_ai_prompt_context = ["my_app.ai.contribute"]

# my_app/ai.py
def contribute(site_type: str | None = None) -> str:
    return "## MY SHORTCODES\n..."
```

Each contributor returns a markdown block (or `""` to stay out of it) and they
are concatenated into the prompt. A contributor taking no argument works too.
The dotted path has to live inside an **installed app** — `frappe.get_attr`
refuses anything else — so a stale entry can only ever log a warning.

## Testing it

```bash
cd sites
../env/bin/python ../apps/unpress_core/scripts/smoke-ai-chat.py <site>
```

Eight read-only checks; detects whether it is running against `unpress_core` or
a bench that carries the same engine inside the `builder` app. It deliberately never calls `start_session()` —
that would flip every `Active` session older than 24 h to `Abandoned`.

After a manual UI test, clean up what it left behind. An upload writes to
`File`, `Builder Content Asset` **and** `Builder Site Inspiration` at once;
miss one and a test photo stays in a client's content library, where the
generator will put it on their site:

```bash
../env/bin/python ../apps/unpress_core/scripts/clean-test-artifacts.py <site> --delete
```
