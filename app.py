# -*- coding: utf-8 -*-
"""
app.py — Streamlit UI cho vcode
Chạy: streamlit run app.py
"""
import json
import os
import tempfile
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime

# Load .env nếu có (dev mode)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────
# CLOUDFLARE WORKER — fetch OPENAI_API_KEY
# WORKER_URL và APP_TOKEN được hard-code ở đây
# OPENAI_API_KEY vẫn bảo mật trong Cloudflare Worker
# ─────────────────────────────────────────────────────────────
_WORKER_URL  = "https://wkr-ai-coding.hung-daotuan-1991.workers.dev"
_APP_TOKEN   = "vcode2025XmP2xL8nQ5wR7jT4"
_HMAC_SECRET = "b7f3c9a4e2d84f1c" + "9a6b7e5d2f0a3c8b1d6e4f9a2c7b5e8d3f1a9c6b2e4d7f0"  # tách để khó search

def _sign_request(token: str, timestamp: str, secret: str) -> str:
    """Tạo HMAC-SHA256 signature cho request"""
    import hmac, hashlib
    message = f"{token}:{timestamp}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

def fetch_openai_key() -> str:
    """Fetch OPENAI_API_KEY dùng session token — cache trong session"""
    # Trả cache nếu đã có
    if ss.get("_cached_openai_key"):
        return ss._cached_openai_key
    token = ss.get("auth_token") or _load_token()
    if token:
        key = get_openai_key(token)
        if key:
            ss._cached_openai_key = key  # cache lại
            return key
    return os.environ.get("OPENAI_API_KEY", "")

