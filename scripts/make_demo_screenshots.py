"""Generate sample chat screenshots for the demo video and for testing the
screenshot (OCR) path. Every image is clearly watermarked as sample data, and
all names, numbers, UPI IDs and links are made up.

  pip install playwright && playwright install chromium
  python scripts/make_demo_screenshots.py      # writes samples/screenshots/*.png
"""
import asyncio
import html
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "samples", "screenshots")

CSS = """
*{box-sizing:border-box} body{margin:0;width:390px;font-family:'Noto Sans','Noto Sans Devanagari',sans-serif;background:#efe7dd}
.bar{background:#1f5c4f;color:#fff;padding:14px 16px;display:flex;gap:12px;align-items:center}
.av{width:38px;height:38px;border-radius:50%;background:#9cc;display:grid;place-items:center;font-weight:700;color:#134}
.bar b{display:block;font-size:16px}.bar span{font-size:12px;opacity:.85}
.chat{padding:12px 10px 18px;display:flex;flex-direction:column;gap:8px;position:relative}
.m{max-width:82%;padding:7px 10px 18px;border-radius:8px;font-size:14.5px;line-height:1.38;position:relative;box-shadow:0 1px 1px rgba(0,0,0,.1)}
.in{background:#fff;align-self:flex-start}.out{background:#d9fdd3;align-self:flex-end}
.who{font-size:12.5px;font-weight:700;margin-bottom:2px}.t{position:absolute;right:8px;bottom:3px;font-size:10.5px;color:#7a8a85}
.img{background:#fff;border-radius:8px;padding:8px}.img .ph{height:120px;border-radius:6px;background:linear-gradient(135deg,#1c8b4a,#7fd39c);color:#fff;display:grid;place-items:center;font-weight:800;font-size:20px}
.wm{position:fixed;inset:0;display:grid;place-items:center;pointer-events:none}
.wm div{transform:rotate(-28deg);font-size:30px;font-weight:800;color:rgba(200,0,0,.16);border:4px solid rgba(200,0,0,.16);padding:6px 14px;border-radius:10px}
.rc{background:#fff;margin:24px 16px;border-radius:14px;padding:22px;text-align:center}
.rc .ok{width:56px;height:56px;border-radius:50%;background:#1aa260;color:#fff;font-size:30px;display:grid;place-items:center;margin:0 auto 10px}
.rc h2{margin:6px 0;font-size:30px}.rc table{width:100%;font-size:14px;margin-top:14px;text-align:left;border-collapse:collapse}
.rc td{padding:7px 0;border-top:1px solid #eee}.rc td:last-child{text-align:right;font-weight:600}
"""


def bubble(text, who=None, time="", out=False):
    w = f'<div class="who" style="color:{who[1]}">{html.escape(who[0])}</div>' if who else ""
    body = html.escape(text).replace("\n", "<br>")
    return f'<div class="m {"out" if out else "in"}">{w}{body}<span class="t">{time}</span></div>'


def page(title, sub, inner):
    return (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"
            f"<div class='bar'><div class='av'>{html.escape(title[:1])}</div><div><b>{html.escape(title)}</b><span>{html.escape(sub)}</span></div></div>"
            f"<div class='chat'>{inner}</div><div class='wm'><div>SAMPLE · DEMO DATA</div></div></body></html>")


PROF = ("Prof. R. Mehta (Admin)", "#b5432f")
ASST = ("Assistant Neha", "#2a6fb0")
M1, M2, M3 = ("Suresh K", "#7b4fb0"), ("Kavita 🙏", "#b07a1f"), ("Amit Jain", "#1f8a6a")

SHOTS = {
    "1_group_invite.png": page("VIP Stock Learning Group 📈", "Prof. R. Mehta, Neha, +248 members",
        bubble("Good morning everyone 🌞 Today's FREE tip at 9:15 AM. Our system has 92% accuracy.", PROF, "08:02")
        + bubble("Made ₹42,000 profit today following sir's tip 🙏🙏", M1, "10:41")
        + bubble("Thank you sir! 18% profit this week 💰", M2, "10:44")
        + bubble("Guaranteed returns with zero risk for VIP members. Limited seats, join today only.\nReply YES to get your institutional trading account.", ASST, "11:05")
        + bubble("Already got my institutional account, best decision 👍", M3, "11:07")),
    "2_payment_request.png": page("Assistant Neha", "online",
        bubble("Sir, download our institutional trading app from this link:\nhttps://motilal-vip-trade.top/app.apk\n(Not on Play Store due to SEBI rules)", ASST, "14:20")
        + bubble("First deposit minimum Rs 50,000.\nPay to UPI ID: shreeganesh.traders@ybl", ASST, "14:21")
        + bubble("We are SEBI registered INH000099999. IPO allotment 100% guaranteed for VIP members.", ASST, "14:21")
        + bubble("Is it safe?", None, "14:30", out=True)
        + bubble("100% safe sir. Many members are earning daily. Don't tell anyone, this is confidential channel.", ASST, "14:31")),
    "3_withdrawal_tax_hindi.png": page("Customer Service – StockPro", "online",
        bubble("मुझे अपना प्रॉफिट निकालना है", None, "16:02", out=True)
        + bubble("सर, आपका प्रॉफिट ₹14,85,000 है। पैसे निकालने के लिए पहले 20% टैक्स ₹2,97,000 जमा करना होगा।", ASST, "16:05")
        + bubble("टैक्स तो प्रॉफिट से कट सकता है ना?", None, "16:06", out=True)
        + bubble("नहीं सर, यह नियम है। 24 घंटे में जमा नहीं किया तो अकाउंट फ्रीज़ हो जाएगा। जल्दी करें।\nA/c No 50100234567891 IFSC HDFC0001234", ASST, "16:08")),
    "4_payment_receipt.png": (f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body style='background:#eef2f6'>"
        "<div class='rc'><div class='ok'>✓</div><div>Payment successful</div><h2>₹25,000</h2>"
        "<table><tr><td>To</td><td>shreeganesh.traders@ybl</td></tr><tr><td>Date</td><td>12 Nov 2026, 2:47 PM</td></tr>"
        "<tr><td>UTR</td><td>432198765432</td></tr><tr><td>Note</td><td>StockPro deposit</td></tr></table></div>"
        "<div class='wm'><div>SAMPLE · DEMO DATA</div></div></body></html>"),
}


async def main():
    from playwright.async_api import async_playwright
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        exe = os.environ.get("CHROME_PATH")
        b = await p.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--no-sandbox"])
        pg = await b.new_page(viewport={"width": 390, "height": 300}, device_scale_factor=2)
        for name, doc in SHOTS.items():
            await pg.set_content(doc)
            await pg.screenshot(path=os.path.join(OUT, name), full_page=True)
            print("wrote", name)
        await b.close()


if __name__ == "__main__":
    asyncio.run(main())
