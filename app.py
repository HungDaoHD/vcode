# -*- coding: utf-8 -*-
"""
app.py — Streamlit UI cho vcode
Run: streamlit run app.py
"""
import json
import os
import tempfile
import pandas as pd
import streamlit as st
from pathlib import Path
from datetime import datetime

# Load .env if available (dev mode)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────
# CLOUDFLARE WORKER — fetch OPENAI_API_KEY
# WORKER_URL and APP_TOKEN are hard-coded here
# OPENAI_API_KEY remains secure in Cloudflare Worker
# ─────────────────────────────────────────────────────────────
_WORKER_URL  = "https://wkr-ai-coding.hung-daotuan-1991.workers.dev"
_APP_TOKEN   = "vcode2025XmP2xL8nQ5wR7jT4"
_HMAC_SECRET = "b7f3c9a4e2d84f1c" + "9a6b7e5d2f0a3c8b1d6e4f9a2c7b5e8d3f1a9c6b2e4d7f0"  # split to avoid easy search

def _sign_request(token: str, timestamp: str, secret: str) -> str:
    """Generate HMAC-SHA256 signature for request"""
    import hmac, hashlib
    message = f"{token}:{timestamp}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

def fetch_openai_key() -> str:
    """Fetch OPENAI_API_KEY using session token — cached in session"""
    # Return cached key if available
    if ss.get("_cached_openai_key"):
        return ss._cached_openai_key
    token = ss.get("auth_token") or _load_token()
    if token:
        key = get_openai_key(token)
        if key:
            ss._cached_openai_key = key  # cache for reuse
            return key
    return os.environ.get("OPENAI_API_KEY", "")

from src.models import Codeframe, CodeEntry, VerbatimRecord
from src.excel_reader import ExcelReader
from src.session_manager import SessionManager
from src.auth import send_otp, verify_otp, check_session, get_openai_key, ALLOWED_DOMAIN, block_email, unblock_email, list_blocked, is_admin, get_usage, save_usage_cost
from src.i18n import t

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
    button[disabled] { opacity: 0.4 !important; cursor: not-allowed !important; filter: grayscale(60%) !important; }
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
        "ai_provider":     "gpt",
        "api_key":         "",
        "_prev_provider":  "",    # detect provider change
        "_prev_model":     "",    # detect model change
        "model":           None,
        "threshold":       0.9,
        "auth_token":        "",
        "auth_email":        "",
        "auth_step":         "email",
        "auth_otp_email":    "",
        "_cached_openai_key": "",  # cached key, avoid calling Worker on every render
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()
ss = st.session_state

def lang() -> str:
    return "EN"

def is_loading(key: str) -> bool:
    return ss.get(f"_loading_{key}", False)

def set_loading(key: str, val: bool):
    ss[f"_loading_{key}"] = val

# ─────────────────────────────────────────────────────────────
# AUTH GATE
# ─────────────────────────────────────────────────────────────
# Save token to file to persist across app restarts
_TOKEN_FILE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "vcode" / "session.json"

def _save_token(token: str):
    "Save token to file"
    try:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps({"token": token}), encoding="utf-8")
    except Exception:
        pass
    ss.auth_token = token

def _clear_token():
    "Clear token from file"
    try:
        if _TOKEN_FILE.exists():
            _TOKEN_FILE.unlink()
    except Exception:
        pass

def _load_token() -> str:
    "Read token from file or session_state"
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
    pass  # localStorage no longer needed


def check_auth() -> bool:
    token = _load_token()
    if not token:
        return False
    # Cache session check — chỉ gọi Worker khi chưa có email trong session
    if ss.get("auth_email") and ss.get("auth_token") == token:
        return True
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
        st.markdown(f"*{t('app_subtitle', lang())}*")
        st.divider()

        if ss.auth_step == "email":
            st.markdown(f"#### {t('login_title', lang())}")
            st.caption(t("login_email_hint", lang()))
            email = st.text_input(t("login_email_label", lang()), placeholder=f"ten@{ALLOWED_DOMAIN}")
            if st.button(t("login_send_otp", lang()), type="primary", width="stretch", disabled=is_loading("otp")):
                if not email:
                    st.error(t("login_err_no_email", lang()))
                elif not email.lower().endswith(f"@{ALLOWED_DOMAIN}"):
                    st.error(t("login_err_domain", lang()))
                else:
                    set_loading("otp", True)
                    with st.spinner(t("login_sending", lang())):
                        ok, msg = send_otp(email)
                    set_loading("otp", False)
                    if ok:
                        ss.auth_otp_email = email
                        ss.auth_step = "otp"
                        st.rerun()
                    else:
                        st.error(msg)

        elif ss.auth_step == "otp":
            st.markdown(f"#### {t('login_otp_title', lang())}")
            st.info(f"{t('login_otp_sent', lang())} **{ss.auth_otp_email}**")
            st.caption(t("login_otp_hint", lang()))
            otp = st.text_input(t("login_otp_label", lang()), max_chars=6, placeholder="123456")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(t("login_back", lang()), width="stretch"):
                    ss.auth_step = "email"
                    st.rerun()
            with c2:
                if st.button(t("login_confirm", lang()), type="primary", width="stretch", disabled=is_loading("verify")):
                    if not otp or len(otp) != 6:
                        st.error(t("login_err_otp_len", lang()))
                    else:
                        set_loading("verify", True)
                        with st.spinner(t("login_verifying", lang())):
                            ok, msg, token = verify_otp(ss.auth_otp_email, otp)
                        set_loading("verify", False)
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
USD_TO_VND = 25_000  # Tỷ giá cố định, cập nhật thủ công khi cần

