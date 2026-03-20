"""
main.py — Entry point
Chạy: python main.py [fresh|continue|recoding|review]

Chọn AI provider và cấu hình bên dưới.
"""
import os
from src.vcode import VCode


# ─────────────────────────────────────────────────────────────
# CHỌN AI PROVIDER
# ─────────────────────────────────────────────────────────────
#
#   "gemini" — Google Gemini (FREE tier, không cần thẻ tín dụng)
#              Key tại: https://aistudio.google.com/apikey
#              Models: "gemini-2.5-flash" (default) | "gemini-2.5-pro" | "gemini-2.5-flash-lite"
#
#   "gpt"    — OpenAI GPT (trả phí, ~$0.5–2 / 500 verbatim)
#              Key tại: https://platform.openai.com/api-keys
#              Models: "gpt-4o" (default) | "gpt-4o-mini" | "gpt-4-turbo"
#
AI_PROVIDER = "gemini"      # ← đổi thành "gpt" nếu muốn dùng OpenAI

# API Keys — set qua environment variable hoặc paste trực tiếp
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# Model — để None sẽ dùng model mặc định của provider
MODEL = None
# MODEL = "gemini-2.5-pro"      # override nếu muốn chọn model cụ thể
# MODEL = "gpt-4o-mini"

# ─────────────────────────────────────────────────────────────
# CẤU HÌNH CHUNG
# ─────────────────────────────────────────────────────────────
THRESHOLD   = 0.9
EXCEL_PATH  = "data/input.xlsx"
RULE_PATH   = "data/rules.json"
OUTPUT_PATH = "output/session.json"


def _get_api_key() -> str:
    """Trả về API key tương ứng với provider đang chọn"""
    if AI_PROVIDER == "gemini":
        return GEMINI_API_KEY
    elif AI_PROVIDER == "gpt":
        return OPENAI_API_KEY
    return ""


def _build_tool() -> VCode:
    """Khởi tạo VCode với provider và key đã cấu hình"""
    return VCode(
        ai_provider=AI_PROVIDER,
        api_key=_get_api_key(),
        model=MODEL,
        confidence_threshold=THRESHOLD
    )


# ─────────────────────────────────────────────────────────────
# MODES
# ─────────────────────────────────────────────────────────────
def run_fresh():
    """Chạy mới hoàn toàn từ đầu"""
    tool = _build_tool()
    tool.run_full_workflow(
        excel_path=EXCEL_PATH,
        rule_path=RULE_PATH,
        output_path=OUTPUT_PATH,
        skip_codeframe_edit=False   # True: bỏ qua bước dừng để edit codeframe
    )


def run_continue(recoding: bool = False):
    """Tiếp tục từ session cũ — không ghi đè records đã coded"""
    tool = _build_tool()
    tool.load_session(OUTPUT_PATH)
    tool.continue_coding(EXCEL_PATH, recoding=recoding)
    tool.review_all()
    tool.save(OUTPUT_PATH)
    print("\n✅ Hoàn thành!")


def run_review_only():
    """Chỉ review các records cần review, không coding lại"""
    tool = _build_tool()
    tool.load_session(OUTPUT_PATH)
    tool.review_all()
    tool.save(OUTPUT_PATH)
    print("\n✅ Hoàn thành!")


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "fresh"

    print(f"\n{'═'*50}")
    print(f"  vcode — AI provider: {AI_PROVIDER.upper()}")
    print(f"  Mode: {mode}")
    print(f"{'═'*50}")

    if mode == "fresh":
        run_fresh()
    elif mode == "continue":
        run_continue(recoding=False)
    elif mode == "recoding":
        run_continue(recoding=True)
    elif mode == "review":
        run_review_only()
    else:
        print(f"Mode không hợp lệ: '{mode}'")
        print("Dùng: python main.py [fresh|continue|recoding|review]")