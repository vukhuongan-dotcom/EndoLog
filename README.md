# EndoLog — Gastrointestinal Endoscopy Registry & Quality Platform
## Dự Án: Hệ Thống Sổ Bộ Lâm Sàng & Đánh Giá Chất Lượng Nội Soi Tiêu Hóa
### Đơn vị công tác: Khoa Nội soi Tiêu hóa — Bệnh viện Bình Dân
### Nguồn tham chiếu: [version.md](version.md) (SSoT Phiên bản) • [AGENTS.md](AGENTS.md) (Quy chuẩn dự án) • [BUG_FIX_REGISTRY.md](docs/BUG_FIX_REGISTRY.md) (Sổ lỗi & Tính năng)

**Trạng thái Khởi tạo:** `DAY-0 SCAFFOLD SPECIFICATION (Rule v2:R47)` — **ZERO-PHI & ZERO-IMAGE DESIGN**  
**Superadmin & Quản trị kỹ thuật:** **BSCKII. Vũ Khương An — Bệnh viện Bình Dân**  
**Người dùng chính (`Primary Endoscopist`):** **ThS. BSCKI. Nguyễn Bình An — Khoa Nội soi Tiêu hóa, Bệnh viện Bình Dân**

> [!IMPORTANT]
> **NGUYÊN TẮC BẢO VỆ DỮ LIỆU & PHÂN TÁCH QUYỀN HẠN (`CLEAN-ROOM PROTOCOL`):**
> 1. **Định hướng bảo vệ dữ liệu cá nhân y tế:** Thiết kế bám sát yêu cầu bảo vệ dữ liệu cá nhân của Luật Khám bệnh, chữa bệnh số 15/2023/QH15, Luật Bảo vệ Dữ liệu Cá nhân số 91/2025/QH15 và Nghị định số 356/2025/NĐ-CP. Thư mục dữ liệu (`data*/`) bị loại trừ khỏi Git qua `.gitignore` và kiểm soát cache trình duyệt ở cả 5 tầng.
> 2. **Không lưu trữ hình ảnh nội soi:** Hệ thống chỉ lưu trữ dữ liệu biến số cấu trúc, không tải lên hay lưu trữ ảnh chụp hoặc video nội soi người bệnh.
> 3. **Phân tách 3 cổng phê duyệt độc lập (`Rule v2:R47` & `Rule v2:R01`):** Khởi tạo bộ khung (Gate A), Phát triển mã nguồn tính năng (Gate B) và Triển khai máy chủ (Gate C) yêu cầu phê duyệt riêng biệt ở từng cổng.

---

## 1. Cấu Trúc Thư Mục Chuẩn Hóa (Profile `webapp` — ISO 15489-1:2016)

```text
endolog/
├── AGENTS.md                                      # Quy chuẩn kỹ thuật, môi trường fail-closed & bảo mật cục bộ (CLS-03)
├── README.md                                      # Tổng quan dự án & kiến trúc (CLS-02)
├── version.md                                     # Lịch sử phiên bản SemVer 2.0.0 (CLS-07)
├── .gitignore                                     # Chốt chặn bảo vệ dữ liệu lâm sàng & khóa bí mật
├── PROJECT_CONTEXT/                               # Bộ não tri thức dự án (SSoT Brain — CLS-02/07)
│   ├── CONTEXT.md                                 # Hợp đồng đặc tả nghiệp vụ & dữ liệu sau Crosscheck vòng 1
│   ├── FILE_CLASSIFICATION_MATRIX.md              # Ma trận phân loại tệp ISO 15489-1:2016
│   └── BANG_TONG_HOP_LOI_VA_KHAC_PHUC.md          # Sổ lỗi & tính năng SSoT #2 (Schema v3.1)
├── docs/                                          # Tài liệu kỹ thuật & kiểm toán (CLS-02/06/07)
│   ├── file_classification_matrix.md              # Ma trận phân loại tệp bản repo
│   ├── BUG_FIX_REGISTRY.md                        # Sổ lỗi & tính năng SSoT #1 (Schema v3.1)
│   └── [scaffolding_receipt.md]                   # (Chỉ sinh ra ở State 4 sau khi tạo thật và kiểm tra SHA-256)
├── src/                                           # Mã nguồn ứng dụng Backend & PWA `src/endolog/` (trống ở bước Scaffold)
├── scripts/                                       # Công cụ kiểm tra SSoT & bảo trì an toàn (trống ở bước Scaffold)
├── tests/                                         # Bộ kiểm thử tự động cô lập sandbox (trống ở bước Scaffold)
├── data/                                          # [Git-Ignored] Lưu trữ AtomicJsonStore cục bộ (CLS-04)
└── data_backups/                                  # [Git-Ignored] Bản chụp sao lưu tự động (CLS-04)
```
