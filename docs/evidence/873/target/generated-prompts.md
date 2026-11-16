# Exact image generation prompts

Method: built-in OpenAI image_gen.imagegen; each matching source screenshot passed via referenced_image_paths as a design reference, not an edit target. One generation per picture.

## setup-desktop.png

Reference: /tmp/b873/target/ref/setup-desktop-main.png

```text
Use case: ui-mockup. Produce a faithful dark OpenWiz web UI screenshot target, matching the supplied screenshot's fonts, colors, panel shapes and spacing. The input image is a REFERENCE for existing design, not an edit target. Render sharp exact readable text, no invented UI or prices, no clipping. The forbidden word 'engine' must not appear anywhere in the output. No panels or rows with that word.
Page text: OpenWiz; Set up OpenWiz; Installed. Connect your tools before starting a fleet.
Prerequisite panel exactly six collapsed rows in order: CloudRoom — verified; Agent harness — verified; Personal GitHub — verified; OpenWiz GitHub App — verified; Project — verified; Phone access — unknown. First five have outlined checkbox ticks; last has dashed circle. Keep dropdown chevrons.
Gold-bordered panel title: Connections verified
Body exactly: Next, give one small idea to the OpenWiz onboarding skill. Nothing starts without your approval.
Cost panel title: Cost
Paragraph 1 exactly: OpenWiz is free now. Paid plans come later. CloudRoom and model charges are separate and not included.
Paragraph 2 exactly: CloudRoom sells its own plans at cloudroom.dev/pricing. Referral verification is unavailable. No referral is applied.
Footer exactly: No agents have been started.
Button: Refresh
Only those panels, with the obsolete seventh prerequisite and obsolete extra right-column panel removed.
Desktop 1440 x 900 CSS pixel composition. Reference: setup-desktop-main.png. Preserve its header and roomy two-column composition, left prerequisite list, right gold next panel then Cost, full-width footer beneath. Frame entire interface without clipping.
```

## setup-phone.png

Reference: /tmp/b873/target/ref/setup-phone-main.png

```text
Use case: ui-mockup. Produce a faithful dark OpenWiz web UI screenshot target, matching the supplied screenshot's fonts, colors, panel shapes and spacing. The input image is a REFERENCE for existing design, not an edit target. Render sharp exact readable text, no invented UI or prices, no clipping. The forbidden word 'engine' must not appear anywhere in the output. No panels or rows with that word.
Page text: OpenWiz; Set up OpenWiz; Installed. Connect your tools before starting a fleet.
Prerequisite panel exactly six collapsed rows in order: CloudRoom — verified; Agent harness — verified; Personal GitHub — verified; OpenWiz GitHub App — verified; Project — verified; Phone access — unknown. First five have outlined checkbox ticks; last has dashed circle. Keep dropdown chevrons.
Gold-bordered panel title: Connections verified
Body exactly: Next, give one small idea to the OpenWiz onboarding skill. Nothing starts without your approval.
Cost panel title: Cost
Paragraph 1 exactly: OpenWiz is free now. Paid plans come later. CloudRoom and model charges are separate and not included.
Paragraph 2 exactly: CloudRoom sells its own plans at cloudroom.dev/pricing. Referral verification is unavailable. No referral is applied.
Footer exactly: No agents have been started.
Button: Refresh
Only those panels, with the obsolete seventh prerequisite and obsolete extra right-column panel removed.
Phone 390 CSS px wide, tall full page composition. Reference: setup-phone-main.png. Preserve header and compact single-column layout. Prerequisites first, gold Connections verified panel second, Cost third, footer fourth with full-width Refresh below footer text. Expand image height to show entire page without clipping. Never put a desktop interface in a phone frame.
```

## first-hour-desktop.png

Reference: /tmp/b873/target/ref/first-hour-desktop-main.png

