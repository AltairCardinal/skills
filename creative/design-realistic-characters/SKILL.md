---
name: design-realistic-characters
description: Design, diagnose, and lock believable photorealistic adult human character identities that avoid generic, averaged, or visibly AI-generated faces. Use when creating adult actors or characters for film, video, games, or visual stories; when a portrait feels like an "AI face," stock model, beauty render, or character sheet; when a face must feel sympathetic, ordinary, distinctive, or consistent across scenes; or before turning a character identity into cinematic, emotional, or continuity-controlled images and video.
---

# Design Realistic Characters

Build the person before building the shot. Separate identity, photography, performance, and continuity so cinematic polish cannot hide a weak or generic face.

Use this workflow for adult characters. Route requests involving minors through an age-appropriate workflow and applicable safety rules instead of adapting these casting heuristics casually.

Use an available raster image-generation skill or tool for image work. Keep each generation to one reviewable asset unless the user explicitly requests variants.

## Core rules

- Treat “realistic” as individual specificity, not extra pores, grain, blur, or camera jargon.
- Treat “distinctive” as a small set of related anatomical particulars, not ugliness or a defect pile.
- Never infer morality, intelligence, weakness, or trustworthiness from ethnicity or anatomy. Design emotional casting through expression, styling, behavior, and story context.
- Preserve subject-relative left and right consistently. Say “the subject’s left” when direction matters.
- Keep identity work emotionally neutral. Add character performance only after the user approves the person.
- Do not reuse a rejected face as a reference when the rejection concerns the identity itself.
- Preserve rejected outputs as diagnostic evidence when working in a project; do not silently overwrite them.
- Require permission or a clear usage right before conditioning on a real person’s photographs. Do not publish private references or biometric material.

## Choose the control path

### Pure text identity discovery

Use when no face reference exists. Expect to reduce default-face behavior, not guarantee a perfectly natural or repeatable identity. Generate one candidate, review it, and then lock the approved image as the reference.

### Generated identity reference

Use after a text-generated identity passes review. Attach the approved identity image to later photography and performance generations. State that the face, proportions, localized marks, and stable accessories are invariants.

### Real-person identity reference

Use when maximum human specificity or identity continuity matters and the user supplies authorized photographs. Prefer multiple angles and expressions when the tool supports them. Keep identity conditioning separate from pose, lighting, and expression controls.

Do not claim that prompt wording alone is equivalent to face embeddings, landmarks, adapters, or fine-tuning. State the current tool’s real control limits.

## Workflow

### 1. Define the identity objective

Record:

- adult age range;
- cultural context without turning it into a stereotype;
- ordinary social impression the story needs;
- traits to avoid, such as glamour, villain coding, infantilization, or heroic hardness;
- stage in the character arc;
- whether the result is identity discovery, identity preservation, or performance.

Translate moral or emotional requests into casting and behavior. For example, “the audience should mourn him” becomes “approachable, attentive, everyday, and capable of believable vulnerability,” not a supposedly virtuous skull shape.

### 2. Diagnose the visible AI signal

Classify the problem before rewriting the prompt:

- **Default identity:** demographic average, harmonious features, no personal history.
- **Emotion stack:** brows, tears, sweat, open mouth, hunched shoulders, and symbolic hands all explaining one emotion.
- **Catalog presentation:** gray seamless backdrop, split panels, repeated full-body and close-up poses, uniform sharpness.
- **Synthetic texture:** evenly distributed pores, sweat, wrinkles, highlights, or skin gloss.
- **Beauty prior:** symmetric face, ideal jaw, tiny nose, large eyes, perfect hair, cosmetic skin.
- **Cinematic camouflage:** grain, darkness, bokeh, or color grading applied before the person is credible.

Fix only the diagnosed layer. Do not add more photographic effects to repair a default identity.

### 3. Write an identity fingerprint

Specify five to seven observable groups. Read [prompt-recipes.md](references/prompt-recipes.md) when drafting a generation prompt.

Cover a useful subset of:

1. face silhouette and unequal left/right contour;
2. eye spacing plus different eyelid behavior;
3. brow height, density, or tail length;
4. nose bridge, tip, and nostril relationship;
5. lips, cupid’s bow, mouth corners, and chin;
6. one or two localized skin marks;
7. hairline, sideburns, flyaways, ears, or stable eyewear.

Use directional relationships such as “the subject’s left eyelid is slightly more hooded.” Avoid vague instructions such as “unique face,” “real person,” or “not AI.” Keep every difference mild and anatomically plausible.

Do not maximize every axis. One strong irregularity plus several quiet supporting differences is usually more believable than six exaggerated defects.

### 4. Generate the identity layer

Remove narrative and cinematic variables:

- one adult person;
- emotionally neutral, closed mouth, relaxed brows;
- direct or near-direct attentive gaze;
- plain real wall;
- broad natural light and neutral white balance;
- normal perspective around a 50 mm look;
- enough depth of field to read both ears and the facial plane;
- ordinary, mildly worn clothing;
- no beauty retouching, HDR, glamour, film grain, artificial blur, or dramatic grading.

Do not attach a rejected identity reference. Do not add fear, grief, romance, menace, or action at this stage.

### 5. Review before iterating

Read [review-rubric.md](references/review-rubric.md). Ask the user for a first-impression judgment and do not generate another candidate automatically.

Separate these verdicts:

- identity realism;
- character fit;
- emotional casting;
- photographic quality.

A face can pass realism and fail casting. Keep that distinction explicit.

### 6. Lock the identity

After explicit approval:

- name the approved asset as the identity anchor;
- record stable anatomy, localized marks, hairline, and accessories;
- exclude all rejected identities from later reference sets;
- require the approved anchor for every later generation that shows the face;
- avoid asking later prompts to redesign approved facial geometry.

### 7. Add the photography layer

Generate or edit with the approved identity attached. Add only environment, wardrobe, lens, exposure, composition, and medium-specific artifacts. Confirm the face still matches before adding acting.

Photography can support realism but cannot create identity. Reject outputs that regain beauty symmetry or smooth away localized marks.

### 8. Add the performance layer

Drive acting with a concrete micro-situation rather than an adjective stack:

- weak: “terrified, desperate, crying, sweating”;
- strong: “he heard one floorboard move behind him and is trying to stop breathing.”

Allow one or two involuntary signals, such as fixed gaze and a tight jaw. Keep symbolic hand poses, crying eyebrows, open mouths, and full-body emotional pantomime out unless the story specifically needs them.

### 9. Build continuity

For image sequences or video, provide:

- the approved identity anchor;
- the last approved scene or continuity frame when supported;
- stable wardrobe and localized identity marks;
- the current shot’s micro-situation;
- a short invariant list that forbids facial redesign.

Use multi-reference or identity-conditioning features when available. Do not imply that a video model can repair an unconvincing source identity.

## Iterate with one variable

When a result fails, change one layer:

- default face → rewrite identity fingerprint;
- realistic but wrong casting → create a new identity rather than restyling the old face;
- correct person but artificial portrait → change photography only;
- correct person and shot but theatrical acting → reduce performance signals;
- identity drift → strengthen reference conditioning, not prose adjectives.

Stop pure-text iteration when several candidates remain visibly synthetic despite concrete fingerprints. Recommend authorized real-person references or a dedicated identity-conditioning workflow.

## Handoff

Report:

- the approved or candidate asset path;
- whether generation was pure text or reference-conditioned;
- the identity fingerprint used;
- what passed and what remains uncertain;
- the next single layer to test;
- the exact tool limitations that affect identity fidelity.
