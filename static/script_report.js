// static/script_report.js
// Report UI: download button hides on click + Home button in header that resets to main landing
document.addEventListener("DOMContentLoaded", () => {
  console.log("📊 Report Agent script loaded (home + vanish button)");

  const chatBody = document.getElementById("chat-body");
  const sendBtn = document.getElementById("sendBtn");
  const userInput = document.getElementById("userInput");
  const header = document.querySelector(".chat-header");

  if (!chatBody) return console.error("Missing #chat-body - report UI won't work.");
  if (!sendBtn) return console.error("Missing #sendBtn.");
  if (!userInput) return console.error("Missing #userInput.");
  if (!header) console.warn("Missing .chat-header - home button will be appended to body.");

  // track whether we're on the main landing screen
  let isLanding = true;

  function addMessage(content, sender = "bot") {
    const msg = document.createElement("div");
    msg.classList.add(sender === "bot" ? "bot-message" : "user-message");
    msg.innerHTML = String(content).replace(/\n/g, "<br/>");
    chatBody.appendChild(msg);
    chatBody.scrollTop = chatBody.scrollHeight;
  }

  function parseFilenameFromDisposition(disposition) {
    if (!disposition) return null;
    let match = disposition.match(/filename\*=UTF-8''([^;]+)/);
    if (match && match[1]) return decodeURIComponent(match[1]);
    match = disposition.match(/filename="([^"]+)"/);
    if (match && match[1]) return match[1];
    match = disposition.match(/filename=([^;]+)/);
    if (match && match[1]) return match[1];
    return null;
  }

  // create or return the header home button
  function ensureHomeButton() {
    let hb = document.getElementById("homeBtnReport");
    if (hb) return hb;

    // create a small home button and append to .chat-header (or body as fallback)
    hb = document.createElement("button");
    hb.id = "homeBtnReport";
    hb.type = "button";
    hb.title = "Home";
    hb.textContent = "Home";
    // simple style — your CSS can override this selector
    hb.style.cssText = "padding:6px 10px;border-radius:8px;border:none;background:#0078ff;color:#fff;cursor:pointer;font-weight:600;display:none;";

    if (header) {
      header.appendChild(hb);
    } else {
      // fallback placement
      document.body.insertBefore(hb, document.body.firstChild);
    }

    // click handler resets to landing
    hb.addEventListener("click", (e) => {
      e.preventDefault();
      initReportChat(); // reset UI to landing
    });

    return hb;
  }

  // Modal builder (same as before, but exposes close for home logic)
  function openCredentialModal(defaultFormat = "csv") {
    if (document.getElementById("cred-modal-overlay")) {
      console.warn("Modal already open");
      return document.getElementById("cred-modal-overlay");
    }

    const overlay = document.createElement("div");
    overlay.id = "cred-modal-overlay";
    overlay.className = "cred-overlay";
    overlay.innerHTML = `
      <div id="cred-modal" class="cred-box" role="dialog" aria-modal="true" aria-labelledby="cred-title">
        <h3 id="cred-title">Authenticate to Download Report</h3>
        <input id="cred-user" type="text" placeholder="Username" autocomplete="username" />
        <input id="cred-pass" type="password" placeholder="Password" autocomplete="current-password" />
        <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px;">
          <button id="cred-cancel" type="button">Cancel</button>
          <button id="cred-submit" type="button">Download</button>
        </div>
        <div id="cred-error" style="color:#b00020;margin-top:8px;min-height:18px;"></div>
      </div>
    `;
    document.body.appendChild(overlay);

    const cancelBtn = document.getElementById("cred-cancel");
    const submitBtn = document.getElementById("cred-submit");
    const usernameInput = document.getElementById("cred-user");
    const passwordInput = document.getElementById("cred-pass");
    const errorDiv = document.getElementById("cred-error");

    function closeModal() {
      try {
        submitBtn.removeEventListener("click", onSubmit);
        cancelBtn.removeEventListener("click", onCancel);
        overlay.remove();
      } catch (e) {}
    }

    function onCancel(e) {
      e?.preventDefault();
      addMessage("Report download cancelled.", "bot");
      closeModal();
      // show home button so user can reset to landing (where download button will reappear)
      const hb = ensureHomeButton();
      hb.style.display = "inline-block";
      isLanding = false;
    }

    async function onSubmit(e) {
      e?.preventDefault();
      errorDiv.textContent = "";
      const username = usernameInput.value.trim();
      const password = passwordInput.value;

      if (!username || !password) {
        errorDiv.textContent = "Please enter both username and password.";
        usernameInput.focus();
        return;
      }

      submitBtn.disabled = true;
      cancelBtn.disabled = true;
      submitBtn.textContent = "Downloading...";

      addMessage("Authenticating and preparing report...", "bot");

      try {
        const res = await fetch("/api/report", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password, format: defaultFormat })
        });

        if (!res.ok) {
          let body = {};
          try { body = await res.json(); } catch (e) {}
          const errMsg = body.error || `Server returned ${res.status}`;
          errorDiv.textContent = errMsg;
          addMessage(`⚠️ ${errMsg}`, "bot");
          submitBtn.disabled = false;
          cancelBtn.disabled = false;
          submitBtn.textContent = "Download";
          // show home button so user can return
          const hb = ensureHomeButton();
          hb.style.display = "inline-block";
          isLanding = false;
          return;
        }

        const blob = await res.blob();
        const disposition = res.headers.get("content-disposition");
        const filename = parseFilenameFromDisposition(disposition) || (defaultFormat === "xlsx" ? "report.xlsx" : "report.csv");

        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();

        URL.revokeObjectURL(url);
        closeModal();
        addMessage(`✅ Report "${filename}" downloaded successfully!`, "bot");

        // After successful download, show home button so user can return
        const hb = ensureHomeButton();
        hb.style.display = "inline-block";
        isLanding = false;
      } catch (err) {
        console.error("Error fetching report:", err);
        errorDiv.textContent = "Network error: " + (err.message || err);
        addMessage("❌ Failed to download report. See console for details.", "bot");
        submitBtn.disabled = false;
        cancelBtn.disabled = false;
        submitBtn.textContent = "Download";
        const hb = ensureHomeButton();
        hb.style.display = "inline-block";
        isLanding = false;
      }
    }

    cancelBtn.addEventListener("click", onCancel);
    submitBtn.addEventListener("click", onSubmit);

    function keyHandler(e) {
      if (e.key === "Enter") onSubmit(e);
      else if (e.key === "Escape") onCancel(e);
    }
    overlay.addEventListener("keydown", keyHandler);
    usernameInput.focus();

    return overlay;
  }

  // build landing UI (welcome + download button). Hides header home button while landing.
  function initReportChat() {
    isLanding = true;

    // hide home button while on landing
    const hb = ensureHomeButton();
    hb.style.display = "none";

    chatBody.innerHTML = "";
    addMessage("👋 Welcome to the Olyph AI Employee.", "bot");

    // avoid dupes - if element exists remove it first
    const existing = chatBody.querySelector(".report-action");
    if (existing) existing.remove();

    const action = document.createElement("div");
    action.className = "report-action";
    action.style = "display:flex;gap:8px;align-items:center;margin-top:8px;";

    const btn = document.createElement("button");
    btn.type = "button";
    btn.id = "reportDownloadBtn";
    btn.textContent = "Download Report";
    btn.style = "padding:10px 14px;border-radius:8px;border:none;background:#1e90ff;color:#fff;cursor:pointer;font-weight:600;";

    const hint = document.createElement("div");
    hint.style = "font-size:13px;color:#123;opacity:0.85";

    action.appendChild(btn);
    action.appendChild(hint);
    chatBody.appendChild(action);
    chatBody.scrollTop = chatBody.scrollHeight;

    // attach click handler: hides btn immediately, opens modal
    btn.addEventListener("click", () => {
      // hide (vanish) the button immediately
      btn.style.display = "none";
      addMessage("Opening authentication modal...", "bot");
      openCredentialModal("csv");
      // reveal home button so user can navigate back if needed
      const hb2 = ensureHomeButton();
      hb2.style.display = "inline-block";
      isLanding = false;
    });
  }

  // typed command handling (keeps same semantics)
  sendBtn.addEventListener("click", () => {
    const msg = String(userInput.value || "").trim();
    if (!msg) return;
    addMessage(msg, "user");
    userInput.value = "";

    if (msg.toLowerCase().includes("download")) {
      // hide download button if present
      const btn = document.getElementById("reportDownloadBtn");
      if (btn) btn.style.display = "none";
      addMessage("Opening authentication modal...", "bot");
      openCredentialModal("csv");
      const hb = ensureHomeButton();
      hb.style.display = "inline-block";
      isLanding = false;
    } else {
      addMessage("Type 'download' or click the Download Report button to begin.", "bot");
    }
  });

  userInput.addEventListener("keypress", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendBtn.click();
    }
  });

  // initialize landing
  initReportChat();
  console.log("Report UI initialized. Home button created.");
});
