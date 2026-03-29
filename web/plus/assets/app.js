(function () {
  const i18n = window.plusI18n || {
    t: function (key) { return key; },
  };

  const state = {
    currentStep: 1,
    verified: false,
    cdk: "",
    accountRaw: "",
    accountName: "",
    statusTone: "warning",
    statusKey: "status_waiting",
    statusLiteral: "",
    chargeMode: "ready",
    chargeTextKey: "charge_ready_text",
    chargeTextLiteral: "",
    successBaseMessage: "",
  };

  const stepCards = Array.from(document.querySelectorAll("[data-step-card]"));
  const step1Panel = document.getElementById("step1Panel");
  const step2Panel = document.getElementById("step2Panel");
  const step3Panel = document.getElementById("step3Panel");
  const successPanel = document.getElementById("successPanel");

  const cdkInput = document.getElementById("cdkInput");
  const accountInput = document.getElementById("accountInput");
  const verifyButton = document.getElementById("verifyButton");
  const parseButton = document.getElementById("parseButton");
  const chargeButton = document.getElementById("chargeButton");
  const backToStep1Button = document.getElementById("backToStep1Button");
  const backToStep2Button = document.getElementById("backToStep2Button");

  const statusCard = document.getElementById("statusCard");
  const statusText = document.getElementById("statusText");
  const maskedCdk = document.getElementById("maskedCdk");
  const recognizedAccount = document.getElementById("recognizedAccount");
  const recognizedAccountFinal = document.getElementById("recognizedAccountFinal");
  const recognizedBox = document.getElementById("recognizedBox");
  const successText = document.getElementById("successText");

  const chargeStateCard = document.getElementById("chargeStateCard");
  const chargeStateIcon = document.getElementById("chargeStateIcon");
  const chargeStateTitle = document.getElementById("chargeStateTitle");
  const chargeStateText = document.getElementById("chargeStateText");
  const toast = document.getElementById("toast");

  if (!step1Panel || !step2Panel || !step3Panel || !verifyButton || !parseButton || !chargeButton) {
    return;
  }

  function t(key, vars) {
    return i18n.t(key, vars || {});
  }

  function showToast(message, type) {
    if (!toast) {
      return;
    }

    toast.textContent = message;
    toast.className = "toast show" + (type ? " " + type : "");
    window.clearTimeout(showToast._timer);
    showToast._timer = window.setTimeout(function () {
      toast.className = "toast";
    }, 3200);
  }

  function setLoading(button, label) {
    button.dataset.originalText = button.dataset.originalText || button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="loader"></span><span>' + label + "</span>";
  }

  function clearLoading(button) {
    if (button.dataset.originalText) {
      button.innerHTML = button.dataset.originalText;
    }
    button.disabled = false;
  }

  function renderStatus() {
    if (!statusCard || !statusText) {
      return;
    }

    statusCard.className = "feedback-banner" + (state.statusTone ? " " + state.statusTone : "");
    statusText.textContent = state.statusKey ? t(state.statusKey) : state.statusLiteral;
  }

  function setStatusKey(key, tone) {
    state.statusKey = key;
    state.statusLiteral = "";
    state.statusTone = tone || "";
    renderStatus();
  }

  function setStatusLiteral(message, tone) {
    state.statusKey = "";
    state.statusLiteral = message;
    state.statusTone = tone || "";
    renderStatus();
  }

  function updateMaskedCdk(value) {
    if (!maskedCdk) {
      return;
    }

    maskedCdk.textContent = value || t("masked_unverified");
  }

  function renderChargeState() {
    if (!chargeStateCard || !chargeStateIcon || !chargeStateTitle || !chargeStateText) {
      return;
    }

    if (state.chargeMode === "processing") {
      chargeStateCard.className = "status-card processing-card";
      chargeStateIcon.className = "status-icon rotating";
      chargeStateIcon.textContent = "↻";
      chargeStateTitle.textContent = t("charge_processing_title");
      chargeStateText.textContent = state.chargeTextKey ? t(state.chargeTextKey) : state.chargeTextLiteral;
      return;
    }

    if (state.chargeMode === "success") {
      chargeStateCard.className = "status-card success-card-state";
      chargeStateIcon.className = "status-icon bounce";
      chargeStateIcon.textContent = "✓";
      chargeStateTitle.textContent = t("charge_success_title");
      chargeStateText.textContent = state.chargeTextKey ? t(state.chargeTextKey) : state.chargeTextLiteral;
      return;
    }

    chargeStateCard.className = "status-card ready-card";
    chargeStateIcon.className = "status-icon pulse";
    chargeStateIcon.textContent = "✓";
    chargeStateTitle.textContent = t("charge_ready_title");
    chargeStateText.textContent = state.chargeTextKey ? t(state.chargeTextKey) : state.chargeTextLiteral;
  }

  function setChargeStateKey(mode, key) {
    state.chargeMode = mode;
    state.chargeTextKey = key;
    state.chargeTextLiteral = "";
    renderChargeState();
  }

  function setChargeStateLiteral(mode, message) {
    state.chargeMode = mode;
    state.chargeTextKey = "";
    state.chargeTextLiteral = message;
    renderChargeState();
  }

  function renderSuccessText() {
    if (!successText) {
      return;
    }

    if (state.successBaseMessage && state.accountName) {
      successText.textContent = state.successBaseMessage + " " + t("current_account_prefix") + " " + state.accountName;
      return;
    }

    successText.textContent = t("success_text_default");
  }

  function setStep(step) {
    state.currentStep = step;
    [step1Panel, step2Panel, step3Panel].forEach(function (panel, index) {
      panel.classList.toggle("is-active", index + 1 === step);
    });

    stepCards.forEach(function (card) {
      const value = Number(card.getAttribute("data-step-card"));
      card.classList.toggle("active", value === step);
      card.classList.toggle("completed", value < step);
    });
  }

  function maskCode(value) {
    const clean = (value || "").trim();
    if (!clean) {
      return t("masked_unverified");
    }

    if (clean.length <= 8) {
      return clean;
    }

    return clean.slice(0, 4) + "••••••" + clean.slice(-4);
  }

  function sanitizeJsonText(value) {
    let result = (value || "")
      .replace(/\uFEFF/g, "")
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
      .replace(/\u00A0/g, " ")
      .replace(/\uFF1A/g, ":")
      .replace(/\uFF0C/g, ",")
      .replace(/[\u201C\u201D\u2018\u2019]/g, '"')
      .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "")
      .trim();

    const start = result.indexOf("{");
    const end = result.lastIndexOf("}");
    if (start !== -1 && end !== -1 && end > start) {
      result = result.slice(start, end + 1);
    }

    return result;
  }

  function parseAccount(value) {
    const cleaned = sanitizeJsonText(value);
    const candidates = [
      cleaned,
      cleaned.replace(/,\s*([\]}])/g, "$1"),
      cleaned.replace(/,\s*([\]}])/g, "$1").replace(/{\s+"/g, '{"').replace(/,\s+"/g, ',"'),
    ];

    let parsed = null;
    for (let index = 0; index < candidates.length; index += 1) {
      try {
        parsed = JSON.parse(candidates[index]);
        break;
      } catch (error) {
        parsed = null;
      }
    }

    if (!parsed || typeof parsed !== "object") {
      return { ok: false, message: t("toast_account_format_error") };
    }

    const user = parsed.user || {};
    const accountName = user.email || user.name || parsed.email || "";
    if (!accountName) {
      return { ok: false, message: t("toast_account_not_found") };
    }

    return {
      ok: true,
      raw: cleaned,
      accountName: accountName,
    };
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    const text = await response.text();
    let data = {};
    try {
      data = text ? JSON.parse(text) : {};
    } catch (error) {
      throw new Error(t("interface_format_error"));
    }

    return {
      ok: response.ok,
      status: response.status,
      data: data,
    };
  }

  async function verifyCdk() {
    const cdk = (cdkInput.value || "").trim().toUpperCase();
    if (!cdk) {
      showToast(t("toast_enter_cdk"), "error");
      cdkInput.focus();
      return;
    }

    state.cdk = cdk;
    updateMaskedCdk(maskCode(cdk));

    setLoading(verifyButton, t("toast_verify_loading"));
    setStatusKey("toast_verifying", "warning");

    try {
      const result = await postJson("/api/white/vip/c", { cdk: cdk });
      if (result.data && result.data.code === 1) {
        state.verified = true;
        setStep(2);
        setStatusKey("toast_verify_success_status", "success");
        showToast(t("toast_verify_success"), "success");
        accountInput.focus();
        return;
      }

      const message = (result.data && result.data.message) || t("toast_verify_fail");
      setStatusLiteral(message, "error");
      showToast(message, "error");
    } catch (error) {
      setStatusKey("toast_verify_unavailable", "error");
      showToast(error.message || t("toast_verify_unavailable"), "error");
    } finally {
      clearLoading(verifyButton);
    }
  }

  function identifyAccount() {
    if (!state.verified) {
      showToast(t("toast_need_verify"), "error");
      setStep(1);
      return;
    }

    const parsed = parseAccount(accountInput.value || "");
    if (!parsed.ok) {
      if (recognizedBox) {
        recognizedBox.hidden = true;
      }
      if (recognizedAccount) {
        recognizedAccount.textContent = t("recognized_waiting");
      }
      if (recognizedAccountFinal) {
        recognizedAccountFinal.textContent = t("recognized_waiting");
      }
      setStatusLiteral(parsed.message, "error");
      showToast(parsed.message, "error");
      return;
    }

    state.accountRaw = parsed.raw;
    state.accountName = parsed.accountName;
    if (recognizedAccount) {
      recognizedAccount.textContent = parsed.accountName;
    }
    if (recognizedAccountFinal) {
      recognizedAccountFinal.textContent = parsed.accountName;
    }
    if (recognizedBox) {
      recognizedBox.hidden = false;
    }

    setStep(3);
    setStatusKey("toast_account_ready", "success");
    setChargeStateKey("ready", "charge_ready_text");
    showToast(t("toast_account_success"), "success");
  }

  async function submitCharge() {
    if (!state.verified || !state.cdk) {
      showToast(t("toast_need_verify"), "error");
      setStep(1);
      return;
    }

    if (!state.accountRaw || !state.accountName) {
      showToast(t("toast_need_account"), "error");
      setStep(2);
      return;
    }

    setLoading(chargeButton, t("toast_charge_loading"));
    setStatusKey("toast_charge_submitting", "warning");
    setChargeStateKey("processing", "charge_processing_text");

    try {
      const result = await postJson("/api/white/vip/r", {
        cdk: state.cdk,
        account: state.accountRaw,
        type: "gpt",
      });

      if (result.data && result.data.code === 1) {
        setChargeStateKey("success", "toast_charge_submit_success");
        if (successPanel) {
          successPanel.hidden = false;
          successPanel.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        state.successBaseMessage = (result.data && result.data.message) || t("toast_charge_success");
        renderSuccessText();
        setStatusKey("toast_charge_success_status", "success");
        showToast(t("toast_charge_success"), "success");
        return;
      }

      const message = (result.data && result.data.message) || t("toast_charge_fail");
      setChargeStateKey("ready", "toast_charge_retry");
      setStatusLiteral(message, "error");
      showToast(message, "error");
    } catch (error) {
      setChargeStateKey("ready", "toast_interface_retry");
      setStatusKey("toast_charge_unavailable", "error");
      showToast(error.message || t("toast_charge_unavailable"), "error");
    } finally {
      clearLoading(chargeButton);
    }
  }

  verifyButton.addEventListener("click", verifyCdk);
  parseButton.addEventListener("click", identifyAccount);
  chargeButton.addEventListener("click", submitCharge);

  backToStep1Button.addEventListener("click", function () {
    setStep(1);
    setStatusKey("toast_back_step_1", "warning");
  });

  backToStep2Button.addEventListener("click", function () {
    setStep(2);
    setStatusKey("toast_back_step_2", "warning");
    setChargeStateKey("ready", "charge_ready_text");
  });

  cdkInput.addEventListener("input", function () {
    cdkInput.value = (cdkInput.value || "").replace(/\s+/g, "").toUpperCase();
  });

  cdkInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter") {
      event.preventDefault();
      verifyCdk();
    }
  });

  accountInput.addEventListener("paste", function () {
    window.setTimeout(function () {
      const parsed = parseAccount(accountInput.value || "");
      if (!parsed.ok) {
        return;
      }

      state.accountRaw = parsed.raw;
      state.accountName = parsed.accountName;
      if (recognizedAccount) {
        recognizedAccount.textContent = parsed.accountName;
      }
      if (recognizedAccountFinal) {
        recognizedAccountFinal.textContent = parsed.accountName;
      }
      if (recognizedBox) {
        recognizedBox.hidden = false;
      }
      setStatusKey("toast_auto_recognized", "success");
    }, 180);
  });

  window.addEventListener("plus-language-change", function () {
    if (!state.cdk) {
      updateMaskedCdk("");
    }

    if (!state.accountName) {
      if (recognizedAccount) {
        recognizedAccount.textContent = t("recognized_waiting");
      }
      if (recognizedAccountFinal) {
        recognizedAccountFinal.textContent = t("recognized_waiting");
      }
    }

    renderStatus();
    renderChargeState();
    renderSuccessText();
  });

  setStep(1);
  updateMaskedCdk("");
  setStatusKey("status_waiting", "warning");
  setChargeStateKey("ready", "charge_ready_text");
  renderSuccessText();
})();
