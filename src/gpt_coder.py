# -*- coding: utf-8 -*-
"""
GPTCoder — gọi OpenAI GPT API để:
1. Sinh codeframe từ verbatim samples
2. Coding từng verbatim dựa trên codeframe + rule

Models được hỗ trợ:
  - gpt-4o          → mạnh nhất, chính xác cao (default)
  - gpt-4o-mini     → nhanh hơn, rẻ hơn, phù hợp batch lớn
  - gpt-4-turbo     → thay thế cho gpt-4o nếu cần

Lấy API key tại: https://platform.openai.com/api-keys
Pricing: https://openai.com/pricing
"""
import json
import os
from openai import OpenAI
from src.models import CodeEntry, Codeframe, VerbatimRecord
from src.base_coder import BaseCoder


SYSTEM_CODEFRAME = """Bạn là chuyên gia market research với kinh nghiệm coding câu hỏi mở (open-end coding).
Nhiệm vụ: đọc các verbatim mẫu và xây dựng codeframe (bảng mã) phù hợp.
Luôn trả lời bằng JSON hợp lệ, không có markdown, không có text thừa."""

SYSTEM_CODING = """Bạn là chuyên gia market research với kinh nghiệm coding câu hỏi mở.
Nhiệm vụ: gán mã (multi-code) cho từng verbatim dựa trên codeframe và quy tắc coding đã cho.
Luôn trả lời bằng JSON hợp lệ, không có markdown, không có text thừa."""


# GPT pricing (USD per 1M tokens) — update if OpenAI changes pricing
GPT_PRICING = {
    "gpt-4o":      {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini": {"input": 0.15,  "output": 0.60},
}

def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost for a GPT API call"""
    p = GPT_PRICING.get(model, {"input": 2.50, "output": 10.00})
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


class GPTCoder(BaseCoder):
    """AI coding engine dùng OpenAI GPT API"""

    SUPPORTED_MODELS = ["gpt-4o", "gpt-4o-mini"]

    def __init__(
        self,
        api_key: str = None,
        model: str = "gpt-4o"
    ):
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError(
                "Cần OPENAI_API_KEY. Lấy tại: https://platform.openai.com/api-keys\n"
                "Set bằng: export OPENAI_API_KEY=sk-...  hoặc truyền vào GPTCoder(api_key=...)"
            )
        self.client = OpenAI(api_key=key)
        self.model  = model
        # Token usage tracking (instance variables)
        self._session_input_tokens  = 0
        self._session_output_tokens = 0
        self._session_cost_usd      = 0.0
        print(f"  ✓ GPTCoder khởi tạo — model: {self.model}")

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
    ...
    {{"code_id": "99", "label": "Khác / Other", "description": "Các ý không thuộc mã nào trên"}}
  ]
}}"""

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_CODEFRAME},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        data = json.loads(resp.choices[0].message.content)
        return Codeframe(
            question_code=data.get("question_code", question_code),
            question_text=data.get("question_text", ""),
            codes=[CodeEntry.from_dict(c) for c in data.get("codes", [])]
        )

    # ------------------------------------------------------------------
    # 2. CODING VERBATIM (batch)
    # ------------------------------------------------------------------
    def reset_usage(self):
        self._session_input_tokens  = 0
        self._session_output_tokens = 0
        self._session_cost_usd      = 0.0

    def get_usage(self) -> dict:
        return {
            "input_tokens":  self._session_input_tokens,
            "output_tokens": self._session_output_tokens,
            "total_tokens":  self._session_input_tokens + self._session_output_tokens,
            "cost_usd":      round(self._session_cost_usd, 6),
        }

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
        rules_text    = self._format_rules(rules)
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
  {{
    "idx": 0,
    "codes": ["01", "03"],
    "code_labels": ["Tên mã 01", "Tên mã 03"],
    "confidence": 0.95,
    "note": "lý do ngắn nếu cần"
  }},
  ...
]
Quy tắc:
- Chỉ dùng code_id có trong codeframe ở trên.
- confidence từ 0.0 đến 1.0. Thấp khi verbatim mơ hồ hoặc có thể gán nhiều cách.
- Nếu không rõ hoặc không thuộc mã nào, gán mã "99" (Khác).
- note để trống nếu không cần giải thích."""

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_CODING},
                {"role": "user",   "content": prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        # Track token usage
        if resp.usage:
            it = resp.usage.prompt_tokens
            ot = resp.usage.completion_tokens
            self._session_input_tokens  += it
            self._session_output_tokens += ot
            self._session_cost_usd      += calc_cost(self.model, it, ot)

        parsed = json.loads(resp.choices[0].message.content)
        items  = self._parse_coding_response(parsed)
        return self._map_results(records, items, codeframe)

    # ------------------------------------------------------------------
    # HELPER
    # ------------------------------------------------------------------
    @staticmethod
    def _map_results(
        records: list[VerbatimRecord],
        items: list[dict],
        cf=None
    ) -> list[VerbatimRecord]:
        # Build label lookup từ codeframe
        cf_labels = {}
        if cf:
            for c in cf.codes:
                cf_labels[c.code_id] = c.label

        result_map = {item["idx"]: item for item in items}
        coded = []
        for i, rec in enumerate(records):
            res = result_map.get(i, {})
            codes = [str(c) for c in res.get("codes", ["99"])]
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