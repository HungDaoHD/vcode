# -*- coding: utf-8 -*-
"""
GeminiCoder — gọi Google Gemini API (free tier) để:
1. Sinh codeframe từ verbatim samples
2. Coding từng verbatim dựa trên codeframe + rule

Free tier models (không cần thẻ tín dụng):
  - gemini-2.5-flash      → 15 RPM, khuyên dùng (default)
  - gemini-2.5-pro        → 5 RPM, mạnh hơn, rate limit thấp hơn
  - gemini-2.5-flash-lite → 30 RPM, nhanh nhất, phù hợp batch lớn

Lấy API key miễn phí tại: https://aistudio.google.com/apikey
"""
import json
import os
import time
import google.generativeai as genai
from src.models import CodeEntry, Codeframe, VerbatimRecord
from src.base_coder import BaseCoder


SYSTEM_CODEFRAME = """Bạn là chuyên gia market research với kinh nghiệm coding câu hỏi mở (open-end coding).
Nhiệm vụ: đọc các verbatim mẫu và xây dựng codeframe (bảng mã) phù hợp.
Luôn trả lời bằng JSON hợp lệ, không có markdown, không có text thừa."""

SYSTEM_CODING = """Bạn là chuyên gia market research với kinh nghiệm coding câu hỏi mở.
Nhiệm vụ: gán mã (multi-code) cho từng verbatim dựa trên codeframe và quy tắc coding đã cho.
Luôn trả lời bằng JSON hợp lệ, không có markdown, không có text thừa."""


