---
name: image-prompt-crafting
description: "Craft high-quality prompts for external image generators for conceptual illustrations, graphical abstracts, and cover art. Triggers: image generation prompt, DALL-E prompt, Midjourney prompt, graphical abstract, journal cover art, illustrate this concept. Never used for data or results figures."
---

# Image Prompt Crafting

Convert a figure intent into a precise, generator-ready prompt for an external image model, plus the disclosure text and policy checks the manuscript will need.

## Purpose and Hard Boundary

This skill covers **conceptual illustrations, graphical abstracts, schematic metaphors, and journal cover art only**. It never produces prompts for:

- data plots or results figures of any kind
- charts, or anything with axes, error bars, tick marks, or plotted quantities
- architecture diagrams that carry measured numbers (layer sizes, throughput, accuracy)
- tables rendered as images

Those route to the deterministic tools instead:

| Request | Route to |
|---------|----------|
| Plots, charts, results figures | **visualization** |
| Schematics, pipelines, architectures | **tikz-diagrams** |
| Neural network diagrams | **plotneuralnet** |
| Tabular content | **latex-tables** |

If the user asks for an image-generator prompt for a data figure, **refuse and redirect** to the matching skill above. Explain why: generated imagery cannot represent real measurements. A diffusion model paints plausible-looking bars and curves; it does not plot the user's data, and presenting its output as results would fabricate data.

### Borderline cases

- "Illustrate our pipeline" with no numbers: allowed here as a schematic metaphor, but offer tikz-diagrams first; a TikZ schematic is editable, compiles into the manuscript, and needs no AI disclosure.
- "A brain with our accuracy numbers floating around it": refuse the numbers, offer the brain. Generate the illustration without any figures or text, then overlay real, verified numbers in the LaTeX figure environment if the user still wants them.
- "Make our scatter plot prettier": that is a data figure; route to visualization.
- "Cover art inspired by our results": allowed, as long as the image evokes the finding without depicting plotted quantities.

## Workflow

1. **Classify the intent.** Apply the hard boundary above first. Conceptual illustration, graphical abstract, metaphor, or cover art proceeds; anything data-bearing is refused and redirected.
2. **Gather context.** Ask for or infer:
   - Subject: what concept, process, or finding the image should evoke (evoke, not report)
   - Audience: specialist readers, broad journal readership, or the public
   - Target generator: ChatGPT/DALL-E, Gemini/Imagen, or Midjourney (dialects below)
   - Journal context: a target journal implies size, aspect, and policy constraints. Check `manuscript/config.yaml` for the journal name, then look up its graphical abstract or cover specs (dimensions, file type, whether AI imagery is permitted). If no journal is set yet, default to a 16:9 graphical abstract and flag the specs as unverified.
   - Placement: graphical abstract slot, cover submission, or an in-text conceptual figure. Placement changes both the aspect ratio and which policy applies.
3. **Draft 2-3 prompt variants** in the target generator's dialect, differing in style or composition so the user can pick a direction rather than iterate blind.
4. **Emit the caption disclosure text and a policy checklist** (see Disclosure and Policy below). The prompt is not the deliverable; the prompt plus disclosure plus checklist is.

### Prompt package format

Deliver each variant in this structure:

```
Variant N: [short style label, e.g. "flat vector, cool palette"]
  Generator:  ChatGPT/DALL-E | Gemini/Imagen | Midjourney
  Prompt:     <the full prompt text>
  Aspect:     16:9 graphical abstract | portrait cover (per journal spec)
  Palette:    <preset name from references/figure-styles.md>
  Post-work:  labels to overlay (TikZ/Inkscape), cropping, format conversion
  Alt text:   <one line describing the concept the image depicts, shared
               across style variants; see Alt Text below>
  Disclosure: "Illustration generated with <tool> on <date>; no experimental
               data are depicted."
```

## Generator Dialects