@st.cache_data(show_spinner=False)
def _cached_bytes(data: str) -> bytes:
    """Cache download data để tránh MediaFileHandler missing file error"""
    return data.encode("utf-8-sig")

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
        "Codes":       ", ".join(str(c) for c in r.codes),
        "Labels":      ", ".join(str(l) for l in r.code_labels),
        "Confidence":  f"{r.confidence:.2f}",
        "Needs Review": "⚠️" if r.needs_review else "✅",
        "Note":        r.note,
    } for r in recs])


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔤 vcode")
    st.markdown(f"*{t('app_subtitle', lang())}*")
    if ss.auth_email:
        st.caption(f"👤 {ss.auth_email}")
        if st.button(t("logout", lang()), width="stretch"):
            ss.auth_token = ""
            ss.auth_email = ""
            ss.auth_step  = "email"
            ss._cached_openai_key = ""
            ss["_is_admin"] = False
            ss["_blocked_list"] = []
            _clear_token()
            st.rerun()
    st.divider()

    st.markdown(t("sidebar_ai_config", lang()))

    # GPT only
    ss.ai_provider  = "gpt"
    model_opts      = ["gpt-4o", "gpt-4o-mini"]
    selected_model  = st.selectbox(t("sidebar_model", lang()), model_opts)

    # Clear key if model changes
    if selected_model != ss._prev_model:
        ss.api_key = ""

    # Fetch key from Worker
    _openai_key = fetch_openai_key()
    if _openai_key:
        ss.api_key = _openai_key
        st.success(t("sidebar_gpt_ready", lang()))
    else:
        ss.api_key = ""
        st.error(t("sidebar_gpt_no_key", lang()))

    ss.model          = selected_model
    ss._prev_model    = selected_model
    ss._prev_provider = "gpt" 
    ss.threshold = st.slider(
        t("sidebar_threshold", lang()), 0.5, 1.0, ss.threshold, 0.05,
        help=t("sidebar_threshold_help", lang())
    )



    st.divider()

    # Progress steps
    st.markdown("### 📋 Progress")
    steps = [
        ("1", "Upload & Rules"),
        ("2", "Codeframe"),
        ("3", "AI Coding"),
        ("4", "Review"),
        ("5", "Export"),
    ]
    for num, label in steps:
        icon = "✅" if int(num) < ss.step else ("🔵" if int(num) == ss.step else "⚪")
        st.markdown(f"{icon} **Step {num}** — {label}")

    st.divider()
    if ss.records:
        total, coded, review = stats()
        st.markdown("### 📊 Statistics")
        c1, c2 = st.columns(2)
        c1.metric("Total", total)
        c2.metric("Coded", coded)
        c1.metric("Need Review", review)
        c2.metric("Questions", len(ss.records))


# ─────────────────────────────────────────────────────────────
# MAIN TABS
# ─────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab_admin = st.tabs([
    t("tab_upload", lang()),
    t("tab_codeframe", lang()),
    t("tab_coding", lang()),
    t("tab_review", lang()),
    t("tab_export", lang()),
    t("tab_admin", lang()),
])


