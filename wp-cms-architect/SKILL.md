---
name: wp-cms-architect
description: "WordPress theme and plugin work under strict rules: atomic refactoring that leaves no dead or commented-out code, modular template parts, SCSS variables with tree-shaking, ACF as the content engine, no hardcoded values, proper escaping. Includes an audit and purge mode that removes obsolete ACF references, dead SCSS selectors, unused JS handlers and stale enqueue registrations. Covers RTL and Hebrew themes and plugin-agnostic multilingual work. It is also the Standards source that review-two-axis reads on WordPress work."
---

# WordPress CMS Architect — Full Development Protocol (v2.4)

This document defines the mandatory technical standards, architectural patterns,
and development workflows for WordPress theme and plugin development.

---

## 1. Core Philosophy: Zero Hardcoding & Atomic Refactoring

* **The CMS Rule:** WordPress must function as a true Content Management System.
  Any data that might change must be editable via the WordPress Admin.
* **Atomic Refactoring:** Every rewrite must be "destructive" to the old code.
  If a logic block or style is replaced, the old version must be purged
  immediately. **No "zombie code" (commented-out blocks) is allowed to remain.**
* **Modular Architecture:** Code must be reusable and single-purpose. Extract
  logic into helpers and UI into components.

## 2. Advanced Custom Fields (ACF) Protocol

### Field Creation (Strict Manual Mode)

By default, you are **PROHIBITED** from generating PHP or JSON files for field
registration.

* **Requirement:** Provide a clear specification table for the user to manually
  create fields in the WP Admin.
* **Exception:** Generate PHP registration code **ONLY** if the user explicitly
  asks: *"Generate PHP code for these fields."*

### Code Implementation & Sync

* **Conditional Checks:** Always check if a field has data before outputting
  HTML: `if ( get_field('name') )`.
* **ACF Sync:** When refactoring, if a field is removed from the specification
  table, you **MUST** delete all corresponding `get_field()` or `have_rows()`
  calls from the PHP templates.

## 3. Theme Architecture & File Structure

### Clean `functions.php`

The `functions.php` file serves only as a bootstrap. It must not contain
business logic. Use `require_once` to load modules from `/lib/`.

### Directory Structure

* `lib/theme-setup.php`: `add_theme_support`, navigation menus, custom image sizes.
* `lib/enqueue.php`: All script and style registrations.
* `lib/helpers.php`: Reusable utility functions.
* `template-parts/components/`: Reusable UI blocks (Hero, Cards, Sliders).

## 4. Styling (SCSS) & Visual Integrity

### Strict Variable Integration

* **No Hardcoding:** Do not use raw hex codes, RGB values, or pixel sizes for
  colors, spacing, or typography.
* **Variable Mapping:** Analyze the project's `_variables.scss` first. If the
  project has `$brand-primary`, use it.

### SCSS Tree Shaking

* **Class Audit:** During any redesign, cross-reference the SCSS partial with
  the HTML/PHP output. If a class or variable is defined in SCSS but not used
  in the markup, you **MUST** delete it.

###  ACF Gutenberg Block Registration

* **Block Mode:** When registering custom ACF blocks, you MUST prevent fields from being trapped in the right sidebar. 
- Always set the ACF block `mode` to `edit` (or `auto`) by default.
- If registering via `block.json`, include:
  `"acf": { "mode": "edit", "renderTemplate": "..." }`
- If registering via PHP (`acf_register_block_type`), include:
  `'mode' => 'edit'`

* **`mode: edit` is not always enough — verify in the REAL editor.** ACF resolves
  the displayed mode at runtime, and an ACF-version ↔ WP-version mismatch can
  force blocks into `preview` regardless of config (fields go read-only / to the
  inspector sidebar). Symptoms and mitigations seen in the field:
  - The block's `mode` lives in the block **instance attributes**, not just the
    block type. ACF can reset it to `preview` on insert.
  - In WP's **iframed** block editor (`apiVersion: 3` on all blocks), ACF may
    misdetect the canvas as a non-desktop preview and force `preview`. Omitting
    `apiVersion` (so the canvas is not iframed) sidesteps this; also add
    `"supports": { "mode": false }` to lock the toggle off.
  - If config alone won't hold it, a tiny `enqueue_block_editor_assets` script
    that forces `mode: 'edit'` on the theme's blocks is an accepted bridge until
    the plugin ships compatibility — comment it as removable.
* **VERIFY before claiming a fix.** Do NOT declare an editor/block fix working
  from reasoning or the rendered front end alone. Open the actual block editor
  and confirm (login + headless Chrome/CDP DevTools if needed, or have the user
  check). Editor state is JS- and version-dependent; static analysis lies.
* **When stuck, check versions and a known-good reference FIRST.** Read the
  exact WP + ACF (or plugin) versions early, and look for a sibling site/theme
  on the same server that already does it — copy the working pattern instead of
  guessing repeatedly.

## 5. Security & Data Handling

* **Escape Everything on Output:** `esc_html()`, `esc_attr()`, `esc_url()`,
  `wp_kses_post()`.
* **Sanitize All Input:** `sanitize_text_field()`, `absint()`, `sanitize_email()`.

### Nonces and Capabilities

Escaping and sanitizing cover the *data*. These cover the *actor*: did this
request really come from that user, and is that user allowed to do this? Both are
required on every state-changing request.

* **Nonce on every form and AJAX call.** `wp_nonce_field( 'action', 'name' )` in
  the form, then `check_admin_referer()` or `wp_verify_nonce()` before acting on
  it. A nonce that is created and never verified is decoration.
