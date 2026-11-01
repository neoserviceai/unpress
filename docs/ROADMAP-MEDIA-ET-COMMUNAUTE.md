# Two things Unpress does not have yet — and what building them costs

Written 2026-08-03, after an audit of both repos. This is a scoping note, not
a plan of record: it says what exists today, factually, and what the gap is.

## 1. A media library — BUILT (2026-08-03)

`unpress_core/media.py` + `MediaLibrary.vue`, reachable from the sidebar. What
follows is the scoping note that produced it, kept because the reasoning still
explains the shape.

**What it does now.** Lists every public image, and for each one the pages it
appears on — walking both `blocks` and `draft_blocks`, because an image only
present in a draft is still in use. Flags the ones used nowhere, the ones that
are the site logo, and the `File` rows whose bytes are gone. Deleting is
refused while a page still points at the image; a dangling row can always be
cleaned up. A second tab inventories the links and names the internal ones that
lead nowhere.

Two things learned building it:

- **"The site's media" is not a folder.** The builder uploads into
  `Home/Builder Uploads`, but the AI image worker writes into the default
  folder. Filtering on the upload folder found zero of a generated site's
  images. It is *every public image*: a private File is an attachment to some
  document, not something the site shows.
- **Thumbnails are not optional.** A generated image is ~2.8 MB; thirty of them
  as grid thumbnails is 60 MB for a screen that shows them 200 px wide.
  `File.make_thumbnail` brings that to ~82 kB each — 34× lighter, generated
  once (1.8 s for thirty, then instant).

Still missing from the original list: picking from the library instead of
re-uploading, and responsive variants.

## 1b. The original scoping

**What exists today.** Nothing that lists images. There is no route, no
sidebar entry, no component that browses what has already been uploaded. Every
image field uploads one file (`ImageUploadInput.vue`, `BackgroundHandler.vue`,
the Theme tab, the chat) into the Frappe `File` doctype under
`Home/Builder Uploads`, and the resulting URL is written straight into the
page's `blocks` JSON. That JSON is the only record of "this image is used on
that page", and it is not indexed.

`Builder Content Asset` looks like a catalogue but is not one: it holds only
what a client dropped into the AI chat, it has no UI, and images uploaded in
the canvas never enter it. `image_matcher.match_and_apply` does produce a
`page / slot / section / asset` report — and throws it away; it is a return
value, never persisted.

WebP conversion **does** exist (`builder/api.py`, on by default). Resizing,
thumbnails, `srcset` and lazy-loading do not.

**Nothing inventories links either** — no internal/external link list, no
broken-link report. `exporter.py` extracts `src`/`href` but only to copy local
assets into a static bundle, and its report is printed, not stored.

**The gap, and what it costs.**

| Piece | Difficulty | Why |
|---|---|---|
| List every uploaded image | small | `File` filtered on `folder = "Home/Builder Uploads"` is already the source of truth; it needs a `createListResource` and a grid |
| Show where each image is used | medium | requires walking every page's `blocks` and indexing image sources. `_walk_blocks_for_placeholders` (generation.py) already knows how to walk blocks recursively — the walk exists, the index does not |
| Pick from the library instead of re-uploading | medium | the grid plus a picker mode in `ImageUploadInput` |
| Delete / find orphans | medium | needs the usage index first, or deleting breaks pages silently |
| Link inventory + broken links | medium | same walk, different attribute; the check itself is an HTTP HEAD per external URL, best queued |
| Responsive variants (`srcset`, thumbnails) | medium | PIL is already a dependency and `save_as_webp` is the place to add it |

The honest summary: the **data is all there**, none of it is **indexed**. The
work is an index and a screen, not new plumbing.

## 2. Plugins — BUILT (2026-08-04), except the community hub

The plugin mechanism exists and is documented in [PLUGINS.md](PLUGINS.md):

- **Level 1** — `Website Plugin` registry, and switching one off does exactly
  three things (hides its Studio entry, refuses its endpoints, 404s its
  routes) while keeping every table. The blog and the WordPress importer are
  the first two.
- **Level 2** — installing and removing a whole Frappe app from a git URL,
  as a background job, System Manager only, with a per-site allowlist and an
  off switch that defaults to off on a hosted tenant.

### What is left, and it is the community half

