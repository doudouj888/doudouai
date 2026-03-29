(function () {
  const messages = {
    maskedUnverified: "미확인",
    statusWaiting: "카드키를 입력하고 확인을 시작해 주세요.",
    verifyLoading: "확인 중",
    verifying: "카드키를 확인하고 있습니다. 잠시만 기다려 주세요.",
    verifySuccessStatus: "카드키 확인이 완료되었습니다. 계정 연결 단계로 이동합니다.",
    verifySuccessToast: "카드키 확인이 완료되었습니다.",
    verifyFail: "카드키 확인에 실패했습니다. 다시 시도해 주세요.",
    verifyUnavailable: "확인 서버에 일시적으로 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
    enterCdk: "먼저 카드키를 입력해 주세요.",
    needVerify: "먼저 카드키 확인을 완료해 주세요.",
    accountFormatError: "계정 정보 형식이 올바르지 않습니다. 다시 가져와서 전체 내용을 붙여넣어 주세요.",
    accountNotFound: "계정을 인식하지 못했습니다. 복사한 계정 정보가 완전한지 확인해 주세요.",
    accountReadyStatus: "계정을 인식했습니다. 마지막 단계로 이동합니다.",
    accountSuccessToast: "계정을 정상적으로 인식했습니다.",
    recognizedWaiting: "대기 중",
    needAccount: "먼저 계정 정보를 인식해 주세요.",
    chargeLoading: "처리 중",
    chargeSubmitting: "충전 요청을 전송하고 있습니다. 잠시만 기다려 주세요.",
    chargeReadyTitle: "준비 완료",
    chargeReadyText: "인식된 계정이 맞으면 충전을 시작할 수 있습니다.",
    chargeProcessingTitle: "충전 진행 중",
    chargeProcessingText: "서버에서 충전 요청을 처리하고 있습니다. 잠시만 기다려 주세요.",
    chargeSuccessTitle: "충전 완료",
    chargeSuccessText: "계정 업그레이드 요청이 정상적으로 접수되었습니다.",
    chargeSubmitSuccessStatus: "충전 요청이 정상적으로 접수되었습니다.",
    chargeSuccessToast: "충전이 완료되었습니다.",
    chargeFail: "충전에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    chargeRetry: "계정 정보를 다시 확인한 뒤 재시도해 주세요.",
    chargeUnavailable: "충전 서버에 일시적으로 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
    interfaceFormatError: "서버 응답 형식이 올바르지 않습니다.",
    backStep1: "카드키 확인 단계로 돌아왔습니다.",
    backStep2: "계정 연결 단계로 돌아왔습니다.",
    autoRecognized: "붙여넣은 내용에서 계정을 자동으로 인식했습니다.",
    currentAccountPrefix: "현재 인식된 계정:",
  };

  const state = {
    verified: false,
    cdk: "",
    accountRaw: "",
    accountName: "",
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

  function showToast(message, type) {
    if (!toast) {
      return;
    }

    toast.textContent = message;
    toast.className = "toast show" + (type ? " " + type : "");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(function () {
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

  function setStatus(message, tone) {
    if (!statusCard || !statusText) {
      return;
    }

    statusCard.className = "feedback-banner" + (tone ? " " + tone : "");
    statusText.textContent = message;
  }

  function updateMaskedCode(value) {
    if (!maskedCdk) {
      return;
    }

    maskedCdk.textContent = value || messages.maskedUnverified;
  }

  function setChargeState(mode, message) {
    if (!chargeStateCard || !chargeStateIcon || !chargeStateTitle || !chargeStateText) {
      return;
    }

    if (mode === "processing") {
      chargeStateCard.className = "status-card processing-card";
      chargeStateIcon.className = "status-icon rotating";
      chargeStateIcon.textContent = "↻";
      chargeStateTitle.textContent = messages.chargeProcessingTitle;
      chargeStateText.textContent = message || messages.chargeProcessingText;
      return;
    }

    if (mode === "success") {
      chargeStateCard.className = "status-card success-card-state";
      chargeStateIcon.className = "status-icon bounce";
      chargeStateIcon.textContent = "✓";
      chargeStateTitle.textContent = messages.chargeSuccessTitle;
      chargeStateText.textContent = message || messages.chargeSuccessText;
      return;
    }

    chargeStateCard.className = "status-card ready-card";
    chargeStateIcon.className = "status-icon pulse";
    chargeStateIcon.textContent = "✓";
    chargeStateTitle.textContent = messages.chargeReadyTitle;
    chargeStateText.textContent = message || messages.chargeReadyText;
  }

  function setStep(step) {
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
      return messages.maskedUnverified;
    }

    if (clean.length <= 8) {
      return clean;
    }

    return clean.slice(0, 4) + "******" + clean.slice(-4);
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
      return { ok: false, message: messages.accountFormatError };
    }

    const user = parsed.user || {};
    const accountName = user.email || user.name || parsed.email || "";
    if (!accountName) {
      return { ok: false, message: messages.accountNotFound };
    }

    return {
      ok: true,
      raw: cleaned,
      accountName: accountName,
    };
  }

  function localizeServerMessage(message, fallback) {
    if (!message) {
      return fallback;
    }

    const source = String(message);
    if (source.includes("卡密错误") || source.includes("卡密有误")) {
      return "카드키가 올바르지 않습니다.";
    }
    if (source.includes("卡密不存在") || source.includes("卡密无效")) {
      return "유효하지 않은 카드키입니다.";
    }
    if (source.includes("卡密已使用")) {
      return "이미 사용된 카드키입니다.";
    }
    if (source.includes("请求过于频繁")) {
      return "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.";
    }
    if (source.includes("充值成功")) {
      return messages.chargeSuccessToast;
    }

    return source;
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
      throw new Error(messages.interfaceFormatError);
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
      showToast(messages.enterCdk, "error");
      cdkInput.focus();
      return;
    }

    state.cdk = cdk;
    updateMaskedCode(maskCode(cdk));

    setLoading(verifyButton, messages.verifyLoading);
    setStatus(messages.verifying, "warning");

    try {
      const result = await postJson("/api/white/vip/c", { cdk: cdk });
      if (result.data && result.data.code === 1) {
        state.verified = true;
        setStep(2);
        setStatus(messages.verifySuccessStatus, "success");
        showToast(messages.verifySuccessToast, "success");
        accountInput.focus();
        return;
      }

      const message = localizeServerMessage(result.data && result.data.message, messages.verifyFail);
      setStatus(message, "error");
      showToast(message, "error");
    } catch (error) {
      setStatus(messages.verifyUnavailable, "error");
      showToast(error.message || messages.verifyUnavailable, "error");
    } finally {
      clearLoading(verifyButton);
    }
  }

  function identifyAccount() {
    if (!state.verified) {
      showToast(messages.needVerify, "error");
      setStep(1);
      return;
    }

    const parsed = parseAccount(accountInput.value || "");
    if (!parsed.ok) {
      if (recognizedBox) {
        recognizedBox.hidden = true;
      }
      if (recognizedAccount) {
        recognizedAccount.textContent = messages.recognizedWaiting;
      }
      if (recognizedAccountFinal) {
        recognizedAccountFinal.textContent = messages.recognizedWaiting;
      }
      setStatus(parsed.message, "error");
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
    setStatus(messages.accountReadyStatus, "success");
    setChargeState("ready", messages.chargeReadyText);
    showToast(messages.accountSuccessToast, "success");
  }

  function renderSuccessText() {
    if (!successText) {
      return;
    }

    if (state.successBaseMessage && state.accountName) {
      successText.textContent = state.successBaseMessage + " " + messages.currentAccountPrefix + " " + state.accountName;
      return;
    }

    successText.textContent = messages.chargeSuccessText;
  }

  async function submitCharge() {
    if (!state.verified || !state.cdk) {
      showToast(messages.needVerify, "error");
      setStep(1);
      return;
    }

    if (!state.accountRaw || !state.accountName) {
      showToast(messages.needAccount, "error");
      setStep(2);
      return;
    }

    setLoading(chargeButton, messages.chargeLoading);
    setStatus(messages.chargeSubmitting, "warning");
    setChargeState("processing", messages.chargeProcessingText);

    try {
      const result = await postJson("/api/white/vip/r", {
        cdk: state.cdk,
        account: state.accountRaw,
        type: "gpt",
      });

      if (result.data && result.data.code === 1) {
        setChargeState("success", messages.chargeSuccessText);
        if (successPanel) {
          successPanel.hidden = false;
          successPanel.scrollIntoView({ behavior: "smooth", block: "start" });
        }
        state.successBaseMessage = localizeServerMessage(result.data && result.data.message, messages.chargeSuccessToast);
        renderSuccessText();
        setStatus(messages.chargeSubmitSuccessStatus, "success");
        showToast(messages.chargeSuccessToast, "success");
        return;
      }

      const message = localizeServerMessage(result.data && result.data.message, messages.chargeFail);
      setChargeState("ready", messages.chargeRetry);
      setStatus(message, "error");
      showToast(message, "error");
    } catch (error) {
      setChargeState("ready", messages.chargeRetry);
      setStatus(messages.chargeUnavailable, "error");
      showToast(error.message || messages.chargeUnavailable, "error");
    } finally {
      clearLoading(chargeButton);
    }
  }

  verifyButton.addEventListener("click", verifyCdk);
  parseButton.addEventListener("click", identifyAccount);
  chargeButton.addEventListener("click", submitCharge);

  backToStep1Button.addEventListener("click", function () {
    setStep(1);
    setStatus(messages.backStep1, "warning");
  });

  backToStep2Button.addEventListener("click", function () {
    setStep(2);
    setStatus(messages.backStep2, "warning");
    setChargeState("ready", messages.chargeReadyText);
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
      setStatus(messages.autoRecognized, "success");
    }, 180);
  });

  setStep(1);
  updateMaskedCode("");
  setStatus(messages.statusWaiting, "warning");
  setChargeState("ready", messages.chargeReadyText);
  renderSuccessText();
})();
