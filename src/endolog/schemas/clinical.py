"""Clinical domain models for 3-track gastrointestinal endoscopy (EGD, COL, ERCP)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TrackType = Literal["EGD", "COL", "ERCP"]
CareSettingType = Literal["INPATIENT", "OUTPATIENT"]
SexType = Literal["M", "F", "O"]

ColoIndicationType = Literal[
    "SCREENING",
    "DIAGNOSTIC",
    "ABNORMAL_FECAL_TEST",
    "SURVEILLANCE",
    "THERAPEUTIC",
    "IBD_EVAL",
    "GI_BLEEDING",
    "EARLY_CANCER_WORKUP",
    "BILIARY_STONE",
    "MALIGNANT_STRICTURE",
    "CHOLANGITIS",
    "BILIARY_PANCREATITIS",
    "STENT_EXCHANGE",
    "OTHER",
]

PathologyCompletionType = Literal["NOT_APPLICABLE", "PENDING", "PARTIAL", "COMPLETE"]
Followup30dStatusType = Literal[
    "PENDING_WINDOW",
    "COMPLETED_NO_AE",
    "COMPLETED_WITH_AE",
    "LOST_TO_FOLLOWUP",
]
TriStateType = Literal["YES", "NO", "PENDING_UNKNOWN"]
AgreeGradeType = Literal["NONE", "I", "II", "IIIa", "IIIb", "IVa", "IVb", "V"]
PepSeverityType = Literal["NONE", "MILD", "MODERATE", "SEVERE"]

PapillaStatusType = Literal[
    "NATIVE_INTACT",
    "PRIOR_SPHINCTEROTOMY",
    "PRIOR_STENT_IN_SITU",
    "SURGICAL_BILIARY_ENTERIC",
]


def compute_privacy_initials(full_name: str) -> str:
    tokens = [w for w in full_name.strip().split() if w]
    if not tokens:
        return "B.N"
    return ".".join(t[0].upper() for t in tokens[:4])


class IndexLesion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anatomical_site: str = ""
    size_mm: float | None = Field(default=None, ge=0, le=250)
    paris_class: str = ""
    surface_pattern: str = ""
    bleeding_source_type: Literal[
        "NONE",
        "VARICEAL_ESOPHAGEAL",
        "VARICEAL_GASTRIC",
        "NON_VARICEAL_ULCER",
        "NON_VARICEAL_OTHER",
    ] = "NONE"
    forrest_class: str = ""
    hemostasis_modality: str = ""
    hemostasis_initial_success: Literal["NA", "YES", "NO"] = "NA"
    biopsy_jar_count: int = Field(default=0, ge=0, le=20)
    resection_method: Literal[
        "NONE",
        "BIOPSY_ONLY",
        "COLD_SNARE",
        "HOT_SNARE",
        "EMR_EN_BLOC",
        "EMR_PIECEMEAL",
        "ESD",
        "HEMOSTASIS",
        "UNRESECTED_REFERRED",
    ] = "NONE"
    histology_type: Literal[
        "NONE",
        "INFLAMMATORY_BENIGN",
        "INTESTINAL_METAPLASIA",
        "HYPERPLASTIC",
        "TUBULAR_ADENOMA",
        "TUBULOVILLOUS_ADENOMA",
        "VILLOUS_ADENOMA",
        "SSL_NO_DYSPLASIA",
        "SSL_WITH_DYSPLASIA",
        "TSA",
        "LGD_VIENNA_C3",
        "HGD_VIENNA_C4",
        "ADENOCARCINOMA_INTRAMUCOSAL",
        "ADENOCARCINOMA_INVASIVE",
        "OTHER",
    ] = "NONE"
    dysplasia_grade: Literal["NONE", "LGD", "HGD", "INVASIVE"] = "NONE"
    margins_status: Literal["NA", "PENDING", "R0", "HM1_ONLY", "VM1_OR_R1", "RX_PIECEMEAL"] = "NA"
    sm_invasion_um: int | None = Field(default=None, ge=0, le=50000)
    lvi_status: Literal["NA", "NEGATIVE", "POSITIVE"] = "NA"
    differentiation: Literal["NA", "WELL_MOD", "POOR_UNDIFF"] = "NA"
    budding_grade: Literal["NA", "BD1", "BD2_BD3"] = "NA"


class WholeCasePolypSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    macroscopic_polyp_count: int = Field(default=0, ge=0, le=200)
    complete_resection_all_lesions: Literal[
        "NOT_APPLICABLE",
        "ALL_RESECTED_COMPLETELY",
        "INCOMPLETE_OR_UNRESECTED",
    ] = "NOT_APPLICABLE"
    any_piecemeal_ge_20mm: Literal["YES", "NO"] = "NO"
    any_confirmed_adenoma: TriStateType = "NO"
    confirmed_adenoma_count_bin: Literal["0", "1_2", "3_4", "5_10", "GT_10"] = "0"
    max_adenoma_size_mm: float | None = Field(default=None, ge=0, le=250)
    any_villous_or_hgd_any_lesion: TriStateType = "NO"
    any_hgd_any_lesion: TriStateType = "NO"
    any_confirmed_ssl: TriStateType = "NO"
    confirmed_ssl_count_bin: Literal["0", "1_2", "3_4", "GE_5"] = "0"
    max_ssl_size_mm: float | None = Field(default=None, ge=0, le=250)
    any_ssl_with_dysplasia_or_tsa: TriStateType = "NO"
    any_invasive_cancer_or_noncurative_feature: TriStateType = "NO"


class ErcpLabs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bili_total_mg_dl: float | None = None
    bili_direct_mg_dl: float | None = None
    ast_u_l: float | None = None
    alt_u_l: float | None = None
    ggt_u_l: float | None = None
    alp_u_l: float | None = None
    amylase_u_l: float | None = None
    lipase_u_l: float | None = None
    wbc_g_l: float | None = None
    crp_mg_l: float | None = None
    plt_g_l: float | None = None
    inr: float | None = None


class ErcpProcedureDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    history_flags: list[str] = Field(default_factory=list)
    altered_anatomy: Literal["NONE", "BILLROTH_II", "ROUX_EN_Y", "OTHER"] = "NONE"
    antithrombotic_status: str = "NONE"
    imaging_modality: str = "MRCP"
    imaging_cbd_mm: float | None = Field(default=None, ge=0, le=60)
    imaging_stone_count: int = Field(default=0, ge=0, le=50)
    imaging_stone_max_mm: float | None = Field(default=None, ge=0, le=60)
    stricture_site: str = ""
    labs: ErcpLabs = Field(default_factory=ErcpLabs)
    papilla_status: PapillaStatusType = "NATIVE_INTACT"
    duodenal_obstruction_or_altered: bool = False
    vater_papilla_type: Literal["1", "2", "3a", "3b", "4"] = "1"
    pad_diverticulum: bool = False
    target_duct: Literal["CBD", "PD", "BOTH"] = "CBD"
    selective_cannulation: Literal["SUCCESS", "FAILED"] = "SUCCESS"
    cannulation_contacts_count: int = Field(default=1, ge=0, le=50)
    cannulation_time_min: float = Field(default=2.0, ge=0, le=240)
    total_procedure_time_min: float = Field(default=25.0, ge=0, le=480)
    unintended_pd_count: int = Field(default=0, ge=0, le=20)
    cannulation_technique: str = "STANDARD_SPHINCTEROTOME_GUIDEWIRE"
    biliary_interventions: list[str] = Field(default_factory=list)
    pep_prophylaxis: list[str] = Field(default_factory=list)
    ercp_procedure_note: str = ""


class AdverseEventRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ae_id: str
    window: Literal["INTRAPROCEDURAL", "INPATIENT_EARLY", "DELAYED_30D"] = "INPATIENT_EARLY"
    event_type: Literal["PEP", "BLEEDING", "PERFORATION", "CHOLANGITIS", "CARDIOPULMONARY", "OTHER"] = "OTHER"
    pep_severity: PepSeverityType = "NONE"
    agree_grade: AgreeGradeType = "I"
    readmission_required: bool = False
    surgical_rescue_required: bool = False
    note: str = ""


class CaseCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Patient & Admission Episode linkage (OD-04)
    patient_uid: str | None = None
    confirm_outpatient_new_patient: bool = False
    full_name: str = Field(..., min_length=2, max_length=120)
    birth_year: int = Field(..., ge=1900, le=2026)
    sex: SexType = "M"
    hospital_mrn: str | None = Field(default=None, max_length=40)
    care_setting: CareSettingType = "OUTPATIENT"
    episode_id: str | None = None
    admission_date: str | None = None
    referring_dept: str = "Khoa Nội soi Tiêu hóa"
    prior_unrecorded_ercp_offset: int = Field(default=0, ge=0, le=20)

    # Core Case Phase 1..4 (non-blocking)
    track: TrackType
    procedure_start_at: str
    operator_name: str = "ThS. BSCKI. Nguyễn Bình An"
    indication: ColoIndicationType = "DIAGNOSTIC"
    indication_detail: str = ""
    has_ibd_or_polyposis: bool = False
    exclude_from_cir: bool = False
    bbps_right: int | None = Field(default=None, ge=0, le=3)
    bbps_transverse: int | None = Field(default=None, ge=0, le=3)
    bbps_left: int | None = Field(default=None, ge=0, le=3)
    cecal_intubation: Literal["NA", "YES", "NO"] = "NA"
    cecal_failure_reason: str = ""
    withdrawal_time_clean_min: float | None = Field(default=None, ge=0, le=180)
    pathology_completion_status: PathologyCompletionType = "NOT_APPLICABLE"
    followup_30d_status: Followup30dStatusType = "PENDING_WINDOW"
    clinician_followup_due_date: str | None = None
    clinician_followup_note: str = ""
    index_lesion: IndexLesion | None = None
    whole_case_summary: WholeCasePolypSummary | None = None
    ercp_detail: ErcpProcedureDetail | None = None
    adverse_events: list[AdverseEventRecord] = Field(default_factory=list)
    clinical_note: str = ""

    @model_validator(mode="after")
    def validate_clinical_invariants(self) -> "CaseCreateRequest":
        if self.care_setting == "INPATIENT" and not (self.hospital_mrn or "").strip():
            raise ValueError("OD-04: Ca nội trú (INPATIENT) bắt buộc nhập mã hồ sơ bệnh viện (hospital_mrn).")
        if self.track == "COL":
            if self.cecal_intubation == "NA":
                self.cecal_intubation = "YES"
            if self.whole_case_summary is None:
                self.whole_case_summary = WholeCasePolypSummary()
        if self.track == "ERCP" and self.ercp_detail is None:
            self.ercp_detail = ErcpProcedureDetail()
        return self


class CasePhasePatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(..., ge=1)
    pathology_completion_status: PathologyCompletionType | None = None
    followup_30d_status: Followup30dStatusType | None = None
    clinician_followup_due_date: str | None = None
    clinician_followup_note: str | None = None
    bbps_right: int | None = Field(default=None, ge=0, le=3)
    bbps_transverse: int | None = Field(default=None, ge=0, le=3)
    bbps_left: int | None = Field(default=None, ge=0, le=3)
    cecal_intubation: Literal["NA", "YES", "NO"] | None = None
    withdrawal_time_clean_min: float | None = Field(default=None, ge=0, le=180)
    index_lesion: IndexLesion | None = None
    whole_case_summary: WholeCasePolypSummary | None = None
    ercp_detail: ErcpProcedureDetail | None = None
    adverse_events: list[AdverseEventRecord] | None = None
    clinical_note: str | None = None
    fulfill_surveillance_rec_id: str | None = None
