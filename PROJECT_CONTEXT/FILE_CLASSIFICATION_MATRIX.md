# BẢNG MA TRẬN PHÂN LOẠI TỆP TIN DỰ ÁN (FILE CLASSIFICATION MATRIX)
**Dự án:** EndoLog (`endolog`) — Sổ Bộ Lâm Sàng & Đánh Giá Chất Lượng Nội Soi Tiêu Hóa (Bệnh viện Bình Dân)  
**Phiên bản:** 1.3 (Gate B — Phase 1–5 Completed Locally · v0.2.0)  
**Tiêu chuẩn tham khảo:** ISO 15489-1:2016 Records Management (§8.3 Business Classification System & §9.4 Classification and Indexing)  
**Căn cứ pháp lý tham chiếu:** Luật Khám bệnh, chữa bệnh số 15/2023/QH15, Luật Bảo vệ Dữ liệu Cá nhân số 91/2025/QH15, Nghị định số 356/2025/NĐ-CP

---

## 📊 1. MA TRẬN PHÂN LOẠI TỆP TIN (FILE TAXONOMY MATRIX)

| Mã Nhóm | Phân Loại Nghiệp Vụ | Định Dạng Cho Phép | Thư Mục Bắt Buộc | Điểm Đến Lưu Trữ & Chính Sách Git | Mức Độ Bảo Mật & Quyền Hạn |
|:---:|---|---|---|---|:---:|
| **CLS-01** | **Mã nguồn Backend, Giao diện PWA (`src/endolog/static/`), Công cụ kiểm toán (`tools/`) & Scripts** | `.py`, `.js`, `.html`, `.css`, `.json`, `.sh`, `.svg`, `.png`, `.woff2` | `src/`, `scripts/`, `tools/`, `tests/` | `CODE_REPOSITORY` — Git Versioned (chỉ chứa icon PWA tự host, 0 ảnh lâm sàng) | Nội bộ (Internal) |
| **CLS-02** | **Đặc tả, Kiến trúc & Bộ nhận diện thương hiệu (`docs/brand/`)** | `.md`, `.json`, `.yaml`, `.mmd`, `.svg`, `.png`, `.txt`, `.py` | `PROJECT_CONTEXT/`, `docs/` | `CODE_REPOSITORY` — Git Versioned (SSoT Brain & Brand Identity v1) | Nội bộ (Internal) |
| **CLS-03** | **Quy tắc nội bộ dự án** | `AGENTS.md` | Thư mục gốc (`project_root/`) | `CODE_REPOSITORY` — Git Versioned (Tự nạp tự động) | Nội bộ (Internal) |
| **CLS-04** | **Dữ liệu lâm sàng nội soi (Raw PHI — Không lưu ảnh)** | `.json` | `data/`, `data_real_clinical/`, `data_synthetic_dev/`, `data_backups/` | `LOCAL_SANDBOX` — **BẮT BUỘC nằm trong `.gitignore`**. Cấm commit Git/Git LFS hay đẩy lên Cloud công cộng. | **Tuyệt mật (Strict Zero-PHI)** |
| **CLS-05** | **Dữ liệu nghiên cứu giả danh hóa dọc (Profile B) & Thống kê gộp (Profile C)** | `.csv`, `.xlsx`, `.json` | `data/exports_research/` | **Mặc định `LOCAL_SANDBOX`** (nằm trong `.gitignore`). Chỉ xuất theo hợp đồng EndoLog Export Contract v1.0. | Hạn chế (Restricted) |
| **CLS-06** | **Tài liệu hành chính & Hướng dẫn** | `.docx`, `.pdf`, `.pptx`, `.md` | `docs/` | `CODE_REPOSITORY` hoặc hạ tầng lưu trữ được phê duyệt. Văn bản hành chính tuân thủ Nghị định 30/2020/NĐ-CP (`Rule v2:R43`). | Hạn chế (Restricted) |
| **CLS-07** | **Sổ theo dõi sự cố, Tính năng & Lịch sử phiên bản** | `.md` | `docs/BUG_FIX_REGISTRY.md`, `PROJECT_CONTEXT/BANG_TONG_HOP_LOI_VA_KHAC_PHUC.md` & `version.md` | `CODE_REPOSITORY` — Git Versioned theo `Rule v2:R45` & `Rule v2:R47`. Cập nhật đồng bộ khi có bằng chứng xác minh thật. | Nội bộ (Internal) |

---

## 🔒 2. CHÍNH SÁCH CÔ LẬP DỮ LIỆU DEV SYNTHETIC VÀ DỮ LIỆU THẬT
1. **`LOCAL_SANDBOX` tách đôi vật lý khi phát triển:** Dữ liệu giả lập cho phát triển/Playwright đặt tại `data_synthetic_dev/`; dữ liệu lâm sàng thật đặt tại `data_real_clinical/` (hoặc `data/` kèm `.phi_vault_marker`, phân quyền `0700`/`0600`). Cả hai đều bị chặn bởi `.gitignore` và tuyệt đối không dùng chung tiến trình bật dev auth-bypass.
2. **`HOSPITAL_SECURE_STORAGE`:** Hạ tầng triển khai nội bộ / VPS bảo mật phục vụ sổ bộ cá nhân của `ThS. BSCKI. Nguyễn Bình An` dưới quyền quản trị kỹ thuật của `BSCKII. Vũ Khương An`, chỉ triển khai khi có phê duyệt tường minh tại Gate C (`Rule v2:R01`).
3. **`CODE_REPOSITORY`:** Kho mã nguồn Git của dự án `endolog`, chỉ chứa mã nguồn, bộ nhận diện thương hiệu (`docs/brand/`), dữ liệu kiểm thử tổng hợp (synthetic fixtures) và tài liệu không chứa thông tin định danh người bệnh.

---

## 🚫 3. QUY ĐỊNH VỀ TỆP TIN Ở THƯ MỤC GỐC (ROOT HYGIENE)
* Thư mục gốc (`project_root/`) chỉ được phép chứa các tệp tin quản trị hệ thống chuẩn: `AGENTS.md`, `README.md`, `version.md`, `.gitignore`, và tệp cấu hình môi trường lập trình (`pyproject.toml` / `requirements.txt`, `pytest.ini`, `package.json` khi bước sang giai đoạn phát triển tính năng được duyệt riêng ở Gate B).
* **Nghiêm cấm tuyệt đối:** Cấm tạo thư mục `app/`, `public/`, `database/` rời rạc ngoài `src/`; cấm đặt tệp dữ liệu (`.xlsx`, `.csv`, `.sqlite`, `.json` lâm sàng) ở thư mục gốc.