# ══════════════════════════════════════════════════════════════
# TAB 1: UPLOAD & RULES
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### 📁 Upload Data")

    col_ex, col_sess = st.columns(2)

    # --- Upload Excel ---
    with col_ex:
        st.markdown("#### File Excel (verbatim)")
        st.caption("Each sheet = 1 question | Columns: RespondentID, QuestionCode, Verbatim")
        excel_file = st.file_uploader("Select Excel file", type=["xlsx", "xls"], key="excel_upload")

        if excel_file:
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(excel_file.read())
                tmp_path = tmp.name
            try:
                reader = ExcelReader(tmp_path)
                new_records, dup_warnings = reader.read_all_sheets()
                if new_records:
                    total = sum(len(v) for v in new_records.values())
                    st.success(f"✅ Read **{total} verbatims** from **{len(new_records)} sheets**")
                    for sheet, recs in new_records.items():
                        st.markdown(f"- **{sheet}**: {len(recs)} records")
                    if dup_warnings:
                        for sheet, dups in dup_warnings.items():
                            st.warning(f"⚠️ Sheet **{sheet}**: {len(dups)} duplicate ResID+Question pairs — kept first row, dropped duplicates")
                            with st.expander(f"View duplicate details — {sheet}"):
                                for d in dups:
                                    st.code(d)

                    if st.button("📥 Load This Data", type="primary", width="stretch"):
                        if ss.records:
                            # Count new records
                            existing_keys = {
                                f"{r.res_id}|{r.question}"
                                for recs in ss.records.values()
                                for r in recs
                            }
                            # Merge directly from session_state
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
                            st.success(f"✅ Merged — added **{new_count} new records**")
                        else:
                            ss.records = new_records
                            st.success("✅ New data loaded")
                        ss.step = max(ss.step, 2)
                        st.rerun()
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")

    # --- Load Existing Session ---
    with col_sess:
        st.markdown("#### Load Existing Session (JSON)")
        st.caption("Continue from a previous coding session")
        sess_file = st.file_uploader("Select session JSON file", type=["json"], key="sess_upload")

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
                st.info(f"📦 {n_q} questions · {n_coded}/{n_r} records coded")

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
                    st.success("✅ Session loaded")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error loading session: {e}")

    st.divider()

    # --- Rules ---
    st.markdown("#### 📜 Coding Rules")

    # Default rules
    _rules_default = [
        {"rule": "language",            "description": "Tiếng Việt — phân tích ngữ nghĩa tiếng Việt, không dịch sang tiếng Anh"},
        {"rule": "multi_code",          "description": "Mỗi verbatim có thể gán nhiều mã nếu đề cập nhiều chủ đề khác nhau"},
        {"rule": "code_99",             "description": "Chỉ gán mã 99 (Khác) khi verbatim thực sự không thuộc bất kỳ mã nào, không dùng mã 99 thay thế cho mã cụ thể"},
        {"rule": "confidence_low",      "description": "Gán confidence thấp (< 0.9) khi verbatim mơ hồ, có thể hiểu nhiều cách, hoặc thiếu thông tin"},
        {"rule": "short_answer",        "description": "Với các câu trả lời rất ngắn (1–3 từ), cố gắng suy ra ý chính từ ngữ cảnh câu hỏi"},
        {"rule": "negation",            "description": "Chú ý phủ định — 'không thích giá' khác với 'thích giá'"},
        {"rule": "custom_rule_example", "description": "Ví dụ rule tùy chỉnh: nếu đề cập 'ship' hoặc 'giao hàng' → gán mã liên quan đến Dịch vụ giao hàng"},
        {"rule": "new_codes",           "description": "Nếu phát hiện verbatim không thể chuẩn hóa theo codeframe, ghi chú cho người dùng nên thêm code mới vào codeframe"},
        {"rule": "code_detail",         "description": "Tạo codeframe chi tiết nhất có thể, mỗi verbatim phải code được ít nhất 3 codes"},
    ]

    # Convert ss.rules dict → list for table display
    if ss.rules:
        rules_df_data = [{"rule": k, "description": v} for k, v in ss.rules.items()]
    else:
        rules_df_data = _rules_default

    st.caption("Edit directly in the table — press Enter to save. You can add/remove rows.")
    edited_rules = st.data_editor(
        pd.DataFrame(rules_df_data),
        num_rows="dynamic",
        key="rules_editor",
        column_config={
            "rule":        st.column_config.TextColumn("Rule Name", width=180),
            "description": st.column_config.TextColumn("Description / AI Guidance"),
        },
        hide_index=True,
    )

    col_rs, col_ru, col_re = st.columns(3)
    with col_rs:
        if st.button("💾 Save Rules", width="stretch", type="primary"):
            new_rules = {
                row["rule"].strip(): row["description"].strip()
                for _, row in edited_rules.iterrows()
                if row["rule"] and row["rule"].strip()
            }
            ss.rules = new_rules
            st.success(f"✅ Saved {len(new_rules)} rules")

    with col_ru:
        rule_file = st.file_uploader("Upload rules.json", type=["json"], key="rule_upload", label_visibility="collapsed")
        if rule_file:
            try:
                loaded = json.load(rule_file)
                ss.rules = loaded
                st.success(f"✅ Loaded {len(loaded)} rules")
                st.rerun()
            except Exception as e:
                st.error(f"❌ {e}")

    with col_re:
        export_rules = json.dumps(ss.rules, ensure_ascii=False, indent=2) if ss.rules else "{}"
        st.download_button(
            "⬇️ Export rules.json",
            data=export_rules.encode("utf-8-sig"),
            file_name="rules.json",
            mime="application/json",
            width="stretch",
            disabled=not ss.rules
        )


