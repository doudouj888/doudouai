(function () {
  const i18n = window.plusI18n || {
    t: function (key) { return key; },
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

  function t(key, vars) {
    return i18n.t(key, vars || {});
  }

  function showToast(message, type) {
    toast.textContent = message;
    toast.className = "toast show" + (type ? " " + type : "");
    window.clearTimeout(showToast._timer);
    showToast._timer = window.setTimeout(function () {
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
    const labels = {
      used: t("status_used"),
      not_used: t("status_unused"),
      invalid: t("status_invalid"),
    };
    return labels[status] || status;
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
      emptyState.textContent = t("empty_no_data");
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

  function parseLines(value) {
    return (value || "")
      .split(/\r?\n/)
      .map(function (item) { return item.trim(); })
      .filter(function (item) { return Boolean(item); });
  }

  async function queryCdks() {
    const lines = parseLines(queryInput.value);
    if (!lines.length) {
      showToast(t("toast_need_query"), "error");
      queryInput.focus();
      return;
    }

    setLoading(queryButton, t("toast_query_loading"));
    try {
      const result = await postJson("/api/white/vip/cdks", lines);
      if (result.data && result.data.code === 1) {
        renderRows(result.data.data || []);
        showToast(t("toast_query_success"), "success");
        return;
      }

      const message = (result.data && result.data.message) || t("toast_query_fail");
      showToast(message, "error");
    } catch (error) {
      showToast(error.message || t("toast_query_unavailable"), "error");
    } finally {
      clearLoading(queryButton);
    }
  }

  async function copyByType(type, button) {
    if (!currentRows.length) {
      showToast(t("toast_copy_empty"), "error");
      return;
    }

    let rows = currentRows;
    if (type !== "all") {
      rows = currentRows.filter(function (row) {
        return normalizeStatus(row.useStatus) === type;
      });
    }

    if (!rows.length) {
      showToast(t("toast_copy_no_match"), "error");
      return;
    }

    const text = rows.map(function (row) { return row.cdk || row.carmi || ""; }).join("\n");
    try {
      await navigator.clipboard.writeText(text);
      copyButtons.forEach(function (item) { item.classList.remove("is-active"); });
      button.classList.add("is-active");
      showToast(t("toast_copy_success", { count: rows.length }), "success");
      window.setTimeout(function () {
        button.classList.remove("is-active");
      }, 1600);
    } catch (error) {
      showToast(t("toast_copy_fail"), "error");
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

  window.addEventListener("plus-language-change", function () {
    if (currentRows.length) {
      renderRows(currentRows);
      return;
    }

    emptyState.textContent = t("empty_initial");
  });
})();
