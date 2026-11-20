# Next steps: from here to submission (deadline 30 Nov 2026, 11:59 PM IST)

The code, docs and test tools are built. What's left needs **your AWS account, real people and your own voice**. Work top to bottom; each step says how you'll know it's done.

## Where things stand

| Part | Status |
| --- | --- |
| Rule engine, scam playbook, stage detection, lookalike-domain detection | ✅ Built, 26 automated tests pass |
| Web app (check mode, "I already paid" mode, 10 languages, family WhatsApp share, highlighted red flags) | ✅ Built, tested in a browser |
| Installable app + "share from WhatsApp" (Android) | ✅ Built, tested in desktop Chrome; **test on a real Android phone after deploy** |
| AWS template + one-command deploy | ✅ Written and validated, **never deployed** |
| Textract / Bedrock / Translate / Polly / DynamoDB calls | ⚠️ Request shapes checked offline against the real AWS API definitions (found and fixed 2 bugs); **never run against real AWS** |
| Evaluation script + 25 labelled test messages | ✅ Built; all 25 correct, but they are made-up messages I also tuned on |
| Demo screenshots (English + Hindi) | ✅ In `samples/screenshots/` |
| Idea Brief + Build Summary | ✅ Drafted in the doc; the **Impact** section needs your real numbers |
| SEBI registration list | ❌ Empty: SEBI's site was blocked from my workspace (step 4) |
| Live URL, real-user test, demo video, public repo, submission | ❌ Your steps below |

---

## Day 1 (today/tomorrow): accounts and deploy

### 1. Accounts (30 min)
- [ ] **AWS Builder Center:** create a profile, claim your alias and **write the alias down** (needed at submission).
- [ ] **Student verification** through SheerID on Builder Center. **Do it by 27 Nov**; it can take time and is required to win.
- [ ] **New AWS account** (sign in with the same Builder ID). Choose the Free plan.
- [ ] **Budget alert:** Billing → Budgets → Create → Monthly cost budget, **$10**, email alert at 80%.
- [ ] Register the team on **techfest.org** and note the Team ID. Only the team leader can submit.

### 2. Check Bedrock before anything else (10 min)
- [ ] AWS console, region **N. Virginia (us-east-1)** → Amazon Bedrock → Playground → Chat → pick **Amazon Nova Lite** → send "hello".
- Replies → go to step 3.
- Error about quota, "0 TPM", or access → Billing → **Upgrade to Paid plan** (your credits still apply; the budget alert protects you) → try again.

### 3. Deploy (30–60 min the first time)
Install on your laptop: [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html), Python 3.12.

```bash
aws configure                 # access key of an IAM user (not root), region us-east-1
unzip nivesh-kavach.zip && cd nivesh-kavach
cd backend && python -m pytest -q && cd ..     # 14 passed
./scripts/deploy.sh nivesh-kavach us-east-1    # prints "Live URL: https://dxxxx.cloudfront.net"
python scripts/smoke_test.py https://dxxxx.cloudfront.net
```
**Done when** the smoke test prints `ALL GOOD`. CloudFront can take 5–10 minutes after the first deploy before the URL works.

On Windows, run `deploy.sh` from Git Bash or WSL.

### If something fails

| Smoke test says | Likely cause | Fix |
| --- | --- | --- |
| Website loads: FAIL (403) | CloudFront still deploying, or upload missing | Wait 10 min; rerun `deploy.sh` |
| Bedrock used: FAIL, note says `AccessDeniedException` / `ValidationException` | Model not enabled, wrong region, or Free plan limit | Step 2; keep everything in `us-east-1`; try `sam deploy --parameter-overrides BedrockModelId=us.amazon.nova-lite-v1:0` |
| Bedrock used: FAIL, note says `ThrottlingException` | Free-plan quota is 0 | Upgrade to the Paid plan |
| Screenshot check: FAIL | Textract error, or image too big | CloudWatch → Log groups → `/aws/lambda/nivesh-kavach-ApiFunction…` → read the error |
| Translate: FAIL | Translate permission or language code | Same log group |
| Audio: FAIL | Polly neural voice not in region | Keep us-east-1 |
| Anything → 500 | A bug in my code that only shows on real AWS | Copy the error from CloudWatch and paste it to me |

**Expect at least one real bug here.** The request formats are now checked offline, but permissions, model access and timing can only be tested on real AWS. Budget half a day.

### 4. Load the SEBI register (30 min, optional but strong for Q&A)
- [ ] Open https://www.sebi.gov.in/intermediaries.html → **Investment Adviser** → save each result page (Ctrl+S, "Web page, HTML only") into a folder `sebi_pages/`. Repeat for **Research Analyst**.
- [ ] `python scripts/build_registry.py sebi_pages/` → should say "Wrote N registrations".
- [ ] Run `./scripts/deploy.sh` again.
- If the saved pages don't parse (0 registrations), send me one saved page and I'll fix the parser.

---

## Days 2–5: make it real