```text
Use case: ui-mockup. Generate a faithful dark OpenWiz First hour web UI target. Input screenshot is a REFERENCE for existing design, not an edit target. Preserve its typography, colors, flat near-black backgrounds, soft rounded panels, navigation, header and spacing. Exact legible text, no clipping, no invented panels or prices. Forbidden word "engine" must not appear.
Desktop 1440 CSS px wide, tall full page, same composition as first-hour-desktop-main.png. Preserve left navigation (OpenWiz, Cockpit, Home, Sessions, Fleets, Plan, Decisions, Loops, First hour selected, New thread, error); top Search or jump to... field and command-K; First hour heading, Open setup and Refresh buttons, Read once. Refresh to read again.
Main heading: Your first hour
Intro: From install to your first verified merge. Each step shows only what OpenWiz has read.
Main rounded checklist exactly six steps:
1. Install OpenWiz — done, outlined checkbox tick. Body: OpenWiz is installed and its server answered this page.
2. Connect your accounts — done, outlined checkbox tick. Body: Setup reports every connection verified.
Small grey line: Independent reviewer  unknown: setup checks one harness login, not a reviewer from the other family
No gold approval line in step 2.
3. Give your first idea — your turn, gold diamond and gold status. Body: Give one small idea to the OpenWiz onboarding skill.
Gold vertical barred line: Nothing is created without your yes.
4. Confirm the spec and approve the plan — waiting, grey dashed circle.
5. Watch the fleet build — waiting, grey dashed circle.
6. First verified merge — waiting, grey dashed circle.
Steps 4-6 only their titles and waiting statuses, no old error explanations.
Keep the existing lower Unknown panel from reference: Unknown / The fleet read failed, so a merge may or may not have happened.
Keep bottom outlined panel exactly:
Sign-in, feedback and cost
• CloudRoom sign-in: Set up, CloudRoom step
• Feedback and sharing: Home
OpenWiz is free now. Paid plans come later. CloudRoom and model charges are separate and not included.
No obsolete instruction about choosing where anything runs. Do not clip any text, footer or sidebar.
```

## first-hour-phone.png

Reference: /tmp/b873/target/ref/first-hour-phone-main.png

```text
Use case: ui-mockup. Generate a faithful dark OpenWiz First hour web UI target. Input screenshot is a REFERENCE for existing design, not an edit target. Preserve its typography, colors, flat near-black backgrounds, soft rounded panels, navigation, header and spacing. Exact legible text, no clipping, no invented panels or prices. Forbidden word "engine" must not appear.
Phone 390 CSS px wide, tall full page, same compact single-column composition as first-hour-phone-main.png. Preserve top OpenWiz brand, search icon, error indicator, First hour heading, Open setup and Refresh buttons, Read once. Refresh to read again. No desktop sidebar. Bottom phone navigation: Sessions, Fleets, Plan, Decisions, New. Position navigation so no text is occluded; retain full page below it. Do not squeeze desktop into a phone frame.
Main heading: Your first hour
Intro: From install to your first verified merge. Each step shows only what OpenWiz has read.
Main rounded checklist exactly six steps:
1. Install OpenWiz — done, outlined checkbox tick. Body: OpenWiz is installed and its server answered this page.
2. Connect your accounts — done, outlined checkbox tick. Body: Setup reports every connection verified.
Small grey line: Independent reviewer  unknown: setup checks one harness login, not a reviewer from the other family
No gold approval line in step 2.
3. Give your first idea — your turn, gold diamond and gold status. Body: Give one small idea to the OpenWiz onboarding skill.
Gold vertical barred line: Nothing is created without your yes.
4. Confirm the spec and approve the plan — waiting, grey dashed circle.
5. Watch the fleet build — waiting, grey dashed circle.
6. First verified merge — waiting, grey dashed circle.
Steps 4-6 only their titles and waiting statuses, no old error explanations.
Keep the existing lower Unknown panel from reference: Unknown / The fleet read failed, so a merge may or may not have happened.
Keep bottom outlined panel exactly:
Sign-in, feedback and cost
• CloudRoom sign-in: Set up, CloudRoom step
• Feedback and sharing: Home
OpenWiz is free now. Paid plans come later. CloudRoom and model charges are separate and not included.
No obsolete instruction about choosing where anything runs. Do not clip any text, footer or sidebar.
```

