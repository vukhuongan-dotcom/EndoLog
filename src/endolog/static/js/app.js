/* EndoLog Frontend Controller v1 — Zero-PHI 5-Layer Browser Compliance & Brand v1
 * - 0 mã màu hex cứng ngoài tokens.css; 0 emoji; 0 token/PHI trong localStorage/sessionStorage/IndexedDB.
 * - Mặc định nền SÁNG; nền TỐI chỉ bật qua [data-theme="dark"] khi người dùng chủ động chọn. */

(function () {
  'use strict';

  const THEME_STORAGE_KEY = 'endolog_theme';
  const TAB_SESSION_KEY = 'endolog_active_view';
  const DEFAULT_IDLE_TIMEOUT_MS = 15 * 60 * 1000;
  const DEFAULT_HARD_SESSION_MS = 15 * 60 * 1000;

  /* Bảng ánh xạ mã kỹ thuật sang nhãn tiếng Việt chuẩn lâm sàng (giữ nguyên mã máy trong API/dữ liệu) */
  const GUIDELINE_LABELS_VI = {
    USMSTF_POST_POLYPECTOMY_2020: 'USMSTF 2020',
    ESGE_POST_POLYPECTOMY_2020: 'ESGE 2020',
    ESGE_ESD_2022: 'ESGE ESD 2022',
    CLINICIAN_DIRECTED_EGD: 'Theo chỉ định bác sĩ',
    CLINICIAN_DIRECTED_ERCP: 'Theo chỉ định bác sĩ'
  };

  const GUIDELINE_SHORT_LABELS_VI = {
    USMSTF_POST_POLYPECTOMY_2020: 'USMSTF 2020',
    ESGE_POST_POLYPECTOMY_2020: 'ESGE 2020',
    ESGE_ESD_2022: 'ESGE ESD 2022',
    CLINICIAN_DIRECTED_EGD: 'Theo chỉ định bác sĩ',
    CLINICIAN_DIRECTED_ERCP: 'Theo chỉ định bác sĩ'
  };

  const RA_CUSUM_STATUS_LABELS_VI = {
    DISABLED_UNVALIDATED_MODEL: 'RA-CUSUM chưa bật (chưa có mô hình nguy cơ được thẩm định)'
  };

  const INDICATION_LABELS_VI = {
    SCREENING: 'Tầm soát định kỳ',
    DIAGNOSTIC: 'Chẩn đoán triệu chứng',
    ABNORMAL_FECAL_TEST: 'Xét nghiệm phân bất thường (FIT)',
    SURVEILLANCE: 'Theo dõi hẹn soi lại',
    THERAPEUTIC: 'Nội soi can thiệp điều trị',
    IBD_EVAL: 'Đánh giá bệnh viêm ruột mạn (IBD)',
    GI_BLEEDING: 'Xuất huyết tiêu hóa',
    EARLY_CANCER_WORKUP: 'Đánh giá tổn thương nghi ung thư sớm',
    BILIARY_STONE: 'Sỏi đường mật',
    MALIGNANT_STRICTURE: 'Hẹp đường mật nghi ác tính',
    CHOLANGITIS: 'Viêm đường mật cấp',
    BILIARY_PANCREATITIS: 'Viêm tụy cấp do sỏi mật',
    STENT_EXCHANGE: 'Thay hoặc rút stent mật — tụy',
    OTHER: 'Chỉ định lâm sàng khác'
  };

  const HISTOLOGY_LABELS_VI = {
    NONE: 'Chưa có / đang chờ giải phẫu bệnh',
    INFLAMMATORY_BENIGN: 'Viêm niêm mạc lành tính',
    INTESTINAL_METAPLASIA: 'Dị sản ruột',
    HYPERPLASTIC: 'Polyp tăng sản',
    TUBULAR_ADENOMA: 'U tuyến ống',
    TUBULOVILLOUS_ADENOMA: 'U tuyến ống — nhung mao',
    VILLOUS_ADENOMA: 'U tuyến nhung mao',
    SSL_NO_DYSPLASIA: 'Polyp răng cưa không cuống (SSL) không loạn sản',
    SSL_WITH_DYSPLASIA: 'Polyp răng cưa không cuống (SSL) có loạn sản',
    TSA: 'U tuyến răng cưa truyền thống (TSA)',
    LGD_VIENNA_C3: 'Loạn sản biểu mô độ thấp (Vienna 3)',
    HGD_VIENNA_C4: 'Loạn sản biểu mô độ cao (Vienna 4)',
    ADENOCARCINOMA_INTRAMUCOSAL: 'Ung thư biểu mô tuyến nội niêm mạc',
    ADENOCARCINOMA_INVASIVE: 'Ung thư biểu mô tuyến xâm lấn',
    OTHER: 'Mô bệnh học khác'
  };

  const RESECTION_METHOD_LABELS_VI = {
    ESD: 'Cắt tách dưới niêm mạc (ESD)',
    EMR_EN_BLOC: 'Cắt niêm mạc nguyên khối qua nội soi (EMR)',
    EMR: 'Cắt niêm mạc qua nội soi (EMR)',
    EMR_PIECEMEAL: 'Cắt niêm mạc từng mảnh (EMR)',
    COLD_SNARE: 'Cắt polyp bằng thòng lọng lạnh',
    HOT_SNARE: 'Cắt polyp bằng thòng lọng nhiệt',
    UNRESECTED_REFERRED: 'Chưa cắt qua nội soi (chuyển hội chẩn)',
    BIOPSY_ONLY: 'Sinh thiết kìm chẩn đoán',
    HEMOSTASIS: 'Can thiệp cầm máu',
    NONE: 'Quan sát chẩn đoán'
  };

  const MARGINS_STATUS_LABELS_VI = {
    R0: 'diện cắt R0',
    HM1_ONLY: 'diện ngang HM1',
    RX_PIECEMEAL: 'diện cắt RX (từng mảnh)',
    VM1_OR_R1: 'diện sâu VM1/R1',
    PENDING: 'đang chờ diện cắt'
  };

  const PAPILLA_STATUS_LABELS_VI = {
    NATIVE_INTACT: 'Nhú nguyên vẹn',
    PRIOR_SPHINCTEROTOMY: 'Nhú đã cắt cơ vòng trước đó',
    PRIOR_STENT_IN_SITU: 'Nhú có stent lưu sẵn',
    SURGICAL_BILIARY_ENTERIC: 'Miệng nối mật — ruột phẫu thuật'
  };

  const HEMOSTASIS_MODALITY_LABELS_VI = {
    NONE: 'Chưa can thiệp cầm máu',
    EVL: 'Thắt vòng cao su tĩnh mạch thực quản (EVL)',
    CYANOACRYLATE: 'Tiêm keo sinh học Cyanoacrylate',
    HEMOCLIP: 'Kẹp clip cầm máu',
    EPINEPHRINE_INJECTION: 'Tiêm cầm máu Adrenaline',
    THERMAL_COAGULATION: 'Đốt nhiệt / Argon Plasma cầm máu',
    HEMOSPRAY: 'Xịt bột cầm máu nội soi'
  };

  const PEP_SEVERITY_LABELS_VI = {
    NONE: 'không ghi nhận',
    MILD: 'mức nhẹ',
    MODERATE: 'mức vừa',
    SEVERE: 'mức nặng'
  };

  const FOLLOWUP_30D_LABELS_VI = {
    PENDING_WINDOW: 'Đang trong cửa sổ theo dõi 14–30 ngày',
    COMPLETED_NO_AE: 'Hoàn tất 30 ngày — không ghi nhận biến cố',
    COMPLETED_WITH_AE: 'Hoàn tất — có ghi nhận biến cố sau thủ thuật',
    LOST_TO_FOLLOWUP: 'Mất dấu theo dõi sau xuất viện'
  };

  const PATH_STATUS_LABELS_VI = {
    NOT_APPLICABLE: 'Không sinh thiết / không áp dụng',
    PENDING: 'Đang chờ kết quả giải phẫu bệnh',
    PARTIAL: 'Đã có một phần kết quả giải phẫu bệnh',
    COMPLETE: 'Đã hoàn tất toàn bộ giải phẫu bệnh'
  };

  const AE_EVENT_TYPE_LABELS_VI = {
    PEP: 'Viêm tụy sau ERCP',
    BLEEDING: 'Chảy máu tiêu hóa sau thủ thuật',
    PERFORATION: 'Thủng ống tiêu hóa — đường mật',
    CHOLANGITIS: 'Viêm đường mật sau can thiệp',
    SEDATION_CARDIORESP: 'Biến cố tim phổi — an thần',
    POST_POLYPECTOMY_SYNDROME: 'Hội chứng đốt điện sau cắt polyp',
    OTHER: 'Biến cố sau thủ thuật khác'
  };

  const AE_WINDOW_LABELS_VI = {
    INTRAPROCEDURAL: 'Trong lúc soi',
    INPATIENT_EARLY: 'Nội trú sớm (< 48 giờ)',
    DELAYED_30D: 'Muộn trong 14–30 ngày'
  };

  const SITE_QUICK_CHIPS_BY_TRACK = {
    COL: ['Manh tràng', 'Đại tràng lên', 'Đại tràng ngang', 'Đại tràng xuống', 'Đại tràng chậu hông', 'Trực tràng'],
    EGD: ['Thực quản giữa', 'Thực quản dưới', 'Tâm vị', 'Thân vị', 'Góc bờ cong nhỏ', 'Hang vị', 'Tá tràng D1', 'Tá tràng D2']
  };

  const ERCP_INTERVENTION_CHIPS = [
    { code: 'EST', label: 'Cắt cơ vòng mật (EST)' },
    { code: 'EPLBD', label: 'Nong bóng nhú lớn (EPLBD)' },
    { code: 'STONE_EXTRACTION', label: 'Lấy sỏi bóng / rọ Dormia' },
    { code: 'MECHANICAL_LITHOTRIPSY', label: 'Tán sỏi cơ học' },
    { code: 'PLASTIC_STENT', label: 'Đặt stent mật nhựa' },
    { code: 'SEMS_STENT', label: 'Đặt stent kim loại tự bung (SEMS)' },
    { code: 'BILIARY_BRUSHING_BIOPSY', label: 'Chải tế bào / sinh thiết đường mật' }
  ];

  const ERCP_PROPHYLAXIS_CHIPS = [
    { code: 'RECTAL_NSAID_100MG', label: 'NSAID đặt hậu môn 100 mg' },
    { code: 'PANCREATIC_PD_STENT', label: 'Đặt stent ống tụy dự phòng' },
    { code: 'AGRESSIVE_LR_HYDRATION', label: 'Truyền dịch Lactated Ringer tích cực' }
  ];

  const ERCP_HISTORY_CHIPS = [
    { code: 'PRIOR_PEP', label: 'Tiền căn viêm tụy sau ERCP' },
    { code: 'RECURRENT_CBD_STONE', label: 'Sỏi ống mật chủ tái phát' },
    { code: 'PRIOR_CHOLECYSTECTOMY', label: 'Đã cắt túi mật trước đó' },
    { code: 'RECURRENT_CHOLANGITIS', label: 'Viêm đường mật tái diễn' }
  ];

  const TRACK_DEFAULT_INDICATION = {
    COL: 'SCREENING',
    EGD: 'DIAGNOSTIC',
    ERCP: 'BILIARY_STONE'
  };

  let sessionEpoch = 0;
  let activeAbortController = null;
  let pendingLogoutPromise = null;
  let kpiReqSeq = 0;
  let cusumReqSeq = 0;
  let idleTimeoutMs = DEFAULT_IDLE_TIMEOUT_MS;
  let idleDeadlineMs = 0;
  let hardSessionDeadlineMs = 0;

  const state = {
    user: null,
    activeView: 'cases',
    trackFilter: 'ALL',
    survFilter: 'ALL',
    searchQuery: '',
    adrMinAge: 45,
    cusumMetric: 'CIR',
    cusumPreset: 'DEFAULT_90',
    settings: {
      colo_guideline_mode: 'USMSTF_2020',
      adr_min_age: 45,
      cusum_preset: 'DEFAULT_90',
      kpi_min_sample_size: 20
    },
    cases: [],
    surveillanceRows: [],
    kpiBundle: null,
    cusumData: null,
    auditStatus: null,
    idleTimer: null,
    hardExpiryTimer: null
  };

  const drawerState = {
    isOpen: false,
    mode: 'create',
    editingCaseId: null,
    editingCaseCode: '',
    expectedVersion: 1,
    activePhase: 'p1',
    track: 'COL',
    sex: 'M',
    careSetting: 'OUTPATIENT',
    egdMode: 'lesion',
    hasIbdOrPolyposis: false,
    excludeFromCir: false,
    hasIndexLesion: false,
    bbpsRight: null,
    bbpsTransverse: null,
    bbpsLeft: null,
    vaterType: '1',
    padDiverticulum: false,
    duodenalObstruction: false,
    biliaryInterventions: [],
    pepProphylaxis: [],
    ercpHistoryFlags: [],
    aeItems: [],
    linkedPatientUid: null,
    fulfillSurvRecId: null,
    linkedOriginCaseCode: '',
    isDirty: false,
    pendingCreatePayload: null,
    returnFocusEl: null,
    timerRunning: false,
    timerElapsedSec: 0,
    timerIntervalId: null
  };

  const detailModalState = {
    isOpen: false,
    caseId: null,
    returnFocusEl: null
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function escapeHtml(raw) {
    return String(raw == null ? '' : raw)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function formatViDate(isoStr) {
    if (!isoStr) return 'Chưa ấn định';
    const d = String(isoStr).slice(0, 10).split('-');
    if (d.length !== 3) return String(isoStr);
    return d[2] + '/' + d[1] + '/' + d[0];
  }

  function formatViPct(val) {
    if (val == null || typeof val === 'boolean' || val === '' || Number.isNaN(Number(val))) return '—';
    return Number(val).toFixed(1).replace('.', ',') + '%';
  }

  function formatViNum(val) {
    if (val == null || typeof val === 'boolean' || val === '' || Number.isNaN(Number(val))) return '—';
    return String(val).replace('.', ',');
  }

  function sanitizeEnumFallbackVi(raw, fallbackLabel) {
    if (raw == null || raw === '') return fallbackLabel || '';
    const s = String(raw).trim();
    if (/^[A-Z0-9]{2,}(?:_[A-Z0-9]+)+$/.test(s)) {
      return fallbackLabel || 'Phân loại chuyên môn khác';
    }
    return s.replace(/\b[A-Z0-9]{2,}(?:_[A-Z0-9]+)+\b/g, () => fallbackLabel || 'phân loại chuyên môn');
  }

  function formatGuidelineLabelVi(code, shortForm) {
    const key = String(code || '').trim();
    if (!key) return 'Theo chỉ định lâm sàng';
    const map = shortForm ? GUIDELINE_SHORT_LABELS_VI : GUIDELINE_LABELS_VI;
    if (Object.prototype.hasOwnProperty.call(map, key)) {
      return map[key];
    }
    return sanitizeEnumFallbackVi(key, 'Hướng dẫn chuyên môn nội soi');
  }

  function formatRaCusumStatusVi(code) {
    const key = String(code || '').trim();
    if (Object.prototype.hasOwnProperty.call(RA_CUSUM_STATUS_LABELS_VI, key)) {
      return RA_CUSUM_STATUS_LABELS_VI[key];
    }
    return sanitizeEnumFallbackVi(key, 'Chưa kích hoạt hiệu chỉnh nguy cơ');
  }

  function formatIndicationVi(detailText, indicationCode) {
    const detail = String(detailText || '').trim();
    if (detail && !Object.prototype.hasOwnProperty.call(INDICATION_LABELS_VI, detail)) {
      return sanitizeEnumFallbackVi(detail, 'Chỉ định nội soi tiêu hóa');
    }
    const key = detail || String(indicationCode || '').trim();
    if (Object.prototype.hasOwnProperty.call(INDICATION_LABELS_VI, key)) {
      return INDICATION_LABELS_VI[key];
    }
    return sanitizeEnumFallbackVi(key, 'Chỉ định nội soi tiêu hóa');
  }

  function formatHistologyVi(code) {
    const key = String(code || '').trim();
    if (Object.prototype.hasOwnProperty.call(HISTOLOGY_LABELS_VI, key)) {
      return HISTOLOGY_LABELS_VI[key];
    }
    return sanitizeEnumFallbackVi(key, 'Chưa có mô bệnh học');
  }

  function formatHemostasisModalityVi(raw) {
    const key = String(raw || '').trim();
    if (!key) return 'Can thiệp cầm máu qua nội soi';
    if (Object.prototype.hasOwnProperty.call(HEMOSTASIS_MODALITY_LABELS_VI, key)) {
      return HEMOSTASIS_MODALITY_LABELS_VI[key];
    }
    return sanitizeEnumFallbackVi(key, 'Can thiệp cầm máu qua nội soi');
  }

  function humanizeClinicalBadgeLabelVi(rawLabel) {
    let txt = String(rawLabel || '').trim();
    if (!txt) return 'Đang cập nhật';
    txt = txt.replace(/(?:Biến cố\s+)?\bPEP\s+(MILD|MODERATE|SEVERE|NONE)\b/g, (_m, sev) => {
      return 'Viêm tụy sau ERCP ' + (PEP_SEVERITY_LABELS_VI[sev] || 'ghi nhận');
    });
    return sanitizeEnumFallbackVi(txt, 'Trạng thái lâm sàng');
  }

  /* Đánh giá huy hiệu trạng thái KPI dựa trên ngưỡng cỡ mẫu tối thiểu n_min (mặc định 20) và tử số/mẫu số chính xác (B01 + R3) */
  function evaluateKpiRateBadge(metricObj, fallbackNMin) {
    const nMin = (metricObj && typeof metricObj.n_min === 'number' && Number.isFinite(metricObj.n_min) && metricObj.n_min >= 1)
      ? Math.floor(metricObj.n_min)
      : ((typeof fallbackNMin === 'number' && Number.isFinite(fallbackNMin) && fallbackNMin >= 1) ? Math.floor(fallbackNMin) : 20);
    const den = metricObj && typeof metricObj.denominator === 'number' && Number.isFinite(metricObj.denominator)
      ? metricObj.denominator
      : 0;
    const rawRate = metricObj ? metricObj.rate_pct : null;
    const hasRate = typeof rawRate === 'number' && Number.isFinite(rawRate);
    const hasNum = Boolean(metricObj && typeof metricObj.numerator === 'number' && Number.isFinite(metricObj.numerator));

    if (den < nMin || den <= 0 || !hasRate || (metricObj && metricObj.status === 'insufficient_n')) {
      return { tone: 'neutral', label: 'Chưa đủ cỡ mẫu (n < ' + nMin + ')' };
    }

    const rawTarget = metricObj ? metricObj.target_pct : null;
    const hasTarget = typeof rawTarget === 'number' && Number.isFinite(rawTarget);
    if (!hasTarget || (metricObj && metricObj.status === 'no_target')) {
      return { tone: 'neutral', label: 'Chưa thiết lập ngưỡng' };
    }

    const target = rawTarget;
    const targetTxt = formatViNum(target) + '%';
    /* So sánh trực tiếp tử số/mẫu số khi có để tránh làm tròn 1 chữ số thập phân (ví dụ 36/103 = 34,95% -> 35,0%) tạo dương tính giả */
    const meetsTarget = (metricObj && (metricObj.status === 'met' || metricObj.status === 'below_target'))
      ? (metricObj.status === 'met')
      : (hasNum ? (metricObj.numerator * 100 >= target * den - 1e-9) : (rawRate >= target));

    if (meetsTarget) {
      return { tone: 'ned', label: 'Đạt ngưỡng (≥ ' + targetTxt + ')' };
    }
    return { tone: 'urgent', label: 'Chưa đạt ngưỡng (< ' + targetTxt + ')' };
  }

  function describeUnclosedFollowupSuffix(aeAll) {
    const hasSplit = Boolean(
      aeAll &&
      typeof aeAll.pending_window_count === 'number' &&
      typeof aeAll.lost_to_followup_count === 'number'
    );
    if (hasSplit) {
      const pw = aeAll.pending_window_count;
      const lost = aeAll.lost_to_followup_count;
      if (pw > 0 && lost > 0) {
        return pw + ' ca chờ cửa sổ, ' + lost + ' mất dấu';
      }
      if (pw > 0) {
        return pw + ' ca chờ cửa sổ';
      }
      if (lost > 0) {
        return lost + ' ca mất dấu theo dõi';
      }
      return '';
    }
    const totalMissing = aeAll && typeof aeAll.missing_or_pending_fu_count === 'number'
      ? aeAll.missing_or_pending_fu_count
      : 0;
    return totalMissing > 0 ? (totalMissing + ' ca chờ cửa sổ') : '';
  }

  function evaluateAdverseEventKpiBadge(aeAll, ercpPep) {
    const den = aeAll && typeof aeAll.completed_fu_denominator === 'number' && Number.isFinite(aeAll.completed_fu_denominator)
      ? aeAll.completed_fu_denominator
      : 0;
    const rawSevereRate = aeAll ? aeAll.agree_severe_rate_pct : null;
    const hasRate = typeof rawSevereRate === 'number' && Number.isFinite(rawSevereRate);
    const severeNum = aeAll && typeof aeAll.agree_severe_numerator === 'number' ? aeAll.agree_severe_numerator : 0;
    const anyNum = aeAll && typeof aeAll.agree_any_numerator === 'number' ? aeAll.agree_any_numerator : 0;
    const pepNum = ercpPep && typeof ercpPep.numerator === 'number' ? ercpPep.numerator : 0;
    const pepSevereNum = ercpPep && typeof ercpPep.pep_severe_numerator === 'number' ? ercpPep.pep_severe_numerator : 0;
    const unclosedSuffix = describeUnclosedFollowupSuffix(aeAll);
    const hasPendingWindow = Boolean(
      (aeAll && typeof aeAll.pending_window_count === 'number' && aeAll.pending_window_count > 0) ||
      (aeAll && aeAll.pending_window_count === undefined && (aeAll.missing_or_pending_fu_count || 0) > 0)
    );

    if (den <= 0 || !hasRate) {
      if (unclosedSuffix) {
        return { tone: hasPendingWindow ? 'due' : 'neutral', label: 'Chưa đủ dữ liệu (' + unclosedSuffix + ')' };
      }
      return { tone: 'neutral', label: 'Chưa đủ dữ liệu' };
    }
    if (severeNum > 0) {
      return { tone: 'urgent', label: 'Có biến cố nặng AGREE ≥ III (' + severeNum + ' ca)' };
    }
    if (pepSevereNum > 0) {
      return { tone: 'urgent', label: 'Có viêm tụy sau ERCP mức nặng (' + pepSevereNum + ' ca)' };
    }
    if (anyNum > 0 || pepNum > 0) {
      return {
        tone: 'pending',
        label: unclosedSuffix
          ? ('Có biến cố nhẹ/vừa · ' + unclosedSuffix)
          : 'Có biến cố nhẹ/vừa (AGREE < III)'
      };
    }
    if (unclosedSuffix) {
      return {
        tone: hasPendingWindow ? 'due' : 'neutral',
        label: '0 biến cố đã đóng · ' + unclosedSuffix
      };
    }
    return { tone: 'ned', label: '0 biến cố trong ca đã đóng 30 ngày' };
  }

  /* Đồng bộ <meta name="theme-color"> động từ biến CSS --meta-theme-color trong tokens.css */
  function syncMetaThemeColor() {
    const metaEl = byId('el-meta-theme');
    if (!metaEl) return;
    const computed = getComputedStyle(document.documentElement)
      .getPropertyValue('--meta-theme-color')
      .trim();
    if (computed) {
      metaEl.setAttribute('content', computed);
    }
  }

  function applyTheme(mode, persist) {
    const isDark = mode === 'dark';
    if (isDark) {
      document.documentElement.setAttribute('data-theme', 'dark');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
    if (persist) {
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, isDark ? 'dark' : 'light');
      } catch (_err) {
        /* ignore storage quota */
      }
    }
    const moon = byId('el-icon-moon');
    const sun = byId('el-icon-sun');
    const lbl = byId('el-theme-label');
    if (moon && sun && lbl) {
      if (isDark) {
        moon.setAttribute('hidden', '');
        sun.removeAttribute('hidden');
      } else {
        sun.setAttribute('hidden', '');
        moon.removeAttribute('hidden');
      }
      lbl.textContent = isDark ? 'Nền sáng' : 'Nền tối';
    }
    syncMetaThemeColor();
  }

  function scrubLocalStorageAllowlist() {
    try {
      const keys = Object.keys(window.localStorage);
      keys.forEach((k) => {
        if (k !== THEME_STORAGE_KEY) {
          window.localStorage.removeItem(k);
          return;
        }
        const v = window.localStorage.getItem(k);
        if (v !== 'light' && v !== 'dark') {
          window.localStorage.setItem(k, 'light');
        }
      });
    } catch (_err) {
      /* ignore storage restrictions */
    }
  }

  function initTheme() {
    scrubLocalStorageAllowlist();
    let saved = 'light';
    try {
      const candidate = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (candidate === 'dark' || candidate === 'light') {
        saved = candidate;
      }
    } catch (_err) {
      saved = 'light';
    }
    applyTheme(saved, false);
  }

  function statusIconSvg(tone) {
    if (tone === 'urgent') {
      return '<svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    }
    if (tone === 'pending') {
      return '<svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
    }
    if (tone === 'due') {
      return '<svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>';
    }
    if (tone === 'ned') {
      return '<svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
    }
    return '<svg class="el-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="8" y1="12" x2="16" y2="12"/></svg>';
  }

  /* Chip thủ thuật: nền -tint, chữ -text, chấm 7 px màu --proc-*, LUÔN ghi mã EGD/COL/ERCP */
  function renderProcChip(track) {
    const code = String(track || 'COL').toUpperCase();
    const cls = code === 'EGD' ? 'egd' : (code === 'ERCP' ? 'ercp' : 'col');
    return (
      '<span class="el-proc-chip el-proc-chip--' + cls + '">' +
      '<span class="el-proc-dot" aria-hidden="true"></span>' +
      '<span>' + escapeHtml(code) + '</span>' +
      '</span>'
    );
  }

  function renderStatusBadge(tone, label) {
    const safeTone = ['ned', 'due', 'pending', 'urgent', 'neutral'].includes(tone) ? tone : 'neutral';
    return (
      '<span class="el-status-badge el-status-badge--' + safeTone + '">' +
      statusIconSvg(safeTone) +
      '<span>' + escapeHtml(label) + '</span>' +
      '</span>'
    );
  }

  function describeTrackClinicalHighlights(c) {
    const idx = c.index_lesion || {};
    const wc = c.whole_case_summary || {};
    if (c.track === 'COL') {
      const bbpsTxt = c.bbps && c.bbps.evaluable
        ? ('BBPS ' + c.bbps.segments.join('+') + ' = ' + c.bbps.total + (c.bbps.adequate ? ' (Đạt)' : ' (Chưa đạt)'))
        : 'BBPS chưa chấm';
      const cecalTxt = c.cecal_intubation === 'YES' ? 'Luồn tới manh tràng' : 'Chưa tới manh tràng';
      const count = wc.macroscopic_polyp_count || 0;
      let lesionLine = 'Không phát hiện polyp · Rút ống sạch ' + formatViNum(c.withdrawal_time_clean_min) + ' phút';
      if (count > 0) {
        const sitePart = idx.anatomical_site || 'Đại tràng';
        const sizePart = idx.size_mm != null ? (' ' + formatViNum(idx.size_mm) + ' mm') : '';
        const parisPart = idx.paris_class ? (' (' + idx.paris_class + ')') : '';
        lesionLine = 'Toàn ca ' + count + ' polyp · Đại diện: ' + sitePart + sizePart + parisPart;
      }
      return { title: bbpsTxt + ' · ' + cecalTxt, detail: lesionLine };
    }
    if (c.track === 'EGD') {
      const resection = idx.resection_method || 'NONE';
      if (resection === 'HEMOSTASIS') {
        return {
          title: (idx.anatomical_site || 'Thực quản — dạ dày') + ' · ' + formatHemostasisModalityVi(idx.hemostasis_modality),
          detail: 'Cầm máu ban đầu: ' + (idx.hemostasis_initial_success === 'YES' ? 'Đạt hoàn toàn' : 'Cần theo dõi sát')
        };
      }
      if (resection in RESECTION_METHOD_LABELS_VI && resection !== 'BIOPSY_ONLY' && resection !== 'NONE') {
        const marginTxt = idx.margins_status && MARGINS_STATUS_LABELS_VI[idx.margins_status]
          ? (' (' + MARGINS_STATUS_LABELS_VI[idx.margins_status] + ')')
          : '';
        return {
          title: (idx.anatomical_site || 'Dạ dày') + ' · ' + (idx.paris_class || 'Tổn thương niêm mạc') + (idx.size_mm != null ? (' (' + formatViNum(idx.size_mm) + ' mm)') : ''),
          detail: RESECTION_METHOD_LABELS_VI[resection] + marginTxt + ' · Mô học: ' + formatHistologyVi(idx.histology_type)
        };
      }
      if (!c.index_lesion || (!idx.anatomical_site && !idx.biopsy_jar_count && resection === 'NONE')) {
        return {
          title: 'Thực quản — dạ dày — tá tràng · Không ghi nhận tổn thương khu trú',
          detail: 'Không bấm sinh thiết · Theo dõi theo bệnh cảnh lâm sàng'
        };
      }
      if ((idx.biopsy_jar_count || 0) === 0 && resection === 'NONE') {
        return {
          title: (idx.anatomical_site || 'Dạ dày') + ' · ' + (idx.paris_class || 'Tổn thương niêm mạc') + (idx.size_mm != null ? (' (' + formatViNum(idx.size_mm) + ' mm)') : ''),
          detail: 'Quan sát chẩn đoán · Không bấm sinh thiết'
        };
      }
      return {
        title: (idx.anatomical_site || 'Dạ dày') + ' · ' + (idx.paris_class || 'Tổn thương niêm mạc') + (idx.size_mm != null ? (' (' + formatViNum(idx.size_mm) + ' mm)') : ''),
        detail: 'Sinh thiết kìm ' + (idx.biopsy_jar_count || 0) + ' mảnh · Mô học: ' + formatHistologyVi(idx.histology_type)
      };
    }
    const er = c.ercp_computed || c.ercp_detail || {};
    const papillaCode = er.papilla_status || 'NATIVE_INTACT';
    const papillaBase = PAPILLA_STATUS_LABELS_VI[papillaCode] || 'Nhú Vater';
    const papillaTypeTxt = papillaCode === 'NATIVE_INTACT'
      ? (' phân loại ' + (er.vater_papilla_type || '1'))
      : '';
    let diffTxt = 'Thông nhú thuận lợi';
    if (er.difficult_cannulation_esge2016 === 'YES') {
      diffTxt = 'Thông nhú khó ESGE 2016 (' + er.cannulation_contacts_count + ' chạm, ' + formatViNum(er.cannulation_time_min) + ' phút, ' + er.unintended_pd_count + ' lần ống tụy)';
    } else if (er.difficult_cannulation_esge2016 === 'NA_NON_NATIVE') {
      diffTxt = 'Không tính thông nhú khó (nhú đã can thiệp trước đó)';
    }
    return {
      title: 'Lần ERCP thứ ' + (er.ercp_session_index_in_episode || 1) + ' trong đợt · ' + papillaBase + papillaTypeTxt + (er.pad_diverticulum ? ' + túi thừa cạnh nhú' : ''),
      detail: diffTxt + ' · ' + (er.selective_cannulation === 'SUCCESS' ? 'Thông nhú chọn lọc đạt' : 'Thông nhú thất bại')
    };
  }

  function phasePillIconSvg(stateKey) {
    if (stateKey === 'done') {
      return '<svg class="el-phase-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>';
    }
    if (stateKey === 'pending') {
      return '<svg class="el-phase-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 3h14"/><path d="M5 21h14"/><path d="M17 3v4.5a5 5 0 0 1-2.2 4.16L12 13.5l-2.8-1.84A5 5 0 0 1 7 7.5V3"/><path d="M7 21v-4.5a5 5 0 0 1 2.2-4.16L12 10.5l2.8 1.84A5 5 0 0 1 17 16.5V21"/></svg>';
    }
    if (stateKey === 'active') {
      return '<svg class="el-phase-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/></svg>';
    }
    if (stateKey === 'urgent') {
      return '<svg class="el-phase-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    }
    return '<svg class="el-phase-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><line x1="8.5" y1="12" x2="15.5" y2="12"/></svg>';
  }

  function moreDotsIconSvg() {
    return '<svg class="el-icon" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg>';
  }

  /* Tính toán tiến độ theo dõi dọc 4 pha (P1..P4) đồng bộ SurgiLog Pro cho mọi ca EGD / COL / ERCP */
  function computeCasePhaseProgression(c) {
    const rec = c || {};
    const track = String(rec.track || 'COL').toUpperCase();
    const surv = rec.surveillance || {};
    const idx = rec.index_lesion || null;

    const p1 = {
      key: 'p1',
      code: 'P1',
      state: 'done',
      shortText: 'Đã lập hồ sơ',
      title: 'Pha 1 (Hành chính & chỉ định): Đã hoàn tất — bấm để sửa Pha 1'
    };

    let p2Done = true;
    if (track === 'COL') {
      const bbpsOk = Boolean(
        (rec.bbps && rec.bbps.evaluable) ||
        (typeof rec.bbps_right === 'number' && typeof rec.bbps_transverse === 'number' && typeof rec.bbps_left === 'number')
      );
      p2Done = Boolean(
        (rec.cecal_intubation === 'YES' && bbpsOk) ||
        (rec.cecal_intubation === 'NO' && rec.cecal_failure_reason) ||
        rec.exclude_from_cir
      );
    } else if (track === 'EGD') {
      if (idx && idx.resection_method && idx.resection_method !== 'NONE') {
        const hasSiteOrBleed = Boolean(idx.anatomical_site || (idx.bleeding_source_type && idx.bleeding_source_type !== 'NONE'));
        p2Done = hasSiteOrBleed;
      } else {
        p2Done = true;
      }
    } else if (track === 'ERCP') {
      const er = rec.ercp_computed || rec.ercp_detail || null;
      p2Done = Boolean(er && (er.selective_cannulation === 'SUCCESS' || er.selective_cannulation === 'FAILED'));
    }

    const p2 = {
      key: 'p2',
      code: 'P2',
      state: p2Done ? 'done' : 'pending',
      shortText: p2Done ? 'Thủ thuật đạt' : 'Chờ nhập P2',
      title: p2Done
        ? 'Pha 2 (Thông số thủ thuật): Đã ghi nhận đầy đủ — bấm để mở Pha 2'
        : 'Pha 2 (Thông số thủ thuật): Chưa đủ thông số — bấm để bổ sung Pha 2'
    };

    const fu30 = rec.followup_30d_status || 'PENDING_WINDOW';
    const aeCount = Array.isArray(rec.adverse_events) ? rec.adverse_events.length : 0;
    let p3State = 'pending';
    let p3Short = 'Theo dõi 30 ngày';
    let p3Title = 'Pha 3 (Biến cố 14–30 ngày): Đang trong cửa sổ theo dõi — bấm để cập nhật Pha 3';
    if (fu30 === 'COMPLETED_NO_AE') {
      p3State = 'done';
      p3Short = '0 biến cố';
      p3Title = 'Pha 3 (Biến cố 14–30 ngày): Đã đóng cửa sổ 30 ngày, không có biến cố';
    } else if (fu30 === 'COMPLETED_WITH_AE') {
      p3State = 'urgent';
      p3Short = (aeCount || 1) + ' biến cố';
      p3Title = 'Pha 3 (Biến cố 14–30 ngày): Đã ghi nhận biến cố sau thủ thuật — bấm để mở Pha 3';
    } else if (fu30 === 'LOST_TO_FOLLOWUP') {
      p3State = 'na';
      p3Short = 'Mất dấu';
      p3Title = 'Pha 3 (Biến cố 14–30 ngày): Mất dấu theo dõi sau xuất viện';
    }
    const p3 = { key: 'p3', code: 'P3', state: p3State, shortText: p3Short, title: p3Title };

    const pathSt = rec.pathology_completion_status || 'NOT_APPLICABLE';
    const intervalLabel = sanitizeEnumFallbackVi(surv.recommended_interval_label || '', 'Theo chỉ định');
    let p4State = 'na';
    let p4Short = intervalLabel ? ('Hẹn ' + intervalLabel) : 'Thường quy';
    let p4Title = 'Pha 4 (Giải phẫu bệnh & hẹn soi): Không sinh thiết / tầm soát thường quy';

    if (pathSt === 'PENDING' || pathSt === 'PARTIAL' || surv.status === 'PENDING_GPB') {
      p4State = 'pending';
      p4Short = 'Chờ GPB';
      p4Title = 'Pha 4 (Giải phẫu bệnh & hẹn soi): Đang chờ kết quả giải phẫu bệnh — bấm để nhập GPB';
    } else if (surv.category === 'SURGICAL_MDT_CONSULT_ALERT') {
      p4State = 'urgent';
      p4Short = 'Hội chẩn Ngoại';
      p4Title = 'Pha 4 (Giải phẫu bệnh & hẹn soi): Cảnh báo chuyển hội chẩn Ngoại khoa — bấm để mở Pha 4';
    } else if (surv.fulfilled_by_case_id) {
      p4State = 'done';
      p4Short = 'Đã soi lại';
      p4Title = 'Pha 4 (Giải phẫu bệnh & hẹn soi): Đã đóng vòng hẹn bằng ca soi lại liên kết';
    } else if (
      pathSt === 'COMPLETE' ||
      Boolean(rec.clinician_followup_due_date) ||
      (Boolean(surv.due_date) && intervalLabel !== '10 năm')
    ) {
      p4State = 'active';
      p4Short = rec.clinician_followup_due_date
        ? ('Hẹn ' + formatViDate(rec.clinician_followup_due_date))
        : (intervalLabel ? ('Hẹn ' + intervalLabel) : 'Đang hẹn soi');
      p4Title = 'Pha 4 (Giải phẫu bệnh & hẹn soi): Đang theo dõi hẹn soi lại — bấm để mở Pha 4';
    }
    const p4 = { key: 'p4', code: 'P4', state: p4State, shortText: p4Short, title: p4Title };

    const phases = [p1, p2, p3, p4];
    const settledCount = phases.filter((ph) => ph.state !== 'pending').length;

    let nextStepLabel = 'Hoàn tất ' + settledCount + '/4 pha';
    if (p2.state === 'pending') {
      nextStepLabel = 'Bước tiếp: Bổ sung thông số Pha 2';
    } else if (p4.state === 'pending') {
      nextStepLabel = 'Bước tiếp: Nhập giải phẫu bệnh Pha 4';
    } else if (p4.state === 'urgent') {
      nextStepLabel = 'Ưu tiên: Chuyển hội chẩn chuyên khoa';
    } else if (p3.state === 'pending') {
      nextStepLabel = 'Bước tiếp: Đóng theo dõi 30 ngày (Pha 3)';
    } else if (p4.state === 'active') {
      nextStepLabel = 'Đang quản lý lịch hẹn soi lại (Pha 4)';
    }

    const summaryLine = (
      'P1: ' + p1.shortText +
      ' · P2: ' + p2.shortText +
      ' · P3: ' + p3.shortText +
      ' · P4: ' + p4.shortText
    );

    return { p1, p2, p3, p4, phases, settledCount, nextStepLabel, summaryLine };
  }

  function renderPhasePillTrackHtml(caseId, prog) {
    const cid = escapeHtml(caseId || '');
    return (
      '<div class="el-phase-pill-cluster" role="group" aria-label="Tiến độ 4 pha theo dõi ca soi">' +
      prog.phases.map((ph) => (
        '<button type="button" class="el-phase-pill el-phase-pill--' + escapeHtml(ph.state) + '" ' +
        'data-phase-pill="' + escapeHtml(ph.key) + '" ' +
        'data-case-edit="' + cid + '" ' +
        'data-target-phase="' + escapeHtml(ph.key) + '" ' +
        'title="' + escapeHtml(ph.title) + '" ' +
        'aria-label="' + escapeHtml(ph.title) + '">' +
        phasePillIconSvg(ph.state) +
        '<span>' + escapeHtml(ph.code) + '</span>' +
        '</button>'
      )).join('') +
      '</div>'
    );
  }

  function renderCaseProgressionBar(c, contextView) {
    const cid = escapeHtml(c.case_id || '');
    const surv = c.surveillance || {};
    const prog = computeCasePhaseProgression(c);
    const isP2Pending = prog.p2.state === 'pending';
    const isPendingGpb = prog.p4.state === 'pending';
    const isPending30d = prog.p3.state === 'pending';
    const canCreateLinked = Boolean(
      !surv.fulfilled_by_case_id &&
      !isPendingGpb &&
      surv.category !== 'SURGICAL_MDT_CONSULT_ALERT' &&
      (contextView === 'surveillance' || prog.p4.state === 'active')
    );

    let contextualPrimaryBtnHtml = '';
    if (contextView === 'surveillance') {
      if (isPendingGpb) {
        contextualPrimaryBtnHtml = '<button type="button" class="el-btn el-btn--compact el-btn--primary action-btn-p4" data-case-edit="' + cid + '" data-target-phase="p4">Nhập GPB</button>';
      } else if (canCreateLinked) {
        contextualPrimaryBtnHtml = '<button type="button" class="el-btn el-btn--compact el-btn--primary action-btn-link-surv" data-create-linked="' + cid + '">Tạo ca soi lại</button>';
      } else if (isPending30d) {
        contextualPrimaryBtnHtml = '<button type="button" class="el-btn el-btn--compact el-btn--primary action-btn-p3" data-case-edit="' + cid + '" data-target-phase="p3">Theo dõi 30 ngày</button>';
      }
    } else if (isP2Pending) {
      contextualPrimaryBtnHtml = '<button type="button" class="el-btn el-btn--compact el-btn--primary action-btn-p2" data-case-edit="' + cid + '" data-target-phase="p2">Hoàn tất thủ thuật</button>';
    } else if (isPendingGpb) {
      contextualPrimaryBtnHtml = '<button type="button" class="el-btn el-btn--compact el-btn--primary action-btn-p4" data-case-edit="' + cid + '" data-target-phase="p4">Nhập GPB</button>';
    } else if (isPending30d) {
      contextualPrimaryBtnHtml = '<button type="button" class="el-btn el-btn--compact el-btn--primary action-btn-p3" data-case-edit="' + cid + '" data-target-phase="p3">Theo dõi 30 ngày</button>';
    } else if (canCreateLinked) {
      contextualPrimaryBtnHtml = '<button type="button" class="el-btn el-btn--compact el-btn--primary action-btn-link-surv" data-create-linked="' + cid + '">Tạo ca soi lại</button>';
    }

    const allowLinkInMenu = Boolean(!surv.fulfilled_by_case_id && !isPendingGpb && surv.category !== 'SURGICAL_MDT_CONSULT_ALERT');
    const isSuper = Boolean(state.user && state.user.role === 'superadmin');

    const overflowMenuHtml = (
      '<div class="el-action-menu-wrap">' +
      '<button type="button" class="el-btn el-btn--compact el-btn-more" data-case-more="' + cid + '" aria-haspopup="menu" aria-expanded="false" aria-label="Mở trình đơn thao tác nhanh 4 pha" title="Thao tác khác">' +
      moreDotsIconSvg() +
      '</button>' +
      '<div class="el-action-menu-dropdown" role="menu" hidden>' +
      '<button type="button" role="menuitem" class="el-action-menu-item" data-case-detail="' + cid + '">Xem chi tiết diễn tiến 4 pha</button>' +
      '<button type="button" role="menuitem" class="el-action-menu-item" data-case-edit="' + cid + '" data-target-phase="p1">Pha 1 · Hành chính &amp; chỉ định</button>' +
      '<button type="button" role="menuitem" class="el-action-menu-item" data-case-edit="' + cid + '" data-target-phase="p2">Pha 2 · Thông số thủ thuật</button>' +
      '<button type="button" role="menuitem" class="el-action-menu-item" data-case-edit="' + cid + '" data-target-phase="p3">Pha 3 · Biến cố 14–30 ngày</button>' +
      '<button type="button" role="menuitem" class="el-action-menu-item" data-case-edit="' + cid + '" data-target-phase="p4">Pha 4 · Giải phẫu bệnh &amp; hẹn soi</button>' +
      (allowLinkInMenu
        ? ('<button type="button" role="menuitem" class="el-action-menu-item" data-create-linked="' + cid + '">Tạo ca soi lại liên kết</button>')
        : '') +
      (isSuper
        ? ('<div class="el-action-menu-sep" role="separator"></div><button type="button" role="menuitem" class="el-action-menu-item el-action-menu-item--danger" data-danger-case="' + cid + '">Hủy hiệu lực hồ sơ...</button>')
        : '') +
      '</div>' +
      '</div>'
    );

    return (
      '<div class="el-card-progression-bar">' +
      renderPhasePillTrackHtml(c.case_id, prog) +
      '<div class="el-action-buttons-row">' +
      contextualPrimaryBtnHtml +
      '<button type="button" class="el-btn el-btn--compact action-btn-detail" data-case-detail="' + cid + '">Chi tiết</button>' +
      overflowMenuHtml +
      '</div>' +
      '</div>'
    );
  }

  function renderCasesView() {
    const summaryEl = byId('el-cases-summary');
    const listEl = byId('el-case-list');
    if (!summaryEl || !listEl) return;

    const all = state.cases;
    const urgentCount = all.filter((c) => c.clinical_badge && c.clinical_badge.tone === 'urgent').length;
    const pendingGpbCount = all.filter((c) => c.pathology_completion_status === 'PENDING' || c.pathology_completion_status === 'PARTIAL').length;
    const window30dCount = all.filter((c) => c.followup_30d_status === 'PENDING_WINDOW').length;

    summaryEl.innerHTML = [
      { label: 'Tổng ca đang quản lý', shortLabel: 'Tổng ca', value: all.length, sub: 'EGD: ' + all.filter((x) => x.track === 'EGD').length + ' · COL: ' + all.filter((x) => x.track === 'COL').length + ' · ERCP: ' + all.filter((x) => x.track === 'ERCP').length },
      { label: 'Cảnh báo Ngoại & biến cố', shortLabel: 'Cảnh báo', value: urgentCount, sub: 'Ưu tiên xử trí hội chẩn & theo dõi sát' },
      { label: 'Hồ sơ đang chờ GPB', shortLabel: 'Chờ GPB', value: pendingGpbCount, sub: 'Mở trực tiếp Pha 4 ngay khi có kết quả' },
      { label: 'Trong cửa sổ 14–30 ngày', shortLabel: 'Theo dõi', value: window30dCount, sub: 'Theo dõi biến cố muộn sau thủ thuật' }
    ].map((s) => (
      '<article class="el-stat-card">' +
      '<p class="el-stat-label"><span class="el-stat-label-full">' + escapeHtml(s.label) + '</span><span class="el-stat-label-short">' + escapeHtml(s.shortLabel) + '</span></p>' +
      '<p class="el-stat-value">' + escapeHtml(s.value) + '</p>' +
      '<p class="el-stat-sub">' + escapeHtml(s.sub) + '</p>' +
      '</article>'
    )).join('');

    const q = state.searchQuery.trim().toLowerCase();
    const filtered = all.filter((c) => {
      if (state.trackFilter !== 'ALL' && c.track !== state.trackFilter) return false;
      if (!q) return true;
      const hay = [
        c.case_code,
        c.patient && c.patient.privacy_initials,
        c.patient && c.patient.full_name,
        c.index_lesion && c.index_lesion.anatomical_site,
        formatIndicationVi(c.indication_detail, c.indication),
        c.surveillance && c.surveillance.surgical_consult_target_dept,
        c.clinical_note
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });

    listEl.innerHTML = filtered.map((c) => {
      const hl = describeTrackClinicalHighlights(c);
      const surv = c.surveillance || {};
      const pat = c.patient || {};
      const badgeObj = c.clinical_badge || { tone: 'neutral', label: 'Đang cập nhật' };
      const settingLabel = c.care_setting === 'INPATIENT' ? 'Nội trú' : 'Ngoại trú';
      const sexLabel = pat.sex === 'F' ? 'Nữ' : (pat.sex === 'O' ? 'Khác' : 'Nam');
      const mrnPart = pat.hospital_mrn_masked ? (' · Mã HS: ' + pat.hospital_mrn_masked) : '';
      const survSummary = surv.category === 'SURGICAL_MDT_CONSULT_ALERT'
        ? ('Chuyển hội chẩn ' + (surv.surgical_consult_target_dept || 'Ngoại khoa'))
        : ('Hẹn soi lại: ' + (surv.recommended_interval_label || 'Theo chỉ định') + (surv.due_date ? (' (' + formatViDate(surv.due_date) + ')') : ''));
      const guidelineShort = formatGuidelineLabelVi(surv.guideline_id, true);
      const refShort = surv.reference_guideline_id ? formatGuidelineLabelVi(surv.reference_guideline_id, true) : 'ESGE 2020';

      return (
        '<article class="el-case-card">' +
        '<div class="el-case-top">' +
        '<div class="el-case-id-group">' +
        renderProcChip(c.track) +
        '<span class="el-case-code">' + escapeHtml(c.case_code) + '</span>' +
        '<span class="el-case-meta">' + escapeHtml(formatViDate(c.procedure_start_at)) + ' · ' + escapeHtml(settingLabel) + '</span>' +
        '</div>' +
        renderStatusBadge(badgeObj.tone, humanizeClinicalBadgeLabelVi(badgeObj.label)) +
        '</div>' +
        '<div class="el-case-grid">' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Người bệnh &amp; chỉ định</p>' +
        '<p class="el-field-primary">' + escapeHtml(pat.privacy_initials || '') + ' · ' + escapeHtml(pat.age) + ' tuổi (' + escapeHtml(sexLabel) + ')' + escapeHtml(mrnPart) + '</p>' +
        '<p class="el-field-secondary">' + escapeHtml(formatIndicationVi(c.indication_detail, c.indication)) + '</p>' +
        '</div>' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Thông số kỹ thuật &amp; tổn thương đại diện</p>' +
        '<p class="el-field-primary">' + escapeHtml(hl.title) + '</p>' +
        '<p class="el-field-secondary">' + escapeHtml(hl.detail) + '</p>' +
        '</div>' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Giải phẫu bệnh &amp; hướng xử trí</p>' +
        '<p class="el-field-primary">' + escapeHtml(survSummary) + '</p>' +
        '<p class="el-field-muted">' + escapeHtml(guidelineShort) + (surv.is_divergent_guideline ? (' · Đối chiếu ' + escapeHtml(refShort) + ': ' + escapeHtml(surv.reference_interval_label)) : '') + '</p>' +
        '</div>' +
        '</div>' +
        renderCaseProgressionBar(c, 'cases') +
        '</article>'
      );
    }).join('');
  }

  function renderSurveillanceView() {
    const listEl = byId('el-surveillance-list');
    if (!listEl) return;

    const rows = state.surveillanceRows.filter((r) => {
      if (state.survFilter === 'ALL') return true;
      return r.urgency && r.urgency.tone === state.survFilter;
    });

    listEl.innerHTML = rows.map((r) => {
      const fullCase = state.cases.find((item) => item.case_id === r.case_id) || r;
      const surv = r.surveillance || fullCase.surveillance || {};
      const pat = r.patient || fullCase.patient || {};
      const urg = r.urgency || { tone: 'neutral', label: 'Chưa đến hạn' };
      const sexLabel = pat.sex === 'F' ? 'Nữ' : (pat.sex === 'O' ? 'Khác' : 'Nam');
      const primaryPlan = surv.category === 'SURGICAL_MDT_CONSULT_ALERT'
        ? ('Hội chẩn chuyên khoa: ' + (surv.surgical_consult_target_dept || 'Ngoại khoa'))
        : ('Mốc hẹn soi lại: ' + (surv.recommended_interval_label || 'Theo chỉ định') + (surv.due_date ? (' · Ngày dự kiến ' + formatViDate(surv.due_date)) : ''));

      const primaryGuideFull = formatGuidelineLabelVi(surv.guideline_id, false);
      const primaryGuideShort = formatGuidelineLabelVi(surv.guideline_id, true);
      const refGuideShort = formatGuidelineLabelVi(surv.reference_guideline_id, true);

      const divergenceHtml = surv.is_divergent_guideline
        ? (
          '<div class="el-guideline-box">' +
          '<div><strong>Khuyến cáo chính (' + escapeHtml(primaryGuideShort) + '):</strong> ' + escapeHtml(surv.recommended_interval_label) + '</div>' +
          '<div class="el-guideline-ref">Tham chiếu song song (' + escapeHtml(refGuideShort) + '): ' + escapeHtml(surv.reference_interval_label) + '</div>' +
          '</div>'
        )
        : '';

      return (
        '<article class="el-case-card">' +
        '<div class="el-case-top">' +
        '<div class="el-case-id-group">' +
        renderProcChip(r.track || fullCase.track) +
        '<span class="el-case-code">' + escapeHtml(r.case_code || fullCase.case_code) + '</span>' +
        '<span class="el-case-meta">Ngày soi gốc: ' + escapeHtml(formatViDate(r.procedure_date || fullCase.procedure_start_at)) + '</span>' +
        '</div>' +
        renderStatusBadge(urg.tone, humanizeClinicalBadgeLabelVi(urg.label)) +
        '</div>' +
        '<div class="el-case-grid">' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Người bệnh &amp; bệnh cảnh gốc</p>' +
        '<p class="el-field-primary">' + escapeHtml(pat.privacy_initials || '') + ' · ' + escapeHtml(pat.age) + ' tuổi (' + escapeHtml(sexLabel) + ')</p>' +
        '<p class="el-field-secondary">' + escapeHtml(formatIndicationVi(r.indication_detail || fullCase.indication_detail, fullCase.indication || '')) + '</p>' +
        '</div>' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Quyết định hẹn soi lại / hội chẩn</p>' +
        '<p class="el-field-primary">' + escapeHtml(primaryPlan) + '</p>' +
        '<p class="el-field-secondary">' + escapeHtml(surv.reason || '') + '</p>' +
        divergenceHtml +
        '</div>' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Nguồn hướng dẫn áp dụng</p>' +
        '<p class="el-field-primary">' + escapeHtml(primaryGuideFull) + '</p>' +
        '<p class="el-field-muted">' + escapeHtml(surv.fulfilled_by_case_id ? 'Đã soi lại' : 'Đang theo dõi') + '</p>' +
        '</div>' +
        '</div>' +
        renderCaseProgressionBar(fullCase, 'surveillance') +
        '</article>'
      );
    }).join('');
  }

  function renderCusumSvg(cusum) {
    const pts = cusum.points || [];
    const h = cusum.h_limit || 2.890372;
    const traj = Array.isArray(cusum.trajectory) && cusum.trajectory.length > 0 ? cusum.trajectory : [0];
    const width = 760;
    const height = 210;
    const padL = 48;
    const padR = 24;
    const padT = 22;
    const padB = 34;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;
    const yMax = Math.max(3.4, h * 1.18, ...traj);

    function xPos(i) {
      const n = Math.max(1, pts.length);
      return padL + (i / n) * plotW;
    }
    function yPos(val) {
      return padT + plotH - (Math.min(val, yMax) / yMax) * plotH;
    }

    const polyPoints = traj.map((v, idx) => xPos(idx).toFixed(1) + ',' + yPos(v).toFixed(1)).join(' ');
    const yThresh = yPos(h).toFixed(1);
    const yZero = yPos(0).toFixed(1);
    const yMid = yPos(h / 2).toFixed(1);

    const circles = traj.map((v, idx) => {
      const label = idx === 0 ? 'Khởi điểm' : (pts[idx - 1] ? pts[idx - 1].case_code : ('Ca ' + idx));
      return (
        '<circle cx="' + xPos(idx).toFixed(1) + '" cy="' + yPos(v).toFixed(1) + '" r="4.5" fill="var(--chart-line)">' +
        '<title>' + escapeHtml(label + ': S=' + v.toFixed(3)) + '</title>' +
        '</circle>'
      );
    }).join('');

    const xLabels = pts.map((pt, idx) => (
      '<text x="' + xPos(idx + 1).toFixed(1) + '" y="' + (height - 10) + '" text-anchor="middle" fill="var(--text-muted)" font-size="11">' +
      escapeHtml(pt.case_code) +
      '</text>'
    )).join('');

    return (
      '<svg class="el-cusum-svg" viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="Biểu đồ kiểm soát chất lượng Tabular Bernoulli QC-CUSUM">' +
      '<line x1="' + padL + '" y1="' + yZero + '" x2="' + (width - padR) + '" y2="' + yZero + '" stroke="var(--chart-grid)" stroke-width="1"/>' +
      '<line x1="' + padL + '" y1="' + yMid + '" x2="' + (width - padR) + '" y2="' + yMid + '" stroke="var(--chart-grid)" stroke-width="1" stroke-dasharray="3 3"/>' +
      '<line x1="' + padL + '" y1="' + yThresh + '" x2="' + (width - padR) + '" y2="' + yThresh + '" stroke="var(--chart-threshold)" stroke-width="1.75" stroke-dasharray="6 4"/>' +
      '<text x="' + (width - padR) + '" y="' + (Number(yThresh) - 6).toFixed(1) + '" text-anchor="end" fill="var(--chart-threshold)" font-size="11" font-weight="600">Ngưỡng cảnh báo h = ' + formatViNum(h.toFixed(2)) + '</text>' +
      '<text x="' + (padL - 8) + '" y="' + (Number(yZero) + 4).toFixed(1) + '" text-anchor="end" fill="var(--text-muted)" font-size="11">0,0</text>' +
      '<polyline fill="none" stroke="var(--chart-line)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" points="' + polyPoints + '"/>' +
      circles +
      xLabels +
      '</svg>'
    );
  }

  function renderQualityView() {
    const gridEl = byId('el-kpi-grid');
    const discEl = byId('el-cusum-disclaimer');
    const cusumEl = byId('el-cusum-container');
    const auditEl = byId('el-audit-strip');
    if (!gridEl || !state.kpiBundle) return;

    const k = state.kpiBundle.kpi;
    const nMin = (typeof k.n_min === 'number' && k.n_min >= 1)
      ? k.n_min
      : (state.kpiBundle.kpi_min_sample_size || 20);
    const cirBadge = evaluateKpiRateBadge(k.cir, nMin);
    const bbpsBadge = evaluateKpiRateBadge(k.bbps_adequate, nMin);
    const adrBadge = evaluateKpiRateBadge(k.adr, nMin);
    const ssldrBadge = evaluateKpiRateBadge(k.ssldr, nMin);
    const ercpBadge = evaluateKpiRateBadge(k.ercp_native_cannulation, nMin);
    const aeBadge = evaluateAdverseEventKpiBadge(k.adverse_events_all, k.ercp_pep);

    const aePendingWindow = typeof k.adverse_events_all.pending_window_count === 'number'
      ? k.adverse_events_all.pending_window_count
      : k.adverse_events_all.missing_or_pending_fu_count;
    const aeLostFu = typeof k.adverse_events_all.lost_to_followup_count === 'number'
      ? k.adverse_events_all.lost_to_followup_count
      : 0;
    const aeNoteTail = aeLostFu > 0
      ? ('Đang trong cửa sổ 30 ngày tách riêng: ' + aePendingWindow + ' ca · Mất dấu theo dõi: ' + aeLostFu + ' ca')
      : ('Đang trong cửa sổ 30 ngày tách riêng: ' + aePendingWindow + ' ca');

    const cards = [
      {
        title: 'Luồn tới manh tràng (CIR)',
        chip: 'COL',
        rate: formatViPct(k.cir.rate_pct),
        frac: k.cir.numerator + ' / ' + k.cir.denominator + ' ca mục tiêu toàn bộ khung đại tràng',
        note: 'Chuẩn tham chiếu ≥ 90% (tầm soát ≥ 95%)',
        badge: renderStatusBadge(cirBadge.tone, cirBadge.label)
      },
      {
        title: 'Chuẩn bị đại tràng đạt (BBPS)',
        chip: 'COL',
        rate: formatViPct(k.bbps_adequate.rate_pct),
        frac: k.bbps_adequate.numerator + ' / ' + k.bbps_adequate.denominator + ' ca chấm đủ 3 đoạn',
        note: 'Yêu cầu tổng BBPS ≥ 6 và mỗi đoạn đại tràng ≥ 2 · Chuẩn ≥ 90%',
        badge: renderStatusBadge(bbpsBadge.tone, bbpsBadge.label)
      },
      {
        title: 'Phát hiện u tuyến (ADR ≥ ' + k.min_adr_age + ' tuổi)',
        chip: 'COL',
        rate: formatViPct(k.adr.rate_pct),
        frac: k.adr.numerator + ' / ' + k.adr.denominator + ' ca tầm soát / chẩn đoán đã có GPB',
        note: 'Tách khỏi mẫu số: ' + k.adr.pending_gpb_excluded_count + ' ca chờ GPB · Chuẩn ASGE/ACG ≥ 35%',
        badge: renderStatusBadge(adrBadge.tone, adrBadge.label)
      },
      {
        title: 'Polyp răng cưa không cuống (SSLDR)',
        chip: 'COL',
        rate: formatViPct(k.ssldr.rate_pct),
        frac: k.ssldr.numerator + ' / ' + k.ssldr.denominator + ' ca đã xác nhận mô bệnh học',
        note: 'PDR đại thể cùng đoàn hệ: ' + formatViPct(k.pdr.rate_pct) + ' (' + k.pdr.numerator + '/' + k.pdr.denominator + ') · Chuẩn ≥ 6%',
        badge: renderStatusBadge(ssldrBadge.tone, ssldrBadge.label)
      },
      {
        title: 'Thông nhú chọn lọc nhú nguyên vẹn',
        chip: 'ERCP',
        rate: formatViPct(k.ercp_native_cannulation.rate_pct),
        frac: k.ercp_native_cannulation.numerator + ' / ' + k.ercp_native_cannulation.denominator + ' ca nhú Vater nguyên vẹn',
        note: 'Thông nhú khó theo ESGE 2016: ' + k.ercp_native_cannulation.difficult_esge2016_count + ' ca · Chuẩn ≥ 90%',
        badge: renderStatusBadge(ercpBadge.tone, ercpBadge.label)
      },
      {
        title: 'Biến cố hoàn tất theo dõi 30 ngày',
        chips: ['EGD', 'COL', 'ERCP'],
        rate: formatViPct(k.adverse_events_all.agree_severe_rate_pct),
        frac: 'AGREE ≥ III: ' + k.adverse_events_all.agree_severe_numerator + ' / ' + k.adverse_events_all.completed_fu_denominator + ' ca hoàn tất theo dõi',
        note: 'Viêm tụy sau ERCP: ' + k.ercp_pep.numerator + '/' + k.ercp_pep.completed_fu_denominator + ' ca · ' + aeNoteTail,
        badge: renderStatusBadge(aeBadge.tone, aeBadge.label)
      }
    ];

    gridEl.innerHTML = cards.map((c) => {
      const chipHtml = c.chips
        ? '<div class="el-kpi-chip-cluster">' + c.chips.map((tr) => renderProcChip(tr)).join('') + '</div>'
        : renderProcChip(c.chip);
      return (
        '<article class="el-kpi-card">' +
        '<div>' +
        '<div class="el-kpi-header">' +
        '<h2 class="el-kpi-title">' + escapeHtml(c.title) + '</h2>' +
        chipHtml +
        '</div>' +
        '<p class="el-kpi-rate">' + escapeHtml(c.rate) + '</p>' +
        '<p class="el-kpi-fraction">' + escapeHtml(c.frac) + '</p>' +
        '</div>' +
        '<div>' +
        '<div class="el-kpi-badge-row">' + c.badge + '</div>' +
        '<p class="el-kpi-note">' + escapeHtml(c.note) + '</p>' +
        '</div>' +
        '</article>'
      );
    }).join('');

    const activeCusum = state.cusumData || (state.cusumMetric === 'ERCP_NATIVE' ? state.kpiBundle.cusum_ercp : state.kpiBundle.cusum_cir);
    if (discEl && activeCusum) {
      discEl.textContent = activeCusum.disclaimer_vi + ' (' + formatRaCusumStatusVi(activeCusum.ra_cusum_status) + ').';
    }
    if (cusumEl && activeCusum) {
      cusumEl.innerHTML = renderCusumSvg(activeCusum);
    }

    if (auditEl && state.auditStatus) {
      const v = state.auditStatus.verification;
      auditEl.innerHTML = (
        '<div>' +
        renderStatusBadge(v.valid ? 'ned' : 'urgent', v.valid ? ('Chuỗi kiểm toán toàn vẹn (' + v.checked_entries + ' bản ghi)') : 'Phát hiện sai lệch chuỗi băm') +
        '</div>' +
        '<div>Mã băm đầu chuỗi SHA-256: <span class="el-audit-hash">' + escapeHtml(v.head_hash || '') + '</span></div>'
      );
    }

    syncSettingsPanelInputs();
  }

  function switchView(viewName, skipPersist) {
    const allowed = ['cases', 'surveillance', 'quality'];
    const target = allowed.includes(viewName) ? viewName : 'cases';
    state.activeView = target;
    if (!skipPersist && state.user) {
      try {
        window.sessionStorage.setItem(TAB_SESSION_KEY, target);
      } catch (_err) {
        /* ignore */
      }
    }

    const vCases = byId('el-view-cases');
    const vSurv = byId('el-view-surveillance');
    const vQual = byId('el-view-quality');
    if (vCases) vCases.hidden = target !== 'cases';
    if (vSurv) vSurv.hidden = target !== 'surveillance';
    if (vQual) vQual.hidden = target !== 'quality';

    document.querySelectorAll('[data-nav-target]').forEach((btn) => {
      const active = btn.getAttribute('data-nav-target') === target;
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
  }

  function resetUiControlsToDefault() {
    document.querySelectorAll('[data-track-filter]').forEach((p) => {
      p.setAttribute('aria-pressed', p.getAttribute('data-track-filter') === 'ALL' ? 'true' : 'false');
    });
    document.querySelectorAll('[data-surv-filter]').forEach((p) => {
      p.setAttribute('aria-pressed', p.getAttribute('data-surv-filter') === 'ALL' ? 'true' : 'false');
    });
    document.querySelectorAll('[data-age-toggle]').forEach((p) => {
      p.setAttribute('aria-pressed', p.getAttribute('data-age-toggle') === '45' ? 'true' : 'false');
    });
    document.querySelectorAll('[data-cusum-metric]').forEach((p) => {
      p.setAttribute('aria-pressed', p.getAttribute('data-cusum-metric') === 'CIR' ? 'true' : 'false');
    });
    switchView('cases', true);
  }

  function setLoginControlsDisabled(disabled) {
    const bypassBtn = byId('el-btn-dev-bypass');
    if (bypassBtn) bypassBtn.disabled = Boolean(disabled);
    document.querySelectorAll('#el-login-form button').forEach((btn) => {
      btn.disabled = Boolean(disabled);
    });
  }

  function setLoginErrorBanner(message) {
    const errEl = byId('el-login-error');
    if (!errEl) return;
    if (message) {
      errEl.textContent = String(message);
      errEl.hidden = false;
    } else {
      errEl.textContent = '';
      errEl.hidden = true;
    }
  }

  function clearSessionTimers() {
    if (state.idleTimer) {
      window.clearTimeout(state.idleTimer);
      state.idleTimer = null;
    }
    if (state.hardExpiryTimer) {
      window.clearTimeout(state.hardExpiryTimer);
      state.hardExpiryTimer = null;
    }
    idleDeadlineMs = 0;
    hardSessionDeadlineMs = 0;
  }

  function bumpSessionEpoch(createNewController) {
    sessionEpoch += 1;
    kpiReqSeq += 1;
    cusumReqSeq += 1;
    if (activeAbortController) {
      try {
        activeAbortController.abort();
      } catch (_err) {
        /* ignore */
      }
      activeAbortController = null;
    }
    if (createNewController && typeof AbortController !== 'undefined') {
      activeAbortController = new AbortController();
    }
    return sessionEpoch;
  }

  function isSessionActiveForEpoch(expectedEpoch) {
    return Boolean(state.user) && expectedEpoch === sessionEpoch;
  }

  function isExpectedSessionTerminationError(err) {
    if (!err) return false;
    if (err.name === 'AbortError') return true;
    const msg = String(err.message || '');
    return msg === 'UNAUTHENTICATED' || msg === 'STALE_SESSION_ABORTED';
  }

  /* ==========================================================================
   * PHASE 4B: ĐIỀU KHIỂN NGĂN KÉO 4 PHA, CẤU HÌNH CHUYÊN MÔN & XUẤT HỒ SƠ A/B/C
   * ========================================================================== */

  function populateSelectOptions(selectId, items, defaultVal) {
    const el = byId(selectId);
    if (!el) return;
    el.innerHTML = items.map((it) => (
      '<option value="' + escapeHtml(it.code) + '">' + escapeHtml(it.label) + '</option>'
    )).join('');
    if (defaultVal !== undefined) {
      el.value = defaultVal;
    }
  }

  function computePrivacyInitialsVi(fullName) {
    const parts = String(fullName || '').trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '';
    return parts.slice(0, 4).map((w) => w.charAt(0).toUpperCase()).join('.');
  }

  function formatLocalDatetimeInput(isoOrNow) {
    const dtObj = isoOrNow ? new Date(isoOrNow) : new Date();
    const safe = Number.isNaN(dtObj.getTime()) ? new Date() : dtObj;
    const pad = (n) => String(n).padStart(2, '0');
    return (
      safe.getFullYear() + '-' +
      pad(safe.getMonth() + 1) + '-' +
      pad(safe.getDate()) + 'T' +
      pad(safe.getHours()) + ':' +
      pad(safe.getMinutes())
    );
  }

  function populateIndicationOptionsForTrack(track, selectedCode) {
    const el = byId('el-f-indication');
    if (!el) return;
    const orderByTrack = {
      COL: ['SCREENING', 'ABNORMAL_FECAL_TEST', 'DIAGNOSTIC', 'SURVEILLANCE', 'THERAPEUTIC', 'GI_BLEEDING', 'IBD_EVAL', 'EARLY_CANCER_WORKUP', 'OTHER'],
      EGD: ['DIAGNOSTIC', 'EARLY_CANCER_WORKUP', 'GI_BLEEDING', 'THERAPEUTIC', 'SURVEILLANCE', 'SCREENING', 'OTHER'],
      ERCP: ['BILIARY_STONE', 'CHOLANGITIS', 'MALIGNANT_STRICTURE', 'BILIARY_PANCREATITIS', 'STENT_EXCHANGE', 'THERAPEUTIC', 'DIAGNOSTIC', 'OTHER']
    };
    const codes = orderByTrack[track] || Object.keys(INDICATION_LABELS_VI);
    const merged = codes.slice();
    if (selectedCode && !merged.includes(selectedCode) && INDICATION_LABELS_VI[selectedCode]) {
      merged.unshift(selectedCode);
    }
    el.innerHTML = merged.map((c) => (
      '<option value="' + escapeHtml(c) + '">' + escapeHtml(INDICATION_LABELS_VI[c] || 'Chỉ định khác') + '</option>'
    )).join('');
    el.value = selectedCode && merged.includes(selectedCode) ? selectedCode : (TRACK_DEFAULT_INDICATION[track] || merged[0]);
  }

  function initFormOptions() {
    populateSelectOptions('el-setting-guideline', [
      { code: 'USMSTF_2020', label: 'USMSTF 2020 (mặc định chính)' },
      { code: 'ESGE_2020', label: 'ESGE 2020' }
    ], 'USMSTF_2020');

    populateSelectOptions('el-setting-cusum-preset', [
      { code: 'DEFAULT_90', label: 'Mục tiêu chung ≥ 90% (p0 = 0,10)' },
      { code: 'SCREENING_CIR_95', label: 'Tầm soát ≥ 95% (p0 = 0,05)' }
    ], 'DEFAULT_90');

    populateIndicationOptionsForTrack('COL', 'SCREENING');

    populateSelectOptions('el-f-cecal', [
      { code: 'YES', label: 'Đã luồn tới manh tràng' },
      { code: 'NO', label: 'Chưa luồn tới manh tràng' },
      { code: 'NA', label: 'Không áp dụng' }
    ], 'YES');

    populateSelectOptions('el-f-complete-resection', [
      { code: 'ALL_RESECTED_COMPLETELY', label: 'Đã cắt trọn hoàn toàn mọi polyp' },
      { code: 'INCOMPLETE_OR_UNRESECTED', label: 'Còn polyp chưa cắt hoặc cắt dở dang' },
      { code: 'NOT_APPLICABLE', label: 'Không áp dụng (0 polyp)' }
    ], 'NOT_APPLICABLE');

    populateSelectOptions('el-f-piecemeal-20', [
      { code: 'NO', label: 'Không' },
      { code: 'YES', label: 'Có cắt từng mảnh polyp ≥ 20 mm' }
    ], 'NO');

    populateSelectOptions('el-f-bleeding-source', [
      { code: 'NONE', label: 'Không xuất huyết tiêu hóa' },
      { code: 'VARICEAL_ESOPHAGEAL', label: 'Vỡ giãn tĩnh mạch thực quản' },
      { code: 'VARICEAL_GASTRIC', label: 'Vỡ giãn tĩnh mạch phình vị — tâm vị' },
      { code: 'NON_VARICEAL_ULCER', label: 'Loét dạ dày — tá tràng xuất huyết' },
      { code: 'NON_VARICEAL_OTHER', label: 'Nguồn chảy máu không do vỡ giãn khác' }
    ], 'NONE');

    populateSelectOptions('el-f-forrest', [
      { code: '', label: 'Không áp dụng' },
      { code: 'Ia', label: 'Forrest Ia — Máu phun thành tia' },
      { code: 'Ib', label: 'Forrest Ib — Máu rỉ rả hoạt động' },
      { code: 'IIa', label: 'Forrest IIa — Điểm mạch lộ rõ' },
      { code: 'IIb', label: 'Forrest IIb — Cục máu đông bám chặt' },
      { code: 'IIc', label: 'Forrest IIc — Cặn máu đen đáy loét' },
      { code: 'III', label: 'Forrest III — Đáy ổ loét sạch' }
    ], '');

    populateSelectOptions('el-f-hemostasis-mod', Object.keys(HEMOSTASIS_MODALITY_LABELS_VI).map((k) => ({
      code: k,
      label: HEMOSTASIS_MODALITY_LABELS_VI[k]
    })), 'NONE');

    populateSelectOptions('el-f-hemostasis-success', [
      { code: 'NA', label: 'Không áp dụng' },
      { code: 'YES', label: 'Cầm máu tức thì thành công' },
      { code: 'NO', label: 'Thất bại cầm máu ban đầu' }
    ], 'NA');

    populateSelectOptions('el-f-paris-class', [
      { code: '', label: 'Chưa phân loại / Không áp dụng' },
      { code: '0-Ip', label: 'Paris 0-Ip (có cuống)' },
      { code: '0-Isp', label: 'Paris 0-Isp (bán cuống)' },
      { code: '0-Is', label: 'Paris 0-Is (không cuống nhô)' },
      { code: '0-IIa', label: 'Paris 0-IIa (phẳng gồ nhẹ)' },
      { code: '0-IIb', label: 'Paris 0-IIb (phẳng hoàn toàn)' },
      { code: '0-IIc', label: 'Paris 0-IIc (phẳng lõm)' },
      { code: '0-IIa+IIc', label: 'Paris 0-IIa+IIc (gồ nhẹ kèm lõm)' },
      { code: '0-III', label: 'Paris 0-III (loét sâu)' },
      { code: 'LST-G', label: 'Tổn thương lan rộng dạng hạt (LST-G)' },
      { code: 'LST-NG', label: 'Tổn thương lan rộng không hạt (LST-NG)' }
    ], '');

    populateSelectOptions('el-f-resection-method', [
      { code: 'NONE', label: 'Quan sát chẩn đoán (không sinh thiết)' },
      { code: 'BIOPSY_ONLY', label: 'Sinh thiết kìm chẩn đoán' },
      { code: 'COLD_SNARE', label: 'Cắt polyp bằng thòng lọng lạnh' },
      { code: 'HOT_SNARE', label: 'Cắt polyp bằng thòng lọng nhiệt' },
      { code: 'EMR_EN_BLOC', label: 'Cắt niêm mạc nguyên khối (EMR)' },
      { code: 'EMR_PIECEMEAL', label: 'Cắt niêm mạc từng mảnh (EMR)' },
      { code: 'ESD', label: 'Cắt tách dưới niêm mạc (ESD)' },
      { code: 'HEMOSTASIS', label: 'Can thiệp cầm máu qua nội soi' },
      { code: 'UNRESECTED_REFERRED', label: 'Chưa cắt qua nội soi (chuyển hội chẩn)' }
    ], 'NONE');

    populateSelectOptions('el-f-papilla-status', Object.keys(PAPILLA_STATUS_LABELS_VI).map((k) => ({
      code: k,
      label: PAPILLA_STATUS_LABELS_VI[k]
    })), 'NATIVE_INTACT');

    populateSelectOptions('el-f-target-duct', [
      { code: 'CBD', label: 'Ống mật chủ (CBD)' },
      { code: 'PD', label: 'Ống tụy chính (PD)' },
      { code: 'BOTH', label: 'Cả ống mật chủ và ống tụy' }
    ], 'CBD');

    populateSelectOptions('el-f-selective-cann', [
      { code: 'SUCCESS', label: 'Thông nhú chọn lọc thành công' },
      { code: 'FAILED', label: 'Thông nhú chọn lọc thất bại' }
    ], 'SUCCESS');

    populateSelectOptions('el-f-cann-tech', [
      { code: 'STANDARD_SPHINCTEROTOME_GUIDEWIRE', label: 'Chuẩn guidewire qua dao cắt cơ vòng' },
      { code: 'DOUBLE_GUIDEWIRE', label: 'Kỹ thuật hai dây dẫn (Double-guidewire)' },
      { code: 'NEEDLE_KNIFE_PRECUT', label: 'Cắt trước bằng dao kim (Needle-knife precut)' },
      { code: 'TRANSPANCREATIC_SPHINCTEROTOMY', label: 'Cắt vách qua ống tụy (TPS)' },
      { code: 'FISTULOTOMY_SUPRAPAPILLARY', label: 'Mở rò trên nhú (Suprapapillary fistulotomy)' },
      { code: 'EUS_RENDEZVOUS', label: 'Hỗ trợ siêu âm nội soi (EUS-rendezvous)' }
    ], 'STANDARD_SPHINCTEROTOME_GUIDEWIRE');

    populateSelectOptions('el-f-altered-anat', [
      { code: 'NONE', label: 'Giải phẫu tiêu hóa trên bình thường' },
      { code: 'BILLROTH_II', label: 'Sau nối vị tràng Billroth II' },
      { code: 'ROUX_EN_Y', label: 'Sau nối kiểu Roux-en-Y' },
      { code: 'OTHER', label: 'Biến đổi giải phẫu sau mổ khác' }
    ], 'NONE');

    populateSelectOptions('el-f-img-mod', [
      { code: 'MRCP', label: 'Cộng hưởng từ mật tụy (MRCP)' },
      { code: 'EUS', label: 'Siêu âm nội soi (EUS)' },
      { code: 'CT', label: 'Cắt lớp vi tính bụng cản quang (CT)' },
      { code: 'US', label: 'Siêu âm bụng tổng quát' }
    ], 'MRCP');

    populateSelectOptions('el-f-followup-30d', [
      { code: 'PENDING_WINDOW', label: 'Đang trong cửa sổ theo dõi 14–30 ngày' },
      { code: 'COMPLETED_NO_AE', label: 'Hoàn tất 30 ngày — không ghi nhận biến cố' },
      { code: 'COMPLETED_WITH_AE', label: 'Hoàn tất — có ghi nhận biến cố sau thủ thuật' },
      { code: 'LOST_TO_FOLLOWUP', label: 'Mất dấu theo dõi sau xuất viện' }
    ], 'PENDING_WINDOW');

    populateSelectOptions('el-f-path-status', [
      { code: 'NOT_APPLICABLE', label: 'Không sinh thiết / không áp dụng' },
      { code: 'PENDING', label: 'Đang chờ kết quả giải phẫu bệnh' },
      { code: 'PARTIAL', label: 'Đã có một phần kết quả giải phẫu bệnh' },
      { code: 'COMPLETE', label: 'Đã hoàn tất toàn bộ giải phẫu bệnh' }
    ], 'NOT_APPLICABLE');

    populateSelectOptions('el-f-histology', Object.keys(HISTOLOGY_LABELS_VI).map((k) => ({
      code: k,
      label: HISTOLOGY_LABELS_VI[k]
    })), 'NONE');

    populateSelectOptions('el-f-dysplasia', [
      { code: 'NONE', label: 'Không loạn sản' },
      { code: 'LGD', label: 'Loạn sản biểu mô độ thấp (LGD)' },
      { code: 'HGD', label: 'Loạn sản biểu mô độ cao (HGD)' },
      { code: 'INVASIVE', label: 'Ung thư biểu mô xâm lấn' }
    ], 'NONE');

    populateSelectOptions('el-f-margins', [
      { code: 'NA', label: 'Không áp dụng (chưa cắt / chỉ sinh thiết)' },
      { code: 'PENDING', label: 'Đang chờ kết quả diện cắt' },
      { code: 'R0', label: 'Diện cắt âm tính hoàn toàn (R0)' },
      { code: 'HM1_ONLY', label: 'Dương tính diện ngang đơn thuần (HM1)' },
      { code: 'VM1_OR_R1', label: 'Dương tính diện sâu (VM1 / R1)' },
      { code: 'RX_PIECEMEAL', label: 'Không xác định diện cắt do cắt từng mảnh (RX)' }
    ], 'NA');

    populateSelectOptions('el-f-lvi', [
      { code: 'NA', label: 'Không áp dụng' },
      { code: 'NEGATIVE', label: 'Âm tính (không xâm nhập mạch)' },
      { code: 'POSITIVE', label: 'Dương tính (có xâm nhập mạch)' }
    ], 'NA');

    populateSelectOptions('el-f-diff', [
      { code: 'NA', label: 'Không áp dụng' },
      { code: 'WELL_MOD', label: 'Biệt hóa tốt — vừa (G1 / G2)' },
      { code: 'POOR_UNDIFF', label: 'Biệt hóa kém — không biệt hóa (G3)' }
    ], 'NA');

    populateSelectOptions('el-f-budding', [
      { code: 'NA', label: 'Không áp dụng' },
      { code: 'BD1', label: 'Nảy chồi thấp (BD1: 0–4 ổ)' },
      { code: 'BD2_BD3', label: 'Nảy chồi trung bình — cao (BD2 / BD3)' }
    ], 'NA');

    const triStateOpts = [
      { code: 'NO', label: 'Không' },
      { code: 'YES', label: 'Có' },
      { code: 'PENDING_UNKNOWN', label: 'Đang chờ xác nhận mô bệnh học' }
    ];
    ['el-f-wc-any-ad', 'el-f-wc-vill-hgd', 'el-f-wc-hgd', 'el-f-wc-any-ssl', 'el-f-wc-ssl-dys', 'el-f-wc-inv-noncur'].forEach((id) => {
      populateSelectOptions(id, triStateOpts, 'NO');
    });

    populateSelectOptions('el-f-wc-ad-bin', [
      { code: '0', label: '0 u tuyến' },
      { code: '1_2', label: '1–2 u tuyến' },
      { code: '3_4', label: '3–4 u tuyến' },
      { code: '5_10', label: '5–10 u tuyến' },
      { code: 'GT_10', label: 'Trên 10 u tuyến' }
    ], '0');

    populateSelectOptions('el-f-wc-ssl-bin', [
      { code: '0', label: '0 polyp răng cưa (SSL)' },
      { code: '1_2', label: '1–2 polyp răng cưa (SSL)' },
      { code: '3_4', label: '3–4 polyp răng cưa (SSL)' },
      { code: 'GE_5', label: 'Từ 5 polyp răng cưa trở lên' }
    ], '0');
  }

  function syncSettingsPanelInputs() {
    const gEl = byId('el-setting-guideline');
    const nEl = byId('el-setting-n-min');
    const cEl = byId('el-setting-cusum-preset');
    if (gEl && state.settings && state.settings.colo_guideline_mode) {
      gEl.value = state.settings.colo_guideline_mode;
    }
    if (nEl && state.settings && typeof state.settings.kpi_min_sample_size === 'number') {
      nEl.value = String(state.settings.kpi_min_sample_size);
    }
    if (cEl && state.settings && state.settings.cusum_preset) {
      cEl.value = state.settings.cusum_preset;
    }
  }

  function stopWithdrawalStopwatch() {
    if (drawerState.timerIntervalId) {
      window.clearInterval(drawerState.timerIntervalId);
      drawerState.timerIntervalId = null;
    }
    drawerState.timerRunning = false;
  }

  function updateStopwatchUi() {
    const toggleBtn = byId('el-btn-timer-toggle');
    const applyBtn = byId('el-btn-timer-apply');
    const dispEl = byId('el-timer-display');
    if (!toggleBtn || !applyBtn || !dispEl) return;
    toggleBtn.textContent = drawerState.timerRunning ? 'Tạm dừng' : 'Bấm giờ';
    const mins = Math.floor(drawerState.timerElapsedSec / 60);
    const secs = drawerState.timerElapsedSec % 60;
    dispEl.textContent = String(mins).padStart(2, '0') + ':' + String(secs).padStart(2, '0');
    applyBtn.hidden = drawerState.timerElapsedSec <= 0 && !drawerState.timerRunning;
  }

  function setDrawerAlert(message) {
    const el = byId('el-drawer-alert');
    if (!el) return;
    if (message) {
      el.textContent = String(message);
      el.hidden = false;
    } else {
      el.textContent = '';
      el.hidden = true;
    }
  }

  function setDrawerSyncBadge(text, tone) {
    const el = byId('el-drawer-sync-badge');
    if (!el) return;
    el.textContent = String(text || '');
    el.className = 'el-sync-pill' + (tone ? (' el-sync-pill--' + tone) : '');
  }

  function markDrawerDirty() {
    if (!drawerState.isOpen) return;
    if (!drawerState.isDirty) {
      drawerState.isDirty = true;
      setDrawerSyncBadge('Đang sửa đổi (chưa lưu)', 'warn');
    }
  }

  function getActiveTopmostModalContainer() {
    const subIds = ['el-dirty-modal-backdrop', 'el-dup-modal-backdrop', 'el-vault-modal-backdrop', 'el-detail-modal-backdrop'];
    for (let i = 0; i < subIds.length; i += 1) {
      const wrap = byId(subIds[i]);
      if (wrap && !wrap.hidden) {
        return wrap;
      }
    }
    const drWrap = byId('el-case-drawer-backdrop');
    if (drWrap && !drWrap.hidden) {
      return byId('el-case-drawer') || drWrap;
    }
    return null;
  }

  function syncModalInertAndFocusTrap() {
    const shellEl = byId('el-app-shell');
    const drawerWrap = byId('el-case-drawer-backdrop');
    const drawerEl = byId('el-case-drawer');
    const dirtyWrap = byId('el-dirty-modal-backdrop');
    const dupWrap = byId('el-dup-modal-backdrop');
    const vaultWrap = byId('el-vault-modal-backdrop');
    const detailWrap = byId('el-detail-modal-backdrop');

    const anySubOpen = Boolean(
      (dirtyWrap && !dirtyWrap.hidden) ||
      (dupWrap && !dupWrap.hidden) ||
      (vaultWrap && !vaultWrap.hidden) ||
      (detailWrap && !detailWrap.hidden)
    );
    const drawerOpen = Boolean(drawerWrap && !drawerWrap.hidden);
    const anyModalOpen = anySubOpen || drawerOpen;

    if (shellEl) {
      shellEl.inert = anyModalOpen;
      if (anyModalOpen) {
        shellEl.setAttribute('inert', '');
      } else {
        shellEl.removeAttribute('inert');
      }
    }
    if (drawerEl) {
      drawerEl.inert = anySubOpen;
      if (anySubOpen) {
        drawerEl.setAttribute('inert', '');
      } else {
        drawerEl.removeAttribute('inert');
      }
    }
  }

  function handleGlobalModalKeydown(ev) {
    const activeContainer = getActiveTopmostModalContainer();
    if (!activeContainer) {
      if (ev.key === 'Escape') {
        closeAllCardActionMenus();
      }
      return;
    }

    if (ev.key === 'Escape') {
      ev.preventDefault();
      const dirtyWrap = byId('el-dirty-modal-backdrop');
      if (dirtyWrap && !dirtyWrap.hidden) {
        dirtyWrap.hidden = true;
        syncModalInertAndFocusTrap();
        return;
      }
      const dupWrap = byId('el-dup-modal-backdrop');
      if (dupWrap && !dupWrap.hidden) {
        dupWrap.hidden = true;
        drawerState.pendingCreatePayload = null;
        syncModalInertAndFocusTrap();
        return;
      }
      const vaultWrap = byId('el-vault-modal-backdrop');
      if (vaultWrap && !vaultWrap.hidden) {
        closeVaultModal();
        return;
      }
      const detailWrap = byId('el-detail-modal-backdrop');
      if (detailWrap && !detailWrap.hidden) {
        closeCaseDetailModal(false);
        return;
      }
      requestCloseDrawer();
      return;
    }

    if (ev.key === 'Tab' && typeof activeContainer.querySelectorAll === 'function') {
      const focusable = Array.from(
        activeContainer.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary')
      ).filter((el) => {
        if (el.hidden) return false;
        let cur = el.parentElement;
        while (cur && cur !== activeContainer) {
          if (cur.hidden) return false;
          if (cur.tagName === 'DETAILS' && !cur.open && el.tagName !== 'SUMMARY') return false;
          cur = cur.parentElement;
        }
        return true;
      });
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (ev.shiftKey && document.activeElement === first) {
        ev.preventDefault();
        last.focus();
      } else if (!ev.shiftKey && document.activeElement === last) {
        ev.preventDefault();
        first.focus();
      }
    }
  }

  function renderMultiSelectChips(containerId, catalog, selectedList, onToggle) {
    const el = byId(containerId);
    if (!el) return;
    el.innerHTML = catalog.map((item) => {
      const active = selectedList.includes(item.code);
      return (
        '<button type="button" class="el-chip-toggle" data-chip-code="' + escapeHtml(item.code) + '" aria-pressed="' + (active ? 'true' : 'false') + '">' +
        escapeHtml(item.label) +
        '</button>'
      );
    }).join('');
    if (typeof el.querySelectorAll === 'function') {
      el.querySelectorAll('[data-chip-code]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const code = btn.getAttribute('data-chip-code') || '';
          const idx = selectedList.indexOf(code);
          if (idx >= 0) {
            selectedList.splice(idx, 1);
          } else {
            selectedList.push(code);
          }
          markDrawerDirty();
          if (typeof onToggle === 'function') onToggle();
          renderMultiSelectChips(containerId, catalog, selectedList, onToggle);
        });
      });
    }
  }

  function renderQuickSiteChips(track) {
    const el = byId('el-site-quick-chips');
    const siteInput = byId('el-f-lesion-site');
    if (!el) return;
    const sites = SITE_QUICK_CHIPS_BY_TRACK[track] || [];
    const currentVal = siteInput ? siteInput.value.trim() : '';
    el.innerHTML = sites.map((s) => (
      '<button type="button" class="el-chip-toggle" data-quick-site="' + escapeHtml(s) + '" aria-pressed="' + (currentVal === s ? 'true' : 'false') + '">' +
      escapeHtml(s) +
      '</button>'
    )).join('');
    if (typeof el.querySelectorAll === 'function') {
      el.querySelectorAll('[data-quick-site]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const val = btn.getAttribute('data-quick-site') || '';
          if (siteInput) siteInput.value = val;
          markDrawerDirty();
          renderQuickSiteChips(track);
        });
      });
    }
  }

  function updateBbpsLiveUi() {
    const r = drawerState.bbpsRight;
    const t = drawerState.bbpsTransverse;
    const l = drawerState.bbpsLeft;
    document.querySelectorAll('[data-bbps-seg]').forEach((btn) => {
      const seg = btn.getAttribute('data-bbps-seg');
      const v = Number(btn.getAttribute('data-bbps-val'));
      const cur = seg === 'right' ? r : (seg === 'transverse' ? t : l);
      btn.setAttribute('aria-pressed', cur === v ? 'true' : 'false');
    });
    const badgeEl = byId('el-bbps-live-badge');
    if (!badgeEl) return;
    if (r == null || t == null || l == null) {
      badgeEl.textContent = 'BBPS: chưa chấm đủ 3 đoạn';
      badgeEl.className = 'el-sync-pill';
      return;
    }
    const sum = r + t + l;
    const adequate = sum >= 6 && r >= 2 && t >= 2 && l >= 2;
    badgeEl.textContent = 'BBPS ' + r + '+' + t + '+' + l + ' = ' + sum + (adequate ? ' (Đạt ≥ 6 & mỗi đoạn ≥ 2)' : ' (Chưa đạt)');
    badgeEl.className = 'el-sync-pill ' + (adequate ? 'el-sync-pill--ok' : 'el-sync-pill--urgent');
  }

  function updateErcpDifficultyLiveBadge() {
    const badgeEl = byId('el-ercp-diff-badge');
    if (!badgeEl) return;
    const papEl = byId('el-f-papilla-status');
    const cEl = byId('el-f-cann-contacts');
    const tEl = byId('el-f-cann-time');
    const pEl = byId('el-f-unintended-pd');
    const pap = papEl ? papEl.value : 'NATIVE_INTACT';
    if (pap !== 'NATIVE_INTACT') {
      badgeEl.textContent = PAPILLA_STATUS_LABELS_VI[pap] || 'Nhú đã can thiệp trước đó';
      badgeEl.className = 'el-sync-pill';
      return;
    }
    const contacts = Number(cEl ? cEl.value : 0) || 0;
    const mins = Number(tEl ? tEl.value : 0) || 0;
    const pd = Number(pEl ? pEl.value : 0) || 0;
    const isDiff = contacts > 5 || mins > 5 || pd >= 2;
    badgeEl.textContent = isDiff
      ? 'Thông nhú khó theo ESGE 2016 (5-5-2)'
      : 'Nhú nguyên vẹn · Thông nhú thuận lợi';
    badgeEl.className = 'el-sync-pill ' + (isDiff ? 'el-sync-pill--warn' : 'el-sync-pill--ok');
  }

  function updateSwitchPill(id, active) {
    const el = byId(id);
    if (el) el.setAttribute('aria-pressed', active ? 'true' : 'false');
  }

  function updatePatientPreviewHints() {
    const nameEl = byId('el-f-full-name');
    const byEl = byId('el-f-birth-year');
    const initHint = byId('el-preview-initials');
    const ageHint = byId('el-preview-age');
    if (initHint && nameEl) {
      const ini = computePrivacyInitialsVi(nameEl.value);
      initHint.textContent = ini ? ('(Hiển thị kín: ' + ini + ')') : '';
    }
    if (ageHint && byEl) {
      const y = Number(byEl.value);
      const procStartEl = byId('el-f-proc-start');
      const procYear = procStartEl && procStartEl.value ? Number(procStartEl.value.slice(0, 4)) : 2026;
      if (y >= 1900 && y <= procYear) {
        ageHint.textContent = '(' + (procYear - y) + ' tuổi)';
      } else {
        ageHint.textContent = '';
      }
    }
  }

  function applyDrawerTrackAndCareVisibility() {
    const tr = drawerState.track;
    const isInpatient = drawerState.careSetting === 'INPATIENT';

    document.querySelectorAll('[data-form-track]').forEach((btn) => {
      const code = btn.getAttribute('data-form-track');
      btn.setAttribute('aria-pressed', code === tr ? 'true' : 'false');
      btn.disabled = drawerState.mode === 'edit';
    });

    document.querySelectorAll('[data-form-sex]').forEach((btn) => {
      btn.setAttribute('aria-pressed', btn.getAttribute('data-form-sex') === drawerState.sex ? 'true' : 'false');
    });

    document.querySelectorAll('[data-form-care]').forEach((btn) => {
      const val = btn.getAttribute('data-form-care') === 'inpatient' ? 'INPATIENT' : 'OUTPATIENT';
      btn.setAttribute('aria-pressed', val === drawerState.careSetting ? 'true' : 'false');
    });

    const mrnHint = byId('el-mrn-req-hint');
    if (mrnHint) {
      mrnHint.textContent = isInpatient ? '(bắt buộc cho ca nội trú)' : '(tùy chọn cho ngoại trú)';
    }

    const inpWrap = byId('el-inpatient-fields');
    if (inpWrap) inpWrap.hidden = !isInpatient;
    const ercpOffWrap = byId('el-ercp-offset-wrap');
    if (ercpOffWrap) ercpOffWrap.hidden = !(isInpatient && tr === 'ERCP');

    const colPreset = byId('el-col-quick-preset-box');
    if (colPreset) colPreset.hidden = !(tr === 'COL' && drawerState.mode === 'create');
    const colFlags = byId('el-col-p1-flags');
    if (colFlags) colFlags.hidden = tr !== 'COL';

    const p2Col = byId('el-p2-col');
    const p2Egd = byId('el-p2-egd');
    const p2Lesion = byId('el-p2-index-lesion');
    const p2Ercp = byId('el-p2-ercp');
    if (p2Col) p2Col.hidden = tr !== 'COL';
    if (p2Egd) p2Egd.hidden = tr !== 'EGD';
    if (p2Lesion) p2Lesion.hidden = tr === 'ERCP';
    if (p2Ercp) p2Ercp.hidden = tr !== 'ERCP';

    const egdBleedBox = byId('el-egd-bleeding-box');
    if (egdBleedBox) egdBleedBox.hidden = !(tr === 'EGD' && drawerState.egdMode === 'bleeding');
    document.querySelectorAll('[data-egd-mode]').forEach((btn) => {
      btn.setAttribute('aria-pressed', btn.getAttribute('data-egd-mode') === drawerState.egdMode ? 'true' : 'false');
    });

    const cecalEl = byId('el-f-cecal');
    const cecalFailWrap = byId('el-cecal-fail-wrap');
    if (cecalFailWrap && cecalEl) {
      cecalFailWrap.hidden = !(tr === 'COL' && cecalEl.value === 'NO');
    }

    const polypCntEl = byId('el-f-macro-polyp-count');
    const polypCnt = Number(polypCntEl ? polypCntEl.value : 0) || 0;
    const compWrap = byId('el-col-macro-complete-wrap');
    const pieceWrap = byId('el-col-macro-piecemeal-wrap');
    if (compWrap) compWrap.hidden = !(tr === 'COL' && polypCnt > 0);
    if (pieceWrap) pieceWrap.hidden = !(tr === 'COL' && polypCnt > 0);

    updateSwitchPill('el-sw-has-index-lesion', drawerState.hasIndexLesion);
    const lesionBody = byId('el-index-lesion-macro-body');
    if (lesionBody) lesionBody.hidden = !drawerState.hasIndexLesion;

    const p4LesionBox = byId('el-p4-lesion-path-box');
    const p4ColRollup = byId('el-p4-col-rollup-box');
    if (p4LesionBox) p4LesionBox.hidden = tr === 'ERCP';
    if (p4ColRollup) p4ColRollup.hidden = tr !== 'COL';

    if (tr === 'COL' || tr === 'EGD') {
      renderQuickSiteChips(tr);
    }
    if (tr === 'COL') {
      updateBbpsLiveUi();
    }
    if (tr === 'ERCP') {
      document.querySelectorAll('[data-vater-type]').forEach((btn) => {
        btn.setAttribute('aria-pressed', btn.getAttribute('data-vater-type') === drawerState.vaterType ? 'true' : 'false');
      });
      updateSwitchPill('el-sw-pad', drawerState.padDiverticulum);
      updateSwitchPill('el-sw-duodenal-obs', drawerState.duodenalObstruction);
      updateErcpDifficultyLiveBadge();
    }
  }

  function switchDrawerPhase(phaseKey) {
    const allowed = ['p1', 'p2', 'p3', 'p4'];
    const target = allowed.includes(phaseKey) ? phaseKey : 'p1';
    drawerState.activePhase = target;
    allowed.forEach((pk) => {
      const panel = byId('el-phase-panel-' + pk);
      if (panel) panel.hidden = pk !== target;
    });
    document.querySelectorAll('[data-phase-tab]').forEach((tab) => {
      tab.setAttribute('aria-selected', tab.getAttribute('data-phase-tab') === target ? 'true' : 'false');
    });
  }

  function renderAeRows() {
    const listEl = byId('el-ae-list');
    if (!listEl) return;
    if (!drawerState.aeItems.length) {
      listEl.innerHTML = '<p class="el-field-muted">Chưa có dòng biến cố nào được ghi nhận cho ca soi này.</p>';
      return;
    }
    listEl.innerHTML = drawerState.aeItems.map((ae, idx) => {
      const showPep = ae.event_type === 'PEP';
      return (
        '<div class="el-ae-card" data-ae-idx="' + idx + '">' +
        '<div class="el-ae-head">' +
        '<span class="el-ae-title">Biến cố #' + (idx + 1) + '</span>' +
        '<button type="button" class="el-btn el-btn--compact el-btn--danger" data-ae-remove="' + idx + '">Xóa dòng</button>' +
        '</div>' +
        '<div class="el-field-grid el-field-grid--3">' +
        '<div class="el-form-field">' +
        '<label class="el-form-label" for="el-ae-win-' + idx + '">Thời điểm khởi phát</label>' +
        '<select id="el-ae-win-' + idx + '" data-ae-field="window" data-ae-idx="' + idx + '" class="el-form-input">' +
        '<option value="INTRAPROCEDURAL"' + (ae.window === 'INTRAPROCEDURAL' ? ' selected' : '') + '>Trong thủ thuật</option>' +
        '<option value="INPATIENT_EARLY"' + (ae.window === 'INPATIENT_EARLY' ? ' selected' : '') + '>Nội viện sớm</option>' +
        '<option value="DELAYED_30D"' + (ae.window === 'DELAYED_30D' ? ' selected' : '') + '>Muộn trong 30 ngày</option>' +
        '</select>' +
        '</div>' +
        '<div class="el-form-field">' +
        '<label class="el-form-label" for="el-ae-type-' + idx + '">Loại biến cố lâm sàng</label>' +
        '<select id="el-ae-type-' + idx + '" data-ae-field="event_type" data-ae-idx="' + idx + '" class="el-form-input">' +
        '<option value="PEP"' + (ae.event_type === 'PEP' ? ' selected' : '') + '>Viêm tụy cấp sau ERCP (PEP)</option>' +
        '<option value="BLEEDING"' + (ae.event_type === 'BLEEDING' ? ' selected' : '') + '>Xuất huyết tiêu hóa sau can thiệp</option>' +
        '<option value="PERFORATION"' + (ae.event_type === 'PERFORATION' ? ' selected' : '') + '>Thủng tạng tiêu hóa</option>' +
        '<option value="CHOLANGITIS"' + (ae.event_type === 'CHOLANGITIS' ? ' selected' : '') + '>Viêm đường mật / nhiễm khuẩn</option>' +
        '<option value="CARDIOPULMONARY"' + (ae.event_type === 'CARDIOPULMONARY' ? ' selected' : '') + '>Tim mạch — hô hấp / an thần</option>' +
        '<option value="OTHER"' + (ae.event_type === 'OTHER' ? ' selected' : '') + '>Biến cố lâm sàng khác</option>' +
        '</select>' +
        '</div>' +
        '<div class="el-form-field">' +
        '<label class="el-form-label" for="el-ae-agree-' + idx + '">Phân độ AGREE 2022</label>' +
        '<select id="el-ae-agree-' + idx + '" data-ae-field="agree_grade" data-ae-idx="' + idx + '" class="el-form-input">' +
        '<option value="NONE"' + (ae.agree_grade === 'NONE' ? ' selected' : '') + '>Chưa phân độ AGREE</option>' +
        ['I', 'II', 'IIIa', 'IIIb', 'IVa', 'IVb', 'V'].map((g) => (
          '<option value="' + g + '"' + (ae.agree_grade === g ? ' selected' : '') + '>AGREE độ ' + g + '</option>'
        )).join('') +
        '</select>' +
        '</div>' +
        '</div>' +
        (showPep
          ? (
            '<div class="el-form-field">' +
            '<label class="el-form-label" for="el-ae-pep-' + idx + '">Mức độ viêm tụy sau ERCP (Cotton / ESGE — độc lập với AGREE)</label>' +
            '<select id="el-ae-pep-' + idx + '" data-ae-field="pep_severity" data-ae-idx="' + idx + '" class="el-form-input">' +
            '<option value="MILD"' + (ae.pep_severity === 'MILD' ? ' selected' : '') + '>Mức nhẹ</option>' +
            '<option value="MODERATE"' + (ae.pep_severity === 'MODERATE' ? ' selected' : '') + '>Mức vừa</option>' +
            '<option value="SEVERE"' + (ae.pep_severity === 'SEVERE' ? ' selected' : '') + '>Mức nặng</option>' +
            '</select>' +
            '</div>'
          )
          : '') +
        '<div class="el-field-grid el-field-grid--2">' +
        '<button type="button" class="el-check-pill" data-ae-toggle="readmission_required" data-ae-idx="' + idx + '" aria-pressed="' + (ae.readmission_required ? 'true' : 'false') + '">' +
        '<span class="el-check-indicator" aria-hidden="true"></span><span>Phải nhập viện lại vì biến cố</span>' +
        '</button>' +
        '<button type="button" class="el-check-pill" data-ae-toggle="surgical_rescue_required" data-ae-idx="' + idx + '" aria-pressed="' + (ae.surgical_rescue_required ? 'true' : 'false') + '">' +
        '<span class="el-check-indicator" aria-hidden="true"></span><span>Phải phẫu thuật / X-quang can thiệp cứu vãn</span>' +
        '</button>' +
        '</div>' +
        '<div class="el-form-field">' +
        '<label class="el-form-label" for="el-ae-note-' + idx + '">Diễn tiến xử trí biến cố (quét DLP)</label>' +
        '<input id="el-ae-note-' + idx + '" type="text" data-ae-field="note" data-ae-idx="' + idx + '" class="el-form-input" value="' + escapeHtml(ae.note || '') + '" placeholder="Ví dụ: Bù dịch + giảm đau, ổn định xuất viện ngày 3">' +
        '</div>' +
        '</div>'
      );
    }).join('');

    if (typeof listEl.querySelectorAll === 'function') {
      listEl.querySelectorAll('[data-ae-remove]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const i = Number(btn.getAttribute('data-ae-remove'));
          drawerState.aeItems.splice(i, 1);
          markDrawerDirty();
          renderAeRows();
        });
      });
      listEl.querySelectorAll('[data-ae-field]').forEach((ctrl) => {
        const evt = ctrl.tagName === 'SELECT' ? 'change' : 'input';
        ctrl.addEventListener(evt, () => {
          const i = Number(ctrl.getAttribute('data-ae-idx'));
          const f = ctrl.getAttribute('data-ae-field');
          if (!drawerState.aeItems[i] || !f) return;
          drawerState.aeItems[i][f] = ctrl.value;
          if (f === 'event_type') {
            drawerState.aeItems[i].pep_severity = ctrl.value === 'PEP' ? 'MILD' : 'NONE';
            renderAeRows();
          }
          markDrawerDirty();
        });
      });
      listEl.querySelectorAll('[data-ae-toggle]').forEach((btn) => {
        btn.addEventListener('click', () => {
          const i = Number(btn.getAttribute('data-ae-idx'));
          const f = btn.getAttribute('data-ae-toggle');
          if (!drawerState.aeItems[i] || !f) return;
          drawerState.aeItems[i][f] = !drawerState.aeItems[i][f];
          markDrawerDirty();
          renderAeRows();
        });
      });
    }
  }

  function resetDrawerFormFieldsForCreate(initialTrack, linkedOriginCase) {
    stopWithdrawalStopwatch();
    drawerState.timerElapsedSec = 0;
    updateStopwatchUi();

    const formEl = byId('el-case-form');
    if (formEl && typeof formEl.reset === 'function') {
      formEl.reset();
    }

    const tr = initialTrack || 'COL';
    drawerState.mode = 'create';
    drawerState.editingCaseId = null;
    drawerState.editingCaseCode = '';
    drawerState.expectedVersion = 1;
    drawerState.track = tr;
    drawerState.sex = 'M';
    drawerState.careSetting = tr === 'ERCP' ? 'INPATIENT' : 'OUTPATIENT';
    drawerState.egdMode = 'lesion';
    drawerState.hasIbdOrPolyposis = false;
    drawerState.excludeFromCir = false;
    drawerState.hasIndexLesion = tr === 'EGD';
    drawerState.bbpsRight = tr === 'COL' ? 3 : null;
    drawerState.bbpsTransverse = tr === 'COL' ? 3 : null;
    drawerState.bbpsLeft = tr === 'COL' ? 3 : null;
    drawerState.vaterType = '1';
    drawerState.padDiverticulum = false;
    drawerState.duodenalObstruction = false;
    drawerState.biliaryInterventions = [];
    drawerState.pepProphylaxis = [];
    drawerState.ercpHistoryFlags = [];
    drawerState.aeItems = [];
    drawerState.pendingCreatePayload = null;
    drawerState.isDirty = false;

    drawerState.linkedPatientUid = null;
    drawerState.fulfillSurvRecId = null;
    drawerState.linkedOriginCaseCode = '';

    const linkedBanner = byId('el-linked-surv-banner');
    const linkedTxt = byId('el-linked-surv-text');
    const patEditBox = byId('el-patient-edit-fields');
    const patReadBox = byId('el-patient-readonly-box');

    if (linkedOriginCase && linkedOriginCase.patient) {
      drawerState.linkedPatientUid = linkedOriginCase.patient.patient_uid || null;
      drawerState.fulfillSurvRecId = (linkedOriginCase.surveillance && linkedOriginCase.surveillance.rec_id) || linkedOriginCase.case_id;
      drawerState.linkedOriginCaseCode = linkedOriginCase.case_code || '';
      drawerState.sex = linkedOriginCase.patient.sex || 'M';
      if (linkedBanner && linkedTxt) {
        linkedTxt.textContent = 'Đang tạo ca soi lại đóng vòng hẹn của ca gốc ' + drawerState.linkedOriginCaseCode + ' (' + (linkedOriginCase.patient.privacy_initials || '') + ')';
        linkedBanner.hidden = false;
      }
      if (patEditBox) patEditBox.hidden = false;
      if (patReadBox) patReadBox.hidden = true;
      const fnEl = byId('el-f-full-name');
      const byEl = byId('el-f-birth-year');
      if (fnEl) fnEl.value = linkedOriginCase.patient.full_name || '';
      if (byEl) byEl.value = String(linkedOriginCase.patient.birth_year || '');
    } else {
      if (linkedBanner) linkedBanner.hidden = true;
      if (patEditBox) patEditBox.hidden = false;
      if (patReadBox) patReadBox.hidden = true;
    }

    populateIndicationOptionsForTrack(tr, linkedOriginCase ? 'SURVEILLANCE' : TRACK_DEFAULT_INDICATION[tr]);

    const procStartEl = byId('el-f-proc-start');
    if (procStartEl) procStartEl.value = formatLocalDatetimeInput();
    const admDateEl = byId('el-f-admission-date');
    if (admDateEl) admDateEl.value = new Date().toISOString().slice(0, 10);
    const opEl = byId('el-f-operator');
    if (opEl) opEl.value = (state.user && state.user.display_name) || 'ThS. BSCKI. Nguyễn Bình An';
    const refEl = byId('el-f-referring-dept');
    if (refEl) refEl.value = 'Khoa Nội soi Tiêu hóa';
    const offEl = byId('el-f-ercp-offset');
    if (offEl) offEl.value = '0';

    updateSwitchPill('el-sw-ibd-polyposis', false);
    updateSwitchPill('el-sw-exclude-cir', false);

    const cecalEl = byId('el-f-cecal');
    if (cecalEl) cecalEl.value = tr === 'COL' ? 'YES' : 'NA';
    const wdEl = byId('el-f-withdrawal-min');
    if (wdEl) wdEl.value = tr === 'COL' ? '8' : '';
    const mpEl = byId('el-f-macro-polyp-count');
    if (mpEl) mpEl.value = '0';

    const fuEl = byId('el-f-followup-30d');
    if (fuEl) fuEl.value = 'PENDING_WINDOW';
    const psEl = byId('el-f-path-status');
    if (psEl) psEl.value = 'NOT_APPLICABLE';

    renderMultiSelectChips('el-ercp-interventions-chips', ERCP_INTERVENTION_CHIPS, drawerState.biliaryInterventions);
    renderMultiSelectChips('el-ercp-prophylaxis-chips', ERCP_PROPHYLAXIS_CHIPS, drawerState.pepProphylaxis);
    renderMultiSelectChips('el-ercp-history-chips', ERCP_HISTORY_CHIPS, drawerState.ercpHistoryFlags);
    renderAeRows();
    updatePatientPreviewHints();

    const dangerEl = byId('el-danger-zone');
    if (dangerEl) {
      dangerEl.hidden = true;
      dangerEl.open = false;
    }
    const delCodeEl = byId('el-f-confirm-delete-code');
    if (delCodeEl) delCodeEl.value = '';

    const titleEl = byId('el-drawer-title');
    if (titleEl) titleEl.textContent = 'Thêm ca nội soi mới';
    const saveLbl = byId('el-btn-save-label');
    if (saveLbl) saveLbl.textContent = 'Lưu hồ sơ ca soi';
    setDrawerSyncBadge('Bản ghi mới', '');
    setDrawerAlert('');
    applyDrawerTrackAndCareVisibility();
  }

  function populateDrawerFromExistingCase(c) {
    stopWithdrawalStopwatch();
    drawerState.timerElapsedSec = 0;
    updateStopwatchUi();

    const formEl = byId('el-case-form');
    if (formEl && typeof formEl.reset === 'function') {
      formEl.reset();
    }

    drawerState.mode = 'edit';
    drawerState.editingCaseId = c.case_id;
    drawerState.editingCaseCode = c.case_code || '';
    drawerState.expectedVersion = Number(c.version) || 1;
    drawerState.track = c.track || 'COL';
    drawerState.careSetting = c.care_setting || 'OUTPATIENT';
    drawerState.sex = (c.patient && c.patient.sex) || 'M';
    drawerState.hasIbdOrPolyposis = Boolean(c.has_ibd_or_polyposis);
    drawerState.excludeFromCir = Boolean(c.exclude_from_cir);
    drawerState.linkedPatientUid = null;
    drawerState.fulfillSurvRecId = null;
    drawerState.linkedOriginCaseCode = '';
    drawerState.pendingCreatePayload = null;
    drawerState.isDirty = false;

    const linkedBanner = byId('el-linked-surv-banner');
    if (linkedBanner) linkedBanner.hidden = true;

    const patEditBox = byId('el-patient-edit-fields');
    const patReadBox = byId('el-patient-readonly-box');
    const pat = c.patient || {};
    const epi = c.episode || {};
    const sexLabel = pat.sex === 'F' ? 'Nữ' : (pat.sex === 'O' ? 'Khác' : 'Nam');
    const settingLabel = c.care_setting === 'INPATIENT' ? 'Nội trú' : 'Ngoại trú';
    if (patEditBox) patEditBox.hidden = true;
    if (patReadBox) {
      patReadBox.hidden = false;
      patReadBox.innerHTML = (
        '<strong>Người bệnh liên kết dọc:</strong> ' +
        escapeHtml(pat.privacy_initials || '') + ' · Năm sinh ' + escapeHtml(pat.birth_year || '') + ' (' + escapeHtml(pat.age) + ' tuổi, ' + escapeHtml(sexLabel) + ') · ' +
        escapeHtml(settingLabel) +
        (pat.hospital_mrn_masked ? (' · Mã HS: ' + escapeHtml(pat.hospital_mrn_masked)) : '') +
        (epi.referring_dept ? (' · Khoa gửi: ' + escapeHtml(epi.referring_dept)) : '')
      );
    }

    populateIndicationOptionsForTrack(c.track, c.indication);
    const procStartEl = byId('el-f-proc-start');
    if (procStartEl) procStartEl.value = formatLocalDatetimeInput(c.procedure_start_at);
    const opEl = byId('el-f-operator');
    if (opEl) opEl.value = c.operator_name || 'ThS. BSCKI. Nguyễn Bình An';
    const indDetEl = byId('el-f-indication-detail');
    if (indDetEl) indDetEl.value = c.indication_detail || '';

    updateSwitchPill('el-sw-ibd-polyposis', drawerState.hasIbdOrPolyposis);
    updateSwitchPill('el-sw-exclude-cir', drawerState.excludeFromCir);

    drawerState.bbpsRight = typeof c.bbps_right === 'number' ? c.bbps_right : null;
    drawerState.bbpsTransverse = typeof c.bbps_transverse === 'number' ? c.bbps_transverse : null;
    drawerState.bbpsLeft = typeof c.bbps_left === 'number' ? c.bbps_left : null;
    const cecalEl = byId('el-f-cecal');
    if (cecalEl) cecalEl.value = c.cecal_intubation || (c.track === 'COL' ? 'YES' : 'NA');
    const cecalRsnEl = byId('el-f-cecal-reason');
    if (cecalRsnEl) cecalRsnEl.value = c.cecal_failure_reason || '';
    const wdEl = byId('el-f-withdrawal-min');
    if (wdEl) wdEl.value = c.withdrawal_time_clean_min != null ? String(c.withdrawal_time_clean_min) : '';

    const wc = c.whole_case_summary || {};
    const mpEl = byId('el-f-macro-polyp-count');
    if (mpEl) mpEl.value = String(wc.macroscopic_polyp_count != null ? wc.macroscopic_polyp_count : 0);
    const crEl = byId('el-f-complete-resection');
    if (crEl) crEl.value = wc.complete_resection_all_lesions || 'NOT_APPLICABLE';
    const pmEl = byId('el-f-piecemeal-20');
    if (pmEl) pmEl.value = wc.any_piecemeal_ge_20mm || 'NO';

    const idx = c.index_lesion;
    drawerState.hasIndexLesion = Boolean(idx);
    drawerState.egdMode = (idx && idx.bleeding_source_type && idx.bleeding_source_type !== 'NONE') ? 'bleeding' : 'lesion';
    if (idx) {
      const sEl = byId('el-f-lesion-site');
      if (sEl) sEl.value = idx.anatomical_site || '';
      const szEl = byId('el-f-lesion-size');
      if (szEl) szEl.value = idx.size_mm != null ? String(idx.size_mm) : '';
      const prEl = byId('el-f-paris-class');
      if (prEl) prEl.value = idx.paris_class || '';
      const sfEl = byId('el-f-surface-pattern');
      if (sfEl) sfEl.value = idx.surface_pattern || '';
      const rmEl = byId('el-f-resection-method');
      if (rmEl) rmEl.value = idx.resection_method || 'NONE';
      const bjEl = byId('el-f-biopsy-jars');
      if (bjEl) bjEl.value = String(idx.biopsy_jar_count || 0);
      const bsEl = byId('el-f-bleeding-source');
      if (bsEl) bsEl.value = idx.bleeding_source_type || 'NONE';
      const frEl = byId('el-f-forrest');
      if (frEl) frEl.value = idx.forrest_class || '';
      const hmEl = byId('el-f-hemostasis-mod');
      if (hmEl) hmEl.value = idx.hemostasis_modality || 'NONE';
      const hsEl = byId('el-f-hemostasis-success');
      if (hsEl) hsEl.value = idx.hemostasis_initial_success || 'NA';

      const hiEl = byId('el-f-histology');
      if (hiEl) hiEl.value = idx.histology_type || 'NONE';
      const dyEl = byId('el-f-dysplasia');
      if (dyEl) dyEl.value = idx.dysplasia_grade || 'NONE';
      const mgEl = byId('el-f-margins');
      if (mgEl) mgEl.value = idx.margins_status || 'NA';
      const smEl = byId('el-f-sm-um');
      if (smEl) smEl.value = idx.sm_invasion_um != null ? String(idx.sm_invasion_um) : '';
      const lvEl = byId('el-f-lvi');
      if (lvEl) lvEl.value = idx.lvi_status || 'NA';
      const dfEl = byId('el-f-diff');
      if (dfEl) dfEl.value = idx.differentiation || 'NA';
      const bdEl = byId('el-f-budding');
      if (bdEl) bdEl.value = idx.budding_grade || 'NA';
    }

    const setSel = (id, v, dflt) => {
      const el = byId(id);
      if (el) el.value = v || dflt;
    };
    setSel('el-f-wc-any-ad', wc.any_confirmed_adenoma, 'NO');
    setSel('el-f-wc-ad-bin', wc.confirmed_adenoma_count_bin, '0');
    const admEl = byId('el-f-wc-ad-max');
    if (admEl) admEl.value = wc.max_adenoma_size_mm != null ? String(wc.max_adenoma_size_mm) : '';
    setSel('el-f-wc-vill-hgd', wc.any_villous_or_hgd_any_lesion, 'NO');
    setSel('el-f-wc-hgd', wc.any_hgd_any_lesion, 'NO');
    setSel('el-f-wc-any-ssl', wc.any_confirmed_ssl, 'NO');
    setSel('el-f-wc-ssl-bin', wc.confirmed_ssl_count_bin, '0');
    const sslmEl = byId('el-f-wc-ssl-max');
    if (sslmEl) sslmEl.value = wc.max_ssl_size_mm != null ? String(wc.max_ssl_size_mm) : '';
    setSel('el-f-wc-ssl-dys', wc.any_ssl_with_dysplasia_or_tsa, 'NO');
    setSel('el-f-wc-inv-noncur', wc.any_invasive_cancer_or_noncurative_feature, 'NO');

    const det = c.ercp_detail || {};
    setSel('el-f-papilla-status', det.papilla_status, 'NATIVE_INTACT');
    drawerState.vaterType = String(det.vater_papilla_type || '1');
    setSel('el-f-target-duct', det.target_duct, 'CBD');
    setSel('el-f-selective-cann', det.selective_cannulation, 'SUCCESS');
    drawerState.padDiverticulum = Boolean(det.pad_diverticulum);
    drawerState.duodenalObstruction = Boolean(det.duodenal_obstruction_or_altered);
    const setVal = (id, v) => {
      const el = byId(id);
      if (el) el.value = v != null ? String(v) : '';
    };
    setVal('el-f-cann-contacts', det.cannulation_contacts_count != null ? det.cannulation_contacts_count : 1);
    setVal('el-f-cann-time', det.cannulation_time_min != null ? det.cannulation_time_min : 2);
    setVal('el-f-unintended-pd', det.unintended_pd_count != null ? det.unintended_pd_count : 0);
    setVal('el-f-ercp-total-time', det.total_procedure_time_min != null ? det.total_procedure_time_min : 25);
    setSel('el-f-cann-tech', det.cannulation_technique, 'STANDARD_SPHINCTEROTOME_GUIDEWIRE');
    drawerState.biliaryInterventions = Array.isArray(det.biliary_interventions) ? det.biliary_interventions.slice() : [];
    drawerState.pepProphylaxis = Array.isArray(det.pep_prophylaxis) ? det.pep_prophylaxis.slice() : [];
    drawerState.ercpHistoryFlags = Array.isArray(det.history_flags) ? det.history_flags.slice() : [];
    setVal('el-f-ercp-note', det.ercp_procedure_note || '');
    setSel('el-f-altered-anat', det.altered_anatomy, 'NONE');
    setVal('el-f-antithrombotic', det.antithrombotic_status || 'NONE');
    setSel('el-f-img-mod', det.imaging_modality, 'MRCP');
    setVal('el-f-img-cbd', det.imaging_cbd_mm);
    setVal('el-f-img-stone-cnt', det.imaging_stone_count != null ? det.imaging_stone_count : 0);
    setVal('el-f-img-stone-max', det.imaging_stone_max_mm);
    setVal('el-f-stricture-site', det.stricture_site || '');
    const labs = det.labs || {};
    setVal('el-lab-bili-t', labs.bili_total_mg_dl);
    setVal('el-lab-bili-d', labs.bili_direct_mg_dl);
    setVal('el-lab-ast', labs.ast_u_l);
    setVal('el-lab-alt', labs.alt_u_l);
    setVal('el-lab-ggt', labs.ggt_u_l);
    setVal('el-lab-alp', labs.alp_u_l);
    setVal('el-lab-amy', labs.amylase_u_l);
    setVal('el-lab-lip', labs.lipase_u_l);
    setVal('el-lab-wbc', labs.wbc_g_l);
    setVal('el-lab-crp', labs.crp_mg_l);
    setVal('el-lab-plt', labs.plt_g_l);
    setVal('el-lab-inr', labs.inr);

    renderMultiSelectChips('el-ercp-interventions-chips', ERCP_INTERVENTION_CHIPS, drawerState.biliaryInterventions);
    renderMultiSelectChips('el-ercp-prophylaxis-chips', ERCP_PROPHYLAXIS_CHIPS, drawerState.pepProphylaxis);
    renderMultiSelectChips('el-ercp-history-chips', ERCP_HISTORY_CHIPS, drawerState.ercpHistoryFlags);

    setVal('el-f-clinical-note', c.clinical_note || '');
    setSel('el-f-followup-30d', c.followup_30d_status, 'PENDING_WINDOW');
    drawerState.aeItems = Array.isArray(c.adverse_events)
      ? c.adverse_events.map((ev) => Object.assign({}, ev))
      : [];
    renderAeRows();

    setSel('el-f-path-status', c.pathology_completion_status, 'NOT_APPLICABLE');
    setVal('el-f-clin-due-date', c.clinician_followup_due_date || '');
    setVal('el-f-clin-fu-note', c.clinician_followup_note || '');

    const dangerEl = byId('el-danger-zone');
    if (dangerEl) {
      dangerEl.hidden = !(state.user && state.user.role === 'superadmin');
      dangerEl.open = false;
    }
    const delCodeEl = byId('el-f-confirm-delete-code');
    if (delCodeEl) delCodeEl.value = '';

    const titleEl = byId('el-drawer-title');
    if (titleEl) titleEl.textContent = 'Cập nhật hồ sơ ' + (c.case_code || '');
    const saveLbl = byId('el-btn-save-label');
    if (saveLbl) saveLbl.textContent = 'Lưu cập nhật (v' + drawerState.expectedVersion + ')';
    setDrawerSyncBadge('Đã đồng bộ · v' + drawerState.expectedVersion, 'ok');
    setDrawerAlert('');
    applyDrawerTrackAndCareVisibility();
  }

  function openNewCaseDrawer(initialTrack, linkedOriginCase, triggerEl) {
    if (!state.user) return;
    const wrap = byId('el-case-drawer-backdrop');
    if (!wrap) return;
    drawerState.returnFocusEl = triggerEl || document.activeElement || null;
    resetDrawerFormFieldsForCreate(initialTrack || (state.trackFilter !== 'ALL' ? state.trackFilter : 'COL'), linkedOriginCase || null);
    switchDrawerPhase('p1');
    drawerState.isOpen = true;
    wrap.hidden = false;
    syncModalInertAndFocusTrap();
    const fnEl = byId('el-f-full-name');
    if (fnEl && typeof fnEl.focus === 'function') {
      fnEl.focus();
    }
  }

  function openEditCaseDrawer(caseId, targetPhase, triggerEl) {
    if (!state.user) return;
    const found = state.cases.find((item) => item.case_id === caseId);
    if (!found) return;
    const wrap = byId('el-case-drawer-backdrop');
    if (!wrap) return;
    drawerState.returnFocusEl = triggerEl || document.activeElement || null;
    populateDrawerFromExistingCase(found);
    switchDrawerPhase(targetPhase || 'p2');
    drawerState.isOpen = true;
    wrap.hidden = false;
    syncModalInertAndFocusTrap();
    const closeBtn = byId('el-drawer-close');
    if (closeBtn && typeof closeBtn.focus === 'function') {
      closeBtn.focus();
    }
  }

  function closeDrawerImmediately() {
    stopWithdrawalStopwatch();
    drawerState.isOpen = false;
    drawerState.isDirty = false;
    drawerState.pendingCreatePayload = null;
    const wrap = byId('el-case-drawer-backdrop');
    if (wrap) wrap.hidden = true;
    const dirtyWrap = byId('el-dirty-modal-backdrop');
    if (dirtyWrap) dirtyWrap.hidden = true;
    const dupWrap = byId('el-dup-modal-backdrop');
    if (dupWrap) dupWrap.hidden = true;
    setDrawerAlert('');
    syncModalInertAndFocusTrap();
    const ret = drawerState.returnFocusEl;
    drawerState.returnFocusEl = null;
    if (ret && typeof ret.focus === 'function' && state.user) {
      try {
        ret.focus();
      } catch (_err) {
        /* ignore */
      }
    }
  }

  function requestCloseDrawer() {
    if (!drawerState.isOpen) return;
    if (drawerState.isDirty) {
      const dirtyWrap = byId('el-dirty-modal-backdrop');
      if (dirtyWrap) {
        dirtyWrap.hidden = false;
        syncModalInertAndFocusTrap();
        const keepBtn = byId('el-btn-dirty-keep');
        if (keepBtn && typeof keepBtn.focus === 'function') keepBtn.focus();
        return;
      }
    }
    closeDrawerImmediately();
  }

  function closeVaultModal() {
    const wrap = byId('el-vault-modal-backdrop');
    const passEl = byId('el-vault-passphrase');
    const errEl = byId('el-vault-error');
    if (passEl) passEl.value = '';
    if (errEl) {
      errEl.textContent = '';
      errEl.hidden = true;
    }
    if (wrap) wrap.hidden = true;
    syncModalInertAndFocusTrap();
  }

  function closeAllCardActionMenus() {
    if (typeof document.querySelectorAll !== 'function') return;
    document.querySelectorAll('.el-action-menu-dropdown').forEach((menu) => {
      menu.hidden = true;
      menu.classList.remove('is-dropup');
    });
    document.querySelectorAll('.el-btn-more[aria-expanded="true"]').forEach((btn) => {
      btn.setAttribute('aria-expanded', 'false');
    });
    document.querySelectorAll('.el-case-card--menu-open').forEach((card) => {
      card.classList.remove('el-case-card--menu-open');
    });
  }

  function phaseStateBadgeTone(stateKey) {
    if (stateKey === 'done') return 'ned';
    if (stateKey === 'active') return 'due';
    if (stateKey === 'pending') return 'pending';
    if (stateKey === 'urgent') return 'urgent';
    return 'neutral';
  }

  function formatAeListVi(adverseEvents) {
    if (!Array.isArray(adverseEvents) || !adverseEvents.length) {
      return 'Chưa ghi nhận biến cố nội soi';
    }
    return adverseEvents.map((ev) => {
      const evType = AE_EVENT_TYPE_LABELS_VI[ev.event_type] || sanitizeEnumFallbackVi(ev.event_type, 'Biến cố nội soi');
      const winTxt = AE_WINDOW_LABELS_VI[ev.window] || sanitizeEnumFallbackVi(ev.window, 'Sau thủ thuật');
      const pepPart = ev.event_type === 'PEP' && ev.pep_severity && ev.pep_severity !== 'NONE'
        ? (' (' + (PEP_SEVERITY_LABELS_VI[ev.pep_severity] || 'ghi nhận') + ')')
        : '';
      const agreePart = ev.agree_grade ? (' · Phân độ AGREE ' + sanitizeEnumFallbackVi(ev.agree_grade, 'II')) : '';
      const notePart = ev.note ? (' — ' + sanitizeEnumFallbackVi(ev.note, '')) : '';
      return evType + pepPart + ' [' + winTxt + ']' + agreePart + notePart;
    }).join(' | ');
  }

  function openCaseDetailModal(caseId, triggerEl) {
    if (!state.user) return;
    const c = state.cases.find((item) => item.case_id === caseId);
    if (!c) return;
    const wrap = byId('el-detail-modal-backdrop');
    const badgesEl = byId('el-detail-modal-badges');
    const titleEl = byId('el-detail-modal-title');
    const bodyEl = byId('el-detail-modal-body');
    if (!wrap || !badgesEl || !titleEl || !bodyEl) return;

    closeAllCardActionMenus();
    detailModalState.isOpen = true;
    detailModalState.caseId = c.case_id;
    detailModalState.returnFocusEl = triggerEl || document.activeElement || null;

    const pat = c.patient || {};
    const epi = c.episode || {};
    const surv = c.surveillance || {};
    const idx = c.index_lesion || null;
    const hl = describeTrackClinicalHighlights(c);
    const prog = computeCasePhaseProgression(c);
    const badgeObj = c.clinical_badge || { tone: 'neutral', label: 'Đang cập nhật' };
    const settingLabel = c.care_setting === 'INPATIENT' ? 'Nội trú' : 'Ngoại trú';
    const sexLabel = pat.sex === 'F' ? 'Nữ' : (pat.sex === 'O' ? 'Khác' : 'Nam');
    const mrnPart = pat.hospital_mrn_masked ? (' · Mã HS: ' + pat.hospital_mrn_masked) : '';

    badgesEl.innerHTML = (
      renderProcChip(c.track) +
      '<span class="el-case-code">' + escapeHtml(c.case_code || '') + '</span>' +
      renderStatusBadge(badgeObj.tone, humanizeClinicalBadgeLabelVi(badgeObj.label))
    );
    titleEl.textContent = (pat.privacy_initials || '') + ' · ' + (pat.age != null ? (pat.age + ' tuổi') : '') + ' (' + sexLabel + ') — Diễn tiến theo dõi 4 pha';

    const fu30Label = FOLLOWUP_30D_LABELS_VI[c.followup_30d_status] || 'Đang trong cửa sổ theo dõi 14–30 ngày';
    const pathStatusLabel = PATH_STATUS_LABELS_VI[c.pathology_completion_status] || 'Không sinh thiết / không áp dụng';
    const histSummary = idx && idx.histology_type
      ? formatHistologyVi(idx.histology_type)
      : pathStatusLabel;
    const survPlanText = surv.category === 'SURGICAL_MDT_CONSULT_ALERT'
      ? ('Chuyển hội chẩn ' + sanitizeEnumFallbackVi(surv.surgical_consult_target_dept || 'Ngoại khoa', 'Ngoại khoa'))
      : ('Hẹn soi lại: ' + sanitizeEnumFallbackVi(surv.recommended_interval_label || 'Theo chỉ định', 'Theo chỉ định') + (surv.due_date ? (' · Dự kiến ' + formatViDate(surv.due_date)) : ''));
    const primaryGuideLabel = formatGuidelineLabelVi(surv.guideline_id, false);
    const refGuideText = surv.is_divergent_guideline
      ? ('Đối chiếu ' + formatGuidelineLabelVi(surv.reference_guideline_id, true) + ': ' + sanitizeEnumFallbackVi(surv.reference_interval_label || '', ''))
      : '';

    const detailTrackPillsHtml = (
      '<div class="el-phase-pill-cluster" role="group" aria-label="Chuyển nhanh pha từ cửa sổ chi tiết">' +
      prog.phases.map((ph) => (
        '<button type="button" class="el-phase-pill el-phase-pill--' + escapeHtml(ph.state) + '" ' +
        'data-detail-jump-phase="' + escapeHtml(ph.key) + '" ' +
        'title="' + escapeHtml(ph.title) + '" ' +
        'aria-label="' + escapeHtml(ph.title) + '">' +
        phasePillIconSvg(ph.state) +
        '<span>' + escapeHtml(ph.code) + '</span>' +
        '</button>'
      )).join('') +
      '</div>'
    );

    bodyEl.innerHTML = (
      '<div class="el-detail-track-banner">' +
      '<div class="el-detail-track-meta">' +
      '<strong>' + escapeHtml(prog.nextStepLabel) + '</strong> · Phiên bản hồ sơ v' + escapeHtml(c.version || 1) + ' · Nội soi viên: ' + escapeHtml(c.operator_name || 'ThS. BSCKI. Nguyễn Bình An') +
      '</div>' +
      detailTrackPillsHtml +
      '</div>' +
      '<div class="el-detail-phase-grid">' +
      '<section class="el-detail-phase-card">' +
      '<div>' +
      '<div class="el-detail-phase-head">' +
      '<h4 class="el-detail-phase-title">Pha 1 · Hành chính &amp; chỉ định</h4>' +
      renderStatusBadge(phaseStateBadgeTone(prog.p1.state), prog.p1.shortText) +
      '</div>' +
      '<div class="el-detail-kv-list">' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Thời điểm &amp; hình thức:</span> ' + escapeHtml(formatViDate(c.procedure_start_at)) + ' · ' + escapeHtml(settingLabel + mrnPart) + '</p>' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Khoa gửi:</span> ' + escapeHtml(sanitizeEnumFallbackVi(epi.referring_dept || 'Ngoại trú', 'Ngoại trú')) + '</p>' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Chỉ định lâm sàng:</span> ' + escapeHtml(formatIndicationVi(c.indication_detail, c.indication)) + '</p>' +
      '</div>' +
      '</div>' +
      '<div class="el-detail-phase-foot"><button type="button" class="el-btn el-btn--compact" data-detail-jump-phase="p1">Sửa Pha 1</button></div>' +
      '</section>' +

      '<section class="el-detail-phase-card">' +
      '<div>' +
      '<div class="el-detail-phase-head">' +
      '<h4 class="el-detail-phase-title">Pha 2 · Thông số kỹ thuật &amp; thủ thuật</h4>' +
      renderStatusBadge(phaseStateBadgeTone(prog.p2.state), prog.p2.shortText) +
      '</div>' +
      '<div class="el-detail-kv-list">' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Đánh giá chính:</span> ' + escapeHtml(hl.title) + '</p>' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Chi tiết can thiệp:</span> ' + escapeHtml(hl.detail) + '</p>' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Nhận định lâm sàng:</span> ' + escapeHtml(sanitizeEnumFallbackVi(c.clinical_note || 'Chưa ghi chú bổ sung', 'Chưa ghi chú bổ sung')) + '</p>' +
      '</div>' +
      '</div>' +
      '<div class="el-detail-phase-foot"><button type="button" class="el-btn el-btn--compact" data-detail-jump-phase="p2">Sửa Pha 2</button></div>' +
      '</section>' +

      '<section class="el-detail-phase-card">' +
      '<div>' +
      '<div class="el-detail-phase-head">' +
      '<h4 class="el-detail-phase-title">Pha 3 · Biến cố 14–30 ngày</h4>' +
      renderStatusBadge(phaseStateBadgeTone(prog.p3.state), prog.p3.shortText) +
      '</div>' +
      '<div class="el-detail-kv-list">' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Cửa sổ theo dõi:</span> ' + escapeHtml(fu30Label) + '</p>' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Biến cố ghi nhận:</span> ' + escapeHtml(formatAeListVi(c.adverse_events)) + '</p>' +
      '</div>' +
      '</div>' +
      '<div class="el-detail-phase-foot"><button type="button" class="el-btn el-btn--compact" data-detail-jump-phase="p3">Sửa Pha 3</button></div>' +
      '</section>' +

      '<section class="el-detail-phase-card">' +
      '<div>' +
      '<div class="el-detail-phase-head">' +
      '<h4 class="el-detail-phase-title">Pha 4 · Giải phẫu bệnh &amp; hẹn soi</h4>' +
      renderStatusBadge(phaseStateBadgeTone(prog.p4.state), prog.p4.shortText) +
      '</div>' +
      '<div class="el-detail-kv-list">' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Tình trạng GPB:</span> ' + escapeHtml(pathStatusLabel) + (idx ? (' · ' + escapeHtml(histSummary)) : '') + '</p>' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Hướng xử trí:</span> ' + escapeHtml(survPlanText) + '</p>' +
      '<p class="el-detail-kv-row"><span class="el-detail-kv-label">Hướng dẫn áp dụng:</span> ' + escapeHtml(primaryGuideLabel) + (refGuideText ? (' · ' + escapeHtml(refGuideText)) : '') + '</p>' +
      (c.clinician_followup_note ? ('<p class="el-detail-kv-row"><span class="el-detail-kv-label">Dặn dò tái khám:</span> ' + escapeHtml(sanitizeEnumFallbackVi(c.clinician_followup_note, '')) + '</p>') : '') +
      '</div>' +
      '</div>' +
      '<div class="el-detail-phase-foot"><button type="button" class="el-btn el-btn--compact" data-detail-jump-phase="p4">Sửa Pha 4</button></div>' +
      '</section>' +
      '</div>'
    );

    wrap.hidden = false;
    syncModalInertAndFocusTrap();
    const closeBtn = byId('el-btn-detail-close');
    if (closeBtn && typeof closeBtn.focus === 'function') {
      closeBtn.focus();
    }
  }

  function closeCaseDetailModal(skipRestoreFocus) {
    const wrap = byId('el-detail-modal-backdrop');
    if (wrap) wrap.hidden = true;
    detailModalState.isOpen = false;
    detailModalState.caseId = null;
    syncModalInertAndFocusTrap();
    const ret = detailModalState.returnFocusEl;
    detailModalState.returnFocusEl = null;
    if (!skipRestoreFocus && ret && typeof ret.focus === 'function' && state.user) {
      try {
        ret.focus();
      } catch (_err) {
        /* ignore */
      }
    }
  }

  function forceWipeAllModalsAndForms() {
    stopWithdrawalStopwatch();
    closeAllCardActionMenus();
    detailModalState.isOpen = false;
    detailModalState.caseId = null;
    detailModalState.returnFocusEl = null;
    drawerState.isOpen = false;
    drawerState.mode = 'create';
    drawerState.editingCaseId = null;
    drawerState.editingCaseCode = '';
    drawerState.expectedVersion = 1;
    drawerState.isDirty = false;
    drawerState.pendingCreatePayload = null;
    drawerState.returnFocusEl = null;
    drawerState.aeItems = [];
    drawerState.biliaryInterventions = [];
    drawerState.pepProphylaxis = [];
    drawerState.ercpHistoryFlags = [];
    drawerState.linkedPatientUid = null;
    drawerState.fulfillSurvRecId = null;
    drawerState.linkedOriginCaseCode = '';

    const formEl = byId('el-case-form');
    if (formEl && typeof formEl.reset === 'function') {
      formEl.reset();
    }

    [
      'el-f-full-name', 'el-f-birth-year', 'el-f-hospital-mrn', 'el-f-indication-detail',
      'el-f-lesion-site', 'el-f-surface-pattern', 'el-f-ercp-note', 'el-f-clinical-note',
      'el-f-clin-fu-note', 'el-f-confirm-delete-code', 'el-vault-passphrase'
    ].forEach((id) => {
      const inp = byId(id);
      if (inp) inp.value = '';
    });

    ['el-ae-list', 'el-dup-candidates', 'el-patient-readonly-box', 'el-detail-modal-badges', 'el-detail-modal-body'].forEach((id) => {
      const node = byId(id);
      if (node) {
        if (typeof node.replaceChildren === 'function') {
          node.replaceChildren();
        } else {
          node.innerHTML = '';
        }
      }
    });

    ['el-preview-initials', 'el-preview-age', 'el-settings-feedback', 'el-linked-surv-text'].forEach((id) => {
      const node = byId(id);
      if (node) node.textContent = '';
    });
    const dTitle = byId('el-detail-modal-title');
    if (dTitle) dTitle.textContent = 'Hồ sơ diễn tiến 4 pha';

    setDrawerAlert('');
    ['el-case-drawer-backdrop', 'el-dirty-modal-backdrop', 'el-dup-modal-backdrop', 'el-vault-modal-backdrop', 'el-detail-modal-backdrop'].forEach((id) => {
      const el = byId(id);
      if (el) el.hidden = true;
    });
    syncModalInertAndFocusTrap();
  }

  function parseOptionalFloat(id) {
    const el = byId(id);
    if (!el || el.value === '' || el.value == null) return null;
    const n = Number(el.value);
    return Number.isFinite(n) ? n : null;
  }

  function parseOptionalInt(id) {
    const el = byId(id);
    if (!el || el.value === '' || el.value == null) return null;
    const n = parseInt(el.value, 10);
    return Number.isFinite(n) ? n : null;
  }

  function buildIndexLesionPayload() {
    const tr = drawerState.track;
    if (tr === 'ERCP') return null;
    const bleedSrc = (byId('el-f-bleeding-source') && byId('el-f-bleeding-source').value) || 'NONE';
    const hasBleed = tr === 'EGD' && (drawerState.egdMode === 'bleeding' || bleedSrc !== 'NONE');
    if (!drawerState.hasIndexLesion && !hasBleed) return null;

    return {
      anatomical_site: (byId('el-f-lesion-site') && byId('el-f-lesion-site').value.trim()) || '',
      size_mm: parseOptionalFloat('el-f-lesion-size'),
      paris_class: (byId('el-f-paris-class') && byId('el-f-paris-class').value) || '',
      surface_pattern: (byId('el-f-surface-pattern') && byId('el-f-surface-pattern').value.trim()) || '',
      bleeding_source_type: tr === 'EGD' ? bleedSrc : 'NONE',
      forrest_class: tr === 'EGD' ? ((byId('el-f-forrest') && byId('el-f-forrest').value) || '') : '',
      hemostasis_modality: tr === 'EGD' ? ((byId('el-f-hemostasis-mod') && byId('el-f-hemostasis-mod').value) || '') : '',
      hemostasis_initial_success: tr === 'EGD' ? ((byId('el-f-hemostasis-success') && byId('el-f-hemostasis-success').value) || 'NA') : 'NA',
      biopsy_jar_count: Math.max(0, parseOptionalInt('el-f-biopsy-jars') || 0),
      resection_method: (byId('el-f-resection-method') && byId('el-f-resection-method').value) || 'NONE',
      histology_type: (byId('el-f-histology') && byId('el-f-histology').value) || 'NONE',
      dysplasia_grade: (byId('el-f-dysplasia') && byId('el-f-dysplasia').value) || 'NONE',
      margins_status: (byId('el-f-margins') && byId('el-f-margins').value) || 'NA',
      sm_invasion_um: parseOptionalInt('el-f-sm-um'),
      lvi_status: (byId('el-f-lvi') && byId('el-f-lvi').value) || 'NA',
      differentiation: (byId('el-f-diff') && byId('el-f-diff').value) || 'NA',
      budding_grade: (byId('el-f-budding') && byId('el-f-budding').value) || 'NA'
    };
  }

  function buildWholeCasePolypPayload() {
    if (drawerState.track !== 'COL') return null;
    const cnt = Math.max(0, parseOptionalInt('el-f-macro-polyp-count') || 0);
    return {
      macroscopic_polyp_count: cnt,
      complete_resection_all_lesions: cnt === 0
        ? 'NOT_APPLICABLE'
        : ((byId('el-f-complete-resection') && byId('el-f-complete-resection').value) || 'ALL_RESECTED_COMPLETELY'),
      any_piecemeal_ge_20mm: cnt === 0
        ? 'NO'
        : ((byId('el-f-piecemeal-20') && byId('el-f-piecemeal-20').value) || 'NO'),
      any_confirmed_adenoma: (byId('el-f-wc-any-ad') && byId('el-f-wc-any-ad').value) || 'NO',
      confirmed_adenoma_count_bin: (byId('el-f-wc-ad-bin') && byId('el-f-wc-ad-bin').value) || '0',
      max_adenoma_size_mm: parseOptionalFloat('el-f-wc-ad-max'),
      any_villous_or_hgd_any_lesion: (byId('el-f-wc-vill-hgd') && byId('el-f-wc-vill-hgd').value) || 'NO',
      any_hgd_any_lesion: (byId('el-f-wc-hgd') && byId('el-f-wc-hgd').value) || 'NO',
      any_confirmed_ssl: (byId('el-f-wc-any-ssl') && byId('el-f-wc-any-ssl').value) || 'NO',
      confirmed_ssl_count_bin: (byId('el-f-wc-ssl-bin') && byId('el-f-wc-ssl-bin').value) || '0',
      max_ssl_size_mm: parseOptionalFloat('el-f-wc-ssl-max'),
      any_ssl_with_dysplasia_or_tsa: (byId('el-f-wc-ssl-dys') && byId('el-f-wc-ssl-dys').value) || 'NO',
      any_invasive_cancer_or_noncurative_feature: (byId('el-f-wc-inv-noncur') && byId('el-f-wc-inv-noncur').value) || 'NO'
    };
  }

  function buildErcpDetailPayload() {
    if (drawerState.track !== 'ERCP') return null;
    return {
      history_flags: drawerState.ercpHistoryFlags.slice(),
      altered_anatomy: (byId('el-f-altered-anat') && byId('el-f-altered-anat').value) || 'NONE',
      antithrombotic_status: (byId('el-f-antithrombotic') && byId('el-f-antithrombotic').value.trim()) || 'NONE',
      imaging_modality: (byId('el-f-img-mod') && byId('el-f-img-mod').value) || 'MRCP',
      imaging_cbd_mm: parseOptionalFloat('el-f-img-cbd'),
      imaging_stone_count: Math.max(0, parseOptionalInt('el-f-img-stone-cnt') || 0),
      imaging_stone_max_mm: parseOptionalFloat('el-f-img-stone-max'),
      stricture_site: (byId('el-f-stricture-site') && byId('el-f-stricture-site').value.trim()) || '',
      labs: {
        bili_total_mg_dl: parseOptionalFloat('el-lab-bili-t'),
        bili_direct_mg_dl: parseOptionalFloat('el-lab-bili-d'),
        ast_u_l: parseOptionalFloat('el-lab-ast'),
        alt_u_l: parseOptionalFloat('el-lab-alt'),
        ggt_u_l: parseOptionalFloat('el-lab-ggt'),
        alp_u_l: parseOptionalFloat('el-lab-alp'),
        amylase_u_l: parseOptionalFloat('el-lab-amy'),
        lipase_u_l: parseOptionalFloat('el-lab-lip'),
        wbc_g_l: parseOptionalFloat('el-lab-wbc'),
        crp_mg_l: parseOptionalFloat('el-lab-crp'),
        plt_g_l: parseOptionalFloat('el-lab-plt'),
        inr: parseOptionalFloat('el-lab-inr')
      },
      papilla_status: (byId('el-f-papilla-status') && byId('el-f-papilla-status').value) || 'NATIVE_INTACT',
      duodenal_obstruction_or_altered: Boolean(drawerState.duodenalObstruction),
      vater_papilla_type: drawerState.vaterType || '1',
      pad_diverticulum: Boolean(drawerState.padDiverticulum),
      target_duct: (byId('el-f-target-duct') && byId('el-f-target-duct').value) || 'CBD',
      selective_cannulation: (byId('el-f-selective-cann') && byId('el-f-selective-cann').value) || 'SUCCESS',
      cannulation_contacts_count: Math.max(0, parseOptionalInt('el-f-cann-contacts') || 0),
      cannulation_time_min: Math.max(0, parseOptionalFloat('el-f-cann-time') || 0),
      total_procedure_time_min: Math.max(0, parseOptionalFloat('el-f-ercp-total-time') || 0),
      unintended_pd_count: Math.max(0, parseOptionalInt('el-f-unintended-pd') || 0),
      cannulation_technique: (byId('el-f-cann-tech') && byId('el-f-cann-tech').value) || 'STANDARD_SPHINCTEROTOME_GUIDEWIRE',
      biliary_interventions: drawerState.biliaryInterventions.slice(),
      pep_prophylaxis: drawerState.pepProphylaxis.slice(),
      ercp_procedure_note: (byId('el-f-ercp-note') && byId('el-f-ercp-note').value.trim()) || ''
    };
  }

  function extractApiErrorMessageVi(errBody, statusCode) {
    if (!errBody) return 'Yêu cầu không thành công (HTTP ' + statusCode + ').';
    const d = errBody.detail;
    if (typeof d === 'string') return d;
    if (d && typeof d === 'object' && !Array.isArray(d)) {
      if (d.message) return String(d.message);
    }
    if (Array.isArray(d) && d.length > 0) {
      return d.map((item) => item.msg || JSON.stringify(item)).join(' · ');
    }
    return 'Dữ liệu gửi lên chưa hợp lệ (HTTP ' + statusCode + ').';
  }

  function openDuplicateOutpatientModal(candidates, basePayload) {
    const wrap = byId('el-dup-modal-backdrop');
    const listEl = byId('el-dup-candidates');
    if (!wrap || !listEl) return;
    drawerState.pendingCreatePayload = basePayload;
    listEl.innerHTML = (candidates || []).map((cand) => {
      const sexLbl = cand.sex === 'F' ? 'Nữ' : (cand.sex === 'O' ? 'Khác' : 'Nam');
      return (
        '<div class="el-dup-item">' +
        '<div><strong>' + escapeHtml(cand.privacy_initials || '') + '</strong> · Năm sinh ' + escapeHtml(cand.birth_year) + ' (' + escapeHtml(sexLbl) + ')</div>' +
        '<button type="button" class="el-btn el-btn--compact el-btn--primary" data-merge-puid="' + escapeHtml(cand.patient_uid) + '">Ghép vào người bệnh này</button>' +
        '</div>'
      );
    }).join('');

    if (typeof listEl.querySelectorAll === 'function') {
      listEl.querySelectorAll('[data-merge-puid]').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const puid = btn.getAttribute('data-merge-puid');
          if (!drawerState.pendingCreatePayload || !puid) return;
          const mergedPayload = Object.assign({}, drawerState.pendingCreatePayload, {
            patient_uid: puid
          });
          wrap.hidden = true;
          syncModalInertAndFocusTrap();
          await sendCreateCaseRequest(mergedPayload);
        });
      });
    }
    wrap.hidden = false;
    syncModalInertAndFocusTrap();
    const cancelBtn = byId('el-btn-dup-cancel');
    if (cancelBtn && typeof cancelBtn.focus === 'function') cancelBtn.focus();
  }

  async function sendCreateCaseRequest(payload) {
    const reqEpoch = sessionEpoch;
    try {
      const resp = await apiFetch('/api/cases', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      }, reqEpoch);

      if (resp.status === 201 || resp.ok) {
        await resp.json();
        drawerState.pendingCreatePayload = null;
        await loadAllClinicalViews(reqEpoch);
        if (isSessionActiveForEpoch(reqEpoch)) {
          closeDrawerImmediately();
        }
        return;
      }

      const errBody = await resp.json().catch(() => null);
      if (
        resp.status === 409 &&
        errBody &&
        errBody.detail &&
        errBody.detail.code === 'OUTPATIENT_POTENTIAL_DUPLICATE_CONFIRM_REQUIRED'
      ) {
        openDuplicateOutpatientModal(errBody.detail.candidates || [], payload);
        return;
      }
      setDrawerSyncBadge('Cần kiểm tra dữ liệu', 'urgent');
      setDrawerAlert(extractApiErrorMessageVi(errBody, resp.status));
    } catch (err) {
      if (isExpectedSessionTerminationError(err)) return;
      setDrawerAlert('Không thể lưu hồ sơ ca soi do lỗi kết nối máy chủ.');
    }
  }

  async function submitCaseForm() {
    if (!state.user) return;
    setDrawerAlert('');

    const tr = drawerState.track;
    const rawProc = (byId('el-f-proc-start') && byId('el-f-proc-start').value) || formatLocalDatetimeInput();
    const procIso = rawProc.length === 16 ? (rawProc + ':00+07:00') : rawProc;
    const indexLesion = buildIndexLesionPayload();
    const wholeSummary = buildWholeCasePolypPayload();
    const ercpDetail = buildErcpDetailPayload();

    let pathStatus = (byId('el-f-path-status') && byId('el-f-path-status').value) || 'NOT_APPLICABLE';
    /* Zero-Implicit Negative: nếu có sinh thiết / cắt polyp mà chưa có mô bệnh học, tự động đặt PENDING thay vì ngầm tính âm tính */
    const hasSpecimen = Boolean(
      (indexLesion && (indexLesion.biopsy_jar_count > 0 || ['BIOPSY_ONLY', 'COLD_SNARE', 'HOT_SNARE', 'EMR_EN_BLOC', 'EMR_PIECEMEAL', 'ESD'].includes(indexLesion.resection_method))) ||
      (wholeSummary && wholeSummary.macroscopic_polyp_count > 0)
    );
    if (hasSpecimen && pathStatus === 'NOT_APPLICABLE') {
      pathStatus = (indexLesion && indexLesion.histology_type !== 'NONE') ? 'COMPLETE' : 'PENDING';
    }

    let fuStatus = (byId('el-f-followup-30d') && byId('el-f-followup-30d').value) || 'PENDING_WINDOW';
    if (drawerState.aeItems.length > 0 && fuStatus === 'COMPLETED_NO_AE') {
      fuStatus = 'COMPLETED_WITH_AE';
    }

    const clinDueRaw = (byId('el-f-clin-due-date') && byId('el-f-clin-due-date').value) || '';
    const clinDue = clinDueRaw ? clinDueRaw : null;

    if (drawerState.mode === 'create') {
      const fullName = (byId('el-f-full-name') && byId('el-f-full-name').value.trim()) || '';
      const birthYear = parseOptionalInt('el-f-birth-year');
      const mrn = (byId('el-f-hospital-mrn') && byId('el-f-hospital-mrn').value.trim()) || '';

      if (fullName.length < 2) {
        switchDrawerPhase('p1');
        setDrawerAlert('Vui lòng nhập họ và tên người bệnh (tối thiểu 2 ký tự).');
        return;
      }
      if (!birthYear || birthYear < 1900 || birthYear > 2026) {
        switchDrawerPhase('p1');
        setDrawerAlert('Vui lòng nhập năm sinh hợp lệ (từ 1900 đến 2026).');
        return;
      }
      if (drawerState.careSetting === 'INPATIENT' && !mrn) {
        switchDrawerPhase('p1');
        setDrawerAlert('Ca nội trú bắt buộc nhập mã hồ sơ bệnh viện để ghép đợt điều trị chính xác.');
        return;
      }

      const createPayload = {
        patient_uid: drawerState.linkedPatientUid || null,
        confirm_outpatient_new_patient: false,
        full_name: fullName,
        birth_year: birthYear,
        sex: drawerState.sex,
        hospital_mrn: mrn || null,
        care_setting: drawerState.careSetting,
        admission_date: drawerState.careSetting === 'INPATIENT'
          ? ((byId('el-f-admission-date') && byId('el-f-admission-date').value) || procIso.slice(0, 10))
          : null,
        referring_dept: (byId('el-f-referring-dept') && byId('el-f-referring-dept').value.trim()) || 'Khoa Nội soi Tiêu hóa',
        prior_unrecorded_ercp_offset: (drawerState.careSetting === 'INPATIENT' && tr === 'ERCP')
          ? Math.max(0, parseOptionalInt('el-f-ercp-offset') || 0)
          : 0,
        track: tr,
        procedure_start_at: procIso,
        operator_name: (byId('el-f-operator') && byId('el-f-operator').value.trim()) || 'ThS. BSCKI. Nguyễn Bình An',
        indication: (byId('el-f-indication') && byId('el-f-indication').value) || TRACK_DEFAULT_INDICATION[tr],
        indication_detail: (byId('el-f-indication-detail') && byId('el-f-indication-detail').value.trim()) || '',
        has_ibd_or_polyposis: tr === 'COL' ? Boolean(drawerState.hasIbdOrPolyposis) : false,
        exclude_from_cir: tr === 'COL' ? Boolean(drawerState.excludeFromCir) : false,
        bbps_right: tr === 'COL' ? drawerState.bbpsRight : null,
        bbps_transverse: tr === 'COL' ? drawerState.bbpsTransverse : null,
        bbps_left: tr === 'COL' ? drawerState.bbpsLeft : null,
        cecal_intubation: tr === 'COL' ? ((byId('el-f-cecal') && byId('el-f-cecal').value) || 'YES') : 'NA',
        cecal_failure_reason: tr === 'COL' ? ((byId('el-f-cecal-reason') && byId('el-f-cecal-reason').value.trim()) || '') : '',
        withdrawal_time_clean_min: tr === 'COL' ? parseOptionalFloat('el-f-withdrawal-min') : null,
        pathology_completion_status: pathStatus,
        followup_30d_status: fuStatus,
        clinician_followup_due_date: clinDue,
        clinician_followup_note: (byId('el-f-clin-fu-note') && byId('el-f-clin-fu-note').value.trim()) || '',
        index_lesion: indexLesion,
        whole_case_summary: wholeSummary,
        ercp_detail: ercpDetail,
        adverse_events: drawerState.aeItems.slice(),
        clinical_note: (byId('el-f-clinical-note') && byId('el-f-clinical-note').value.trim()) || '',
        fulfill_surveillance_rec_id: drawerState.fulfillSurvRecId || null
      };

      await sendCreateCaseRequest(createPayload);
      return;
    }

    /* Chế độ cập nhật hồ sơ ca soi hiện có (OCC ETag + expected_version) */
    const reqEpoch = sessionEpoch;
    const patchPayload = {
      expected_version: drawerState.expectedVersion,
      procedure_start_at: procIso,
      indication: (byId('el-f-indication') && byId('el-f-indication').value) || TRACK_DEFAULT_INDICATION[tr],
      indication_detail: (byId('el-f-indication-detail') && byId('el-f-indication-detail').value.trim()) || '',
      has_ibd_or_polyposis: tr === 'COL' ? Boolean(drawerState.hasIbdOrPolyposis) : false,
      exclude_from_cir: tr === 'COL' ? Boolean(drawerState.excludeFromCir) : false,
      pathology_completion_status: pathStatus,
      followup_30d_status: fuStatus,
      clinician_followup_due_date: clinDue,
      clinician_followup_note: (byId('el-f-clin-fu-note') && byId('el-f-clin-fu-note').value.trim()) || '',
      bbps_right: tr === 'COL' ? drawerState.bbpsRight : null,
      bbps_transverse: tr === 'COL' ? drawerState.bbpsTransverse : null,
      bbps_left: tr === 'COL' ? drawerState.bbpsLeft : null,
      cecal_intubation: tr === 'COL' ? ((byId('el-f-cecal') && byId('el-f-cecal').value) || 'YES') : 'NA',
      cecal_failure_reason: tr === 'COL' ? ((byId('el-f-cecal-reason') && byId('el-f-cecal-reason').value.trim()) || '') : '',
      withdrawal_time_clean_min: tr === 'COL' ? parseOptionalFloat('el-f-withdrawal-min') : null,
      index_lesion: indexLesion,
      whole_case_summary: wholeSummary,
      ercp_detail: ercpDetail,
      adverse_events: drawerState.aeItems.slice(),
      clinical_note: (byId('el-f-clinical-note') && byId('el-f-clinical-note').value.trim()) || ''
    };

    try {
      const resp = await apiFetch('/api/cases/' + encodeURIComponent(drawerState.editingCaseId), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'If-Match': 'W/"v' + drawerState.expectedVersion + '"'
        },
        body: JSON.stringify(patchPayload)
      }, reqEpoch);

      if (resp.ok) {
        await resp.json();
        await loadAllClinicalViews(reqEpoch);
        if (isSessionActiveForEpoch(reqEpoch)) {
          closeDrawerImmediately();
        }
        return;
      }

      const errBody = await resp.json().catch(() => null);
      if (resp.status === 409) {
        setDrawerSyncBadge('Lỗi xung đột phiên bản (OCC)', 'urgent');
        setDrawerAlert('Xung đột phiên bản dữ liệu (HTTP 409): Hồ sơ đã được cập nhật ở phiên khác. Vui lòng đóng ngăn kéo và mở lại để tải bản mới nhất trước khi lưu.');
        return;
      }
      setDrawerSyncBadge('Cần kiểm tra dữ liệu', 'urgent');
      setDrawerAlert(extractApiErrorMessageVi(errBody, resp.status));
    } catch (err) {
      if (isExpectedSessionTerminationError(err)) return;
      setDrawerAlert('Không thể cập nhật hồ sơ ca soi do lỗi kết nối máy chủ.');
    }
  }

  function syncColRollupFromIndexLesion() {
    const hist = (byId('el-f-histology') && byId('el-f-histology').value) || 'NONE';
    const dys = (byId('el-f-dysplasia') && byId('el-f-dysplasia').value) || 'NONE';
    const mrg = (byId('el-f-margins') && byId('el-f-margins').value) || 'NA';
    const sz = parseOptionalFloat('el-f-lesion-size');

    const isAdenoma = ['TUBULAR_ADENOMA', 'TUBULOVILLOUS_ADENOMA', 'VILLOUS_ADENOMA'].includes(hist);
    const isVillous = ['TUBULOVILLOUS_ADENOMA', 'VILLOUS_ADENOMA'].includes(hist);
    const isHgd = dys === 'HGD' || hist === 'HGD_VIENNA_C4' || hist === 'ADENOCARCINOMA_INTRAMUCOSAL';
    const isSsl = ['SSL_NO_DYSPLASIA', 'SSL_WITH_DYSPLASIA', 'TSA'].includes(hist);
    const isSslDysOrTsa = hist === 'SSL_WITH_DYSPLASIA' || hist === 'TSA' || (isSsl && (dys === 'LGD' || dys === 'HGD'));
    const isInvasiveOrNonCur = hist === 'ADENOCARCINOMA_INVASIVE' || dys === 'INVASIVE' || mrg === 'VM1_OR_R1';

    const setV = (id, v) => {
      const el = byId(id);
      if (el) el.value = v;
    };

    if (isAdenoma || isHgd) {
      setV('el-f-wc-any-ad', 'YES');
      if (byId('el-f-wc-ad-bin') && byId('el-f-wc-ad-bin').value === '0') {
        setV('el-f-wc-ad-bin', '1_2');
      }
      if (sz != null) setV('el-f-wc-ad-max', String(sz));
    }
    setV('el-f-wc-vill-hgd', (isVillous || isHgd) ? 'YES' : 'NO');
    setV('el-f-wc-hgd', isHgd ? 'YES' : 'NO');

    if (isSsl) {
      setV('el-f-wc-any-ssl', 'YES');
      if (byId('el-f-wc-ssl-bin') && byId('el-f-wc-ssl-bin').value === '0') {
        setV('el-f-wc-ssl-bin', '1_2');
      }
      if (sz != null) setV('el-f-wc-ssl-max', String(sz));
    }
    setV('el-f-wc-ssl-dys', isSslDysOrTsa ? 'YES' : 'NO');
    setV('el-f-wc-inv-noncur', isInvasiveOrNonCur ? 'YES' : 'NO');

    if (hist !== 'NONE' && byId('el-f-path-status') && byId('el-f-path-status').value !== 'PARTIAL') {
      setV('el-f-path-status', 'COMPLETE');
    }
    markDrawerDirty();
  }

  async function triggerBlobDownload(url, options, fallbackFilename) {
    const reqEpoch = sessionEpoch;
    const resp = await apiFetch(url, options || null, reqEpoch);
    if (!resp.ok) {
      const errBody = await resp.json().catch(() => null);
      throw new Error(extractApiErrorMessageVi(errBody, resp.status));
    }
    const blob = await resp.blob();
    const objUrl = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = objUrl;
    a.download = fallbackFilename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(objUrl), 1000);
  }
  function wipeClinicalDomAndShowLogin(bannerMessage) {
    bumpSessionEpoch(false);
    clearSessionTimers();
    forceWipeAllModalsAndForms();

    state.user = null;
    state.activeView = 'cases';
    state.trackFilter = 'ALL';
    state.survFilter = 'ALL';
    state.searchQuery = '';
    state.adrMinAge = 45;
    state.cusumMetric = 'CIR';
    state.cusumPreset = 'DEFAULT_90';
    state.settings = {
      colo_guideline_mode: 'USMSTF_2020',
      adr_min_age: 45,
      cusum_preset: 'DEFAULT_90',
      kpi_min_sample_size: 20
    };
    state.cases = [];
    state.surveillanceRows = [];
    state.kpiBundle = null;
    state.cusumData = null;
    state.auditStatus = null;

    try {
      window.sessionStorage.clear();
    } catch (_err) {
      /* ignore */
    }
    scrubLocalStorageAllowlist();

    ['el-case-list', 'el-cases-summary', 'el-surveillance-list', 'el-kpi-grid', 'el-cusum-container', 'el-audit-strip'].forEach((id) => {
      const node = byId(id);
      if (node) {
        if (typeof node.replaceChildren === 'function') {
          node.replaceChildren();
        } else {
          node.innerHTML = '';
        }
      }
    });

    ['el-cusum-disclaimer', 'el-user-name', 'el-user-dept'].forEach((id) => {
      const node = byId(id);
      if (node) node.textContent = '';
    });

    const searchInput = byId('el-case-search');
    if (searchInput) searchInput.value = '';

    const pwdInput = byId('el-login-password');
    if (pwdInput) pwdInput.value = '';

    const userInput = byId('el-login-username');
    if (userInput) userInput.value = userInput.defaultValue || 'nguyenbinhan';

    resetUiControlsToDefault();
    setLoginErrorBanner(bannerMessage);

    const shellEl = byId('el-app-shell');
    const loginEl = byId('el-login-screen');
    if (shellEl) shellEl.hidden = true;
    if (loginEl) loginEl.hidden = false;
  }

  async function performLogout(reasonMessage) {
    /* Xóa ngay lập tức DOM/state và hủy mọi request đang bay của phiên cũ; khóa nút đăng nhập tới khi POST logout kết thúc để tránh đua Set-Cookie */
    wipeClinicalDomAndShowLogin(reasonMessage || '');
    const logoutEpoch = sessionEpoch;
    setLoginControlsDisabled(true);

    const runRevoke = async () => {
      let serverConfirmed = false;
      let failCause = 'do lỗi kết nối mạng';
      try {
        const resp = await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
        serverConfirmed = Boolean(resp && resp.ok);
        if (!serverConfirmed && resp && typeof resp.status === 'number') {
          failCause = 'do máy chủ phản hồi lỗi (HTTP ' + resp.status + ')';
        }
      } catch (_err) {
        serverConfirmed = false;
        failCause = 'do lỗi kết nối mạng';
      } finally {
        setLoginControlsDisabled(false);
        if (sessionEpoch === logoutEpoch && !state.user && !serverConfirmed) {
          const suffix = 'Lưu ý: chưa xác nhận hủy phiên trên máy chủ ' + failCause + '.';
          const notice = reasonMessage
            ? (String(reasonMessage) + ' ' + suffix)
            : ('Đã xóa toàn bộ dữ liệu trên trình duyệt. ' + suffix);
          setLoginErrorBanner(notice);
        }
      }
    };

    const currentPromise = runRevoke();
    pendingLogoutPromise = currentPromise;
    try {
      await currentPromise;
    } finally {
      if (pendingLogoutPromise === currentPromise) {
        pendingLogoutPromise = null;
      }
    }
  }

  async function apiFetch(path, options, expectedEpoch) {
    const reqEpoch = expectedEpoch != null ? expectedEpoch : sessionEpoch;
    if (!isSessionActiveForEpoch(reqEpoch)) {
      throw new Error('STALE_SESSION_ABORTED');
    }
    const fetchOpts = Object.assign({ credentials: 'same-origin' }, options || {});
    if (activeAbortController && !fetchOpts.signal) {
      fetchOpts.signal = activeAbortController.signal;
    }
    const resp = await fetch(path, fetchOpts);
    if (reqEpoch !== sessionEpoch || !state.user) {
      throw new Error('STALE_SESSION_ABORTED');
    }
    if (resp.status === 401) {
      wipeClinicalDomAndShowLogin('Phiên làm việc đã hết hạn hoặc không còn hợp lệ. Đã xóa dữ liệu tạm trên màn hình.');
      throw new Error('UNAUTHENTICATED');
    }
    return resp;
  }

  function armHardSessionTimer(ttlMs) {
    if (state.hardExpiryTimer) {
      window.clearTimeout(state.hardExpiryTimer);
      state.hardExpiryTimer = null;
    }
    if (!state.user) return;
    const effectiveMs = Math.max(10, Number(ttlMs) || DEFAULT_HARD_SESSION_MS);
    hardSessionDeadlineMs = Date.now() + effectiveMs;
    const boundEpoch = sessionEpoch;
    state.hardExpiryTimer = window.setTimeout(() => {
      if (!isSessionActiveForEpoch(boundEpoch)) return;
      performLogout('Phiên xác thực 15 phút đã hết hạn. Đã xóa dữ liệu ca bệnh trên màn hình.');
    }, effectiveMs);
  }

  function checkSessionDeadlinesNow() {
    if (!state.user) return false;
    const now = Date.now();
    if (hardSessionDeadlineMs > 0 && now >= hardSessionDeadlineMs) {
      performLogout('Phiên xác thực 15 phút đã hết hạn. Đã xóa dữ liệu ca bệnh trên màn hình.');
      return true;
    }
    if (idleDeadlineMs > 0 && now >= idleDeadlineMs) {
      performLogout('Phiên làm việc đã tự động khóa sau 15 phút không thao tác.');
      return true;
    }
    return false;
  }

  function resetIdleTimer() {
    if (!state.user) return;
    const now = Date.now();
    if (hardSessionDeadlineMs > 0 && now >= hardSessionDeadlineMs) {
      performLogout('Phiên xác thực 15 phút đã hết hạn. Đã xóa dữ liệu ca bệnh trên màn hình.');
      return;
    }
    if (state.idleTimer) {
      window.clearTimeout(state.idleTimer);
      state.idleTimer = null;
    }
    idleDeadlineMs = now + idleTimeoutMs;
    const boundEpoch = sessionEpoch;
    state.idleTimer = window.setTimeout(() => {
      if (!isSessionActiveForEpoch(boundEpoch)) return;
      performLogout('Phiên làm việc đã tự động khóa sau 15 phút không thao tác.');
    }, idleTimeoutMs);
  }

  async function loadAllClinicalViews(expectedEpoch) {
    const reqEpoch = expectedEpoch != null ? expectedEpoch : sessionEpoch;
    try {
      const [casesResp, survResp, kpiResp, auditResp] = await Promise.all([
        apiFetch('/api/cases', null, reqEpoch),
        apiFetch('/api/surveillance', null, reqEpoch),
        apiFetch('/api/metrics/kpi?min_adr_age=' + encodeURIComponent(state.adrMinAge), null, reqEpoch),
        apiFetch('/api/audit/verify', null, reqEpoch)
      ]);
      const [casesJson, survJson, kpiJson, auditJson] = await Promise.all([
        casesResp.json(),
        survResp.json(),
        kpiResp.json(),
        auditResp.json()
      ]);
      if (!isSessionActiveForEpoch(reqEpoch)) return;

      state.cases = casesJson.items || [];
      state.settings = Object.assign({
        colo_guideline_mode: 'USMSTF_2020',
        adr_min_age: 45,
        cusum_preset: 'DEFAULT_90',
        kpi_min_sample_size: 20
      }, casesJson.settings || {});
      state.cusumPreset = state.settings.cusum_preset || 'DEFAULT_90';
      state.surveillanceRows = survJson.items || [];
      state.kpiBundle = kpiJson;
      state.cusumData = null;
      state.auditStatus = auditJson;

      renderCasesView();
      renderSurveillanceView();
      renderQualityView();
    } catch (err) {
      if (isExpectedSessionTerminationError(err)) return;
      throw err;
    }
  }

  function enterAuthenticatedShell(userObj, ttlSeconds) {
    const newEpoch = bumpSessionEpoch(true);
    clearSessionTimers();

    state.trackFilter = 'ALL';
    state.survFilter = 'ALL';
    state.searchQuery = '';
    state.adrMinAge = 45;
    state.cusumMetric = 'CIR';
    state.cusumPreset = 'DEFAULT_90';
    state.cases = [];
    state.surveillanceRows = [];
    state.kpiBundle = null;
    state.cusumData = null;
    state.auditStatus = null;

    const searchInput = byId('el-case-search');
    if (searchInput) searchInput.value = '';
    setLoginErrorBanner('');

    state.user = userObj;
    byId('el-user-name').textContent = userObj.display_name || 'ThS. BSCKI. Nguyễn Bình An';
    byId('el-user-dept').textContent = userObj.department || 'Khoa Nội soi Tiêu hóa — Bệnh viện Bình Dân';
    byId('el-login-screen').hidden = true;
    byId('el-app-shell').hidden = false;

    resetUiControlsToDefault();

    const params = new URLSearchParams(window.location.search);
    const urlView = params.get('view');
    let savedTab = 'cases';
    try {
      savedTab = window.sessionStorage.getItem(TAB_SESSION_KEY) || 'cases';
    } catch (_err) {
      savedTab = 'cases';
    }
    switchView(urlView || savedTab, false);

    const hardMs = (typeof ttlSeconds === 'number' && Number.isFinite(ttlSeconds) && ttlSeconds > 0)
      ? (ttlSeconds * 1000)
      : DEFAULT_HARD_SESSION_MS;
    armHardSessionTimer(hardMs);
    resetIdleTimer();
    return newEpoch;
  }

  async function bootstrap() {
    initTheme();
    const bootEpoch = sessionEpoch;

    const params = new URLSearchParams(window.location.search);
    const forceLoginScreen = params.get('login') === '1';

    try {
      const health = await (await fetch('/api/health', { credentials: 'same-origin' })).json();
      const bypassBtn = byId('el-btn-dev-bypass');
      if (bypassBtn) {
        bypassBtn.hidden = !health.local_bypass_candidate;
      }

      if (!forceLoginScreen) {
        const meResp = await fetch('/api/auth/me', { credentials: 'same-origin' });
        if (meResp.ok) {
          const meData = await meResp.json();
          if (typeof meData.remaining_seconds === 'number' && meData.remaining_seconds <= 0) {
            await performLogout('Phiên xác thực 15 phút đã hết hạn. Đã xóa dữ liệu ca bệnh trên màn hình.');
            return;
          }
          const ep = enterAuthenticatedShell(meData.user, meData.remaining_seconds);
          await loadAllClinicalViews(ep);
          return;
        }
        if (health.local_bypass_candidate) {
          const bpResp = await fetch('/api/auth/local-bypass', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ target_username: 'nguyenbinhan' })
          });
          if (bpResp.ok) {
            const bpData = await bpResp.json();
            const ep = enterAuthenticatedShell(bpData.user, bpData.expires_in_seconds);
            await loadAllClinicalViews(ep);
            return;
          }
        }
      }
    } catch (_err) {
      /* fall through to login screen if session epoch did not already handle logout/401 */
    }

    if (sessionEpoch === bootEpoch && !state.user) {
      wipeClinicalDomAndShowLogin('');
    }
  }

  function bindEvents() {
    initFormOptions();

    byId('el-theme-toggle').addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      applyTheme(cur === 'dark' ? 'light' : 'dark', true);
    });

    document.querySelectorAll('[data-nav-target]').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (!state.user) return;
        switchView(btn.getAttribute('data-nav-target'), false);
      });
    });

    document.querySelectorAll('[data-track-filter]').forEach((pill) => {
      pill.addEventListener('click', () => {
        if (!state.user) return;
        state.trackFilter = pill.getAttribute('data-track-filter') || 'ALL';
        document.querySelectorAll('[data-track-filter]').forEach((p) => {
          p.setAttribute('aria-pressed', p === pill ? 'true' : 'false');
        });
        renderCasesView();
      });
    });

    document.querySelectorAll('[data-surv-filter]').forEach((pill) => {
      pill.addEventListener('click', () => {
        if (!state.user) return;
        state.survFilter = pill.getAttribute('data-surv-filter') || 'ALL';
        document.querySelectorAll('[data-surv-filter]').forEach((p) => {
          p.setAttribute('aria-pressed', p === pill ? 'true' : 'false');
        });
        renderSurveillanceView();
      });
    });

    document.querySelectorAll('[data-age-toggle]').forEach((pill) => {
      pill.addEventListener('click', async () => {
        if (!state.user) return;
        const reqEpoch = sessionEpoch;
        kpiReqSeq += 1;
        const mySeq = kpiReqSeq;
        state.adrMinAge = Number(pill.getAttribute('data-age-toggle')) || 45;
        document.querySelectorAll('[data-age-toggle]').forEach((p) => {
          p.setAttribute('aria-pressed', p === pill ? 'true' : 'false');
        });
        try {
          const resp = await apiFetch('/api/metrics/kpi?min_adr_age=' + encodeURIComponent(state.adrMinAge), null, reqEpoch);
          const json = await resp.json();
          if (!isSessionActiveForEpoch(reqEpoch) || mySeq !== kpiReqSeq) return;
          state.kpiBundle = json;
          renderQualityView();
        } catch (err) {
          if (isExpectedSessionTerminationError(err)) return;
        }
      });
    });

    document.querySelectorAll('[data-cusum-metric]').forEach((pill) => {
      pill.addEventListener('click', async () => {
        if (!state.user) return;
        const reqEpoch = sessionEpoch;
        cusumReqSeq += 1;
        const mySeq = cusumReqSeq;
        state.cusumMetric = pill.getAttribute('data-cusum-metric') || 'CIR';
        const effectivePreset = state.cusumMetric === 'ERCP_NATIVE' ? 'DEFAULT_90' : (state.cusumPreset || 'DEFAULT_90');
        document.querySelectorAll('[data-cusum-metric]').forEach((p) => {
          p.setAttribute('aria-pressed', p === pill ? 'true' : 'false');
        });
        try {
          const resp = await apiFetch(
            '/api/metrics/cusum?metric=' + encodeURIComponent(state.cusumMetric) + '&preset=' + encodeURIComponent(effectivePreset),
            null,
            reqEpoch
          );
          const json = await resp.json();
          if (!isSessionActiveForEpoch(reqEpoch) || mySeq !== cusumReqSeq) return;
          state.cusumData = json;
          renderQualityView();
        } catch (err) {
          if (isExpectedSessionTerminationError(err)) return;
        }
      });
    });

    const searchInput = byId('el-case-search');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        if (!state.user) {
          searchInput.value = '';
          state.searchQuery = '';
          return;
        }
        state.searchQuery = searchInput.value || '';
        renderCasesView();
      });
    }

    const exportBtn = byId('el-btn-export-csv');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        if (!state.user) return;
        window.location.href = '/api/exports/profile-b?fmt=csv';
      });
    }

    const exportXlsxBtn = byId('el-btn-export-xlsx');
    if (exportXlsxBtn) {
      exportXlsxBtn.addEventListener('click', () => {
        if (!state.user) return;
        window.location.href = '/api/exports/profile-b?fmt=xlsx';
      });
    }

    const exportProfileCBtn = byId('el-btn-export-profile-c');
    if (exportProfileCBtn) {
      exportProfileCBtn.addEventListener('click', () => {
        if (!state.user) return;
        triggerBlobDownload('/api/exports/profile-c', null, 'endolog_profile_c_summary.json').catch(() => {});
      });
    }

    const openVaultBtn = byId('el-btn-open-vault-backup');
    if (openVaultBtn) {
      openVaultBtn.addEventListener('click', () => {
        if (!state.user) return;
        const wrap = byId('el-vault-modal-backdrop');
        const noticeEl = byId('el-vault-role-notice');
        const passBox = byId('el-vault-passphrase-box');
        const passEl = byId('el-vault-passphrase');
        const dlBtn = byId('el-btn-vault-download');
        const errEl = byId('el-vault-error');
        if (!wrap) return;
        if (passEl) passEl.value = '';
        if (errEl) {
          errEl.textContent = '';
          errEl.hidden = true;
        }
        const isSuper = state.user.role === 'superadmin';
        if (noticeEl) {
          noticeEl.textContent = isSuper
            ? 'Tệp sao lưu .endolog.enc mã hóa toàn bộ kho dữ liệu bằng khóa dẫn xuất Argon2id + AES-256-GCM.'
            : 'Chỉ tài khoản Superadmin (BSCKII. Vũ Khương An) có thẩm quyền trích xuất kho sao lưu mã hóa Hồ sơ A (.endolog.enc).';
        }
        if (passBox) passBox.hidden = !isSuper;
        if (dlBtn) dlBtn.hidden = !isSuper;
        wrap.hidden = false;
        syncModalInertAndFocusTrap();
        const focusTarget = isSuper ? passEl : byId('el-btn-vault-close');
        if (focusTarget && typeof focusTarget.focus === 'function') focusTarget.focus();
      });
    }

    const vaultCloseBtn = byId('el-btn-vault-close');
    if (vaultCloseBtn) {
      vaultCloseBtn.addEventListener('click', () => {
        closeVaultModal();
      });
    }

    const vaultDlBtn = byId('el-btn-vault-download');
    if (vaultDlBtn) {
      vaultDlBtn.addEventListener('click', async () => {
        if (!state.user) return;
        const passEl = byId('el-vault-passphrase');
        const errEl = byId('el-vault-error');
        const passphrase = passEl ? passEl.value : '';
        if (passphrase.length < 12) {
          if (errEl) {
            errEl.textContent = 'Khóa mật khẩu mã hóa tập tin sao lưu phải có tối thiểu 12 ký tự.';
            errEl.hidden = false;
          }
          return;
        }
        try {
          await triggerBlobDownload(
            '/api/exports/profile-a',
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ passphrase })
            },
            'endolog_vault_backup.endolog.enc'
          );
          closeVaultModal();
        } catch (err) {
          if (isExpectedSessionTerminationError(err)) return;
          if (errEl) {
            errEl.textContent = String((err && err.message) || 'Không thể tải tệp sao lưu mã hóa.');
            errEl.hidden = false;
          }
        }
      });
    }

    const saveSettingsBtn = byId('el-btn-save-settings');
    if (saveSettingsBtn) {
      saveSettingsBtn.addEventListener('click', async () => {
        if (!state.user) return;
        const reqEpoch = sessionEpoch;
        const gEl = byId('el-setting-guideline');
        const nEl = byId('el-setting-n-min');
        const cEl = byId('el-setting-cusum-preset');
        const fbEl = byId('el-settings-feedback');
        const rawN = nEl ? parseInt(nEl.value, 10) : 20;
        const clampedN = Math.max(1, Math.min(500, Number.isFinite(rawN) ? rawN : 20));
        if (nEl) nEl.value = String(clampedN);
        const body = {
          colo_guideline_mode: (gEl && gEl.value) || 'USMSTF_2020',
          kpi_min_sample_size: clampedN,
          cusum_preset: (cEl && cEl.value) || 'DEFAULT_90'
        };
        try {
          const resp = await apiFetch('/api/settings', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          }, reqEpoch);
          if (resp.ok) {
            await loadAllClinicalViews(reqEpoch);
            if (fbEl && isSessionActiveForEpoch(reqEpoch)) {
              fbEl.textContent = 'Đã lưu cấu hình chuyên môn';
            }
          }
        } catch (err) {
          if (isExpectedSessionTerminationError(err)) return;
        }
      });
    }

    const newCaseBtn = byId('el-btn-new-case');
    if (newCaseBtn) {
      newCaseBtn.addEventListener('click', () => {
        openNewCaseDrawer(null, null, newCaseBtn);
      });
    }

    ['el-case-list', 'el-surveillance-list'].forEach((listId) => {
      const container = byId(listId);
      if (!container) return;
      container.addEventListener('click', (ev) => {
        if (!state.user || !ev.target || typeof ev.target.closest !== 'function') return;

        const moreBtn = ev.target.closest('[data-case-more]');
        if (moreBtn) {
          ev.stopPropagation();
          const wrap = moreBtn.closest('.el-action-menu-wrap');
          const menu = wrap ? wrap.querySelector('.el-action-menu-dropdown') : null;
          if (!menu) return;
          const willOpen = menu.hidden;
          closeAllCardActionMenus();
          if (willOpen) {
            const rect = moreBtn.getBoundingClientRect();
            const menuApproxHeight = 290;
            const bottomNavReserve = window.innerWidth < 768 ? 76 : 20;
            const shouldDropup = (window.innerHeight - rect.bottom) < (menuApproxHeight + bottomNavReserve) && rect.top > menuApproxHeight;
            menu.classList.toggle('is-dropup', shouldDropup);
            menu.hidden = false;
            moreBtn.setAttribute('aria-expanded', 'true');
            const parentCard = moreBtn.closest('.el-case-card');
            if (parentCard) parentCard.classList.add('el-case-card--menu-open');
          }
          return;
        }

        const detailBtn = ev.target.closest('[data-case-detail]');
        if (detailBtn) {
          const cid = detailBtn.getAttribute('data-case-detail');
          closeAllCardActionMenus();
          openCaseDetailModal(cid, detailBtn);
          return;
        }

        const dangerBtn = ev.target.closest('[data-danger-case]');
        if (dangerBtn) {
          const cid = dangerBtn.getAttribute('data-danger-case');
          closeAllCardActionMenus();
          openEditCaseDrawer(cid, 'p4', dangerBtn);
          const dz = byId('el-danger-zone');
          if (dz && !dz.hidden) dz.open = true;
          return;
        }

        const editBtn = ev.target.closest('[data-case-edit]');
        if (editBtn) {
          const cid = editBtn.getAttribute('data-case-edit');
          const phase = editBtn.getAttribute('data-target-phase') || 'p2';
          closeAllCardActionMenus();
          openEditCaseDrawer(cid, phase, editBtn);
          return;
        }

        const linkBtn = ev.target.closest('[data-create-linked]');
        if (linkBtn) {
          const originId = linkBtn.getAttribute('data-create-linked');
          const originCase = state.cases.find((item) => item.case_id === originId) || null;
          closeAllCardActionMenus();
          openNewCaseDrawer((originCase && originCase.track) || 'COL', originCase, linkBtn);
        }
      });
    });

    ['el-btn-detail-close', 'el-btn-detail-close-foot'].forEach((btnId) => {
      const btn = byId(btnId);
      if (btn) {
        btn.addEventListener('click', () => {
          closeCaseDetailModal(false);
        });
      }
    });

    const detailBackdrop = byId('el-detail-modal-backdrop');
    if (detailBackdrop) {
      detailBackdrop.addEventListener('click', (ev) => {
        if (ev.target === detailBackdrop) {
          closeCaseDetailModal(false);
          return;
        }
        if (ev.target && typeof ev.target.closest === 'function') {
          const jumpBtn = ev.target.closest('[data-detail-jump-phase]');
          if (jumpBtn && detailModalState.caseId) {
            const targetCid = detailModalState.caseId;
            const targetPhase = jumpBtn.getAttribute('data-detail-jump-phase') || 'p1';
            const retFocus = detailModalState.returnFocusEl;
            closeCaseDetailModal(true);
            openEditCaseDrawer(targetCid, targetPhase, retFocus);
          }
        }
      });
    }

    if (typeof document.addEventListener === 'function') {
      document.addEventListener('click', (ev) => {
        if (!ev.target || typeof ev.target.closest !== 'function') return;
        if (!ev.target.closest('.el-action-menu-wrap')) {
          closeAllCardActionMenus();
        }
      });
    }

    ['el-drawer-close', 'el-btn-cancel-drawer'].forEach((btnId) => {
      const btn = byId(btnId);
      if (btn) {
        btn.addEventListener('click', () => {
          requestCloseDrawer();
        });
      }
    });

    const drawerBackdrop = byId('el-case-drawer-backdrop');
    if (drawerBackdrop) {
      drawerBackdrop.addEventListener('click', (ev) => {
        if (ev.target === drawerBackdrop) {
          requestCloseDrawer();
        }
      });
    }

    document.querySelectorAll('[data-phase-tab]').forEach((tab) => {
      tab.addEventListener('click', () => {
        switchDrawerPhase(tab.getAttribute('data-phase-tab'));
      });
    });

    document.querySelectorAll('[data-form-track]').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (drawerState.mode !== 'create') return;
        const tr = btn.getAttribute('data-form-track') || 'COL';
        drawerState.track = tr;
        drawerState.careSetting = tr === 'ERCP' ? 'INPATIENT' : 'OUTPATIENT';
        populateIndicationOptionsForTrack(tr, TRACK_DEFAULT_INDICATION[tr]);
        drawerState.hasIndexLesion = tr === 'EGD';
        drawerState.bbpsRight = tr === 'COL' ? 3 : null;
        drawerState.bbpsTransverse = tr === 'COL' ? 3 : null;
        drawerState.bbpsLeft = tr === 'COL' ? 3 : null;
        const cecalEl = byId('el-f-cecal');
        if (cecalEl) cecalEl.value = tr === 'COL' ? 'YES' : 'NA';
        const wdEl = byId('el-f-withdrawal-min');
        if (wdEl) wdEl.value = tr === 'COL' ? '8' : '';
        applyDrawerTrackAndCareVisibility();
        markDrawerDirty();
      });
    });

    document.querySelectorAll('[data-form-sex]').forEach((btn) => {
      btn.addEventListener('click', () => {
        drawerState.sex = btn.getAttribute('data-form-sex') || 'M';
        applyDrawerTrackAndCareVisibility();
        markDrawerDirty();
      });
    });

    document.querySelectorAll('[data-form-care]').forEach((btn) => {
      btn.addEventListener('click', () => {
        drawerState.careSetting = btn.getAttribute('data-form-care') === 'inpatient' ? 'INPATIENT' : 'OUTPATIENT';
        applyDrawerTrackAndCareVisibility();
        markDrawerDirty();
      });
    });

    document.querySelectorAll('[data-egd-mode]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const m = btn.getAttribute('data-egd-mode') || 'lesion';
        drawerState.egdMode = m;
        if (m === 'lesion') drawerState.hasIndexLesion = true;
        if (m === 'routine') drawerState.hasIndexLesion = false;
        applyDrawerTrackAndCareVisibility();
        markDrawerDirty();
      });
    });

    document.querySelectorAll('[data-bbps-seg]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const seg = btn.getAttribute('data-bbps-seg');
        const v = Number(btn.getAttribute('data-bbps-val'));
        if (seg === 'right') drawerState.bbpsRight = v;
        if (seg === 'transverse') drawerState.bbpsTransverse = v;
        if (seg === 'left') drawerState.bbpsLeft = v;
        updateBbpsLiveUi();
        markDrawerDirty();
      });
    });

    const bbps9Btn = byId('el-btn-bbps-9');
    if (bbps9Btn) {
      bbps9Btn.addEventListener('click', () => {
        drawerState.bbpsRight = 3;
        drawerState.bbpsTransverse = 3;
        drawerState.bbpsLeft = 3;
        updateBbpsLiveUi();
        markDrawerDirty();
      });
    }

    const presetColBtn = byId('el-btn-preset-normal-col');
    if (presetColBtn) {
      presetColBtn.addEventListener('click', () => {
        drawerState.track = 'COL';
        drawerState.bbpsRight = 3;
        drawerState.bbpsTransverse = 3;
        drawerState.bbpsLeft = 3;
        drawerState.hasIndexLesion = false;
        const cecalEl = byId('el-f-cecal');
        if (cecalEl) cecalEl.value = 'YES';
        const wdEl = byId('el-f-withdrawal-min');
        if (wdEl) wdEl.value = '8';
        const mpEl = byId('el-f-macro-polyp-count');
        if (mpEl) mpEl.value = '0';
        const psEl = byId('el-f-path-status');
        if (psEl) psEl.value = 'NOT_APPLICABLE';
        applyDrawerTrackAndCareVisibility();
        markDrawerDirty();
        setDrawerSyncBadge('Đã áp mẫu đại tràng bình thường (0 polyp)', 'ok');
      });
    }

    const timerToggleBtn = byId('el-btn-timer-toggle');
    if (timerToggleBtn) {
      timerToggleBtn.addEventListener('click', () => {
        if (drawerState.timerRunning) {
          stopWithdrawalStopwatch();
          updateStopwatchUi();
          return;
        }
        drawerState.timerRunning = true;
        updateStopwatchUi();
        drawerState.timerIntervalId = window.setInterval(() => {
          drawerState.timerElapsedSec += 1;
          updateStopwatchUi();
        }, 1000);
      });
    }

    const timerApplyBtn = byId('el-btn-timer-apply');
    if (timerApplyBtn) {
      timerApplyBtn.addEventListener('click', () => {
        const wdEl = byId('el-f-withdrawal-min');
        if (wdEl) {
          const minsVal = Math.max(0.5, Math.round((drawerState.timerElapsedSec / 60) * 10) / 10);
          wdEl.value = String(minsVal);
        }
        stopWithdrawalStopwatch();
        updateStopwatchUi();
        markDrawerDirty();
      });
    }

    const bindSwitchToggle = (id, propName, recomputeVis) => {
      const sw = byId(id);
      if (!sw) return;
      sw.addEventListener('click', () => {
        drawerState[propName] = !drawerState[propName];
        if (recomputeVis) {
          applyDrawerTrackAndCareVisibility();
        } else {
          updateSwitchPill(id, drawerState[propName]);
        }
        markDrawerDirty();
      });
    };
    bindSwitchToggle('el-sw-ibd-polyposis', 'hasIbdOrPolyposis', false);
    bindSwitchToggle('el-sw-exclude-cir', 'excludeFromCir', false);
    bindSwitchToggle('el-sw-has-index-lesion', 'hasIndexLesion', true);
    bindSwitchToggle('el-sw-pad', 'padDiverticulum', false);
    bindSwitchToggle('el-sw-duodenal-obs', 'duodenalObstruction', false);

    document.querySelectorAll('[data-vater-type]').forEach((btn) => {
      btn.addEventListener('click', () => {
        drawerState.vaterType = btn.getAttribute('data-vater-type') || '1';
        applyDrawerTrackAndCareVisibility();
        markDrawerDirty();
      });
    });

    ['el-f-full-name', 'el-f-birth-year', 'el-f-proc-start'].forEach((id) => {
      const inp = byId(id);
      if (inp) {
        inp.addEventListener('input', updatePatientPreviewHints);
      }
    });

    const lesionSiteInp = byId('el-f-lesion-site');
    if (lesionSiteInp) {
      lesionSiteInp.addEventListener('input', () => {
        renderQuickSiteChips(drawerState.track);
      });
    }

    const cecalSel = byId('el-f-cecal');
    if (cecalSel) {
      cecalSel.addEventListener('change', () => {
        applyDrawerTrackAndCareVisibility();
        markDrawerDirty();
      });
    }

    const macroPolypInp = byId('el-f-macro-polyp-count');
    if (macroPolypInp) {
      macroPolypInp.addEventListener('input', () => {
        const cnt = Number(macroPolypInp.value) || 0;
        if (cnt > 0) {
          drawerState.hasIndexLesion = true;
          const crEl = byId('el-f-complete-resection');
          if (crEl && crEl.value === 'NOT_APPLICABLE') {
            crEl.value = 'ALL_RESECTED_COMPLETELY';
          }
        }
        applyDrawerTrackAndCareVisibility();
        markDrawerDirty();
      });
    }

    ['el-f-papilla-status', 'el-f-cann-contacts', 'el-f-cann-time', 'el-f-unintended-pd'].forEach((id) => {
      const el = byId(id);
      if (el) {
        el.addEventListener(el.tagName === 'SELECT' ? 'change' : 'input', updateErcpDifficultyLiveBadge);
      }
    });

    const addAeBtn = byId('el-btn-add-ae');
    if (addAeBtn) {
      addAeBtn.addEventListener('click', () => {
        drawerState.aeItems.push({
          ae_id: 'ae_' + Date.now() + '_' + drawerState.aeItems.length,
          window: 'INPATIENT_EARLY',
          event_type: drawerState.track === 'ERCP' ? 'PEP' : 'BLEEDING',
          pep_severity: drawerState.track === 'ERCP' ? 'MILD' : 'NONE',
          agree_grade: 'II',
          readmission_required: false,
          surgical_rescue_required: false,
          note: ''
        });
        const fuEl = byId('el-f-followup-30d');
        if (fuEl && fuEl.value !== 'COMPLETED_WITH_AE') {
          fuEl.value = 'COMPLETED_WITH_AE';
        }
        renderAeRows();
        markDrawerDirty();
      });
    }

    const syncWholeBtn = byId('el-btn-sync-whole-case');
    if (syncWholeBtn) {
      syncWholeBtn.addEventListener('click', () => {
        syncColRollupFromIndexLesion();
      });
    }

    const clearLinkBtn = byId('el-btn-clear-surv-link');
    if (clearLinkBtn) {
      clearLinkBtn.addEventListener('click', () => {
        drawerState.linkedPatientUid = null;
        drawerState.fulfillSurvRecId = null;
        drawerState.linkedOriginCaseCode = '';
        const b = byId('el-linked-surv-banner');
        if (b) b.hidden = true;
        markDrawerDirty();
      });
    }

    const supersedeBtn = byId('el-btn-supersede-case');
    if (supersedeBtn) {
      supersedeBtn.addEventListener('click', async () => {
        if (!state.user || drawerState.mode !== 'edit' || !drawerState.editingCaseId) return;
        const codeEl = byId('el-f-confirm-delete-code');
        const typed = codeEl ? codeEl.value.trim() : '';
        if (!typed || typed !== drawerState.editingCaseCode) {
          setDrawerAlert('Vui lòng nhập chính xác mã ca ' + drawerState.editingCaseCode + ' để xác nhận hủy hiệu lực.');
          return;
        }
        const reqEpoch = sessionEpoch;
        try {
          const resp = await apiFetch('/api/cases/' + encodeURIComponent(drawerState.editingCaseId), {
            method: 'DELETE'
          }, reqEpoch);
          if (resp.ok) {
            await loadAllClinicalViews(reqEpoch);
            if (isSessionActiveForEpoch(reqEpoch)) {
              closeDrawerImmediately();
            }
            return;
          }
          const errBody = await resp.json().catch(() => null);
          setDrawerAlert(extractApiErrorMessageVi(errBody, resp.status));
        } catch (err) {
          if (isExpectedSessionTerminationError(err)) return;
          setDrawerAlert('Không thể hủy hiệu lực hồ sơ do lỗi kết nối máy chủ.');
        }
      });
    }

    const caseForm = byId('el-case-form');
    if (caseForm) {
      ['input', 'change'].forEach((evtName) => {
        caseForm.addEventListener(evtName, (ev) => {
          if (ev.target && ev.target.id === 'el-f-confirm-delete-code') return;
          markDrawerDirty();
        });
      });
      caseForm.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter' && ev.target && ev.target.tagName === 'INPUT') {
          ev.preventDefault();
        }
      });
      caseForm.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        await submitCaseForm();
      });
    }

    const dirtyKeepBtn = byId('el-btn-dirty-keep');
    if (dirtyKeepBtn) {
      dirtyKeepBtn.addEventListener('click', () => {
        const dirtyWrap = byId('el-dirty-modal-backdrop');
        if (dirtyWrap) dirtyWrap.hidden = true;
        syncModalInertAndFocusTrap();
      });
    }

    const dirtyDiscardBtn = byId('el-btn-dirty-discard');
    if (dirtyDiscardBtn) {
      dirtyDiscardBtn.addEventListener('click', () => {
        closeDrawerImmediately();
      });
    }

    const dupNewBtn = byId('el-btn-dup-new-patient');
    if (dupNewBtn) {
      dupNewBtn.addEventListener('click', async () => {
        if (!drawerState.pendingCreatePayload) return;
        const payload = Object.assign({}, drawerState.pendingCreatePayload, {
          confirm_outpatient_new_patient: true
        });
        const dupWrap = byId('el-dup-modal-backdrop');
        if (dupWrap) dupWrap.hidden = true;
        syncModalInertAndFocusTrap();
        await sendCreateCaseRequest(payload);
      });
    }

    const dupCancelBtn = byId('el-btn-dup-cancel');
    if (dupCancelBtn) {
      dupCancelBtn.addEventListener('click', () => {
        const dupWrap = byId('el-dup-modal-backdrop');
        if (dupWrap) dupWrap.hidden = true;
        drawerState.pendingCreatePayload = null;
        syncModalInertAndFocusTrap();
      });
    }

    window.addEventListener('keydown', handleGlobalModalKeydown);

    byId('el-btn-logout').addEventListener('click', async () => {
      await performLogout('');
    });

    byId('el-login-form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      if (pendingLogoutPromise) {
        await pendingLogoutPromise.catch(() => {});
      }
      setLoginErrorBanner('');
      const username = byId('el-login-username').value.trim();
      const password = byId('el-login-password').value;
      try {
        const resp = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ username, password })
        });
        if (!resp.ok) {
          setLoginErrorBanner('Tên đăng nhập hoặc mật khẩu không đúng.');
          return;
        }
        const data = await resp.json();
        const ep = enterAuthenticatedShell(data.user, data.expires_in_seconds);
        await loadAllClinicalViews(ep);
      } catch (_err) {
        if (!state.user) {
          setLoginErrorBanner('Không thể kết nối máy chủ xác thực.');
        }
      }
    });

    byId('el-btn-dev-bypass').addEventListener('click', async () => {
      if (pendingLogoutPromise) {
        await pendingLogoutPromise.catch(() => {});
      }
      try {
        const resp = await fetch('/api/auth/local-bypass', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ target_username: 'nguyenbinhan' })
        });
        if (resp.ok) {
          const data = await resp.json();
          const ep = enterAuthenticatedShell(data.user, data.expires_in_seconds);
          await loadAllClinicalViews(ep);
        }
      } catch (_err) {
        if (!state.user) {
          setLoginErrorBanner('Không thể mở phiên giả lập cục bộ do lỗi kết nối.');
        }
      }
    });

    ['click', 'keydown', 'pointerdown'].forEach((evtName) => {
      window.addEventListener(evtName, resetIdleTimer, { passive: true });
    });

    window.addEventListener('focus', checkSessionDeadlinesNow);
    if (typeof document.addEventListener === 'function') {
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) checkSessionDeadlinesNow();
      });
    }

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
  }

  /* Móc kiểm thử phi-PHI (chỉ phơi hàm thuần và ảnh chụp độ sạch bộ nhớ, không lưu/trả dữ liệu bệnh nhân) */
  window.__ENDOLOG_RUNTIME_AUDIT__ = {
    evaluateKpiRateBadge,
    evaluateAdverseEventKpiBadge,
    computeCasePhaseProgression,
    formatGuidelineLabelVi,
    formatRaCusumStatusVi,
    formatIndicationVi,
    formatHistologyVi,
    humanizeClinicalBadgeLabelVi,
    setIdleTimeoutForTest(ms) {
      idleTimeoutMs = Math.max(10, Number(ms) || DEFAULT_IDLE_TIMEOUT_MS);
      if (state.user) resetIdleTimer();
    },
    setHardSessionExpiryForTest(ms) {
      if (state.user) armHardSessionTimer(ms);
    },
    checkSessionDeadlinesNow,
    getSanitizedClientState() {
      return {
        hasUser: Boolean(state.user),
        activeView: state.activeView,
        trackFilter: state.trackFilter,
        survFilter: state.survFilter,
        searchQueryLength: state.searchQuery.length,
        adrMinAge: state.adrMinAge,
        cusumMetric: state.cusumMetric,
        cusumPreset: state.cusumPreset,
        casesCount: state.cases.length,
        surveillanceCount: state.surveillanceRows.length,
        hasKpiBundle: state.kpiBundle !== null,
        hasCusumData: state.cusumData !== null,
        hasAuditStatus: state.auditStatus !== null,
        hasIdleTimer: state.idleTimer !== null,
        hasHardExpiryTimer: state.hardExpiryTimer !== null,
        isDrawerOpen: Boolean(drawerState.isOpen),
        isDetailModalOpen: Boolean(detailModalState.isOpen),
        isDirty: Boolean(drawerState.isDirty),
        aeDraftCount: drawerState.aeItems.length,
        hasPendingDuplicatePayload: drawerState.pendingCreatePayload !== null,
        sessionEpoch
      };
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    bootstrap();
  });
})();
