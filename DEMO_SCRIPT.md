# Demo video script (target 2:45, limit 3:00)

The brief asks the video to cover: the problem, who it helps, how it works, the impact, and why most people should care. Each part below maps to one of these.

**Setup:** an Android phone with the app installed (see NEXT_STEPS step 5) and the sample screenshots sent to yourself on WhatsApp. Fallback: a phone screen recording of the live site (or a desktop browser at phone width), plus the screenshots in `samples/screenshots/` saved on the phone. Speak slowly. Subtitles help judges watching on mute.

| Time | Screen | Voice-over |
| --- | --- | --- |
| 0:00–0:20 | A real (anonymised) WhatsApp "VIP stock group" screenshot, or `1_group_invite.png` | "This is a WhatsApp stock-tips group. Free tips, a 'professor', members posting profits. It looks real. In 2025, Indians lost about ₹19,800 crore to cyber fraud, and 77% of it went to fake investment schemes like this one." |
| 0:20–0:35 | Truecaller / spam label, then a plain chat | "Spam filters check phone numbers and links. But this scam runs for weeks inside a group chat, so nothing warns you. And it doesn't just target the elderly: engineers and finance professionals lose crores too." |
| 0:35–0:45 | In WhatsApp, open `2_payment_request.png` → Share → Nivesh Kavach | "Nivesh Kavach is a free app. No login. In WhatsApp, just tap Share and pick Nivesh Kavach." |
| 0:45–1:15 | The app opens and checks automatically. Show the result: High risk, stage timeline, next move | "It reads the screenshot and checks it two ways: our rule engine for known red flags, and an AI model guided by a playbook of how Indian investment scams unfold, stage by stage. It says: high risk. You're at stage 3, being moved to a fake app. Next, they'll push you to deposit more." |
| 1:15–1:35 | Scroll to the highlighted message, then "Details we checked": UPI not `@valid`, APK link, fake SEBI number | "It highlights the exact words that are red flags. Since October 2025, real SEBI-registered brokers collect money only through '@valid' UPI IDs, so this personal UPI ID is a hard red flag. We link straight to SEBI Check to verify." |
| 1:35–1:55 | Switch language to हिंदी or मराठी; tap Listen | "Everything comes in 10 Indian languages, and it can read the result aloud for people who find reading hard." |
| 1:55–2:05 | Tap "Send to family on WhatsApp" | "One tap sends the warning to a son or daughter: 'Please call me before I send any money.'" |
| 2:05–2:30 | "I already paid" tab, upload `4_payment_receipt.png` + `3_withdrawal_tax_hindi.png`. Show the 1930 button and the complaint draft | "If you've already paid, every minute counts. It gives the first-hour steps and drafts your cyber-crime complaint, with the amount, UTR and UPI ID filled in from your screenshots." |
| 2:30–2:40 | Architecture diagram from the doc | "It runs fully serverless on AWS: Lambda, Bedrock, Textract, Translate, Polly, DynamoDB and CloudFront. Screenshots are never stored." |
| 2:40–2:55 | Your user-test result on screen, e.g. "Spotted scams: 55% → 90% (n=18)" | "In our test with [N] people, spotting scams went from [X]% to [Y]%. Every Indian with a phone and savings is a target. Nivesh Kavach: check before you invest." |

**Replace the [N], [X], [Y] with your real results.** If you didn't run the user test, say instead how many real scam messages it caught, e.g. "it flagged 46 of 50 real scam messages."

## Recording tips
- Do one full take with the real live site; edit out only waiting time. Judges value a working build.
- Keep the browser zoomed so text is readable on a laptop screen.
- Check the final length is under 3:00. Over the limit can cost points.