from src.models import Codeframe, CodeEntry, VerbatimRecord
from src.excel_reader import ExcelReader
from src.session_manager import SessionManager
from src.auth import send_otp, verify_otp, check_session, get_openai_key, ALLOWED_DOMAIN, block_email, unblock_email, list_blocked, is_admin, get_usage

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="vcode",
    page_icon="🔤",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; }
    [data-testid="stDeployButton"] { display: none; }
    footer { visibility: hidden; }
    .stTabs [data-baseweb="tab-list"] { gap: 2px; overflow-x: auto; flex-wrap: nowrap; margin-top: 2.5rem; }
    .stTabs { margin-top: 1rem; }
    .stTabs [data-baseweb="tab"] { font-size: 13px; padding: 8px 12px; white-space: nowrap; }
    .metric-card {
        background: #f8f9fa; border-radius: 8px;
        padding: 12px 16px; text-align: center;
    }
    .metric-num { font-size: 28px; font-weight: 600; }
    .metric-lbl { font-size: 12px; color: #666; margin-top: 2px; }
    .code-badge {
        display: inline-block; padding: 2px 8px; border-radius: 12px;
        font-size: 12px; background: #e8f4f8; color: #1a6b8a;
        margin: 2px; border: 1px solid #b8dce8;
    }
    div[data-testid="stExpander"] { border: 1px solid #e0e0e0; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────
def init_state():
    defaults = {
        "codeframes":      {},
        "records":         {},
        "rules":           {},
        "step":            1,
        "ai_provider":     "gemini",
        "api_key":         "",
        "_gemini_api_key": "",
        "_prev_provider":  "",    # detect khi đổi provider
        "_prev_model":     "",    # detect khi đổi model
        "model":           None,
        "threshold":       0.9,
        "auth_token":        "",
        "auth_email":        "",
        "auth_step":         "email",
        "auth_otp_email":    "",
        "_cached_openai_key": "",  # cache key, tránh gọi Worker mỗi lần render
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()
ss = st.session_state

# ─────────────────────────────────────────────────────────────
# AUTH GATE
# ─────────────────────────────────────────────────────────────
# Lưu token vào file để persist qua các lần tắt/mở app
_TOKEN_FILE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "vcode" / "session.json"

def _save_token(token: str):
    "Lưu token vào file"
    try:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps({"token": token}), encoding="utf-8")
    except Exception:
        pass
    ss.auth_token = token

def _clear_token():
    "Xóa token khỏi file"
    try:
        if _TOKEN_FILE.exists():
            _TOKEN_FILE.unlink()
    except Exception:
        pass

def _load_token() -> str:
    "Đọc token từ file hoặc session_state"
    if ss.get("auth_token"):
        return ss.auth_token
    try:
        if _TOKEN_FILE.exists():
            data = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
            return data.get("token", "")
    except Exception:
        pass
    return ""

def _inject_token_reader():
    pass  # không cần localStorage nữa


def check_auth() -> bool:
    token = _load_token()
    if not token:
        return False
    valid, email = check_session(token)
    if valid:
        ss.auth_token = token
        ss.auth_email = email
        return True
    ss.auth_token = ""
    ss.auth_email = ""
    ss.auth_step  = "email"
    st.query_params.clear()
    return False


def show_login():
    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown("## 🔤 vcode")
        st.markdown("*Verbatim Coding Tool*")
        st.divider()

        if ss.auth_step == "email":
            st.markdown("#### Đăng nhập")
            st.caption(f"Chỉ chấp nhận email @{ALLOWED_DOMAIN}")
            email = st.text_input("Email công ty", placeholder=f"ten@{ALLOWED_DOMAIN}")
            if st.button("Gửi mã OTP", type="primary", width="stretch"):
                if not email:
                    st.error("Vui lòng nhập email")
                elif not email.lower().endswith(f"@{ALLOWED_DOMAIN}"):
                    st.error(f"Chỉ chấp nhận email @{ALLOWED_DOMAIN}")
                else:
                    with st.spinner("Đang gửi OTP..."):
                        ok, msg = send_otp(email)
                    if ok:
                        ss.auth_otp_email = email
                        ss.auth_step = "otp"
                        st.rerun()
                    else:
                        st.error(msg)

        elif ss.auth_step == "otp":
            st.markdown("#### Nhập mã OTP")
            st.info(f"Mã OTP đã gửi đến **{ss.auth_otp_email}**")
            st.caption("Hiệu lực 10 phút")
            otp = st.text_input("Mã OTP (6 chữ số)", max_chars=6, placeholder="123456")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("← Quay lại", width="stretch"):
                    ss.auth_step = "email"
                    st.rerun()
            with c2:
                if st.button("Xác nhận", type="primary", width="stretch"):
                    if not otp or len(otp) != 6:
                        st.error("Nhập đủ 6 chữ số")
                    else:
                        with st.spinner("Đang xác thực..."):
                            ok, msg, token = verify_otp(ss.auth_otp_email, otp)
                        if ok:
                            ss.auth_token = token
                            ss.auth_email = ss.auth_otp_email
                            ss.auth_step  = "done"
                            _save_token(token)
                            st.rerun()
                        else:
                            st.error(msg)


if not check_auth():
    show_login()
    st.stop()



# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
def get_coder():
    from src.vcode import VCode
    tool = VCode(
        ai_provider=ss.ai_provider,
        api_key=ss.api_key or None,
        model=ss.model or None,
        confidence_threshold=ss.threshold
    )
    return tool.coder


def stats():
    total  = sum(len(v) for v in ss.records.values())
    coded  = sum(r.is_coded for recs in ss.records.values() for r in recs)
    review = sum(r.needs_review for recs in ss.records.values() for r in recs)
    return total, coded, review


def records_to_df(question: str) -> pd.DataFrame:
    recs = ss.records.get(question, [])
    return pd.DataFrame([{
        "ResID":       r.res_id,
        "Question":    r.question,
        "Verbatim":    r.verbatim,
        "Codes":       ", ".join(r.codes),
        "Labels":      ", ".join(r.code_labels),
        "Confidence":  f"{r.confidence:.2f}",
        "Cần review":  "⚠️" if r.needs_review else "✅",
        "Note":        r.note,
    } for r in recs])


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔤 vcode")
    st.markdown("*Verbatim Coding Tool*")
    if ss.auth_email:
        st.caption(f"👤 {ss.auth_email}")
        if st.button("Đăng xuất", width="stretch"):
            ss.auth_token = ""
            ss.auth_email = ""
            ss.auth_step  = "email"
            ss._cached_openai_key = ""
            _clear_token()
            st.rerun()
    st.divider()

    st.markdown("### ⚙️ Cấu hình AI")
    provider = st.selectbox(
        "AI Provider",
        ["gemini", "gpt"],
        index=0 if ss.ai_provider == "gemini" else 1,
        format_func=lambda x: "🟢 Gemini (free)" if x == "gemini" else "🔵 GPT (paid)"
    )

    if provider == "gemini":
        model_opts = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"]
        selected_model = st.selectbox("Model", model_opts)

        # Xóa key nếu đổi provider hoặc model
        if provider != ss._prev_provider or selected_model != ss._prev_model:
            ss._gemini_api_key = ""
            ss.api_key         = ""

        help_key    = "Lấy free tại aistudio.google.com/apikey"
        entered_key = st.text_input(
            "API Key", value=ss._gemini_api_key,
            type="password", help=help_key
        )
        ss._gemini_api_key = entered_key
        ss.api_key         = entered_key

    else:
        model_opts      = ["gpt-4o", "gpt-4o-mini"]
        selected_model  = st.selectbox("Model", model_opts)
        # Xóa key nếu đổi provider hoặc model
        if provider != ss._prev_provider or selected_model != ss._prev_model:
            ss.api_key = ""

        # Fetch key từ Worker dùng session token
        _openai_key = fetch_openai_key()
        if _openai_key:
            ss.api_key = _openai_key
            st.success("✅ GPT sẵn sàng")
        else:
            ss.api_key = ""
            st.error("❌ Chưa cấu hình API key (liên hệ admin)")

    # Lưu provider và model hiện tại để so sánh lần sau
    ss.ai_provider  = provider
    ss.model        = selected_model
    ss._prev_provider = provider
    ss._prev_model    = selected_model
    ss.threshold = st.slider(
        "Ngưỡng review (confidence)", 0.5, 1.0, ss.threshold, 0.05,
        help="Records có confidence thấp hơn ngưỡng này sẽ cần review"
    )

    st.divider()

    # Progress steps
    st.markdown("### 📋 Tiến trình")
    steps = [
        ("1", "Upload & Rules"),
        ("2", "Codeframe"),
        ("3", "AI Coding"),
        ("4", "Review"),
        ("5", "Export"),
    ]
    for num, label in steps:
        icon = "✅" if int(num) < ss.step else ("🔵" if int(num) == ss.step else "⚪")
        st.markdown(f"{icon} **Bước {num}** — {label}")

    st.divider()
    if ss.records:
        total, coded, review = stats()
        st.markdown("### 📊 Thống kê")
        c1, c2 = st.columns(2)
        c1.metric("Tổng", total)
        c2.metric("Đã code", coded)
        c1.metric("Cần review", review)
        c2.metric("Câu hỏi", len(ss.records))


# ─────────────────────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab_admin = st.tabs([
    "📁 Upload",
    "📋 Codeframe",
    "🤖 AI Coding",
    "🔍 Review",
    "💾 Export",
    "⚙️ Admin",
])