# ══════════════════════════════════════════════════════════════
# TAB 2: CODEFRAME
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown(t("cf_title", lang()))

    if not ss.records:
        st.info("⬅️ Upload data in Step 1 first")
    else:
        if not ss.api_key:
            st.warning("⚠️ Please enter your API key in the sidebar")

        questions = list(ss.records.keys())

        # Generate codeframe for all questions
        col_gen, col_info = st.columns([1, 2])
        with col_gen:
            if st.button("🤖 AI Generate All Codeframes", type="primary", width="stretch", disabled=is_loading("gen_all")):
                set_loading("gen_all", True)
                with st.spinner("Generating codeframe..."):
                    try:
                        coder = get_coder()
                        progress = st.progress(0)
                        for i, q in enumerate(questions):
                            if q not in ss.codeframes:
                                verbatims = [r.verbatim for r in ss.records[q]]
                                st.write(f"  Processing [{q}]...")
                                cf = coder.generate_codeframe(q, verbatims, ss.rules)
                                ss.codeframes[q] = cf
                            progress.progress((i + 1) / len(questions))
                        ss.step = max(ss.step, 3)
                        set_loading("gen_all", False)
                        st.success("✅ Codeframe generation complete!")
                        st.rerun()
                    except Exception as e:
                        set_loading("gen_all", False)
                        st.error(f"❌ {e}")
        with col_info:
            st.caption(f"{len(ss.codeframes)}/{len(questions)} codeframes created")

        st.divider()

        # Edit each codeframe
        for q in questions:
            with st.expander(f"📋 {q}" + (" ✅" if q in ss.codeframes else " ⚪ not yet created"), expanded=(q not in ss.codeframes)):

                col_qgen, col_qload = st.columns(2)
                with col_qgen:
                    if st.button(f"🤖 AI sinh cho {q}", key=f"gen_{q}"):
                        with st.spinner(f"Generating codeframe for {q}..."):
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

                # Paste from Excel
                with st.expander("📋 Paste from Excel", expanded=False):
                    st.caption("Columns: **code_id | label | net1 | net2 | net3** (net columns optional)")
                    # Reset textarea bằng cách đổi key khi cần clear
                    _paste_ver = ss.get(f"_paste_ver_{q}", 0)
                    excel_paste = st.text_area(
                        "Paste Excel Data",
                        placeholder="101\tGấu trúc\tNhận dạng ký tự\n201\tDễ thương\tHấp dẫn trực quan\t...",
                        height=150,
                        label_visibility="collapsed",
                        key=f"excel_paste_{q}_{_paste_ver}"
                    )
                    if st.button("📥 Load from Excel", key=f"load_excel_{q}", width="stretch"):
                        if excel_paste.strip():
                            try:
                                new_codes = []
                                errors    = []
                                for line in excel_paste.strip().splitlines():
                                    parts = line.strip().split("\t")
                                    if len(parts) < 2:
                                        continue
                                    code_id = parts[0].strip()
                                    label   = parts[1].strip()
                                    net1    = parts[2].strip() if len(parts) > 2 else ""
                                    net2    = parts[3].strip() if len(parts) > 3 else ""
                                    net3    = parts[4].strip() if len(parts) > 4 else ""

                                    if not code_id or not label:
                                        continue

                                    # Validation
                                    if net2 and not net1:
                                        errors.append(f"Code **{code_id}**: Net 2 requires Net 1.")
                                    if net3 and not net2:
                                        errors.append(f"Code **{code_id}**: Net 3 requires Net 2.")

                                    new_codes.append(CodeEntry(
                                        code_id=code_id, label=label,
                                        net1=net1, net2=net2, net3=net3,
                                        description=""
                                    ))

                                if errors:
                                    for err in errors:
                                        st.error(err)
                                elif new_codes:
                                    existing = ss.codeframes.get(q)
                                    ss.codeframes[q] = Codeframe(
                                        question_code=q,
                                        question_text=existing.question_text if existing else "",
                                        codes=new_codes
                                    )
                                    st.success(f"✅ Loaded {len(new_codes)} codes from Excel")
                                    ss[f"_paste_ver_{q}"] = ss.get(f"_paste_ver_{q}", 0) + 1
                                    st.rerun()
                                else:
                                    st.error("❌ Could not read data — check column format")
                            except Exception as e:
                                st.error(f"❌ {e}")
                        else:
                            st.warning("No data to load")

                if q in ss.codeframes:
                    cf = ss.codeframes[q]

                    # Display and edit codes
                    st.markdown(f"**{len(cf.codes)} codes** | *{cf.question_text or 'No question description'}*")

                    # ── Code editor ──────────────────────────────
                    # Collect existing net values for dropdowns
                    existing_net1 = sorted({c.net1 for c in cf.codes if c.net1})
                    existing_net2 = sorted({c.net2 for c in cf.codes if c.net2})
                    existing_net3 = sorted({c.net3 for c in cf.codes if c.net3})
                    codes_data = [{
                        "code_id":     c.code_id,
                        "label":       c.label,
                        "net1":        c.net1,
                        "net2":        c.net2,
                        "net3":        c.net3,
                        "description": c.description,
                    } for c in cf.codes]

                    net1_opts = [""] + existing_net1
                    net2_opts = [""] + existing_net2
                    net3_opts = [""] + existing_net3

                    edited = st.data_editor(
                        pd.DataFrame(codes_data),
                        num_rows="dynamic",
                        width="stretch",
                        key=f"codes_editor_{q}",
                        column_config={
                            "code_id":     st.column_config.TextColumn("Code ID", width=70),
                            "label":       st.column_config.TextColumn("Code Label", width=150),
                            "net1":        st.column_config.SelectboxColumn("Net 1", width=110, options=net1_opts),
                            "net2":        st.column_config.SelectboxColumn("Net 2", width=110, options=net2_opts),
                            "net3":        st.column_config.SelectboxColumn("Net 3", width=110, options=net3_opts),
                            "description": st.column_config.TextColumn("Description / Example"),
                        },
                        hide_index=True,
                    )

                    col_save, col_dl = st.columns(2)
                    with col_save:
                        if st.button(f"💾 Save Changes {q}", key=f"save_cf_{q}", width="stretch"):
                            errors = []
                            new_codes = []
                            for i, row in edited.iterrows():
                                if not row.get("code_id") or not str(row["code_id"]).strip():
                                    continue
                                cid   = str(row["code_id"]).strip()
                                lbl   = str(row.get("label","")).strip()
                                n1    = str(row.get("net1","")).strip() if pd.notna(row.get("net1")) else ""
                                n2    = str(row.get("net2","")).strip() if pd.notna(row.get("net2")) else ""
                                n3    = str(row.get("net3","")).strip() if pd.notna(row.get("net3")) else ""
                                desc  = str(row.get("description","")).strip() if pd.notna(row.get("description")) else ""

                                # Validation: Net 2 requires Net 1, Net 3 requires Net 2
                                if n2 and not n1:
                                    errors.append(f"Code **{cid}**: Net 2 requires Net 1 to be set first.")
                                if n3 and not n2:
                                    errors.append(f"Code **{cid}**: Net 3 requires Net 2 to be set first.")

                                new_codes.append(CodeEntry(
                                    code_id=cid, label=lbl,
                                    net1=n1, net2=n2, net3=n3,
                                    description=desc
                                ))

                            if errors:
                                for err in errors:
                                    st.error(err)
                            else:
                                ss.codeframes[q] = Codeframe(
                                    question_code=q,
                                    question_text=cf.question_text,
                                    codes=new_codes
                                )
                                st.success(f"✅ Saved {len(new_codes)} codes for {q}")

                    with col_dl:
                        cf_json = json.dumps(ss.codeframes[q].to_dict(), ensure_ascii=False, indent=2)
                        st.download_button(
                            f"⬇️ Download codeframe_{q}.json",
                            cf_json, f"codeframe_{q}.json", "application/json",
                            width="stretch", key=f"dl_cf_{q}"
                        )


