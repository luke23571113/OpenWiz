Generate four UI target pictures (dark web app screens) for OpenWiz, a developer tool. They are design targets for a small change: the "engine" step is removed from the Setup page and the First-hour page. Use the four reference screenshots as the existing look and layout to preserve exactly (fonts, colours, spacing, panel shapes, glyphs); change only what is listed.

References (existing pages, before the change):
- ref/setup-desktop-main.png and ref/setup-phone-main.png: the Setup page at 1440 and 390 CSS px.
- ref/first-hour-desktop-main.png and ref/first-hour-phone-main.png: the First-hour page at 1440 and 390 CSS px.

Picture 1, setup-desktop.png (1440 x 900 CSS px layout): the Setup page as in ref/setup-desktop-main.png, except:
- Left list has exactly six rows: CloudRoom verified, Agent harness verified, Personal GitHub verified, OpenWiz GitHub App verified, Project verified (each with the check-box glyph), Phone access unknown (dashed circle). Remove the "Engine missing" row.
- Right column: the gold-bordered panel reads "Connections verified" then "Next, give one small idea to the OpenWiz onboarding skill. Nothing starts without your approval." Below it the Cost panel, unchanged text: "OpenWiz is free now. Paid plans come later. CloudRoom and model charges are separate and not included." and "CloudRoom sells its own plans at cloudroom.dev/pricing. Referral verification is unavailable. No referral is applied." Remove the "Engine / Not selected" panel entirely.
- Footer panel text: "No agents have been started." with the Refresh button on the right.

Picture 2, setup-phone.png (390 CSS px wide, tall full page): the same content as picture 1 in one column, as ref/setup-phone-main.png lays it out: heading, the six rows, the Connections verified panel, the Cost panel, the footer. No Engine row or panel.

Picture 3, first-hour-desktop.png (1440 CSS px wide): the First-hour page as in ref/first-hour-desktop-main.png, except the steps read:
- Install OpenWiz, done (check glyph): "OpenWiz is installed and its server answered this page."
- Connect your accounts, done (check glyph): "Setup reports every connection verified." and the small grey line "Independent reviewer  unknown: setup checks one harness login, not a reviewer from the other family".
- Give your first idea, your turn (gold diamond, gold "your turn"): "Give one small idea to the OpenWiz onboarding skill." and the gold-barred line "Nothing is created without your yes."
- Confirm the spec and approve the plan, waiting (grey). Watch the fleet build, waiting. First verified merge, waiting.
No "Choose where the engine runs next" text anywhere. Keep the left navigation, search bar and bottom "Sign-in, feedback and cost" panel as in the reference.

Picture 4, first-hour-phone.png (390 CSS px wide): the same as picture 3 in the phone layout of ref/first-hour-phone-main.png.

Constraints: dark only; exact text above, spelled exactly; no word "engine" anywhere; no prices, no extra panels, no logos beyond the reference. Do not squeeze the desktop picture into a phone frame.