# ══════════════════════════════════════════════════════════════
# TAB 1: UPLOAD & RULES
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### 📁 Upload dữ liệu")

    col_ex, col_sess = st.columns(2)

    # --- Upload Excel ---
    with col_ex:
        st.markdown("#### File Excel (verbatim)")
        st.caption("Mỗi sheet = 1 câu hỏi | Cột: RespondentID, QuestionCode, Verbatim")
        excel_file = st.file_uploader("Chọn file Excel", type=["xlsx", "xls"], key="excel_upload")

        if excel_file:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(excel_file.read())
                tmp_path = tmp.name
            try:
                reader = ExcelReader(tmp_path)
                new_records, dup_warnings = reader.read_all_sheets()
                if new_records:
                    total = sum(len(v) for v in new_records.values())
                    st.success(f"✅ Đọc được **{total} verbatim** từ **{len(new_records)} sheet**")
                    for sheet, recs in new_records.items():
                        st.markdown(f"- **{sheet}**: {len(recs)} records")
                    if dup_warnings:
                        for sheet, dups in dup_warnings.items():
                            st.warning(f"⚠️ Sheet **{sheet}**: {len(dups)} cặp ResID+Question trùng — giữ dòng đầu tiên, bỏ dòng sau")
                            with st.expander(f"Xem chi tiết trùng lặp — {sheet}"):
                                for d in dups:
                                    st.code(d)

                    if st.button("📥 Load dữ liệu này", type="primary", width="stretch"):
                        if ss.records:
                            # Tính số records mới
                            existing_keys = {
                                f"{r.res_id}|{r.question}"
                                for recs in ss.records.values()
                                for r in recs
                            }
                            # Merge trực tiếp từ session_state
                            merged = {}
                            new_count = 0
                            all_questions = set(ss.records.keys()) | set(new_records.keys())
                            for q in all_questions:
                                old_list = ss.records.get(q, [])
                                new_list = new_records.get(q, [])
                                old_index = {f"{r.res_id}|{r.question}": r for r in old_list}
                                result = dict(old_index)
                                for new_rec in new_list:
                                    key = f"{new_rec.res_id}|{new_rec.question}"
                                    if key not in result:
                                        result[key] = new_rec
                                        new_count += 1
                                merged[q] = list(result.values())
                            ss.records = merged
                            st.success(f"✅ Đã merge — thêm **{new_count} records mới**")
                        else:
                            ss.records = new_records
                            st.success("✅ Đã load dữ liệu mới")
                        ss.step = max(ss.step, 2)
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Lỗi đọc file: {e}")

    # --- Load Session cũ ---
    with col_sess:
        st.markdown("#### Load session cũ (JSON)")
        st.caption("Tiếp tục từ lần coding trước")
        sess_file = st.file_uploader("Chọn file session JSON", type=["json"], key="sess_upload")

        if sess_file:
            try:
                data = json.load(sess_file)
                n_q = len(data.get("codeframes", {}))
                n_r = sum(len(v) for v in data.get("records", {}).values())
                n_coded = sum(
                    r.get("is_coded", False)
                    for recs in data.get("records", {}).values()
                    for r in recs
                )
                st.info(f"📦 {n_q} câu hỏi · {n_coded}/{n_r} records đã coded")

                if st.button("📂 Load session", width="stretch"):
                    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as tmp:
                        json.dump(data, tmp, ensure_ascii=False)
                        tmp_path = tmp.name
                    mgr = SessionManager(tmp_path)
                    cfs, recs, rules, _ = mgr.load()
                    ss.codeframes = cfs
                    ss.records    = recs
                    ss.rules      = rules
                    ss.step       = max(ss.step, 3)
                    st.success("✅ Đã load session")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Lỗi load session: {e}")

    st.divider()

    # --- Rules ---
    st.markdown("#### 📜 Coding Rules")
    col_rf, col_re = st.columns([1, 2])

    with col_rf:
        st.caption("Upload file JSON")
        rule_file = st.file_uploader("File rules.json", type=["json", "txt"], key="rule_upload")
        if rule_file:
            try:
                rules = json.load(rule_file)
                ss.rules = rules
                st.success(f"✅ Đã load {len(rules)} rules")
            except Exception as e:
                st.error(f"❌ {e}")

    with col_re:
        st.caption("Hoặc nhập trực tiếp (bên dưới là rule mẫu)")

        rules_default = """
{
  "language": "Tiếng Việt — phân tích ngữ nghĩa tiếng Việt, không dịch sang tiếng Anh",
  "multi_code": "Mỗi verbatim có thể gán nhiều mã nếu đề cập nhiều chủ đề khác nhau",
  "code_99": "Chỉ gán mã 99 (Khác) khi verbatim thực sự không thuộc bất kỳ mã nào, không dùng mã 99 thay thế cho mã cụ thể",
  "confidence_low": "Gán confidence thấp (< 0.9) khi verbatim mơ hồ, có thể hiểu nhiều cách, hoặc thiếu thông tin",
  "short_answer": "Với các câu trả lời rất ngắn (1–3 từ), cố gắng suy ra ý chính từ ngữ cảnh câu hỏi",
  "negation": "Chú ý phủ định — 'không thích giá' khác với 'thích giá'",
  "custom_rule_example": "Ví dụ rule tùy chỉnh: nếu đề cập 'ship' hoặc 'giao hàng' → gán mã liên quan đến Dịch vụ giao hàng",
  "new_codes": "Nếu phát hiện verbatim không thể chuẩn hóa theo codeframe, ghi chú cho người dùng nên thêm code mới vào codeframe"
}

"""

        rules_text = st.text_area(
            "Rules (JSON format)",
            value=json.dumps(ss.rules, ensure_ascii=False, indent=2) if ss.rules else rules_default,
            height=150, label_visibility="collapsed"
        )
        btn_save, btn_export = st.columns(2)
        with btn_save:
            if st.button("💾 Lưu rules", width="stretch"):
                try:
                    ss.rules = json.loads(rules_text)
                    st.success(f"✅ Đã lưu {len(ss.rules)} rules")
                except Exception as e:
                    st.error(f"❌ JSON không hợp lệ: {e}")
        with btn_export:
            export_rules = json.dumps(ss.rules, ensure_ascii=False, indent=2) if ss.rules else rules_text
            st.download_button(
                "⬇️ Export rules.json",
                data=export_rules.encode("utf-8"),
                file_name="rules.json",
                mime="application/json",
                width="stretch",
                disabled=not ss.rules
            )


