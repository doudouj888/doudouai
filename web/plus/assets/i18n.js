(function () {
  const STORAGE_KEY = "plus-site-language";
  const supported = ["zh", "ko"];

  const dictionaries = {
    zh: {
      recharge: {
        doc_title: "账号充值",
        doc_description: "请按照以下步骤完成充值。",
        page_title: "账号充值",
        page_subtitle: "请按照以下步骤完成充值",
        view_tutorial: "如有疑问可查看教程",
        cdk_query: "卡密查询",
        step_1: "卡密校验",
        step_2: "账户绑定",
        step_3: "完成升级",
        current_status: "当前状态",
        masked_unverified: "未验证",
        status_waiting: "等待输入兑换码并开始验证。",
        cdk_label: "内部兑换码",
        cdk_placeholder: "请输入兑换码",
        verify_button: "开始验证",
        bind_title: "账户绑定",
        bind_subtitle: "验证通过后，请获取并粘贴完整的账号信息。",
        banner_tip: "提示",
        banner_text: "获取之前，请先切换到个人空间，不要在团队里。",
        get_account: "点击获取账号",
        full_tutorial: "查看完整教程",
        account_placeholder: "在此处粘贴您的账号信息...",
        recognized_label: "已识别账号",
        recognized_waiting: "等待识别",
        parse_button: "确认并继续",
        confirm_title: "确认充值",
        confirm_subtitle: "确认信息无误后，再提交充值请求。",
        charge_ready_title: "准备就绪",
        charge_ready_text: "确认识别到的账号正确后，再开始充值。",
        charge_processing_title: "充值进行中",
        charge_processing_text: "正在处理您的充值请求，请稍候...",
        charge_success_title: "充值成功",
        charge_success_text: "您的账号已成功升级。",
        current_account: "当前识别账号",
        charge_button: "开始充值",
        success_title: "充值成功",
        success_text_default: "充值请求已提交成功。",
        back_aria: "返回上一步",
        toast_enter_cdk: "请先输入兑换码。",
        toast_verifying: "正在验证兑换码，请稍候。",
        toast_verify_loading: "验证中",
        toast_verify_success_status: "兑换码验证成功，请继续绑定账号。",
        toast_verify_success: "兑换码验证成功。",
        toast_verify_fail: "兑换码验证失败，请检查后重试。",
        toast_verify_unavailable: "验证接口暂时不可用，请稍后重试。",
        toast_need_verify: "请先完成兑换码验证。",
        toast_account_format_error: "账号信息格式错误，请重新获取并完整粘贴。",
        toast_account_not_found: "未识别到账号，请确认粘贴的是完整账号信息。",
        toast_account_ready: "已识别账号，可以开始充值。",
        toast_account_success: "账号识别成功。",
        toast_need_account: "请先识别账号信息。",
        toast_charge_loading: "处理中",
        toast_charge_submitting: "正在提交充值请求，请稍候。",
        toast_charge_submit_success: "您的账号已成功提交充值。",
        toast_charge_success_status: "充值提交成功。",
        toast_charge_success: "充值成功。",
        toast_charge_fail: "充值失败，请稍后重试。",
        toast_charge_retry: "请确认账号信息无误后重新提交。",
        toast_charge_unavailable: "充值接口暂时不可用，请稍后重试。",
        toast_interface_retry: "接口暂时不可用，请稍后再试。",
        toast_back_step_1: "已返回兑换码验证步骤。",
        toast_back_step_2: "已返回账号绑定步骤。",
        toast_auto_recognized: "已自动识别账号，可直接继续下一步。",
        current_account_prefix: "当前识别账号：",
        interface_format_error: "接口返回格式异常",
      },
      query: {
        doc_title: "卡密查询",
        doc_description: "支持批量查询卡密状态。",
        page_title: "卡密查询",
        page_subtitle: "支持一行一个卡密，批量查询状态",
        back_home: "账号充值",
        tutorial: "使用教程",
        query_label: "请输入卡密（支持多个，每行一个）",
        query_placeholder: "请输入卡密，每行一个",
        query_button: "开始查询",
        fill_demo: "填充示例",
        stat_total: "总数量",
        stat_unused: "未使用",
        stat_used: "已使用",
        stat_invalid: "无效",
        copy_all: "复制全部",
        copy_unused: "复制未使用",
        copy_used: "复制已使用",
        copy_invalid: "复制无效",
        empty_initial: "还没有查询结果。",
        empty_no_data: "没有查到任何数据，请确认卡密格式是否正确。",
        table_index: "#",
        table_cdk: "卡密",
        table_status: "状态",
        table_used_at: "使用时间",
        table_account: "使用账号",
        status_used: "已使用",
        status_unused: "未使用",
        status_invalid: "无效",
        toast_need_query: "请先输入至少一个卡密。",
        toast_query_loading: "查询中",
        toast_query_success: "查询完成。",
        toast_query_fail: "查询失败，请稍后重试。",
        toast_query_unavailable: "查询接口暂时不可用。",
        toast_copy_empty: "还没有可复制的结果。",
        toast_copy_no_match: "没有符合条件的卡密可复制。",
        toast_copy_success: "已复制 {count} 个卡密。",
        toast_copy_fail: "复制失败，请手动复制。",
        interface_format_error: "接口返回格式异常",
      },
    },
    ko: {
      recharge: {
        doc_title: "계정 충전",
        doc_description: "아래 단계에 따라 충전을 진행하세요.",
        page_title: "계정 충전",
        page_subtitle: "아래 단계에 따라 충전을 진행하세요",
        view_tutorial: "문의가 있으면 가이드를 확인하세요",
        cdk_query: "카드키 조회",
        step_1: "카드키 확인",
        step_2: "계정 연결",
        step_3: "업그레이드 완료",
        current_status: "현재 상태",
        masked_unverified: "미확인",
        status_waiting: "교환 코드를 입력한 뒤 확인을 시작하세요.",
        cdk_label: "내부 교환 코드",
        cdk_placeholder: "교환 코드를 입력하세요",
        verify_button: "확인 시작",
        bind_title: "계정 연결",
        bind_subtitle: "확인이 완료되면 전체 계정 정보를 가져와 붙여넣어 주세요.",
        banner_tip: "안내",
        banner_text: "가져오기 전에 계정을 개인 공간으로 전환하고 팀 공간에 있지 않은지 확인하세요.",
        get_account: "계정 정보 가져오기",
        full_tutorial: "전체 가이드 보기",
        account_placeholder: "여기에 계정 정보를 붙여넣으세요...",
        recognized_label: "인식된 계정",
        recognized_waiting: "인식 대기",
        parse_button: "확인 후 계속",
        confirm_title: "충전 확인",
        confirm_subtitle: "정보가 맞는지 확인한 뒤 충전 요청을 제출하세요.",
        charge_ready_title: "준비 완료",
        charge_ready_text: "인식된 계정이 맞는지 확인한 뒤 충전을 시작하세요.",
        charge_processing_title: "충전 진행 중",
        charge_processing_text: "충전 요청을 처리하는 중입니다. 잠시만 기다려 주세요...",
        charge_success_title: "충전 성공",
        charge_success_text: "계정 업그레이드가 완료되었습니다.",
        current_account: "현재 인식된 계정",
        charge_button: "충전 시작",
        success_title: "충전 성공",
        success_text_default: "충전 요청이 정상적으로 제출되었습니다.",
        back_aria: "이전 단계로 돌아가기",
        toast_enter_cdk: "먼저 교환 코드를 입력하세요.",
        toast_verifying: "교환 코드를 확인하는 중입니다. 잠시만 기다려 주세요.",
        toast_verify_loading: "확인 중",
        toast_verify_success_status: "교환 코드 확인이 완료되었습니다. 계정을 계속 연결하세요.",
        toast_verify_success: "교환 코드 확인 완료.",
        toast_verify_fail: "교환 코드 확인에 실패했습니다. 다시 시도해 주세요.",
        toast_verify_unavailable: "확인 인터페이스를 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        toast_need_verify: "먼저 교환 코드 확인을 완료하세요.",
        toast_account_format_error: "계정 정보 형식이 올바르지 않습니다. 다시 가져와 전체 내용을 붙여넣어 주세요.",
        toast_account_not_found: "계정을 인식하지 못했습니다. 전체 계정 정보를 붙여넣었는지 확인하세요.",
        toast_account_ready: "계정이 인식되었습니다. 충전을 시작할 수 있습니다.",
        toast_account_success: "계정 인식 완료.",
        toast_need_account: "먼저 계정 정보를 인식하세요.",
        toast_charge_loading: "처리 중",
        toast_charge_submitting: "충전 요청을 제출하는 중입니다. 잠시만 기다려 주세요.",
        toast_charge_submit_success: "계정 충전 요청이 성공적으로 제출되었습니다.",
        toast_charge_success_status: "충전 제출 완료.",
        toast_charge_success: "충전 성공.",
        toast_charge_fail: "충전에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        toast_charge_retry: "계정 정보를 확인한 뒤 다시 제출해 주세요.",
        toast_charge_unavailable: "충전 인터페이스를 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        toast_interface_retry: "인터페이스를 사용할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        toast_back_step_1: "교환 코드 확인 단계로 돌아왔습니다.",
        toast_back_step_2: "계정 연결 단계로 돌아왔습니다.",
        toast_auto_recognized: "계정이 자동으로 인식되었습니다. 바로 다음 단계로 진행하세요.",
        current_account_prefix: "현재 인식된 계정:",
        interface_format_error: "인터페이스 응답 형식이 올바르지 않습니다.",
      },
      query: {
        doc_title: "카드키 조회",
        doc_description: "카드키 상태를 일괄 조회할 수 있습니다.",
        page_title: "카드키 조회",
        page_subtitle: "카드키를 한 줄에 하나씩 입력해 상태를 일괄 조회할 수 있습니다.",
        back_home: "계정 충전",
        tutorial: "사용 가이드",
        query_label: "카드키를 입력하세요(여러 개 가능, 한 줄에 하나씩)",
        query_placeholder: "카드키를 입력하세요. 한 줄에 하나씩 입력할 수 있습니다.",
        query_button: "조회 시작",
        fill_demo: "예시 채우기",
        stat_total: "전체 수량",
        stat_unused: "미사용",
        stat_used: "사용됨",
        stat_invalid: "무효",
        copy_all: "전체 복사",
        copy_unused: "미사용 복사",
        copy_used: "사용됨 복사",
        copy_invalid: "무효 복사",
        empty_initial: "아직 조회 결과가 없습니다.",
        empty_no_data: "조회된 데이터가 없습니다. 카드키 형식을 확인하세요.",
        table_index: "#",
        table_cdk: "카드키",
        table_status: "상태",
        table_used_at: "사용 시간",
        table_account: "사용 계정",
        status_used: "사용됨",
        status_unused: "미사용",
        status_invalid: "무효",
        toast_need_query: "카드키를 하나 이상 입력하세요.",
        toast_query_loading: "조회 중",
        toast_query_success: "조회 완료.",
        toast_query_fail: "조회에 실패했습니다. 잠시 후 다시 시도해 주세요.",
        toast_query_unavailable: "조회 인터페이스를 사용할 수 없습니다.",
        toast_copy_empty: "복사할 결과가 없습니다.",
        toast_copy_no_match: "조건에 맞는 카드키가 없습니다.",
        toast_copy_success: "카드키 {count}개를 복사했습니다.",
        toast_copy_fail: "복사에 실패했습니다. 직접 복사해 주세요.",
        interface_format_error: "인터페이스 응답 형식이 올바르지 않습니다.",
      },
    },
  };

  function normalizeLanguage(value) {
    return supported.includes(value) ? value : "zh";
  }

  function currentPage() {
    return document.body && document.body.dataset.page ? document.body.dataset.page : "recharge";
  }

  const state = {
    lang: normalizeLanguage(localStorage.getItem(STORAGE_KEY) || "zh"),
  };

  function template(input, vars) {
    return String(input).replace(/\{(\w+)\}/g, function (_, key) {
      return Object.prototype.hasOwnProperty.call(vars, key) ? vars[key] : "";
    });
  }

  function resolveKey(key) {
    const page = currentPage();
    const bundle = (dictionaries[state.lang] && dictionaries[state.lang][page]) || {};
    return bundle[key] || key;
  }

  function t(key, vars) {
    return template(resolveKey(key), vars || {});
  }

  function applyTranslations() {
    document.documentElement.lang = state.lang === "ko" ? "ko" : "zh-CN";

    document.querySelectorAll("[data-i18n]").forEach(function (element) {
      element.textContent = t(element.getAttribute("data-i18n"));
    });

    document.querySelectorAll("[data-i18n-placeholder]").forEach(function (element) {
      element.setAttribute("placeholder", t(element.getAttribute("data-i18n-placeholder")));
    });

    document.querySelectorAll("[data-i18n-content]").forEach(function (element) {
      element.setAttribute("content", t(element.getAttribute("data-i18n-content")));
    });

    document.querySelectorAll("[data-i18n-aria-label]").forEach(function (element) {
      element.setAttribute("aria-label", t(element.getAttribute("data-i18n-aria-label")));
    });

    document.querySelectorAll("[data-lang-toggle]").forEach(function (element) {
      element.textContent = state.lang === "zh" ? "한국어" : "中文";
    });
  }

  function setLanguage(nextLanguage) {
    const normalized = normalizeLanguage(nextLanguage);
    if (state.lang === normalized) {
      return;
    }

    state.lang = normalized;
    localStorage.setItem(STORAGE_KEY, normalized);
    applyTranslations();
    window.dispatchEvent(new CustomEvent("plus-language-change", {
      detail: { lang: normalized },
    }));
  }

  function toggleLanguage() {
    setLanguage(state.lang === "zh" ? "ko" : "zh");
  }

  document.addEventListener("click", function (event) {
    const trigger = event.target.closest("[data-lang-toggle]");
    if (!trigger) {
      return;
    }
    toggleLanguage();
  });

  window.plusI18n = {
    t: t,
    getLanguage: function () {
      return state.lang;
    },
    setLanguage: setLanguage,
    apply: applyTranslations,
  };

  applyTranslations();
})();
