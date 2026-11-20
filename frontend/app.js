(() => {
  const API = window.API_BASE || "/api";
  const $ = (id) => document.getElementById(id);
  const state = { mode: "check", lang: "en", images: [], last: null };

  const EXAMPLES = [
    { label: "Stock-tips group invite", mode: "check",
      text: "Hello! Welcome to Motilal Oswal VIP Stock Learning Group 📈 Professor Rajesh Mehta gives FREE daily tips at 9:15 AM. Our members earned 18% profit last week. Guaranteed returns with zero risk! Limited seats, join today only. Reply YES to get your institutional trading account." },
    { label: "Fake app + payment", mode: "check",
      text: "Dear member, download our institutional trading app from this link: https://motilal-vip-trade.top/app.apk (not available on Play Store due to SEBI rules). First deposit minimum Rs 50,000. Pay to UPI ID shreeganesh.traders@ybl. We are SEBI registered INH000099999. IPO allotment 100% guaranteed for VIP members." },
    { label: "Withdrawal 'tax'", mode: "check",
      text: "Your account profit is ₹14,85,000. To withdraw, you must first pay 20% income tax of ₹2,97,000 to clear the dues. Your account will be frozen within 24 hours if not paid. Don't tell anyone, this is confidential institutional channel. Pay to A/c No 50100234567891 IFSC HDFC0001234." },
    { label: "I already paid", mode: "paid",
      text: "Paid ₹25,000 to shreeganesh.traders@ybl UTR 432198765432 on 12 Nov. Then paid ₹75,000 UTR 432198700011 on 14 Nov. Now app says pay withdrawal fee of ₹40,000 to unlock my profit. App name StockPro Institutional, link stockpro-inst.vip" },
    { label: "हिंदी: रोज़ 3% मुनाफा", mode: "check",
      text: "सिर्फ ₹5000 लगाओ और 3% रोज मुनाफा पाओ! पक्का मुनाफा, बिना रिस्क। 2 दोस्तों को जोड़ो और referral income पाओ। जल्दी करो, आज ही जुड़ो।" },
  ];

  const t = (k) => (I18N[state.lang] && I18N[state.lang][k]) || I18N.en[k];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function applyI18n() {
    document.documentElement.lang = state.lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    $("modeHint").textContent = t(state.mode === "paid" ? "hintPaid" : "hintCheck");
  }

  // ---------- mode tabs ----------
  document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => setMode(b.dataset.mode)));
  function setMode(mode) {
    state.mode = mode;
    document.querySelectorAll(".tab").forEach((b) => {
      const on = b.dataset.mode === mode;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on);
    });
    $("modeHint").textContent = t(mode === "paid" ? "hintPaid" : "hintCheck");
  }

  // ---------- language ----------
  try { state.lang = localStorage.getItem("nk_lang") || "en"; } catch (_) {}
  $("lang").value = state.lang;
  $("lang").addEventListener("change", (e) => {
    state.lang = e.target.value;
    try { localStorage.setItem("nk_lang", state.lang); } catch (_) {}
    applyI18n();
  });

  // ---------- examples ----------
  EXAMPLES.forEach((ex) => {
    const b = document.createElement("button");
    b.className = "chip"; b.type = "button"; b.textContent = ex.label;
    b.addEventListener("click", () => { $("text").value = ex.text; setMode(ex.mode); $("text").focus(); });
    $("exampleChips").appendChild(b);
  });

  // ---------- screenshots (compressed in the browser) ----------
  $("files").addEventListener("change", async (e) => {
    for (const f of [...e.target.files]) {
      if (state.images.length >= 3) break;
      state.images.push(await compress(f));
    }
    e.target.value = "";
    renderThumbs();
  });
  function compress(file) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => {
        const max = 1600;
        const scale = Math.min(1, max / Math.max(img.width, img.height));
        const c = document.createElement("canvas");
        c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
        c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(img.src);
        resolve({ data: c.toDataURL("image/jpeg", 0.82), mime: "image/jpeg" });
      };
      img.onerror = reject;
      img.src = URL.createObjectURL(file);
    });
  }
  function renderThumbs() {
    $("thumbs").innerHTML = state.images.map((im, i) =>
      `<div class="thumb"><img src="${im.data}" alt="Screenshot ${i + 1}"><button type="button" aria-label="Remove" data-i="${i}">×</button></div>`).join("");
    $("thumbs").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { state.images.splice(+b.dataset.i, 1); renderThumbs(); }));
  }

  // ---------- check ----------
  $("checkBtn").addEventListener("click", check);
  $("againBtn").addEventListener("click", () => {
    $("result").hidden = true; $("text").value = ""; state.images = []; renderThumbs();
    window.scrollTo({ top: 0, behavior: "smooth" });
  });

  let loadTimer;
  function showLoading(on) {
    $("loading").hidden = !on; $("checkBtn").disabled = on;
    clearInterval(loadTimer);
    if (on) {
      let i = 0; const msgs = t("loading");
      $("loadingMsg").textContent = msgs[0];
      loadTimer = setInterval(() => { i = Math.min(i + 1, msgs.length - 1); $("loadingMsg").textContent = msgs[i]; }, 2200);
    }
  }

  async function check() {
    const text = $("text").value.trim();
    $("error").hidden = true;
    if (!text && !state.images.length) { showError(t("errEmpty")); return; }
    $("result").hidden = true;
    showLoading(true);
    try {
      const res = await fetch(`${API}/analyze`, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ text, images: state.images, lang: state.lang, mode: state.mode, city: $("city").value }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || t("errNet"));
      state.last = data;
      render(data);
    } catch (err) {
      showError(err.message && !/fetch/i.test(err.message) ? err.message : t("errNet"));
    } finally {
      showLoading(false);
    }
  }

  function showError(msg) { $("error").textContent = msg; $("error").hidden = false; }

  // ---------- render result ----------
  function render(d) {
    const v = $("verdict");
    v.className = `card verdict ${d.risk}`;
    $("riskBadge").innerHTML = `<span class="dot"></span>${esc(t("risk" + d.risk[0].toUpperCase() + d.risk.slice(1)))}`;
    $("summary").textContent = d.summary;
    $("listenBtn").hidden = !["hi", "en"].includes(d.lang);
    $("shareBtn").href = familyLink(d);

    // stage timeline
    if (d.scam) {
      $("stageCard").hidden = false;
      $("scamName").textContent = d.scam.name;
      $("stages").innerHTML = d.scam.stages.map((s) => {
        const cls = s.n < d.scam.current ? "done" : s.n === d.scam.current ? "now" : "";
        return `<li class="${cls}"><span class="n">${s.n}</span><span>${esc(s.name_t || s.name)}</span></li>`;
      }).join("");
      $("nextMove").textContent = d.next_move;
    } else {
      $("stageCard").hidden = true;
    }

    $("paidCard").hidden = d.mode !== "paid";
    $("actions").innerHTML = d.actions.map((a) => `<li>${esc(a)}</li>`).join("");

    $("flagsCard").hidden = !d.flags.length;
    $("flags").innerHTML = d.flags.map((f) => `
      <li><strong>${esc(f.title_t || f.title)}</strong>
      <p>${esc(f.why_t || f.why)}</p>
      ${f.evidence ? `<q>${esc(f.evidence)}</q>` : ""}
      ${f.source === "ai" ? `<span class="tag">AI</span>` : ""}</li>`).join("");

    // the message itself, with each red flag's exact words marked
    renderRead(d);

    // concrete checks
    const e = d.entities || {};
    const parts = [];
    (e.upi_ids || []).forEach((u) => {
      const ok = /@valid/i.test(u);
      parts.push(`<div class="check ${ok ? "ok" : "bad"}"><b>${esc(t("upiTitle"))}: <code>${esc(u)}</code></b>${esc(t(ok ? "upiOk" : "upiBad"))}
        <br><a href="https://siportal.sebi.gov.in/intermediary/sebi-check" target="_blank" rel="noopener">SEBI Check ↗</a></div>`);
    });
    (d.registry || []).forEach((r) => {
      const cls = r.status === "found" ? "ok" : r.status === "not_found" ? "bad" : "warn";
      parts.push(`<div class="check ${cls}"><b>${esc(t("regTitle"))}: <code>${esc(r.reg_no)}</code> (${esc(r.category)})</b>${esc(r.message)}</div>`);
    });
    if ((e.urls || []).length) {
      parts.push(`<div class="check warn"><b>${esc(t("linkTitle"))}</b>${e.urls.map((u) => `<code>${esc(u)}</code>`).join(" ")}</div>`);
    }
    $("checksCard").hidden = !parts.length;
    $("checks").innerHTML = parts.join("");

    $("complaintCard").hidden = !d.complaint;
    if (d.complaint) $("complaint").value = d.complaint.text;

    $("disclaimer").textContent = d.disclaimer;
    $("notes").textContent = (d.notes || []).join(" ");
    $("result").hidden = false;
    $("verdict").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function renderRead(d) {
    const text = d.read_text || "";
    const spans = [];
    const lower = text.toLowerCase();
    d.flags.forEach((f) => {
      const m = (f.match || "").trim();
      if (m.length < 2) return;
      let i = lower.indexOf(m.toLowerCase());
      while (i !== -1) {
        spans.push([i, i + m.length, f.title_t || f.title]);
        i = lower.indexOf(m.toLowerCase(), i + m.length);
      }
    });
    if (!text.trim() || !spans.length) { $("readCard").hidden = true; return; }
    spans.sort((a, b) => a[0] - b[0] || b[1] - a[1]);
    const merged = [];
    spans.forEach((s) => {
      const last = merged[merged.length - 1];
      if (last && s[0] < last[1]) { last[1] = Math.max(last[1], s[1]); if (!last[2].includes(s[2])) last[2] += " · " + s[2]; }
      else merged.push([...s]);
    });
    let html = "", pos = 0;
    merged.forEach(([a, b, title]) => {
      html += esc(text.slice(pos, a)) + `<mark title="${esc(title)}">${esc(text.slice(a, b))}</mark>`;
      pos = b;
    });
    html += esc(text.slice(pos));
    $("readText").innerHTML = html.replace(/\n/g, "<br>");
    $("readCard").hidden = false;
  }

  // ---------- family alert: WhatsApp share (no SMS, so no DLT registration needed) ----------
  function familyLink(d) {
    const verdict = t("risk" + d.risk[0].toUpperCase() + d.risk.slice(1));
    const lines = [
      `${d.risk === "high" ? "⚠️ " : ""}${t("shareIntro")}`,
      `${verdict}`,
      d.summary,
      d.next_move ? `${t("nextMove")}: ${d.next_move}` : "",
      d.mode === "paid" ? t("sharePaid") : t("shareAsk"),
      `${t("brand")}: ${location.origin}`,
    ].filter(Boolean);
    return `https://wa.me/?text=${encodeURIComponent(lines.join("\n\n"))}`;
  }

  // ---------- listen (Amazon Polly) ----------
  $("listenBtn").addEventListener("click", async () => {
    const d = state.last; if (!d) return;
    const text = [t("risk" + d.risk[0].toUpperCase() + d.risk.slice(1)), d.summary, d.next_move, ...(d.actions || []).slice(0, 3)].join(". ");
    $("listenBtn").disabled = true;
    try {
      const res = await fetch(`${API}/speak`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text, lang: d.lang }) });
      const j = await res.json();
      if (j.audio) { $("audio").src = `data:audio/mp3;base64,${j.audio}`; $("audio").play(); }
    } catch (_) { /* ignore */ } finally { $("listenBtn").disabled = false; }
  });

  // ---------- copy complaint ----------
  $("copyBtn").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("complaint").value); } catch (_) { $("complaint").select(); document.execCommand("copy"); }
    $("copyBtn").textContent = t("copied");
    setTimeout(() => { $("copyBtn").textContent = t("copy"); }, 1800);
  });

  // ---------- weekly trends ----------
  async function loadTrends() {
    try {
      const d = await (await fetch(`${API}/trends`)).json();
      if (!d.by_scam || !d.by_scam.length) return;
      const max = Math.max(...d.by_scam.map((x) => x.count));
      $("trendBars").innerHTML = d.by_scam.map((x) => `
        <div class="bar"><div>${esc(x.name)}<div class="track"><div class="fill" style="width:${(x.count / max) * 100}%"></div></div></div><b>${x.count}</b></div>`).join("");
      $("trends").hidden = false;
    } catch (_) { /* trends are optional */ }
  }

  // ---------- installable app + "share to Nivesh Kavach" from WhatsApp ----------
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  let installPrompt = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault(); installPrompt = e; $("installBox").hidden = false;
  });
  $("installBtn").addEventListener("click", async () => {
    if (!installPrompt) return;
    installPrompt.prompt();
    await installPrompt.userChoice.catch(() => {});
    installPrompt = null; $("installBox").hidden = true;
  });
  window.addEventListener("appinstalled", () => { $("installBox").hidden = true; });

  async function loadShared() {
    if (!new URLSearchParams(location.search).has("shared") || !("caches" in window)) return;
    try {
      const cache = await caches.open("nk-share");
      const res = await cache.match("/shared-data");
      if (!res) return;
      const d = await res.json();
      await cache.delete("/shared-data");
      if (d.text) $("text").value = d.text;
      for (const im of (d.images || []).slice(0, 3)) {
        const blob = await (await fetch(im.data)).blob();
        state.images.push(await compress(blob));
      }
      renderThumbs();
      $("sharedNote").hidden = false;
      history.replaceState(null, "", "/");
      if (d.text || (d.images || []).length) check();
    } catch (_) { /* ignore, user can paste instead */ }
  }

  applyI18n();
  loadTrends();
  loadShared();
})();