Each generator rewards a different prompt shape. The worked examples below all target the same subject: a graphical abstract for a self-supervised ECG representation-learning paper (synthetic, for demonstration).

### ChatGPT / DALL-E

Conversational instructions work best. State composition and layout explicitly, then iterate by describing corrections in follow-up messages ("move the heart to the left third", "remove the text labels").

> Create a wide graphical abstract illustration for a machine learning paper. Left third: a stylized human heart emitting a flowing ECG-like waveform, rendered as a smooth abstract ribbon, not a real trace. Center: the ribbon passes through a translucent geometric prism suggesting a neural encoder, splitting into several parallel colored strands. Right third: the strands settle into an orderly constellation of glowing points, suggesting a learned embedding space. Flat vector style, clean white background, cool blue and teal palette with one warm coral accent. No text, no numbers, no axes, no grid lines anywhere in the image.

Iterate conversationally: "keep everything, but make the prism smaller and move the constellation closer to the right edge". DALL-E via ChatGPT holds context across turns, so describe corrections relative to the previous image instead of rewriting the whole prompt.

### Gemini / Imagen

Dense descriptive prose in a single block, with the photographic or illustrative parameters stated up front rather than negotiated later.

> Flat vector scientific illustration, wide banner format, white background, soft studio lighting, high detail. A stylized anatomical heart on the left releases a continuous abstract ribbon evoking a heartbeat rhythm; the ribbon flows rightward through a faceted glass prism representing a self-supervised encoder and refracts into parallel teal, blue, and coral strands; the strands converge into a neat cluster of luminous dots on the right, evoking an organized representation space. Left-to-right reading order, generous negative space, editorial magazine quality. Absolutely no text, numerals, axes, gridlines, or chart elements. (synthetic, for demonstration)

Imagen responds strongly to the opening clause, so lead with the medium and format ("flat vector scientific illustration, wide banner"). To iterate, edit the prose block and regenerate rather than sending short corrections.

### Midjourney

Comma-separated descriptor lists, aspect ratio via `--ar`, style control via `--style` or `--stylize`, and negative guidance via `--no`.

> graphical abstract, stylized heart emitting abstract flowing waveform ribbon, ribbon refracting through geometric prism into parallel colored strands, strands resolving into constellation of glowing embedding points, flat vector scientific illustration, editorial style, white background, teal and blue palette with coral accent, left-to-right visual flow, generous whitespace --ar 16:9 --style raw --no text, numbers, axes, gridlines, charts, watermark, logo

For journal cover art, swap to a portrait ratio such as `--ar 3:4` and check the journal's stated cover dimensions first. Midjourney weights early descriptors more heavily, so put the subject first and style last. The `--no` list is the reliable place for exclusions; "no text" inside the main prompt is often ignored.

### Selecting among generated candidates

Tell the user to generate several candidates per variant and select against this list before any post-work:

- no stray text, numerals, or chart-like artifacts sneaked into the image
- anatomy and physical structures are not misleading (critical for medical subjects)
- palette lands close enough to the manuscript preset to color-correct, not repaint
- composition survives the target crop (journal cover trims, thumbnail sizes)

## Prompt Anatomy

Build every prompt from these components, in roughly this order:

- **Subject.** The one concept the image must communicate. Name concrete visual stand-ins (heart, prism, constellation) rather than abstractions (representation learning).
- **Composition.** State the layout: rule of thirds, a clear focal hierarchy (one dominant element), and left-to-right reading order for process metaphors so the image scans like a sentence.
- **Style descriptors.** Pick one and commit: flat vector, scientific illustration, isometric cutaway, line art, or editorial. Mixing styles in one prompt produces mush.
- **Color guidance.** Reference a preset palette from `references/figure-styles.md` so the illustration matches the manuscript's real figures. Name the hues in prose ("teal and blue with one coral accent"); generators do not honor hex codes reliably, so treat the palette as a target for post-selection among variants.
- **Labeling limits.** Image generators render text unreliably: misspelled words, garbled glyphs, fake ticks. Keep all text OUT of the generated image ("no text, no numbers") and overlay real labels afterward in TikZ (`\node` over `\includegraphics`), Inkscape, or the LaTeX figure environment. This also keeps labels editable and font-consistent with the manuscript.
- **Aspect ratio.** Graphical abstracts are usually wide (16:9 or the journal's stated pixel size). Cover art is typically portrait; check the journal's published cover specs rather than guessing.
- **What to avoid.** Include an explicit negative list in every prompt:
  - fake data plots, charts, axes, or anything resembling plotted results
  - invented numbers, percentages, or equations
  - logos, trademarks, journal branding
  - real people's likenesses
  - anatomically misleading depictions in medical or biological figures (a stylized heart is fine; a wrong-chambered "realistic" heart is not)

## Disclosure and Policy

These rules are refusal-grade: do not hand over a generated-image workflow without them.

1. **Disclose every AI-generated image used in a manuscript.** Emit a caption line with each prompt package, for example:

   > Illustration generated with DALL-E 3 on 2026-07-14; no experimental data are depicted.

   Adapt the tool name and date. The "no experimental data are depicted" clause is part of the point: it tells editors and readers the image is decorative or conceptual, not evidentiary.

2. **Check the target journal's generative-AI image policy before submission.** Policies differ widely (some publishers ban AI imagery outright, some allow it with disclosure, some allow it only for non-scientific content) and they change. Never assert a specific journal's policy from memory; look it up on the journal's current author guidelines and cite where you found it. If the policy cannot be located, tell the user to contact the editorial office before relying on the image.

3. **Emit a policy checklist** with every prompt package:
   - [ ] Journal's generative-AI image policy located and read (link recorded)
   - [ ] Disclosure caption drafted and placed in the figure caption
   - [ ] Image contains no text, numbers, axes, or chart-like elements
   - [ ] Image contains no real person's likeness, logo, or trademark
   - [ ] For medical/biological subjects: anatomy reviewed for misleading detail
   - [ ] Final labels overlaid with TikZ/Inkscape, not generated

## Related Skills

- **figure-suggestions**: hands off conceptual-overview and graphical-abstract recommendations to this skill
- **journal-formatting**: provides cover art and graphical abstract specs (dimensions, file type, color mode)
- **visualization**, **tikz-diagrams**, **plotneuralnet**: the other side of the hard boundary; everything that carries data goes to them, never to an image generator

## Alt Text

Alt text is a REQUIRED output of every prompt package: each variant carries a draft alt-text line
describing the CONCEPT the image depicts (the subject and the relationship it evokes), so the figure
that eventually renders from the prompt inherits an accurate description rather than none. Because this
skill emits prompts for conceptual imagery, not data figures, the alt text describes the concept
depicted; it never claims data content the image does not carry. Style variants share ONE concept
description plus at most a one-clause style note, following the Alt Text convention in
`references/figure-styles.md`.

## Integrity Constraints

Integrity constraints: see `references/integrity-constraints.md`; the refusal-grade rules below are binding.

1. **Never fabricate citations.** Every reference must come from an actual retrieval or user-provided source; if a citation cannot be verified, say so rather than inventing metadata.
2. **Never invent data.** Illustrative content must be labeled `(synthetic, for demonstration)` and never presented as findings.
3. **Refuse** to present as valid output: a citation that is likely fabricated or cannot be resolved, a data claim that cannot be traced to user-provided data or an actual computation, or a source known to be retracted (unless explicitly cited as retracted).
4. **Never generate a prompt for a data or results figure.** Anything with axes, error bars, plotted quantities, or measured numbers is refused and redirected to visualization, tikz-diagrams, plotneuralnet, or latex-tables.
5. **Never present a generated image without AI disclosure.** Every prompt package includes the disclosure caption, and the user is told to verify the target journal's generative-AI policy.

Canonical copy: `references/integrity-constraints.md`.
