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
    USMSTF_POST_POLYPECTOMY_2020: 'Hướng dẫn USMSTF 2020 (hậu cắt polyp đại trực tràng)',
    ESGE_POST_POLYPECTOMY_2020: 'Hướng dẫn ESGE 2020 (hậu cắt polyp đại trực tràng)',
    ESGE_ESD_2022: 'Hướng dẫn ESGE 2022 (sau cắt tách dưới niêm mạc ESD)',
    CLINICIAN_DIRECTED_EGD: 'Theo chỉ định bác sĩ — nội soi thực quản, dạ dày, tá tràng',
    CLINICIAN_DIRECTED_ERCP: 'Theo chỉ định bác sĩ — nội soi mật tụy ngược dòng (ERCP)'
  };

  const GUIDELINE_SHORT_LABELS_VI = {
    USMSTF_POST_POLYPECTOMY_2020: 'USMSTF 2020 — hậu cắt polyp',
    ESGE_POST_POLYPECTOMY_2020: 'ESGE 2020 — hậu cắt polyp',
    ESGE_ESD_2022: 'ESGE 2022 — sau ESD',
    CLINICIAN_DIRECTED_EGD: 'Theo chỉ định bác sĩ — nội soi dạ dày',
    CLINICIAN_DIRECTED_ERCP: 'Theo chỉ định bác sĩ — nội soi mật tụy'
  };

  const RA_CUSUM_STATUS_LABELS_VI = {
    DISABLED_UNVALIDATED_MODEL: 'Đang khóa hiệu chỉnh nguy cơ — chưa có mô hình ngoại kiểm tại đơn vị'
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
    MILD: 'mức độ nhẹ',
    MODERATE: 'mức độ trung bình',
    SEVERE: 'mức độ nặng'
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
    cases: [],
    surveillanceRows: [],
    kpiBundle: null,
    cusumData: null,
    auditStatus: null,
    idleTimer: null,
    hardExpiryTimer: null
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
    txt = txt.replace(/\bPEP\s+(MILD|MODERATE|SEVERE|NONE)\b/g, (_m, sev) => {
      return 'PEP ' + (PEP_SEVERITY_LABELS_VI[sev] || 'ghi nhận');
    });
    txt = txt.replace(/\bAGREE\s+(?!độ\b)(I{1,3}[ab]?|IV[ab]?|V)\b/g, 'AGREE độ $1');
    return sanitizeEnumFallbackVi(txt, 'Trạng thái lâm sàng');
  }

  /* Đánh giá huy hiệu trạng thái KPI dựa trên tử số/mẫu số chính xác và hợp đồng KPI đã duyệt (B01) */
  function evaluateKpiRateBadge(metricObj) {
    const den = metricObj && typeof metricObj.denominator === 'number' && Number.isFinite(metricObj.denominator)
      ? metricObj.denominator
      : 0;
    const rawRate = metricObj ? metricObj.rate_pct : null;
    const hasRate = typeof rawRate === 'number' && Number.isFinite(rawRate);
    const hasNum = Boolean(metricObj && typeof metricObj.numerator === 'number' && Number.isFinite(metricObj.numerator));
    const pendingGpb = metricObj && typeof metricObj.pending_gpb_excluded_count === 'number' && Number.isFinite(metricObj.pending_gpb_excluded_count)
      ? metricObj.pending_gpb_excluded_count
      : 0;

    if (den <= 0 || !hasRate) {
      if (pendingGpb > 0) {
        return { tone: 'pending', label: 'Chưa đủ dữ liệu (' + pendingGpb + ' ca chờ GPB)' };
      }
      return { tone: 'neutral', label: 'Chưa đủ dữ liệu' };
    }

    const rawTarget = metricObj ? metricObj.target_pct : null;
    const hasTarget = typeof rawTarget === 'number' && Number.isFinite(rawTarget);
    if (!hasTarget) {
      return { tone: 'neutral', label: 'Chưa thiết lập ngưỡng' };
    }

    const target = rawTarget;
    const targetTxt = formatViNum(target) + '%';
    /* So sánh trực tiếp tử số/mẫu số khi có để tránh làm tròn 1 chữ số thập phân (ví dụ 36/103 = 34,95% -> 35,0%) tạo dương tính giả */
    const meetsTarget = hasNum
      ? (metricObj.numerator * 100 >= target * den - 1e-9)
      : (rawRate >= target);

    if (meetsTarget) {
      return {
        tone: 'ned',
        label: pendingGpb > 0
          ? ('Đạt ngưỡng ≥ ' + targetTxt + ' (' + pendingGpb + ' chờ GPB)')
          : ('Đạt ngưỡng (≥ ' + targetTxt + ')')
      };
    }
    return {
      tone: 'urgent',
      label: pendingGpb > 0
        ? ('Chưa đạt ngưỡng < ' + targetTxt + ' (' + pendingGpb + ' chờ GPB)')
        : ('Chưa đạt ngưỡng (< ' + targetTxt + ')')
    };
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
      return { tone: 'urgent', label: 'Có biến cố PEP mức độ nặng (' + pepSevereNum + ' ca)' };
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

  function renderCasesView() {
    const summaryEl = byId('el-cases-summary');
    const listEl = byId('el-case-list');
    if (!summaryEl || !listEl) return;

    const all = state.cases;
    const urgentCount = all.filter((c) => c.clinical_badge && c.clinical_badge.tone === 'urgent').length;
    const pendingGpbCount = all.filter((c) => c.pathology_completion_status === 'PENDING' || c.pathology_completion_status === 'PARTIAL').length;
    const window30dCount = all.filter((c) => c.followup_30d_status === 'PENDING_WINDOW').length;

    summaryEl.innerHTML = [
      { label: 'Tổng ca đang quản lý', value: all.length, sub: 'EGD: ' + all.filter((x) => x.track === 'EGD').length + ' · COL: ' + all.filter((x) => x.track === 'COL').length + ' · ERCP: ' + all.filter((x) => x.track === 'ERCP').length },
      { label: 'Cảnh báo Ngoại & biến cố', value: urgentCount, sub: 'Ưu tiên xử trí hội chẩn & theo dõi sát' },
      { label: 'Hồ sơ đang chờ GPB', value: pendingGpbCount, sub: 'Mở trực tiếp Pha 4 ngay khi có kết quả' },
      { label: 'Trong cửa sổ 14–30 ngày', value: window30dCount, sub: 'Theo dõi biến cố muộn sau thủ thuật' }
    ].map((s) => (
      '<article class="el-stat-card">' +
      '<p class="el-stat-label">' + escapeHtml(s.label) + '</p>' +
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
      const surv = r.surveillance || {};
      const pat = r.patient || {};
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
        renderProcChip(r.track) +
        '<span class="el-case-code">' + escapeHtml(r.case_code) + '</span>' +
        '<span class="el-case-meta">Ngày soi gốc: ' + escapeHtml(formatViDate(r.procedure_date)) + '</span>' +
        '</div>' +
        renderStatusBadge(urg.tone, humanizeClinicalBadgeLabelVi(urg.label)) +
        '</div>' +
        '<div class="el-case-grid">' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Người bệnh &amp; bệnh cảnh gốc</p>' +
        '<p class="el-field-primary">' + escapeHtml(pat.privacy_initials || '') + ' · ' + escapeHtml(pat.age) + ' tuổi (' + escapeHtml(sexLabel) + ')</p>' +
        '<p class="el-field-secondary">' + escapeHtml(formatIndicationVi(r.indication_detail, '')) + '</p>' +
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
        '<p class="el-field-muted">Trạng thái vòng lặp: ' + escapeHtml(surv.fulfilled_by_case_id ? 'Đã soi lại & liên kết ca mới' : 'Đang mở theo dõi dọc') + '</p>' +
        '</div>' +
        '</div>' +
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
    const cirBadge = evaluateKpiRateBadge(k.cir);
    const bbpsBadge = evaluateKpiRateBadge(k.bbps_adequate);
    const adrBadge = evaluateKpiRateBadge(k.adr);
    const ssldrBadge = evaluateKpiRateBadge(k.ssldr);
    const ercpBadge = evaluateKpiRateBadge(k.ercp_native_cannulation);
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
        note: 'PEP sau ERCP: ' + k.ercp_pep.numerator + '/' + k.ercp_pep.completed_fu_denominator + ' ca · ' + aeNoteTail,
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

  /* Dọn sạch toàn diện state, bộ lọc, biểu đồ, ô tìm kiếm, timer & DOM ca bệnh (B02) */
  function wipeClinicalDomAndShowLogin(bannerMessage) {
    bumpSessionEpoch(false);
    clearSessionTimers();

    state.user = null;
    state.activeView = 'cases';
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
      state.cusumPreset = (casesJson.settings && casesJson.settings.cusum_preset) || 'DEFAULT_90';
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
        sessionEpoch
      };
    }
  };

  document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    bootstrap();
  });
})();