Deliberately not started (decision 2026-08-04: finish the mechanism first).

| Piece | State | Difficulty |
|---|---|---|
| Metadata on the registry (author, licence, version, homepage) | fields `source` and `version` exist and are unused | **small** |
| A browse screen fed by the hub catalogue | `builder_hub` already serves `get_catalog` / `get_template_bundle` | small to medium |
| A package format (zip) | **does not exist** — everything is a directory tree or JSON over HTTP. This is what makes "download a plugin, edit it, re-upload" impossible | medium; one container would serve plugins, page export and site backup at once |
| Level-1 plugins as data (components/templates in a bundle rather than an app) | the hub carries template bundles already; nothing marks them as plugins | medium — and it is the **lowest-risk** kind, so it should be the first the hub carries |
| Self-service publishing from the Studio | endpoint exists on the v15 branch, no UI, keys handed out by hand | medium |
| Any audit of level-2 apps | none. Installing one is trusting its author with the server | **large**, and the part with real security weight |

The order that still makes sense: metadata → zip container → level-1 bundles
through it → audit, before ever letting the hub hand out level-2 apps.

## 2b. The original scoping

The plugin standard is specified in [PLUGIN-SPEC.md](PLUGIN-SPEC.md) — two
levels (data-only components/templates, and full Frappe apps), a manifest, a
curated store. **None of it is code yet**: `store/index.json` exists and
nothing reads it.

**What is already built, and is more than it looks.** The template hub is real
and working, in both directions:

- a hub server (a separate Frappe app, `builder_hub`) exposes a guest
  `get_catalog` / `get_template_bundle`, with eight template groups published;
- the Studio consumes it (`create_page_from_template`, `import_template_group`)
  — components, variables, client scripts and fonts travel with the bundle;
- publishing exists too — assets uploaded first, URLs rewritten, the bundle
  landing in a **staging** folder (`Hub Inbox — <group>`) for a human to
  depersonalise, then `promote_to_catalog`. There is a `Hub Publisher` role and
  protected groups.

So the distribution channel the plugin spec assumes ("the store wraps the
template hub") already exists. Two caveats: the publishing side lives on the
v15 branches and is **not on the `unpress` branch**, and there is no UI for it
— publishing is an API call today.

**What the community ask actually needs, on top of that:**

| Ask | State | Difficulty |
|---|---|---|
| A hub of ready-made designs, community-contributed | the catalogue, the bundles and the staging→promote moderation exist; author, licence, versioning and search do not | **small to medium** — mostly metadata and a browse UI |
| Self-service publishing from the Studio | endpoint exists (wrong branch), no UI, keys handed out by hand | medium — port + a dialog + real authentication |
| Editable starter plugin zips | **there is no zip format at all** in either repo. Everything is either a directory tree on disk or JSON POSTed over HTTP | medium — one container format would serve plugins, page export and site backup at once |
| A plugin hub (level 1: components/templates) | it *is* the template hub with a different label | small |
| A plugin hub (level 2: Frappe apps) | nothing: no `Plugin` doctype, no installer, no audit pipeline | **large** — and it is the part with real security weight, since a Frappe app has full server access |
| Extension points for a plugin to hook into | exactly one exists: `unpress_ai_prompt_context`. `builder/hooks.py` exposes nothing custom | medium — and worth designing before plugins exist, not after |

**One loose thread worth pulling.** `generation.py` queries a doctype called
`Builder Shortcode` with a `source_app` field — and that doctype exists nowhere
in either repo. It reads like an extension contract someone started: a host app
declares shortcodes, the AI learns to use them. Either finish it and document
it as an extension point, or delete the query.

### The order that makes sense

1. **Metadata on the existing hub** (author, licence, version, search). Turns a
   template catalogue into a community one for very little code.
2. **A zip container**, once, used by plugin packages, page export and site
   backup. Not having it is what makes "download a plugin, edit it, re-upload"
   impossible today.
3. **Level-1 plugins** (components/templates as data) through that container —
   this covers most of what a brochure site calls a "WordPress plugin", with
   near-zero security surface.
4. **Extension points** in `builder/hooks.py`, designed deliberately.
5. **Level-2 apps** last, with the audit pipeline, because that is where an
   install can hand a stranger the server.