class GeminiCoder(BaseCoder):
    """AI coding engine dùng Google Gemini API (free tier)"""

    RATE_LIMITS = {
        "gemini-2.5-pro":        5,
        "gemini-2.5-flash":      15,
        "gemini-2.5-flash-lite": 30,
    }

    def __init__(self, api_key: str = None, model: str = "gemini-2.5-flash"):
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError(
                "Cần GEMINI_API_KEY. Lấy miễn phí tại: https://aistudio.google.com/apikey\n"
                "Set bằng: export GEMINI_API_KEY=your_key  hoặc truyền vào GeminiCoder(api_key=...)"
            )
        genai.configure(api_key=key)
        self.model_name      = model
        self.rpm             = self.RATE_LIMITS.get(model, 15)
        self._last_call_time = 0.0
        print(f"  ✓ GeminiCoder khởi tạo — model: {self.model_name} ({self.rpm} RPM free tier)")

    # ------------------------------------------------------------------
    # RATE LIMIT
    # ------------------------------------------------------------------
    def _wait_for_rate_limit(self):
        min_interval = 60.0 / self.rpm
        elapsed = time.time() - self._last_call_time
        if elapsed < min_interval:
            wait = min_interval - elapsed
            print(f"  ⏳ Rate limit: chờ {wait:.1f}s...")
            time.sleep(wait)
        self._last_call_time = time.time()

    def _parse_retry_wait(self, error_msg: str) -> int:
        """
        Đọc thời gian chờ từ thông báo lỗi 429 của Gemini API.
        Gemini thường trả về dạng: 'retry after X seconds' hoặc 'retryDelay: Xs'
        Nếu không parse được, trả về 60 giây mặc định.
        """
        import re
        patterns = [
            r'retry[_ ]after[":\s]+([0-9]+)',
            r'retryDelay[":\s]+([0-9]+)',
            r'after ([0-9]+) second',
            r'([0-9]+)s retry',
        ]
        for pat in patterns:
            m = re.search(pat, str(error_msg), re.IGNORECASE)
            if m:
                return int(m.group(1))
        return 60  # fallback

    def _call_gemini(self, system_prompt: str, user_prompt: str, max_retries: int = 3) -> str:
        """Gọi Gemini API, tự động retry khi bị rate limit 429"""
        for attempt in range(max_retries):
            self._wait_for_rate_limit()
            try:
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=system_prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        temperature=0.1
                    )
                )
                return model.generate_content(user_prompt).text

            except Exception as e:
                err_str = str(e)
                # Kiểm tra lỗi 429 rate limit
                if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                    wait_sec = self._parse_retry_wait(err_str)
                    wait_min = wait_sec / 60
                    if attempt < max_retries - 1:
                        msg = (
                            f"\n  ⛔ Gemini rate limit! "
                            f"Chờ {wait_sec}s ({wait_min:.1f} phút) rồi thử lại "
                            f"(lần {attempt + 1}/{max_retries - 1})..."
                        )
                        print(msg)
                        time.sleep(wait_sec)
                        self._last_call_time = 0.0  # reset để không cộng thêm interval
                    else:
                        raise RuntimeError(
                            f"⛔ Gemini rate limit — đã thử {max_retries} lần.\n"
                            f"Vui lòng chờ khoảng {wait_min:.0f} phút rồi chạy lại.\n"
                            f"Chi tiết: {err_str}"
                        )
                else:
                    raise  # lỗi khác thì raise ngay

    # ------------------------------------------------------------------
    # 1. SINH CODEFRAME
    # ------------------------------------------------------------------
    def generate_codeframe(
        self,
        question_code: str,
        verbatims: list[str],
        rules: dict = None,
        sample_size: int = 80
    ) -> Codeframe:
        sample = verbatims[:sample_size]
        rules_text = self._format_rules(rules)
        prompt = f"""Câu hỏi: {question_code}
{rules_text}
Dưới đây là {len(sample)} verbatim mẫu (tiếng Việt):
{chr(10).join(f"- {v}" for v in sample)}

Hãy xây dựng codeframe gồm 5–15 mã phù hợp nhất.
Trả về JSON theo format sau, KHÔNG có markdown:
{{
  "question_code": "{question_code}",
  "question_text": "Mô tả câu hỏi nếu suy ra được, để trống nếu không rõ",
  "codes": [
    {{"code_id": "01", "label": "Tên mã ngắn gọn", "description": "Mô tả / ví dụ"}},
    {{"code_id": "99", "label": "Khác / Other", "description": "Các ý không thuộc mã nào trên"}}
  ]
}}"""
        data = json.loads(self._call_gemini(SYSTEM_CODEFRAME, prompt))
        return Codeframe(
            question_code=data.get("question_code", question_code),
            question_text=data.get("question_text", ""),
            codes=[CodeEntry.from_dict(c) for c in data.get("codes", [])]
        )

    # ------------------------------------------------------------------
    # 2. CODING VERBATIM (batch)
    # ------------------------------------------------------------------
    def code_batch(
        self,
        records: list[VerbatimRecord],
        codeframe: Codeframe,
        rules: dict = None,
        batch_size: int = 25
    ) -> list[VerbatimRecord]:
        results = []
        total = len(records)
        num_batches = -(-total // batch_size)
        for i in range(0, total, batch_size):
            batch = records[i:i + batch_size]
            print(f"  Coding batch {i // batch_size + 1}/{num_batches} ({len(batch)} records)...")
            results.extend(self._code_single_batch(batch, codeframe, rules))
        return results

    def _code_single_batch(
        self,
        records: list[VerbatimRecord],
        codeframe: Codeframe,
        rules: dict = None
    ) -> list[VerbatimRecord]:
        rules_text     = self._format_rules(rules)
        codeframe_text = "\n".join(
            f"  {c.code_id}: {c.label}" + (f" — {c.description}" if c.description else "")
            for c in codeframe.codes
        )
        items_json = json.dumps(
            [{"idx": i, "res_id": r.res_id, "verbatim": r.verbatim}
             for i, r in enumerate(records)],
            ensure_ascii=False, indent=2
        )
        prompt = f"""Câu hỏi: {codeframe.question_code} — {codeframe.question_text}

CODEFRAME:
{codeframe_text}

{rules_text}

VERBATIM CẦN CODING (multi-code — có thể gán nhiều mã):
{items_json}

Trả về JSON array, KHÔNG có markdown:
[
  {{"idx": 0, "codes": ["01","03"], "code_labels": ["Tên mã 01","Tên mã 03"], "confidence": 0.95, "note": ""}},
  ...
]
Quy tắc:
- Chỉ dùng code_id có trong codeframe ở trên.
- confidence từ 0.0 đến 1.0.
- Nếu không rõ hoặc không thuộc mã nào, gán mã "99" (Khác).
- note để trống nếu không cần giải thích."""
        parsed = json.loads(self._call_gemini(SYSTEM_CODING, prompt))
        items  = self._parse_coding_response(parsed)
        return self._map_results(records, items, codeframe)

    @staticmethod
    def _map_results(records: list[VerbatimRecord], items: list[dict], cf=None) -> list[VerbatimRecord]:
        # Build label lookup từ codeframe (ưu tiên hơn label do AI trả)
        cf_labels = {}
        if cf:
            for c in cf.codes:
                cf_labels[c.code_id] = c.label

        result_map = {item["idx"]: item for item in items}
        coded = []
        for i, rec in enumerate(records):
            res = result_map.get(i, {})
            codes = [str(c) for c in res.get("codes", ["99"])]
            # Lookup label từ codeframe, fallback về AI label nếu không tìm thấy
            labels = [cf_labels.get(cid, lbl) for cid, lbl in zip(
                codes,
                res.get("code_labels", ["Other"] * len(codes))
            )]
            rec.codes        = codes
            rec.code_labels  = labels
            rec.confidence   = float(res.get("confidence", 0.5))
            rec.note         = res.get("note", "")
            rec.is_coded     = True
            rec.needs_review = rec.confidence < 0.9
            coded.append(rec)
        return coded