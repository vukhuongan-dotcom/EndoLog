/* EndoLog Frontend Controller v1 — Zero-PHI 5-Layer Browser Compliance & Brand v1
 * - 0 mã màu hex cứng ngoài tokens.css; 0 emoji; 0 token/PHI trong localStorage/sessionStorage/IndexedDB.
 * - Mặc định nền SÁNG; nền TỐI chỉ bật qua [data-theme="dark"] khi người dùng chủ động chọn. */

(function () {
  'use strict';

  const THEME_STORAGE_KEY = 'endolog_theme';
  const TAB_SESSION_KEY = 'endolog_active_view';

  const state = {
    user: null,
    activeView: 'cases',
    trackFilter: 'ALL',
    survFilter: 'ALL',
    searchQuery: '',
    adrMinAge: 45,
    cusumMetric: 'CIR',
    cases: [],
    surveillanceRows: [],
    kpiBundle: null,
    cusumData: null,
    auditStatus: null,
    idleTimer: null
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
    if (val == null || Number.isNaN(Number(val))) return '—';
    return Number(val).toFixed(1).replace('.', ',') + '%';
  }

  function formatViNum(val) {
    if (val == null || Number.isNaN(Number(val))) return '—';
    return String(val).replace('.', ',');
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

  function initTheme() {
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
      const lesionLine = count === 0
        ? ('Không phát hiện polyp · Rút ống sạch ' + formatViNum(c.withdrawal_time_clean_min) + ' phút')
        : ('Toàn ca ' + count + ' polyp · Đại diện: ' + (idx.anatomical_site || 'Đại tràng') + ' ' + formatViNum(idx.size_mm) + ' mm (' + (idx.paris_class || '') + ')');
      return { title: bbpsTxt + ' · ' + cecalTxt, detail: lesionLine };
    }
    if (c.track === 'EGD') {
      if (idx.resection_method === 'HEMOSTASIS') {
        return {
          title: (idx.anatomical_site || 'Thực quản — dạ dày') + ' · ' + (idx.hemostasis_modality || 'Can thiệp cầm máu'),
          detail: 'Cầm máu ban đầu: ' + (idx.hemostasis_initial_success === 'YES' ? 'Đạt hoàn toàn' : 'Cần theo dõi sát')
        };
      }
      return {
        title: (idx.anatomical_site || 'Dạ dày') + ' · ' + (idx.paris_class || '') + ' (' + formatViNum(idx.size_mm) + ' mm)',
        detail: 'Sinh thiết kìm ' + (idx.biopsy_jar_count || 0) + ' mảnh · Mô học: ' + (idx.histology_type === 'ADENOCARCINOMA_INVASIVE' ? 'Ung thư biểu mô tuyến xâm lấn' : idx.histology_type)
      };
    }
    const er = c.ercp_computed || c.ercp_detail || {};
    const diffTxt = er.difficult_cannulation_esge2016 === 'YES'
      ? ('Thông nhú khó ESGE 2016 (' + er.cannulation_contacts_count + ' chạm, ' + formatViNum(er.cannulation_time_min) + ' phút, ' + er.unintended_pd_count + ' lần ống tụy)')
      : 'Thông nhú thuận lợi';
    return {
      title: 'Lần ERCP thứ ' + (er.ercp_session_index_in_episode || 1) + ' trong đợt · Nhú nguyên vẹn Type ' + (er.vater_papilla_type || '1') + (er.pad_diverticulum ? ' + túi thừa cạnh nhú' : ''),
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
        c.indication_detail,
        c.clinical_note
      ].join(' ').toLowerCase();
      return hay.includes(q);
    });

    listEl.innerHTML = filtered.map((c) => {
      const hl = describeTrackClinicalHighlights(c);
      const surv = c.surveillance || {};
      const pat = c.patient || {};
      const settingLabel = c.care_setting === 'INPATIENT' ? 'Nội trú' : 'Ngoại trú';
      const sexLabel = pat.sex === 'F' ? 'Nữ' : 'Nam';
      const mrnPart = pat.hospital_mrn_masked ? (' · Mã HS: ' + pat.hospital_mrn_masked) : '';
      const survSummary = surv.category === 'SURGICAL_MDT_CONSULT_ALERT'
        ? ('Chuyển hội chẩn ' + (surv.surgical_consult_target_dept || 'Ngoại khoa'))
        : ('Hẹn soi lại: ' + (surv.recommended_interval_label || 'Theo chỉ định') + (surv.due_date ? (' (' + formatViDate(surv.due_date) + ')') : ''));

      return (
        '<article class="el-case-card">' +
        '<div class="el-case-top">' +
        '<div class="el-case-id-group">' +
        renderProcChip(c.track) +
        '<span class="el-case-code">' + escapeHtml(c.case_code) + '</span>' +
        '<span class="el-case-meta">' + escapeHtml(formatViDate(c.procedure_start_at)) + ' · ' + escapeHtml(settingLabel) + '</span>' +
        '</div>' +
        renderStatusBadge(c.clinical_badge.tone, c.clinical_badge.label) +
        '</div>' +
        '<div class="el-case-grid">' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Người bệnh &amp; chỉ định</p>' +
        '<p class="el-field-primary">' + escapeHtml(pat.privacy_initials || '') + ' · ' + escapeHtml(pat.age) + ' tuổi (' + escapeHtml(sexLabel) + ')' + escapeHtml(mrnPart) + '</p>' +
        '<p class="el-field-secondary">' + escapeHtml(c.indication_detail || c.indication) + '</p>' +
        '</div>' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Thông số kỹ thuật &amp; tổn thương đại diện</p>' +
        '<p class="el-field-primary">' + escapeHtml(hl.title) + '</p>' +
        '<p class="el-field-secondary">' + escapeHtml(hl.detail) + '</p>' +
        '</div>' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Giải phẫu bệnh &amp; hướng xử trí</p>' +
        '<p class="el-field-primary">' + escapeHtml(survSummary) + '</p>' +
        '<p class="el-field-muted">' + escapeHtml(surv.guideline_id || '') + (surv.is_divergent_guideline ? (' · Đối chiếu ESGE 2020: ' + surv.reference_interval_label) : '') + '</p>' +
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
      const sexLabel = pat.sex === 'F' ? 'Nữ' : 'Nam';
      const primaryPlan = surv.category === 'SURGICAL_MDT_CONSULT_ALERT'
        ? ('Hội chẩn chuyên khoa: ' + (surv.surgical_consult_target_dept || 'Ngoại khoa'))
        : ('Mốc hẹn soi lại: ' + (surv.recommended_interval_label || 'Theo chỉ định') + (surv.due_date ? (' · Ngày dự kiến ' + formatViDate(surv.due_date)) : ''));

      const divergenceHtml = surv.is_divergent_guideline
        ? (
          '<div class="el-guideline-box">' +
          '<div><strong>Khuyến cáo chính (' + escapeHtml(surv.guideline_id) + '):</strong> ' + escapeHtml(surv.recommended_interval_label) + '</div>' +
          '<div class="el-guideline-ref">Tham chiếu song song (' + escapeHtml(surv.reference_guideline_id) + '): ' + escapeHtml(surv.reference_interval_label) + '</div>' +
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
        renderStatusBadge(r.urgency.tone, r.urgency.label) +
        '</div>' +
        '<div class="el-case-grid">' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Người bệnh &amp; bệnh cảnh gốc</p>' +
        '<p class="el-field-primary">' + escapeHtml(pat.privacy_initials || '') + ' · ' + escapeHtml(pat.age) + ' tuổi (' + escapeHtml(sexLabel) + ')</p>' +
        '<p class="el-field-secondary">' + escapeHtml(r.indication_detail || '') + '</p>' +
        '</div>' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Quyết định hẹn soi lại / hội chẩn</p>' +
        '<p class="el-field-primary">' + escapeHtml(primaryPlan) + '</p>' +
        '<p class="el-field-secondary">' + escapeHtml(surv.reason || '') + '</p>' +
        divergenceHtml +
        '</div>' +
        '<div class="el-case-col">' +
        '<p class="el-field-kicker">Nguồn hướng dẫn áp dụng</p>' +
        '<p class="el-field-primary">' + escapeHtml(surv.guideline_id || '') + '</p>' +
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
    const width = 760;
    const height = 210;
    const padL = 48;
    const padR = 24;
    const padT = 22;
    const padB = 34;
    const plotW = width - padL - padR;
    const plotH = height - padT - padB;
    const yMax = Math.max(3.4, h * 1.18, ...cusum.trajectory);

    function xPos(i) {
      const n = Math.max(1, pts.length);
      return padL + (i / n) * plotW;
    }
    function yPos(val) {
      return padT + plotH - (Math.min(val, yMax) / yMax) * plotH;
    }

    const polyPoints = cusum.trajectory.map((v, idx) => xPos(idx).toFixed(1) + ',' + yPos(v).toFixed(1)).join(' ');
    const yThresh = yPos(h).toFixed(1);
    const yZero = yPos(0).toFixed(1);
    const yMid = yPos(h / 2).toFixed(1);

    const circles = cusum.trajectory.map((v, idx) => {
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
    const cards = [
      {
        title: 'Luồn tới manh tràng (CIR)',
        chip: 'COL',
        rate: formatViPct(k.cir.rate_pct),
        frac: k.cir.numerator + ' / ' + k.cir.denominator + ' ca mục tiêu toàn bộ khung đại tràng',
        note: 'Chuẩn tham chiếu ≥ 90% (tầm soát ≥ 95%)',
        badge: renderStatusBadge('ned', 'Đạt chuẩn')
      },
      {
        title: 'Chuẩn bị đại tràng đạt (BBPS)',
        chip: 'COL',
        rate: formatViPct(k.bbps_adequate.rate_pct),
        frac: k.bbps_adequate.numerator + ' / ' + k.bbps_adequate.denominator + ' ca chấm đủ 3 đoạn',
        note: 'Yêu cầu tổng BBPS ≥ 6 và mỗi đoạn đại tràng ≥ 2',
        badge: renderStatusBadge('ned', 'Đạt chuẩn')
      },
      {
        title: 'Phát hiện u tuyến (ADR ≥ ' + k.min_adr_age + ' tuổi)',
        chip: 'COL',
        rate: formatViPct(k.adr.rate_pct),
        frac: k.adr.numerator + ' / ' + k.adr.denominator + ' ca tầm soát / chẩn đoán đã có GPB',
        note: 'Tách khỏi mẫu số: ' + k.adr.pending_gpb_excluded_count + ' ca chờ GPB · Chuẩn ASGE/ACG ≥ 35%',
        badge: renderStatusBadge('ned', 'Tách bạch GPB')
      },
      {
        title: 'Polyp răng cưa không cuống (SSLDR)',
        chip: 'COL',
        rate: formatViPct(k.ssldr.rate_pct),
        frac: k.ssldr.numerator + ' / ' + k.ssldr.denominator + ' ca đã xác nhận mô bệnh học',
        note: 'Phát hiện đại thể PDR cùng đoàn hệ: ' + formatViPct(k.pdr.rate_pct) + ' (' + k.pdr.numerator + '/' + k.pdr.denominator + ')',
        badge: renderStatusBadge('ned', 'Đạt chuẩn')
      },
      {
        title: 'Thông nhú chọn lọc nhú nguyên vẹn',
        chip: 'ERCP',
        rate: formatViPct(k.ercp_native_cannulation.rate_pct),
        frac: k.ercp_native_cannulation.numerator + ' / ' + k.ercp_native_cannulation.denominator + ' ca nhú Vater nguyên vẹn',
        note: 'Thông nhú khó theo ESGE 2016: ' + k.ercp_native_cannulation.difficult_esge2016_count + ' ca · Chuẩn ≥ 90%',
        badge: renderStatusBadge('ned', 'Đạt chuẩn')
      },
      {
        title: 'Biến cố hoàn tất theo dõi 30 ngày',
        chips: ['EGD', 'COL', 'ERCP'],
        rate: formatViPct(k.adverse_events_all.agree_severe_rate_pct),
        frac: 'AGREE ≥ III: ' + k.adverse_events_all.agree_severe_numerator + ' / ' + k.adverse_events_all.completed_fu_denominator + ' ca hoàn tất theo dõi',
        note: 'PEP sau ERCP: ' + k.ercp_pep.numerator + '/' + k.ercp_pep.completed_fu_denominator + ' ca · Đang trong cửa sổ 30 ngày tách riêng: ' + k.adverse_events_all.missing_or_pending_fu_count + ' ca',
        badge: renderStatusBadge(
          k.adverse_events_all.missing_or_pending_fu_count > 0 ? 'due' : 'ned',
          k.adverse_events_all.missing_or_pending_fu_count + ' ca chờ hết cửa sổ'
        )
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
      discEl.textContent = activeCusum.disclaimer_vi + ' (RA-CUSUM: ' + activeCusum.ra_cusum_status + ').';
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

  function switchView(viewName) {
    const allowed = ['cases', 'surveillance', 'quality'];
    const target = allowed.includes(viewName) ? viewName : 'cases';
    state.activeView = target;
    try {
      window.sessionStorage.setItem(TAB_SESSION_KEY, target);
    } catch (_err) {
      /* ignore */
    }

    byId('el-view-cases').hidden = target !== 'cases';
    byId('el-view-surveillance').hidden = target !== 'surveillance';
    byId('el-view-quality').hidden = target !== 'quality';

    document.querySelectorAll('[data-nav-target]').forEach((btn) => {
      const active = btn.getAttribute('data-nav-target') === target;
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
  }

  async function apiFetch(path, options) {
    const resp = await fetch(path, Object.assign({ credentials: 'same-origin' }, options || {}));
    if (resp.status === 401) {
      wipeClinicalDomAndShowLogin();
      throw new Error('UNAUTHENTICATED');
    }
    return resp;
  }

  function wipeClinicalDomAndShowLogin() {
    state.user = null;
    state.cases = [];
    state.surveillanceRows = [];
    state.kpiBundle = null;
    ['el-case-list', 'el-cases-summary', 'el-surveillance-list', 'el-kpi-grid', 'el-cusum-container', 'el-audit-strip'].forEach((id) => {
      const node = byId(id);
      if (node) node.replaceChildren();
    });
    byId('el-app-shell').hidden = true;
    byId('el-login-screen').hidden = false;
  }

  function resetIdleTimer() {
    if (state.idleTimer) window.clearTimeout(state.idleTimer);
    if (!state.user) return;
    state.idleTimer = window.setTimeout(async () => {
      try {
        await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
      } catch (_err) {
        /* ignore */
      }
      try {
        window.sessionStorage.clear();
      } catch (_err) {
        /* ignore */
      }
      wipeClinicalDomAndShowLogin();
    }, 15 * 60 * 1000);
  }

  async function loadAllClinicalViews() {
    const [casesResp, survResp, kpiResp, auditResp] = await Promise.all([
      apiFetch('/api/cases'),
      apiFetch('/api/surveillance'),
      apiFetch('/api/metrics/kpi?min_adr_age=' + encodeURIComponent(state.adrMinAge)),
      apiFetch('/api/audit/verify')
    ]);
    const casesJson = await casesResp.json();
    const survJson = await survResp.json();
    state.cases = casesJson.items || [];
    state.surveillanceRows = survJson.items || [];
    state.kpiBundle = await kpiResp.json();
    state.auditStatus = await auditResp.json();

    renderCasesView();
    renderSurveillanceView();
    renderQualityView();
  }

  function enterAuthenticatedShell(userObj) {
    state.user = userObj;
    byId('el-user-name').textContent = userObj.display_name || 'ThS. BSCKI. Nguyễn Bình An';
    byId('el-user-dept').textContent = userObj.department || 'Khoa Nội soi Tiêu hóa — Bệnh viện Bình Dân';
    byId('el-login-screen').hidden = true;
    byId('el-app-shell').hidden = false;

    const params = new URLSearchParams(window.location.search);
    const urlView = params.get('view');
    let savedTab = 'cases';
    try {
      savedTab = window.sessionStorage.getItem(TAB_SESSION_KEY) || 'cases';
    } catch (_err) {
      savedTab = 'cases';
    }
    switchView(urlView || savedTab);
    resetIdleTimer();
  }

  async function bootstrap() {
    initTheme();

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
          enterAuthenticatedShell(meData.user);
          await loadAllClinicalViews();
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
            enterAuthenticatedShell(bpData.user);
            await loadAllClinicalViews();
            return;
          }
        }
      }
    } catch (_err) {
      /* fall through to login screen */
    }

    wipeClinicalDomAndShowLogin();
  }

  function bindEvents() {
    byId('el-theme-toggle').addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
      applyTheme(cur === 'dark' ? 'light' : 'dark', true);
    });

    document.querySelectorAll('[data-nav-target]').forEach((btn) => {
      btn.addEventListener('click', () => switchView(btn.getAttribute('data-nav-target')));
    });

    document.querySelectorAll('[data-track-filter]').forEach((pill) => {
      pill.addEventListener('click', () => {
        state.trackFilter = pill.getAttribute('data-track-filter') || 'ALL';
        document.querySelectorAll('[data-track-filter]').forEach((p) => {
          p.setAttribute('aria-pressed', p === pill ? 'true' : 'false');
        });
        renderCasesView();
      });
    });

    document.querySelectorAll('[data-surv-filter]').forEach((pill) => {
      pill.addEventListener('click', () => {
        state.survFilter = pill.getAttribute('data-surv-filter') || 'ALL';
        document.querySelectorAll('[data-surv-filter]').forEach((p) => {
          p.setAttribute('aria-pressed', p === pill ? 'true' : 'false');
        });
        renderSurveillanceView();
      });
    });

    document.querySelectorAll('[data-age-toggle]').forEach((pill) => {
      pill.addEventListener('click', async () => {
        state.adrMinAge = Number(pill.getAttribute('data-age-toggle')) || 45;
        document.querySelectorAll('[data-age-toggle]').forEach((p) => {
          p.setAttribute('aria-pressed', p === pill ? 'true' : 'false');
        });
        const resp = await apiFetch('/api/metrics/kpi?min_adr_age=' + encodeURIComponent(state.adrMinAge));
        state.kpiBundle = await resp.json();
        renderQualityView();
      });
    });

    document.querySelectorAll('[data-cusum-metric]').forEach((pill) => {
      pill.addEventListener('click', async () => {
        state.cusumMetric = pill.getAttribute('data-cusum-metric') || 'CIR';
        document.querySelectorAll('[data-cusum-metric]').forEach((p) => {
          p.setAttribute('aria-pressed', p === pill ? 'true' : 'false');
        });
        const resp = await apiFetch('/api/metrics/cusum?metric=' + encodeURIComponent(state.cusumMetric) + '&preset=DEFAULT_90');
        state.cusumData = await resp.json();
        renderQualityView();
      });
    });

    const searchInput = byId('el-case-search');
    if (searchInput) {
      searchInput.addEventListener('input', () => {
        state.searchQuery = searchInput.value || '';
        renderCasesView();
      });
    }

    const exportBtn = byId('el-btn-export-csv');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => {
        window.location.href = '/api/exports/profile-b?fmt=csv';
      });
    }

    byId('el-btn-logout').addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' });
      try {
        window.sessionStorage.clear();
      } catch (_err) {
        /* ignore */
      }
      wipeClinicalDomAndShowLogin();
    });

    byId('el-login-form').addEventListener('submit', async (ev) => {
      ev.preventDefault();
      const errEl = byId('el-login-error');
      errEl.hidden = true;
      const username = byId('el-login-username').value.trim();
      const password = byId('el-login-password').value;
      const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ username, password })
      });
      if (!resp.ok) {
        errEl.textContent = 'Tên đăng nhập hoặc mật khẩu không đúng.';
        errEl.hidden = false;
        return;
      }
      const data = await resp.json();
      enterAuthenticatedShell(data.user);
      await loadAllClinicalViews();
    });

    byId('el-btn-dev-bypass').addEventListener('click', async () => {
      const resp = await fetch('/api/auth/local-bypass', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ target_username: 'nguyenbinhan' })
      });
      if (resp.ok) {
        const data = await resp.json();
        enterAuthenticatedShell(data.user);
        await loadAllClinicalViews();
      }
    });

    ['click', 'keydown', 'pointerdown'].forEach((evtName) => {
      window.addEventListener(evtName, resetIdleTimer, { passive: true });
    });

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    bootstrap();
  });
})();
