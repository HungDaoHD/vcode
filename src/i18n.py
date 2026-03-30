# -*- coding: utf-8 -*-
"""
i18n.py — Internationalization cho vcode
Hỗ trợ: VI (Tiếng Việt), EN (English)
"""

TRANSLATIONS = {
    # ── App title ──────────────────────────────────────────────
    "app_title":        {"VI": "vcode",                         "EN": "vcode"},
    "app_subtitle":     {"VI": "Verbatim Coding Tool",          "EN": "Verbatim Coding Tool"},

    # ── Auth ───────────────────────────────────────────────────
    "login_title":          {"VI": "Đăng nhập",                 "EN": "Sign In"},
    "login_email_label":    {"VI": "Email công ty",             "EN": "Company Email"},
    "login_email_hint":     {"VI": "Chỉ chấp nhận email @asia-plus.net", "EN": "Only @asia-plus.net emails accepted"},
    "login_send_otp":       {"VI": "Gửi mã OTP",               "EN": "Send OTP"},
    "login_otp_title":      {"VI": "Nhập mã OTP",              "EN": "Enter OTP"},
    "login_otp_sent":       {"VI": "Mã OTP đã gửi đến",        "EN": "OTP sent to"},
    "login_otp_hint":       {"VI": "Hiệu lực 10 phút",         "EN": "Valid for 10 minutes"},
    "login_otp_label":      {"VI": "Mã OTP (6 chữ số)",        "EN": "OTP Code (6 digits)"},
    "login_otp_placeholder":{"VI": "123456",                    "EN": "123456"},
    "login_confirm":        {"VI": "Xác nhận",                  "EN": "Confirm"},
    "login_back":           {"VI": "← Quay lại",               "EN": "← Back"},
    "login_err_no_email":   {"VI": "Vui lòng nhập email",      "EN": "Please enter your email"},
    "login_err_domain":     {"VI": "Chỉ chấp nhận email @asia-plus.net", "EN": "Only @asia-plus.net emails are allowed"},
    "login_err_otp_len":    {"VI": "Nhập đủ 6 chữ số",         "EN": "Please enter all 6 digits"},
    "login_sending":        {"VI": "Đang gửi OTP...",           "EN": "Sending OTP..."},
    "login_verifying":      {"VI": "Đang xác thực...",          "EN": "Verifying..."},
    "logout":               {"VI": "Đăng xuất",                 "EN": "Sign Out"},

    # ── Sidebar ────────────────────────────────────────────────
    "sidebar_ai_config":    {"VI": "⚙️ Cấu hình AI",           "EN": "⚙️ AI Configuration"},
    "sidebar_provider":     {"VI": "AI Provider",               "EN": "AI Provider"},
    "sidebar_model":        {"VI": "Model",                     "EN": "Model"},
    "sidebar_api_key":      {"VI": "API Key",                   "EN": "API Key"},
    "sidebar_gemini_help":  {"VI": "Lấy free tại aistudio.google.com/apikey", "EN": "Get free at aistudio.google.com/apikey"},
    "sidebar_gpt_help":     {"VI": "Lấy tại platform.openai.com/api-keys", "EN": "Get at platform.openai.com/api-keys"},
    "sidebar_gpt_ready":    {"VI": "✅ GPT sẵn sàng",           "EN": "✅ GPT Ready"},
    "sidebar_gpt_no_key":   {"VI": "❌ Chưa cấu hình API key (liên hệ admin)", "EN": "❌ API key not configured (contact admin)"},
    "sidebar_threshold":    {"VI": "Ngưỡng review (confidence)", "EN": "Review Threshold (confidence)"},
    "sidebar_threshold_help":{"VI": "Records có confidence thấp hơn ngưỡng này sẽ cần review", "EN": "Records below this confidence threshold will need review"},
    "sidebar_language":     {"VI": "🌐 Ngôn ngữ app",          "EN": "🌐 App Language"},
    "sidebar_progress":     {"VI": "### 📋 Tiến trình",         "EN": "### 📋 Progress"},
    "sidebar_gemini_label": {"VI": "🟢 Gemini (free)",          "EN": "🟢 Gemini (free)"},
    "sidebar_gpt_label":    {"VI": "🔵 GPT (paid)",             "EN": "🔵 GPT (paid)"},

    # ── Tabs ───────────────────────────────────────────────────
    "tab_upload":       {"VI": "📁 Upload",                     "EN": "📁 Upload"},
    "tab_codeframe":    {"VI": "📋 Codeframe",                  "EN": "📋 Codeframe"},
    "tab_coding":       {"VI": "🤖 AI Coding",                  "EN": "🤖 AI Coding"},
    "tab_review":       {"VI": "🔍 Review",                     "EN": "🔍 Review"},
    "tab_export":       {"VI": "💾 Export",                     "EN": "💾 Export"},
    "tab_admin":        {"VI": "⚙️ Admin",                      "EN": "⚙️ Admin"},

    # ── Tab 1: Upload ──────────────────────────────────────────
    "upload_title":         {"VI": "### 📁 Upload Dữ liệu",    "EN": "### 📁 Upload Data"},
    "upload_file_label":    {"VI": "Upload file Excel (.xlsx)", "EN": "Upload Excel file (.xlsx)"},
    "upload_sheet_label":   {"VI": "Chọn sheet và cột",        "EN": "Select sheet and columns"},
    "upload_res_id":        {"VI": "Cột ResID",                 "EN": "ResID Column"},
    "upload_question":      {"VI": "Cột Question",              "EN": "Question Column"},
    "upload_verbatim":      {"VI": "Cột Verbatim",              "EN": "Verbatim Column"},
    "upload_load_btn":      {"VI": "📥 Load dữ liệu này",       "EN": "📥 Load This Data"},
    "upload_loading":       {"VI": "Đang load...",              "EN": "Loading..."},
    "upload_or_session":    {"VI": "Hoặc load từ session đã lưu", "EN": "Or load from saved session"},
    "upload_session_label": {"VI": "Upload session.json",       "EN": "Upload session.json"},
    "upload_rules_title":   {"VI": "#### 📜 Coding Rules",      "EN": "#### 📜 Coding Rules"},
    "upload_rules_caption": {"VI": "Chỉnh sửa trực tiếp trên bảng — nhấn Enter để lưu từng ô. Có thể thêm/xóa dòng.", "EN": "Edit directly in the table — press Enter to save each cell. You can add/remove rows."},
    "upload_rules_col_rule":{"VI": "Tên rule",                  "EN": "Rule Name"},
    "upload_rules_col_desc":{"VI": "Mô tả / Hướng dẫn cho AI", "EN": "Description / AI Guidance"},
    "upload_save_rules":    {"VI": "💾 Lưu rules",              "EN": "💾 Save Rules"},
    "upload_export_rules":  {"VI": "⬇️ Export rules.json",      "EN": "⬇️ Export rules.json"},

    # ── Tab 2: Codeframe ───────────────────────────────────────
    "cf_title":             {"VI": "### 📋 Quản lý Codeframe",  "EN": "### 📋 Codeframe Management"},
    "cf_ai_gen_all":        {"VI": "🤖 AI sinh codeframe tất cả", "EN": "🤖 AI Generate All Codeframes"},
    "cf_ai_gen_q":          {"VI": "🤖 AI sinh cho",            "EN": "🤖 AI Generate for"},
    "cf_upload_json":       {"VI": "Upload codeframe_{q}.json", "EN": "Upload codeframe_{q}.json"},
    "cf_paste_excel":       {"VI": "📋 Paste từ Excel",         "EN": "📋 Paste from Excel"},
    "cf_paste_caption":     {"VI": "Copy 2 cột từ Excel: code_id | label rồi paste vào đây", "EN": "Copy 2 columns from Excel: code_id | label then paste here"},
    "cf_paste_placeholder": {"VI": "01\tGiá cả\n02\tChất lượng\n...", "EN": "01\tPrice\n02\tQuality\n..."},
    "cf_load_excel":        {"VI": "📥 Load từ Excel",          "EN": "📥 Load from Excel"},
    "cf_col_code_id":       {"VI": "Mã",                        "EN": "Code"},
    "cf_col_label":         {"VI": "Nhãn",                      "EN": "Label"},
    "cf_col_desc":          {"VI": "Mô tả",                     "EN": "Description"},
    "cf_save":              {"VI": "💾 Lưu codeframe",          "EN": "💾 Save Codeframe"},
    "cf_download":          {"VI": "⬇️ Download JSON",          "EN": "⬇️ Download JSON"},

    # ── Tab 3: AI Coding ───────────────────────────────────────
    "coding_title":         {"VI": "### 🤖 AI Coding",          "EN": "### 🤖 AI Coding"},
    "coding_select_q":      {"VI": "Chọn câu hỏi để code",     "EN": "Select questions to code"},
    "coding_recode":        {"VI": "Re-code tất cả (ghi đè kết quả cũ)", "EN": "Re-code all (overwrite previous results)"},
    "coding_start":         {"VI": "▶️ Bắt đầu AI Coding",      "EN": "▶️ Start AI Coding"},
    "coding_running":       {"VI": "⏳ Đang chạy AI Coding...", "EN": "⏳ Running AI Coding..."},
    "coding_done":          {"VI": "🎉 AI Coding hoàn thành!",  "EN": "🎉 AI Coding Complete!"},
    "coding_no_key":        {"VI": "❌ Chưa nhập API key",      "EN": "❌ API key not set"},

    # ── Tab 4: Review ──────────────────────────────────────────
    "review_title":         {"VI": "### 🔍 Review",             "EN": "### 🔍 Review"},
    "review_no_items":      {"VI": "✅ Không có records nào cần review!", "EN": "✅ No records need review!"},
    "review_run_first":     {"VI": "⬅️ Chạy AI Coding ở Bước 3 trước", "EN": "⬅️ Run AI Coding in Step 3 first"},
    "review_count":         {"VI": "⚠️ Có **{n}** records cần review (confidence < {t})", "EN": "⚠️ **{n}** records need review (confidence < {t})"},
    "review_filter":        {"VI": "Lọc theo câu hỏi",         "EN": "Filter by question"},
    "review_all":           {"VI": "Tất cả",                    "EN": "All"},
    "review_showing":       {"VI": "Hiển thị **{n}** records",  "EN": "Showing **{n}** records"},
    "review_approve_all":   {"VI": "✅ Duyệt tất cả (giữ nguyên AI coding)", "EN": "✅ Approve All (keep AI coding)"},
    "review_ai_codes":      {"VI": "**Mã AI đề xuất:**",        "EN": "**AI Suggested Codes:**"},
    "review_new_codes":     {"VI": "**Chọn mã mới:**",          "EN": "**Select New Codes:**"},
    "review_approve":       {"VI": "✅ Duyệt",                  "EN": "✅ Approve"},
    "review_save":          {"VI": "💾 Lưu mã mới",             "EN": "💾 Save New Codes"},
    "review_add_code":      {"VI": "➕ Thêm mã mới vào codeframe", "EN": "➕ Add New Code to Codeframe"},
    "review_code_id":       {"VI": "Mã ID",                     "EN": "Code ID"},
    "review_code_label":    {"VI": "Tên mã",                    "EN": "Code Label"},
    "review_add_btn":       {"VI": "💾 Thêm vào codeframe",     "EN": "💾 Add to Codeframe"},
    "review_verbatim":      {"VI": "**Verbatim:**",             "EN": "**Verbatim:**"},
    "review_ai_note":       {"VI": "AI note:",                  "EN": "AI note:"},

    # ── Tab 5: Export ──────────────────────────────────────────
    "export_title":         {"VI": "### 💾 Export",             "EN": "### 💾 Export"},
    "export_no_data":       {"VI": "⬅️ Chưa có dữ liệu để export", "EN": "⬅️ No data to export yet"},
    "export_total":         {"VI": "Tổng verbatim",             "EN": "Total Verbatims"},
    "export_coded":         {"VI": "Đã coded",                  "EN": "Coded"},
    "export_review":        {"VI": "Cần review",                "EN": "Need Review"},
    "export_questions":     {"VI": "Câu hỏi",                   "EN": "Questions"},
    "export_session":       {"VI": "📄 Tải session.json (toàn bộ)", "EN": "📄 Download session.json (full)"},
    "export_csv":           {"VI": "📊 Tải CSV",                "EN": "📊 Download CSV"},

    # ── Tab Admin ──────────────────────────────────────────────
    "admin_title":          {"VI": "### ⚙️ Quản lý User",       "EN": "### ⚙️ User Management"},
    "admin_no_access":      {"VI": "⛔ Chỉ admin mới có quyền truy cập", "EN": "⛔ Admin access only"},
    "admin_usage_title":    {"VI": "#### 📊 Thống kê sử dụng GPT API", "EN": "#### 📊 GPT API Usage Statistics"},
    "admin_usage_days":     {"VI": "Thời gian",                 "EN": "Time Period"},
    "admin_usage_btn":      {"VI": "🔄 Xem thống kê",           "EN": "🔄 View Statistics"},
    "admin_usage_empty":    {"VI": "Chưa có dữ liệu usage",     "EN": "No usage data yet"},
    "admin_usage_total":    {"VI": "Tổng {n} lần gọi API trong {d} ngày", "EN": "Total {n} API calls in {d} days"},
    "admin_usage_email":    {"VI": "Email",                     "EN": "Email"},
    "admin_usage_count":    {"VI": "Số lần gọi",                "EN": "Call Count"},
    "admin_block_title":    {"VI": "#### 🚫 Block email",       "EN": "#### 🚫 Block Email"},
    "admin_block_input":    {"VI": "Email cần block",           "EN": "Email to block"},
    "admin_block_btn":      {"VI": "Block",                     "EN": "Block"},
    "admin_blocked_title":  {"VI": "#### 📋 Danh sách email bị block", "EN": "#### 📋 Blocked Emails"},
    "admin_refresh":        {"VI": "🔄 Refresh",                "EN": "🔄 Refresh"},
    "admin_no_blocked":     {"VI": "Không có email nào bị block", "EN": "No emails are blocked"},
    "admin_unblock":        {"VI": "Unblock",                   "EN": "Unblock"},

    # ── Common ─────────────────────────────────────────────────
    "err_prefix":           {"VI": "❌",                        "EN": "❌"},
    "ok_prefix":            {"VI": "✅",                        "EN": "✅"},
    "days_label":           {"VI": "{n} ngày gần nhất",         "EN": "Last {n} days"},
    "no_data":              {"VI": "Chưa có dữ liệu",           "EN": "No data yet"},
    "loading":              {"VI": "Đang tải...",               "EN": "Loading..."},
    "save":                 {"VI": "💾 Lưu",                    "EN": "💾 Save"},
    "cancel":               {"VI": "Hủy",                       "EN": "Cancel"},
    "confirm":              {"VI": "Xác nhận",                  "EN": "Confirm"},
}


def t(key: str, lang: str = "VI", **kwargs) -> str:
    """
    Lấy string đã dịch theo key và ngôn ngữ.
    kwargs: format params, VD: t("review_count", n=5, t=0.9)
    """
    entry = TRANSLATIONS.get(key, {})
    text  = entry.get(lang, entry.get("VI", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text