# ══════════════════════════════════════════════════════════════
# TAB 2: CODEFRAME
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 📋 Quản lý Codeframe")

    if not ss.records:
        st.info("⬅️ Upload dữ liệu ở Bước 1 trước")
    else:
        if not ss.api_key:
            st.warning("⚠️ Chưa nhập API key ở sidebar")

        questions = list(ss.records.keys())

        # Sinh codeframe tất cả câu hỏi
        col_gen, col_info = st.columns([1, 2])
        with col_gen:
            if st.button("🤖 AI sinh codeframe tất cả", type="primary", width="stretch"):
                with st.spinner("Đang sinh codeframe..."):
                    try:
                        coder = get_coder()
                        progress = st.progress(0)
                        for i, q in enumerate(questions):
                            if q not in ss.codeframes:
                                verbatims = [r.verbatim for r in ss.records[q]]
                                st.write(f"  Đang xử lý [{q}]...")
                                cf = coder.generate_codeframe(q, verbatims, ss.rules)
                                ss.codeframes[q] = cf
                            progress.progress((i + 1) / len(questions))
                        ss.step = max(ss.step, 3)
                        st.success("✅ Sinh codeframe xong!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
        with col_info:
            st.caption(f"Có {len(ss.codeframes)}/{len(questions)} codeframe đã tạo")

        st.divider()

        # Edit từng codeframe
        for q in questions:
            with st.expander(f"📋 {q}" + (" ✅" if q in ss.codeframes else " ⚪ chưa có"), expanded=(q not in ss.codeframes)):

                col_qgen, col_qload = st.columns(2)
                with col_qgen:
                    if st.button(f"🤖 AI sinh cho {q}", key=f"gen_{q}"):
                        with st.spinner(f"Đang sinh codeframe cho {q}..."):
                            try:
                                coder = get_coder()
                                verbatims = [r.verbatim for r in ss.records[q]]
                                cf = coder.generate_codeframe(q, verbatims, ss.rules)
                                ss.codeframes[q] = cf
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ {e}")

                with col_qload:
                    cf_upload = st.file_uploader(f"Upload codeframe_{q}.json", type=["json"], key=f"cf_upload_{q}")
                    if cf_upload:
                        try:
                            ss.codeframes[q] = Codeframe.from_dict(json.load(cf_upload))
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ {e}")

                # Paste từ Excel
                with st.expander("📋 Paste từ Excel", expanded=False):
                    st.caption("Copy 2 cột từ Excel: code_id | label rồi paste vào đây")
                    excel_paste = st.text_area(
                        "Paste dữ liệu Excel",
                        placeholder="01\tGiá cả\n02\tChất lượng\n03\tThương hiệu\n...",
                        height=150,
                        label_visibility="collapsed",
                        key=f"excel_paste_{q}"
                    )
                    if st.button("📥 Load từ Excel", key=f"load_excel_{q}", width="stretch"):
                        if excel_paste.strip():
                            try:
                                new_codes = []
                                for line in excel_paste.strip().splitlines():
                                    parts = line.strip().split("\t")
                                    if len(parts) >= 2:
                                        code_id = parts[0].strip()
                                        label   = parts[1].strip()
                                        if code_id and label:
                                            new_codes.append(CodeEntry(code_id=code_id, label=label, description=""))
                                if new_codes:
                                    existing = ss.codeframes.get(q)
                                    ss.codeframes[q] = Codeframe(
                                        question_code=q,
                                        question_text=existing.question_text if existing else "",
                                        codes=new_codes
                                    )
                                    st.success(f"✅ Đã load {len(new_codes)} mã từ Excel")
                                    st.rerun()
                                else:
                                    st.error("❌ Không đọc được dữ liệu — kiểm tra định dạng cột")
                            except Exception as e:
                                st.error(f"❌ {e}")
                        else:
                            st.warning("Chưa có dữ liệu để load")

                if q in ss.codeframes:
                    cf = ss.codeframes[q]

                    # Hiển thị và edit các mã
                    st.markdown(f"**{len(cf.codes)} mã** | *{cf.question_text or 'Chưa có mô tả câu hỏi'}*")

                    # Edit codes dạng bảng
                    codes_data = [{"code_id": c.code_id, "label": c.label, "description": c.description} for c in cf.codes]
                    edited = st.data_editor(
                        pd.DataFrame(codes_data),
                        num_rows="dynamic",
                        width="stretch",
                        key=f"codes_editor_{q}",
                        column_config={
                            "code_id":     st.column_config.TextColumn("Mã ID", width=80),
                            "label":       st.column_config.TextColumn("Tên mã", width=160),
                            "description": st.column_config.TextColumn("Mô tả / Ví dụ"),
                        }
                    )

                    col_save, col_dl = st.columns(2)
                    with col_save:
                        if st.button(f"💾 Lưu thay đổi {q}", key=f"save_cf_{q}", width="stretch"):
                            new_codes = [
                                CodeEntry(
                                    code_id=str(row["code_id"]),
                                    label=str(row["label"]),
                                    description=str(row.get("description", ""))
                                )
                                for _, row in edited.iterrows()
                                if row["code_id"] and row["label"]
                            ]
                            ss.codeframes[q] = Codeframe(
                                question_code=q,
                                question_text=cf.question_text,
                                codes=new_codes
                            )
                            st.success(f"✅ Đã lưu {len(new_codes)} mã cho {q}")

                    with col_dl:
                        cf_json = json.dumps(ss.codeframes[q].to_dict(), ensure_ascii=False, indent=2)
                        st.download_button(
                            f"⬇️ Tải codeframe_{q}.json",
                            cf_json, f"codeframe_{q}.json", "application/json",
                            width="stretch", key=f"dl_cf_{q}"
                        )


# ══════════════════════════════════════════════════════════════
# TAB 3: AI CODING
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### 🤖 AI Coding")

    if not ss.records:
        st.info("⬅️ Upload dữ liệu ở Bước 1 trước")
    elif not ss.codeframes:
        st.info("⬅️ Tạo codeframe ở Bước 2 trước")
    else:
        # Thống kê pending
        questions = list(ss.records.keys())
        pending_info = {}
        for q in questions:
            recs = ss.records.get(q, [])
            pending = [r for r in recs if not r.is_coded]
            pending_info[q] = len(pending)

        total_pending = sum(pending_info.values())

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Chờ coding", total_pending)
        col_b.metric("Đã coded", sum(len(v) for v in ss.records.values()) - total_pending)
        col_c.metric("Codeframe sẵn", len(ss.codeframes))

        st.divider()

        # Chọn câu hỏi để code
        st.markdown("#### Chọn câu hỏi để coding")
        selected_qs = st.multiselect(
            "Câu hỏi",
            options=questions,
            default=[q for q in questions if pending_info.get(q, 0) > 0 and q in ss.codeframes],
            format_func=lambda q: f"{q} ({pending_info.get(q, 0)} chờ code)"
        )

        recoding = st.checkbox(
            "🔄 Re-code lại tất cả (kể cả records đã coded)",
            value=False,
            help="Bật để ghi đè kết quả coding cũ"
        )

        if st.button("▶️ Bắt đầu AI Coding", type="primary", width="stretch", disabled=not selected_qs):
            if not ss.api_key:
                st.error("❌ Chưa nhập API key")
            else:
                try:
                    coder = get_coder()
                    overall_progress = st.progress(0)
                    status = st.empty()

                    for qi, q in enumerate(selected_qs):
                        recs = ss.records[q]
                        cf   = ss.codeframes.get(q)
                        if not cf:
                            st.warning(f"⚠️ [{q}] Chưa có codeframe, bỏ qua")
                            continue

                        to_code = recs if recoding else [r for r in recs if not r.is_coded]
                        already = [] if recoding else [r for r in recs if r.is_coded]

                        if not to_code:
                            st.info(f"[{q}] Tất cả đã coded")
                            continue

                        status.info(f"⏳ Coding [{q}] — {len(to_code)} verbatim...")
                        coded = coder.dedup_and_code(to_code, cf, ss.rules)
                        ss.records[q] = already + coded

                        low = sum(1 for r in coded if r.needs_review)
                        st.success(f"✅ [{q}] Xong — {low} records cần review")
                        overall_progress.progress((qi + 1) / len(selected_qs))

                    status.empty()
                    ss.step = max(ss.step, 4)
                    st.success("🎉 AI Coding hoàn thành!")
                    st.rerun()
                except Exception as e:
                    err_str = str(e)
                    if "rate limit" in err_str.lower() or "429" in err_str or "quota" in err_str.lower():
                        import re
                        m = re.search(r'([0-9]+)[. ]*(phút|phut|minute|min)', err_str, re.IGNORECASE)
                        m2 = re.search(r'chờ khoảng ([0-9]+) phút', err_str)
                        wait_min = int((m or m2).group(1)) if (m or m2) else 1
                        st.warning(
                            f"⛔ **Gemini rate limit!** "
                            f"Vui lòng chờ khoảng **{wait_min} phút** rồi nhấn coding lại.\n\n"
                            f"_{err_str}_"
                        )
                    else:
                        st.error(f"❌ Lỗi coding: {e}")

        st.divider()

        # Preview kết quả
        if any(any(r.is_coded for r in recs) for recs in ss.records.values()):
            st.markdown("#### Preview kết quả")
            preview_q = st.selectbox("Xem câu hỏi", questions, key="preview_q")
            if preview_q:
                df = records_to_df(preview_q)
                if not df.empty:
                    st.dataframe(df, width="stretch", height=300)


# ══════════════════════════════════════════════════════════════
# TAB 4: REVIEW
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### 🔍 Review Low-Confidence Records")

    # Lọc tất cả records cần review
    review_items = []
    for q, recs in ss.records.items():
        cf = ss.codeframes.get(q)
        for r in recs:
            if r.needs_review and r.is_coded:
                review_items.append((q, r, cf))

    if not review_items:
        if ss.records:
            st.success("✅ Không có records nào cần review!")
        else:
            st.info("⬅️ Chạy AI Coding ở Bước 3 trước")
    else:
        st.warning(f"⚠️ Có **{len(review_items)}** records cần review (confidence < {ss.threshold})")

        # Filter theo câu hỏi
        review_qs = list({q for q, _, _ in review_items})
        filter_q  = st.selectbox("Lọc theo câu hỏi", ["Tất cả"] + review_qs)
        filtered  = [(q, r, cf) for q, r, cf in review_items if filter_q == "Tất cả" or q == filter_q]

        st.markdown(f"Hiển thị **{len(filtered)}** records")
        st.divider()

        # Approve all button
        if st.button("✅ Duyệt tất cả (giữ nguyên AI coding)", width="stretch"):
            for q, recs in ss.records.items():
                for r in recs:
                    if r.needs_review:
                        r.needs_review = False
            st.success("✅ Đã duyệt tất cả")
            st.rerun()

        st.divider()

        # Từng record
        for idx, (q, rec, cf) in enumerate(filtered):
            _uk = f"{q}_{rec.question}_{rec.res_id}"  # unique key
            conf_color = "🔴" if rec.confidence < 0.6 else "🟡"
            with st.expander(
                f"{conf_color} [{q}] ResID {rec.res_id} — confidence {rec.confidence:.2f}",
                expanded=(idx < 5)
            ):
                st.markdown(f"**Verbatim:** {rec.verbatim}")
                if rec.note:
                    st.caption(f"AI note: {rec.note}")

                col_curr, col_new = st.columns(2)
                with col_curr:
                    st.markdown("**Mã AI đề xuất:**")
                    for cid, clabel in zip(rec.codes, rec.code_labels):
                        st.markdown(f'<span class="code-badge">{cid} – {clabel}</span>', unsafe_allow_html=True)

                with col_new:
                    st.markdown("**Chọn mã mới:**")
                    if cf:
                        code_options = {f"{c.code_id} – {c.label}": c.code_id for c in cf.codes}
                        current_selected = [f"{cid} – {clabel}" for cid, clabel in zip(rec.codes, rec.code_labels) if f"{cid} – {clabel}" in code_options]
                        new_sel = st.multiselect(
                            "Mã", list(code_options.keys()),
                            default=current_selected,
                            key=f"review_sel_{_uk}",
                            label_visibility="collapsed"
                        )

                col_approve, col_recode = st.columns(2)
                with col_approve:
                    if st.button("✅ Duyệt", key=f"approve_{_uk}", width="stretch"):
                        rec.needs_review = False
                        st.rerun()

                with col_recode:
                    if st.button("💾 Lưu mã mới", key=f"recode_{_uk}", width="stretch"):
                        if cf and new_sel:
                            new_ids    = [code_options[s] for s in new_sel]
                            new_labels = [s.split(" – ", 1)[1] for s in new_sel]
                            rec.codes        = new_ids
                            rec.code_labels  = new_labels
                            rec.confidence   = 1.0
                            rec.needs_review = False
                            rec.note         = (rec.note + " [manually recoded]").strip()
                            st.success("✅ Đã re-code")
                            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 5: EXPORT
# ══════════════════════════════════════════════════════════════
with tab5:
    st.markdown("### 💾 Export")

    if not ss.records:
        st.info("⬅️ Chưa có dữ liệu để export")
    else:
        total, coded, review = stats()

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng verbatim", total)
        c2.metric("Đã coded", coded)
        c3.metric("Cần review", review, delta=f"-{review} cần xử lý" if review else "Sạch ✅")
        c4.metric("Câu hỏi", len(ss.records))

        st.divider()

        # Phân bổ mã theo câu hỏi
        st.markdown("#### 📊 Phân bổ mã coding")
        for q, recs in ss.records.items():
            cf = ss.codeframes.get(q)
            if not cf:
                continue
            coded_recs = [r for r in recs if r.is_coded]
            if not coded_recs:
                continue

            with st.expander(f"📋 {q} — {len(coded_recs)} records đã coded"):
                # Đếm từng mã
                code_counts = {}
                for c in cf.codes:
                    code_counts[f"{c.code_id} – {c.label}"] = 0
                for r in coded_recs:
                    for cid, clabel in zip(r.codes, r.code_labels):
                        key = f"{cid} – {clabel}"
                        code_counts[key] = code_counts.get(key, 0) + 1

                df_chart = pd.DataFrame([
                    {"Mã": k, "Count": v, "Pct": f"{v/len(coded_recs)*100:.1f}%"}
                    for k, v in sorted(code_counts.items(), key=lambda x: -x[1])
                    if v > 0
                ])
                if not df_chart.empty:
                    st.dataframe(df_chart, width="stretch", hide_index=True)

        st.divider()

        # Download buttons
        st.markdown("#### ⬇️ Tải về")
        col_j, col_c = st.columns(2)

        # JSON
        session_data = {
            "meta": {
                "saved_at":     datetime.now().isoformat(),
                "total_records": total,
                "questions":    list(ss.records.keys()),
                "ai_provider":  ss.ai_provider,
                "model":        ss.model,
            },
            "rules":      ss.rules,
            "codeframes": {q: cf.to_dict() for q, cf in ss.codeframes.items()},
            "records": {
                q: [r.to_dict() for r in recs]
                for q, recs in ss.records.items()
            }
        }
        json_bytes = json.dumps(session_data, ensure_ascii=False, indent=2).encode("utf-8")

        with col_j:
            st.download_button(
                "📄 Tải session.json (toàn bộ)",
                json_bytes, "session.json", "application/json",
                width="stretch", type="primary"
            )
            st.caption("Dùng để load lại lần sau")

        # CSV
        all_rows = []
        for q, recs in ss.records.items():
            for r in recs:
                all_rows.append({
                    "ResID":      r.res_id,
                    "Question":   r.question,
                    "Verbatim":   r.verbatim,
                    "Codes":      "|".join(r.codes),
                    "CodeLabels": "|".join(r.code_labels),
                    "Confidence": round(r.confidence, 4),
                    "IsCoded":    r.is_coded,
                    "NeedsReview": r.needs_review,
                    "Note":       r.note,
                })
        csv_bytes = pd.DataFrame(all_rows).to_csv(index=False).encode("utf-8-sig")

        with col_c:
            st.download_button(
                "📊 Tải CSV (mở bằng Excel)",
                csv_bytes, "vcode_results.csv", "text/csv",
                width="stretch"
            )
            st.caption("UTF-8 BOM — mở Excel không lỗi font")

        # Per-question JSON
        st.markdown("#### ⬇️ Tải từng câu hỏi")
        cols = st.columns(min(len(ss.records), 4))
        for i, (q, recs) in enumerate(ss.records.items()):
            q_data = {
                "question":  q,
                "codeframe": ss.codeframes[q].to_dict() if q in ss.codeframes else {},
                "records":   [r.to_dict() for r in recs]
            }
            cols[i % 4].download_button(
                f"⬇️ {q}.json",
                json.dumps(q_data, ensure_ascii=False, indent=2).encode("utf-8"),
                f"{q}_coded.json", "application/json",
                width="stretch", key=f"dl_{q}"
            )


# ══════════════════════════════════════════════════════════════
# TAB ADMIN: Quản lý user
# ══════════════════════════════════════════════════════════════
with tab_admin:
    st.markdown("### ⚙️ Quản lý User")

    # Kiểm tra quyền admin từ Cloudflare KV
    if not is_admin(ss.auth_email):
        st.warning("⛔ Chỉ admin mới có quyền truy cập")
        st.stop()

    st.divider()

    # Block email
    st.markdown("#### 🚫 Block email")
    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        email_to_block = st.text_input("Email cần block", placeholder=f"ten@{ALLOWED_DOMAIN}", key="block_input")
    with col_b2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Block", type="primary", key="btn_block"):
            if email_to_block:
                ok, msg = block_email(email_to_block)
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
            else:
                st.warning("Nhập email cần block")

    st.divider()

    # Usage tracking
    st.markdown("#### 📊 Thống kê sử dụng GPT API")
    days_opt = st.selectbox("Thời gian", [7, 14, 30], format_func=lambda x: f"{x} ngày gần nhất", key="usage_days")
    if st.button("🔄 Xem thống kê", key="btn_usage"):
        with st.spinner("Đang tải..."):
            usage_data = get_usage(days_opt)
        if not usage_data:
            st.info("Chưa có dữ liệu usage")
        else:
            total_calls = sum(u["total"] for u in usage_data)
            st.caption(f"Tổng {total_calls} lần gọi API trong {days_opt} ngày")
            df_usage = pd.DataFrame([
                {"Email": u["email"], "Số lần gọi": u["total"]}
                for u in usage_data
            ])
            st.dataframe(df_usage, width="stretch", hide_index=True)

    st.divider()

    # Danh sách đang bị block
    st.markdown("#### 📋 Danh sách email bị block")
    if st.button("🔄 Refresh", key="btn_refresh_blocked"):
        st.rerun()

    blocked_list = list_blocked()
    if not blocked_list:
        st.info("Không có email nào bị block")
    else:
        for email in blocked_list:
            col_e, col_u = st.columns([4, 1])
            with col_e:
                st.markdown(f"🚫 `{email}`")
            with col_u:
                if st.button("Unblock", key=f"unblock_{email}"):
                    ok, msg = unblock_email(email)
                    if ok:
                        st.success(f"✅ {msg}")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")