* **Capability check on every privileged action**: `current_user_can( 'edit_posts' )`.
  A nonce proves intent, not permission: a logged-in subscriber can hold a
  perfectly valid nonce.
* **REST endpoints always set `permission_callback`.** Write
  `'permission_callback' => '__return_true'` only when the endpoint is genuinely
  public, and say so in a comment beside it.
* **AJAX hooks come in pairs for a reason.** `wp_ajax_{action}` serves logged-in
  users, `wp_ajax_nopriv_{action}` serves anonymous ones. Registering both when
  only the first was meant is how an admin action becomes a public one.

## 6. Performance & Standard Queries

* **WP_Query:** Never use `query_posts()`. Always follow custom queries with
  `wp_reset_postdata()`.
* **Optimization:** Use `'no_found_rows' => true` when pagination is not required.
* **Images:** Always use `wp_get_attachment_image()` for responsive `srcset`.

### Image Sizes and LCP

* **Declare custom sizes in `lib/theme-setup.php`**, next to the other theme
  setup: `add_image_size( 'card-thumb', 400, 250, true )`. A template that asks
  for a size nobody declared silently falls back to full size.
* **The LCP image gets `fetchpriority="high"`.** That is usually the hero, and it
  is the single cheapest Core Web Vitals win in a theme.
* **`loading="lazy"` belongs below the fold only.** WordPress adds it by default,
  which is right for most images and wrong for the LCP one: lazy-loading the hero
  delays the very metric being measured. Pass
  `array( 'loading' => 'eager', 'fetchpriority' => 'high' )` to
  `wp_get_attachment_image()` for it.

## 7. Audit & Purge (The "Garbage Collector" Mode)

When asked to "Audit and Purge" or "Clean up," you must perform the following:

* **ACF Audit:** Compare PHP template logic against the latest ACF Spec Table.
  Remove any code referencing obsolete fields.
* **CSS/SCSS Purge:** Delete all SCSS selectors that do not have a matching
  class in the template-part.
* **JS Cleanup:** Identify and remove event listeners or functions tied to DOM
  elements that have been removed during the redesign.
* **Dependency Check:** In `lib/enqueue.php`, remove registrations for scripts
  or styles that are no longer used.

## 8. Developer Checklist

1. [ ] Are all obsolete SCSS classes and PHP logic purged?
2. [ ] Are all strings wrapped in i18n functions (`__()`, `_e()`)?
3. [ ] Does the HTML satisfy basic A11y standards (ARIA, semantic tags)?
4. [ ] Is all output properly escaped?
5. [ ] Are ACF fields checked for existence before rendering?
6. [ ] Does every state-changing request verify both a nonce and a capability?
7. [ ] Do RTL styles load through `wp_style_add_data`, with logical properties
   carrying the shared stylesheet?
8. [ ] Is every ACF field's translation behaviour recorded in the spec table?
9. [ ] Does the output meet IS 5568? See `israeli-accessibility-compliance`.

## 9. RTL, Hebrew, and Multilingual

Added in v2.4. Applies to every project whose front end is served in Hebrew,
Arabic or any RTL language, and to every project served in more than one language.

### RTL is a WordPress mechanism, not only a CSS one

* **Ship RTL styles through WordPress rather than a duplicated stylesheet.**
  `wp_style_add_data( $handle, 'rtl', 'replace' )` makes WordPress load
  `style-rtl.css` in place of `style.css` whenever `is_rtl()` is true. Use
  `replace` when the RTL file is complete, and the default (append) when it
  carries only overrides.
* **Branch in PHP with `is_rtl()`**, not by reading the locale string. It stays
  correct when a translation plugin switches language mid-request.
* **Let logical properties carry the shared stylesheet**: `margin-inline-start`,
  `padding-inline-end`, `inset-inline`. One stylesheet then serves both
  directions and the RTL file shrinks to typography plus the few genuinely
  mirrored elements. The general web guidance is `hebrew-rtl-best-practices`;
  this section is the WordPress half of it.
* **Mirror what is directional, keep what is not.** Arrows, chevrons and progress
  indicators mirror. Logos, play buttons and photographs stay as they are.
* **Give the editor the same direction as the front end**:
  `add_theme_support( 'editor-styles' )` with an RTL editor stylesheet, so what
  the client sees while editing matches what ships.

### Multilingual, deliberately plugin-agnostic

The theme must not know which translation plugin is installed. A project can
arrive on any of them, or on multisite, or on hand-rolled routing, and it should
survive being moved between them.

* **Templates never call a plugin's functions directly.** Wrap every language
  question in a helper in `lib/helpers.php`: `theme_current_lang()`,
  `theme_lang_switcher()`, `theme_translated_id()`. The plugin-specific branch
  lives in that one file, so swapping plugins touches one file instead of forty
  templates.
* **Every user-visible string goes through i18n** (`__()`, `esc_html__()`) with
  the theme's text domain, whatever the plugin does with the rest of the site.
* **Assume the language can change per request.** Compute language-dependent
  values at render time; anything cached at `init` may belong to the wrong
  language.
* **Each ACF field carries a translation decision.** For every field group,
  record in the ACF spec table whether the field is translated per language or
  shared across all of them. This is the most common multilingual bug in an ACF
  theme, and it stays invisible until real content is entered.
* **One source of hreflang, not two.** For a site served in Hebrew and English,
  either the theme emits hreflang or the plugin does. Two sources produce
  conflicting tags. `seo-hreflang` covers what correct output looks like.

### Accessibility is a legal requirement in Israel

Israeli sites must meet IS 5568. Treat it as a spec requirement stated up front
rather than a review finding: `israeli-accessibility-compliance` holds the law,
who is exempt, the coordinator role, and the RTL ARIA patterns.
