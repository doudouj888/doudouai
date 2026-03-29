(function () {
  const labels = {
    emptyInitial: "아직 조회 결과가 없습니다.",
    emptyNoData: "조회된 결과가 없습니다. 카드키 형식이 올바른지 확인해 주세요.",
    statusUsed: "사용됨",
    statusUnused: "미사용",
    statusInvalid: "무효",
    needQuery: "먼저 카드키를 하나 이상 입력해 주세요.",
    queryLoading: "조회 중",
    querySuccess: "조회가 완료되었습니다.",
    queryFail: "조회에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    queryUnavailable: "조회 서버에 일시적으로 연결할 수 없습니다.",
    copyEmpty: "복사할 결과가 없습니다.",
    copyNoMatch: "조건에 맞는 카드키가 없습니다.",
    copySuccess: "{count}개의 카드키를 복사했습니다.",
    copyFail: "복사에 실패했습니다. 직접 선택해서 복사해 주세요.",
    interfaceFormatError: "서버 응답 형식이 올바르지 않습니다.",
  };

  const queryInput = document.getElementById("queryInput");
  const queryButton = document.getElementById("queryButton");
  const fillDemoButton = document.getElementById("fillDemoButton");
  const tableWrap = document.getElementById("tableWrap");
  const tableBody = document.getElementById("tableBody");
  const emptyState = document.getElementById("emptyState");
  const statTotal = document.getElementById("statTotal");
  const statUnused = document.getElementById("statUnused");
  const statUsed = document.getElementById("statUsed");
  const statInvalid = document.getElementById("statInvalid");
  const copyButtons = Array.from(document.querySelectorAll("[data-copy-type]"));
  const toast = document.getElementById("toast");

  let currentRows = [];

  function format(template, vars) {
    return String(template).replace(/\{(\w+)\}/g, function (_, key) {
      return Object.prototype.hasOwnProperty.call(vars, key) ? vars[key] : "";
    });
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

  function setLoading(button, loadingText) {
    button.dataset.originalText = button.dataset.originalText || button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<span class="loader"></span><span>' + loadingText + "</span>";
  }

  function clearLoading(button) {
    if (button.dataset.originalText) {
      button.innerHTML = button.dataset.originalText;
    }
    button.disabled = false;
  }

  function normalizeStatus(status) {
    const map = {
      used: "used",
      not_used: "not_used",
      unused: "not_used",
      invalid: "invalid",
    };
    return map[status] || status || "invalid";
  }

  function statusLabel(status) {
    const map = {
      used: labels.statusUsed,
      not_used: labels.statusUnused,
      invalid: labels.statusInvalid,
    };
    return map[status] || status;
  }

  function updateStats(rows) {
    const total = rows.length;
    const unused = rows.filter(function (row) { return normalizeStatus(row.useStatus) === "not_used"; }).length;
    const used = rows.filter(function (row) { return normalizeStatus(row.useStatus) === "used"; }).length;
    const invalid = rows.filter(function (row) { return normalizeStatus(row.useStatus) === "invalid"; }).length;

    statTotal.textContent = String(total);
    statUnused.textContent = String(unused);
    statUsed.textContent = String(used);
    statInvalid.textContent = String(invalid);
  }

  function renderRows(rows) {
    currentRows = rows.slice();
    updateStats(rows);

    if (!rows.length) {
      tableWrap.hidden = true;
      emptyState.hidden = false;
      emptyState.textContent = labels.emptyNoData;
      tableBody.innerHTML = "";
      return;
    }

    tableBody.innerHTML = rows.map(function (row, index) {
      const status = normalizeStatus(row.useStatus);
      const cdk = row.cdk || row.carmi || "-";
      const account = row.account || "-";
      const usedAt = row.usedAt || "-";

      return [
        "<tr>",
        "<td>", String(index + 1), "</td>",
        "<td><code>", cdk, "</code></td>",
        '<td><span class="status-pill ', status, '">', statusLabel(status), "</span></td>",
        "<td>", usedAt, "</td>",
        "<td>", account, "</td>",
        "</tr>"
      ].join("");
    }).join("");

    emptyState.hidden = true;
    tableWrap.hidden = false;
  }

  function localizeServerMessage(message, fallback) {
    if (!message) {
      return fallback;
    }

    const source = String(message);
    if (source.includes("获取数据成功")) {
      return labels.querySuccess;
    }
    if (source.includes("卡密错误") || source.includes("卡密有误")) {
      return "카드키가 올바르지 않습니다.";
    }
    if (source.includes("请求过于频繁")) {
      return "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.";
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
      throw new Error(labels.interfaceFormatError);
    }

    return {
      ok: response.ok,
      status: response.status,
      data: data,
    };
  }

  function parseLines(value) {
    return (value || "")
      .split(/\r?\n/)
      .map(function (item) { return item.trim(); })
      .filter(function (item) { return Boolean(item); });
  }

  async function queryCdks() {
    const lines = parseLines(queryInput.value);
    if (!lines.length) {
      showToast(labels.needQuery, "error");
      queryInput.focus();
      return;
    }

    setLoading(queryButton, labels.queryLoading);
    try {
      const result = await postJson("/api/white/vip/cdks", lines);
      if (result.data && result.data.code === 1) {
        renderRows(result.data.data || []);
        showToast(labels.querySuccess, "success");
        return;
      }

      const message = localizeServerMessage(result.data && result.data.message, labels.queryFail);
      showToast(message, "error");
    } catch (error) {
      showToast(error.message || labels.queryUnavailable, "error");
    } finally {
      clearLoading(queryButton);
    }
  }

  async function copyByType(type, button) {
    if (!currentRows.length) {
      showToast(labels.copyEmpty, "error");
      return;
    }

    let rows = currentRows;
    if (type !== "all") {
      rows = currentRows.filter(function (row) {
        return normalizeStatus(row.useStatus) === type;
      });
    }

    if (!rows.length) {
      showToast(labels.copyNoMatch, "error");
      return;
    }

    const text = rows.map(function (row) { return row.cdk || row.carmi || ""; }).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      copyButtons.forEach(function (item) { item.classList.remove("is-active"); });
      button.classList.add("is-active");
      showToast(format(labels.copySuccess, { count: rows.length }), "success");
      window.setTimeout(function () {
        button.classList.remove("is-active");
      }, 1600);
    } catch (error) {
      showToast(labels.copyFail, "error");
    }
  }

  queryButton.addEventListener("click", queryCdks);
  fillDemoButton.addEventListener("click", function () {
    queryInput.value = ["FMJWFQA06YTXXXX", "FMJWFQA06YTYYYY", "FMJWFQA06YTZZZZ"].join("\n");
  });

  copyButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      copyByType(button.getAttribute("data-copy-type"), button);
    });
  });

  emptyState.textContent = labels.emptyInitial;
})();