# ══════════════════════════════════════════════════════════════
# TAB 3: AI CODING
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown(t("coding_title", lang()))

    if not ss.records:
        st.info("⬅️ Upload data in Step 1 first")
    elif not ss.codeframes:
        st.info("⬅️ Create codeframes in Step 2 first")
    else:
        # Pending statistics
        questions = list(ss.records.keys())
        pending_info = {}
        for q in questions:
            recs = ss.records.get(q, [])
            pending = [r for r in recs if not r.is_coded]
            pending_info[q] = len(pending)

        total_pending = sum(pending_info.values())

        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Pending", total_pending)
        col_b.metric("Coded", sum(len(v) for v in ss.records.values()) - total_pending)
        col_c.metric("Codeframes Ready", len(ss.codeframes))

        st.divider()

        # Select questions to code
        st.markdown("#### Select Questions to Code")
        selected_qs = st.multiselect(
            "Questions",
            options=questions,
            default=[q for q in questions if pending_info.get(q, 0) > 0 and q in ss.codeframes],
            format_func=lambda q: f"{q} ({pending_info.get(q, 0)} pending)"
        )

        recoding = st.checkbox(
            "🔄 Re-code all (including already coded records)",
            value=False,
            help="Enable to overwrite previous coding results"
        )

        # Batch size tự động theo provider — set vào session để dùng trong coding loop
        batch_size = 50  # GPT only
        ss["_coding_batch"] = batch_size

        # Show spinner instead of button while coding
        if is_loading("coding"):
            st.spinner(t("coding_running", lang()))
            _coding_error = None
            try:
                coder = get_coder()
                # Reset usage counter trước mỗi run
                if hasattr(coder, 'reset_usage'):
                    coder.reset_usage()
                overall_progress = st.progress(0)
                status = st.empty()

                for qi, q in enumerate(ss.get("_coding_qs", [])):
                    recs = ss.records[q]
                    cf   = ss.codeframes.get(q)
                    if not cf:
                        st.warning(f"⚠️ [{q}] No codeframe found, skipping")
                        continue
                    recoding = ss.get("_coding_recoding", False)
                    to_code  = recs if recoding else [r for r in recs if not r.is_coded]
                    already  = [] if recoding else [r for r in recs if r.is_coded]
                    if not to_code:
                        continue
                    status.info(f"⏳ Coding [{q}] — {len(to_code)} verbatim...")
                    coded = coder.dedup_and_code(to_code, cf, ss.rules, batch_size=ss.get("_coding_batch", 25))
                    ss.records[q] = already + coded
                    low = sum(1 for r in coded if r.needs_review)
                    st.success(f"✅ [{q}] Done — {low} records need review")
                    overall_progress.progress((qi + 1) / len(ss.get("_coding_qs", [])))

                status.empty()
                ss.step = max(ss.step, 4)

                # Track token usage from GPT coder
                if hasattr(coder, 'get_usage'):
                    usage = coder.get_usage()
                    ss["_last_usage"] = usage
                    # Save to Cloudflare KV
                    if usage["total_tokens"] > 0 and ss.get("auth_token"):
                        save_usage_cost(
                            token=ss.auth_token,
                            input_tokens=usage["input_tokens"],
                            output_tokens=usage["output_tokens"],
                            total_tokens=usage["total_tokens"],
                            cost_usd=usage["cost_usd"],
                        )

            except Exception as e:
                _coding_error = e

            set_loading("coding", False)
            st.rerun()

        elif st.button(t("coding_start", lang()), type="primary", width="stretch", disabled=not selected_qs):
            if not ss.api_key:
                st.error(t("coding_no_key", lang()))
            else:
                ss["_coding_qs"]       = list(selected_qs)
                ss["_coding_recoding"] = recoding
                ss["_coding_batch"]    = batch_size
                set_loading("coding", True)
                st.rerun()

        # Show last usage stats
        if ss.get("_last_usage") and not is_loading("coding"):
            u = ss["_last_usage"]
            st.divider()
            st.markdown("#### 📊 Last Run Usage")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Input Tokens",  f"{u['input_tokens']:,}")
            c2.metric("Output Tokens", f"{u['output_tokens']:,}")
            c3.metric("Total Tokens",  f"{u['total_tokens']:,}")
            vnd = u['cost_usd'] * USD_TO_VND
            c4.metric("Cost", f"${u['cost_usd']:.4f}  (~{vnd:,.0f} ₫)")

        if False:  # dummy block to maintain indentation
                try:
                    pass
                except Exception as e:
                    set_loading("coding", False)
                    err_str = str(e)
                    if "rate limit" in err_str.lower() or "429" in err_str or "quota" in err_str.lower():
                        import re
                        m = re.search(r'([0-9]+)[. ]*(phút|phut|minute|min)', err_str, re.IGNORECASE)
                        m2 = re.search(r'chờ khoảng ([0-9]+) phút', err_str)
                        wait_min = int((m or m2).group(1)) if (m or m2) else 1
                        st.warning(
                            f"⛔ **Rate limit!** "
                            f"Please wait approximately **{wait_min} minutes** then try coding again.\n\n"
                            f"_{err_str}_"
                        )
                    else:
                        st.error(f"❌ Coding error: {e}")

        st.divider()

        # Preview results
        if any(any(r.is_coded for r in recs) for recs in ss.records.values()):
            st.markdown("#### Preview results")
            preview_q = st.selectbox("View Question", questions, key="preview_q")
            if preview_q:
                df = records_to_df(preview_q)
                if not df.empty:
                    st.dataframe(df, width="stretch", height=300)