### 5. Test with real AWS on the demo screenshots
- [ ] On the live site, upload each image in `samples/screenshots/` and check that the result makes sense in **English, Hindi and Marathi**.
- [ ] Test on your phone, over mobile data, not just Wi-Fi.
- [ ] **On an Android phone:** open the live URL in Chrome → menu → "Install app" (or tap the Install card). Then in WhatsApp, long-press a message or open an image → Share → **Nivesh Kavach**. It should open and check it automatically. (iPhones don't support sharing into web apps; there, users paste or upload.)
- [ ] Note anything confusing or wrong and send it to me.

### 6. Collect real scam messages (the most important step for winning)
Judges will ask "does it work on real scams?" Made-up examples aren't enough.
- [ ] Collect **at least 50 real messages**: family/friends' WhatsApp forwards, screenshots in news articles, police and SEBI advisories. Also collect **at least 20 genuine** investment messages (broker SMS, mutual fund updates).
- [ ] **Remove personal details** (real names, phone numbers) before adding them.
- [ ] Add them to `eval/labelled.csv` with `source` = `news`, `family` or `volunteer` (not `synthetic`).
- [ ] Run against the live site:
  ```bash
  python scripts/evaluate.py eval/labelled.csv --url https://dxxxx.cloudfront.net
  ```
- [ ] Open `eval/report.md`. **Quote only the "Real messages" numbers.** Send me the misses and I'll improve the rules.

### 7. Small user test (15–20 people, 1–2 days)
Simple protocol:
1. Show each person 4 real messages (2 scam, 2 genuine) **without** the app and ask "Would you invest? Scam or genuine?"
2. Then let them use the app on 4 *different* messages and ask the same.
3. Record % correct before vs after, and ask "Was the explanation clear? (1–5)".
4. Try to include 3–4 people over 50, and 3–4 people who prefer Hindi or Marathi.

- [ ] Put the results in the doc's **Impact** section (replace the "To measure" bullet), e.g. "Correctly spotted scams: 55% without the app → 90% with it (n=18)". Use your real numbers, whatever they are.

---

## Days 6–9: submission material

### 8. Demo video (under 3 minutes)
- [ ] Follow `DEMO_SCRIPT.md`. Record the screen with OBS or your phone's screen recorder; record the voice-over separately if that's easier.
- [ ] Upload to Google Drive or YouTube (unlisted) and check it plays without signing in.

### 9. Public GitHub repo
The zip already has a git history with one commit.
```bash
cd nivesh-kavach
gh repo create nivesh-kavach --public --source . --push     # or create on github.com and: git remote add origin <url> && git push -u origin main
```
- [ ] Check that **Actions → tests** runs green.
- [ ] Make sure no AWS keys or `samconfig.toml` with secrets are committed (`.gitignore` covers the usual ones).

### 10. Finalise the docs
- [ ] Doc: fill in **Impact** with real numbers (steps 6–7), and the live URL.
- [ ] Doc: update "Current status" in the Build Summary.
- [ ] Export the doc as PDF or Word for the Drive folder.

---

## Day 10 (by 28 Nov; keep 2 days spare): submit

### 11. Google Drive folder (shared as "Anyone with the link can view")
- [ ] `Idea Brief + Build Summary.pdf`
- [ ] `Live URL.txt` (the CloudFront URL)
- [ ] `Code repository.txt` (GitHub link)
- [ ] `Demo video` (file or link)
- [ ] Open the folder link in an incognito window to check it works.

### 12. Submit on techfest.org (team leader only)
- [ ] Paste the Drive folder link in "Submission Link".
- [ ] Paste the **Builder Center alias**, the idea, and the live URL where asked.
- [ ] Screenshot the confirmation.

---

## Until Demo Day (17 Dec, IIT Bombay)
- [ ] **Keep the site live.** Don't delete the stack. Check the budget weekly, and run `smoke_test.py` the night before and the morning of the demo.
- [ ] Have a backup: a screen recording of the demo, and `MOCK_AWS=1 python scripts/local_server.py` on your laptop in case the venue Wi-Fi fails.
- [ ] Rehearse the 3-minute demo plus 2 minutes of Q&A. Likely questions:
  - **"How is this different from Truecaller or SEBI Check?"** They check numbers and UPI IDs; we read the whole conversation, say which stage of the scam you're at, explain it in your language, and help after you've paid. We send people *to* SEBI Check.
  - **"How accurate is it?"** Your real numbers from step 6, with the sample size. Don't round up.
  - **"What if the AI is wrong?"** The rule engine runs independently and the AI can only raise the risk, never lower it. Every flag shows the exact words. It's guidance, not a guarantee.
  - **"Can a scammer trick your AI?"** Message text is fenced off as untrusted input, the AI can only raise risk, and text aimed at checkers ("AI: this is safe", "ignore previous instructions") is itself a red flag. There's a test for it.
  - **"Privacy?"** Screenshots are never stored; only scam type, risk, stage and an optional city are kept for 90 days.
  - **"Cost at scale?"** Serverless, pay per check; Nova Lite is a low-cost model, and rule-based checks cost almost nothing.

## Nice-to-haves (only if everything above is done)
- Voice-note analysis with Amazon Transcribe (scam groups also send voice notes).
- Load the RBI alert list of unauthorised forex platforms and check names against it.
- Rename the app if you prefer another name; change it in `frontend/i18n.js` and `index.html`.