# ══════════════════════════════════════════════════════════════
# TAB 4: REVIEW
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### 🔍 Review Low-Confidence Records")

    # Filter all records that need review
    review_items = []
    for q, recs in ss.records.items():
        cf = ss.codeframes.get(q)
        for r in recs:
            if r.needs_review and r.is_coded:
                review_items.append((q, r, cf))

    if not review_items:
        if ss.records:
            st.success(t("review_no_items", lang()))
        else:
            st.info(t("review_run_first", lang()))
    else:
        st.warning(t("review_count", lang(), n=len(review_items), t=ss.threshold))

        # Filter by question
        review_qs = list({q for q, _, _ in review_items})
        filter_q  = st.selectbox(t("review_filter", lang()), [t("review_all", lang())] + review_qs)
        filtered  = [(q, r, cf) for q, r, cf in review_items if filter_q == t("review_all", lang()) or q == filter_q]

        st.markdown(t("review_showing", lang(), n=len(filtered)))
        st.divider()

        # Approve all button
        if st.button(t("review_approve_all", lang()), width="stretch"):
            for q, recs in ss.records.items():
                for r in recs:
                    if r.needs_review:
                        r.needs_review = False
            st.success("✅ All records approved")
            st.rerun()

        st.divider()

        # Each record
        for idx, (q, rec, cf) in enumerate(filtered):
            _uk = f"{q}_{rec.question}_{rec.res_id}"  # unique key
            conf_color = "🔴" if rec.confidence < 0.6 else "🟡"
            with st.expander(
                f"{conf_color} [{q}] ResID {rec.res_id} — confidence {rec.confidence:.2f}",
                expanded=(idx < 5)
            ):
                st.markdown(f"{t('review_verbatim', lang())} {rec.verbatim}")
                if rec.note:
                    st.caption(f"AI note: {rec.note}")

                col_curr, col_new = st.columns(2)
                with col_curr:
                    st.markdown(t("review_ai_codes", lang()))
                    for cid, clabel in zip(rec.codes, rec.code_labels):
                        st.markdown(f'<span class="code-badge">{cid} – {clabel}</span>', unsafe_allow_html=True)

                with col_new:
                    st.markdown(t("review_new_codes", lang()))
                    if cf:
                        code_options = {f"{c.code_id} – {c.label}": c.code_id for c in cf.codes}
                        current_selected = [f"{cid} – {clabel}" for cid, clabel in zip(rec.codes, rec.code_labels) if f"{cid} – {clabel}" in code_options]
                        new_sel = st.multiselect(
                            "Code", list(code_options.keys()),
                            default=current_selected,
                            key=f"review_sel_{_uk}",
                            label_visibility="collapsed"
                        )

                # Add new code to codeframe
                with st.expander("➕ Add New Code to Codeframe", expanded=False):
                    nc1, nc2 = st.columns(2)
                    with nc1:
                        new_code_id = st.text_input("Code ID", placeholder="e.g. 10", key=f"new_cid_{_uk}")
                    with nc2:
                        new_code_label = st.text_input("Code Label", placeholder="e.g. Nice Design", key=f"new_clabel_{_uk}")
                    if st.button("💾 Add to Codeframe", key=f"add_code_{_uk}", width="stretch"):
                        if new_code_id and new_code_label and cf:
                            if any(c.code_id == new_code_id for c in cf.codes):
                                st.error(f"Code ID {new_code_id} already exists")
                            else:
                                cf.codes.append(CodeEntry(
                                    code_id=new_code_id.strip(),
                                    label=new_code_label.strip(),
                                    description=""
                                ))
                                ss.codeframes[q] = cf
                                st.success(f"✅ Added code {new_code_id}: {new_code_label}")
                                st.rerun()
                        else:
                            st.warning("Please enter both Code ID and Code Label")

                col_approve, col_recode = st.columns(2)
                with col_approve:
                    if st.button(t("review_approve", lang()), key=f"approve_{_uk}", width="stretch"):
                        rec.needs_review = False
                        st.rerun()

                with col_recode:
                    if st.button(t("review_save", lang()), key=f"recode_{_uk}", width="stretch"):
                        if cf and new_sel:
                            new_ids    = [code_options[s] for s in new_sel]
                            new_labels = [s.split(" – ", 1)[1] for s in new_sel]
                            rec.codes        = new_ids
                            rec.code_labels  = new_labels
                            rec.confidence   = 1.0
                            rec.needs_review = False
                            rec.note         = (rec.note + " [manually recoded]").strip()
                            st.success("✅ Re-coded successfully")
                            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 5: EXPORT
# ══════════════════════════════════════════════════════════════
with tab5:
    st.markdown(t("export_title", lang()))

    if not ss.records:
        st.info(t("export_no_data", lang()))
    else:
        total, coded, review = stats()

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("export_total", lang()), total)
        c2.metric(t("export_coded", lang()), coded)
        c3.metric(t("export_review", lang()), review)
        c4.metric(t("export_questions", lang()), len(ss.records))

        st.divider()

        # Code distribution by question
        st.markdown("#### 📊 Code Distribution")
        for q, recs in ss.records.items():
            cf = ss.codeframes.get(q)
            if not cf:
                continue
            coded_recs = [r for r in recs if r.is_coded]
            if not coded_recs:
                continue

            with st.expander(f"📋 {q} — {len(coded_recs)} records coded"):
                # Count each code
                code_counts = {}
                for c in cf.codes:
                    code_counts[f"{c.code_id} – {c.label}"] = 0
                for r in coded_recs:
                    for cid, clabel in zip(r.codes, r.code_labels):
                        key = f"{cid} – {clabel}"
                        code_counts[key] = code_counts.get(key, 0) + 1

                df_chart = pd.DataFrame([
                    {"Code": k, "Count": v, "Pct": f"{v/len(coded_recs)*100:.1f}%"}
                    for k, v in sorted(code_counts.items(), key=lambda x: -x[1])
                    if v > 0
                ])
                if not df_chart.empty:
                    st.dataframe(df_chart, width="stretch", hide_index=True)

        st.divider()

        # Download buttons
        st.markdown("#### ⬇️ Download")
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
        json_bytes = json.dumps(session_data, ensure_ascii=False, indent=2).encode("utf-8-sig")

        with col_j:
            st.download_button(
                "📄 Download session.json (full)",
                json_bytes, "session.json", "application/json",
                width="stretch", type="primary"
            )
            st.caption("Use this to reload your session later")

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
                "📊 Download CSV (open with Excel)",
                csv_bytes, "vcode_results.csv", "text/csv",
                width="stretch"
            )
            st.caption("UTF-8 BOM — opens correctly in Excel")

        # Per-question JSON
        st.markdown("#### ⬇️ Download by Question")
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
# TAB ADMIN: User management
# ══════════════════════════════════════════════════════════════
with tab_admin:
    st.markdown(t("admin_title", lang()))

    # Check admin permission from Cloudflare KV
    if not is_admin(ss.auth_email):
        st.warning(t("admin_no_access", lang()))
        st.stop()

    st.divider()

    # Block email
    st.markdown(t("admin_block_title", lang()))
    col_b1, col_b2 = st.columns([3, 1])
    with col_b1:
        email_to_block = st.text_input(t("admin_block_input", lang()), placeholder=f"ten@{ALLOWED_DOMAIN}", key="block_input")
    with col_b2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button(t("admin_block_btn", lang()), type="primary", key="btn_block"):
            if email_to_block:
                ok, msg = block_email(email_to_block)
                if ok:
                    st.success(f"✅ {msg}")
                else:
                    st.error(f"❌ {msg}")
            else:
                st.warning("Enter email to block")

    st.divider()

    # Usage tracking
    st.markdown(t("admin_usage_title", lang()))
    days_opt = st.selectbox(t("admin_usage_days", lang()), [7, 14, 30], format_func=lambda x: t("days_label", lang(), n=x), key="usage_days")
    if st.button(t("admin_usage_btn", lang()), key="btn_usage"):
        with st.spinner("Loading..."):
            usage_data = get_usage(days_opt)
        if not usage_data:
            st.info(t("admin_usage_empty", lang()))
        else:
            total_calls = sum(u["total"] for u in usage_data)
            st.caption(t("admin_usage_total", lang(), n=total_calls, d=days_opt))
            df_usage = pd.DataFrame([
                {
                    t("admin_usage_email", lang()): u["email"],
                    "API Calls":     u.get("total", 0),
                    "Coding Runs":   u.get("runs", 0),
                    "Total Tokens":  f"{u.get('total_tokens', 0):,}",
                    "Input Tokens":  f"{u.get('input_tokens', 0):,}",
                    "Output Tokens": f"{u.get('output_tokens', 0):,}",
                    "Cost (USD)":    f"${u.get('cost_usd', 0):.4f}",
                    "Cost (VNĐ)":    f"{u.get('cost_usd', 0) * USD_TO_VND:,.0f} ₫",
                }
                for u in usage_data
            ])
            st.dataframe(df_usage, width="stretch", hide_index=True)

    st.divider()

    # Currently blocked list
    st.markdown(t("admin_blocked_title", lang()))
    if st.button(t("admin_refresh", lang()), key="btn_refresh_blocked"):
        ss["_blocked_list"] = list_blocked()
        st.rerun()

    if "_blocked_list" not in ss:
        ss["_blocked_list"] = list_blocked()
    blocked_list = ss["_blocked_list"]
    if not blocked_list:
        st.info(t("admin_no_blocked", lang()))
    else:
        for email in blocked_list:
            col_e, col_u = st.columns([4, 1])
            with col_e:
                st.markdown(f"🚫 `{email}`")
            with col_u:
                if st.button(t("admin_unblock", lang()), key=f"unblock_{email}"):
                    ok, msg = unblock_email(email)
                    if ok:
                        st.success(f"✅ {msg}")
                        ss["_blocked_list"] = list_blocked()
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")