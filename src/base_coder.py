"""
BaseCoder — Abstract base class cho tất cả AI coders.
Mọi coder (Gemini, GPT, ...) đều phải kế thừa class này
và implement hai method: generate_codeframe() và code_batch()

Tối ưu chi phí:
  - dedup_and_code(): verbatim trùng nhau chỉ gọi AI 1 lần, copy kết quả cho các record còn lại
  - batch_size lớn hơn → ít API call hơn
"""
from abc import ABC, abstractmethod
from src.models import Codeframe, VerbatimRecord


class BaseCoder(ABC):
    """Interface chung cho AI coding engine"""

    @abstractmethod
    def generate_codeframe(
        self,
        question_code: str,
        verbatims: list[str],
        rules: dict = None,
        sample_size: int = 80
    ) -> Codeframe:
        """Sinh codeframe từ danh sách verbatim mẫu"""
        ...

    @abstractmethod
    def code_batch(
        self,
        records: list[VerbatimRecord],
        codeframe: Codeframe,
        rules: dict = None,
        batch_size: int = 25
    ) -> list[VerbatimRecord]:
        """Coding một danh sách VerbatimRecord theo codeframe"""
        ...

    def dedup_and_code(
        self,
        records: list[VerbatimRecord],
        codeframe: Codeframe,
        rules: dict = None,
        batch_size: int = 25
    ) -> list[VerbatimRecord]:
        """
        Tối ưu chi phí: dedup verbatim trước khi gọi AI.
        - Nhóm các record có verbatim giống nhau (normalize: lowercase + strip)
        - Chỉ gọi AI cho các verbatim unique
        - Copy kết quả coding cho các record trùng
        Tiết kiệm API call tỉ lệ thuận với % verbatim trùng.
        """
        # Normalize verbatim để so sánh (không phân biệt hoa thường, khoảng trắng)
        def normalize(text: str) -> str:
            return " ".join(text.lower().strip().split())

        # Nhóm records theo normalized verbatim
        groups: dict[str, list[VerbatimRecord]] = {}
        for rec in records:
            key = normalize(rec.verbatim)
            groups.setdefault(key, []).append(rec)

        # Lấy 1 đại diện mỗi nhóm để gọi AI
        unique_reps = [recs[0] for recs in groups.values()]

        total_recs    = len(records)
        total_unique  = len(unique_reps)
        total_dupes   = total_recs - total_unique
        saved_pct     = round(total_dupes / total_recs * 100) if total_recs else 0

        if total_dupes > 0:
            print(f"  💡 Dedup: {total_unique} unique / {total_recs} total "
                  f"({total_dupes} trùng — tiết kiệm ~{saved_pct}% API call)")
        else:
            print(f"  ✓ Không có verbatim trùng — coding toàn bộ {total_recs} records")

        # Gọi AI cho unique records
        coded_reps = self.code_batch(unique_reps, codeframe, rules, batch_size)

        # Build lookup: normalized verbatim → coded result
        result_map: dict[str, VerbatimRecord] = {
            normalize(r.verbatim): r for r in coded_reps
        }

        # Copy kết quả cho tất cả records (kể cả duplicates)
        final = []
        for rec in records:
            key    = normalize(rec.verbatim)
            source = result_map.get(key)
            if source and source is not rec:
                # Copy coding từ record đại diện
                rec.codes        = list(source.codes)
                rec.code_labels  = list(source.code_labels)
                rec.confidence   = source.confidence
                rec.note         = source.note + " [copied from duplicate]" if source.note else "[copied from duplicate]"
                rec.is_coded     = True
                rec.needs_review = source.needs_review
            final.append(rec)

        return final

    # ------------------------------------------------------------------
    # SHARED HELPERS
    # ------------------------------------------------------------------
    @staticmethod
    def _format_rules(rules: dict = None) -> str:
        """Format rules dict thành string cho prompt"""
        if not rules:
            return ""
        lines = ["QUY TẮC CODING:"]
        for k, v in rules.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _parse_coding_response(parsed: list | dict) -> list:
        """Xử lý response JSON từ AI — hỗ trợ cả array và object bọc ngoài"""
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v
            return []
        return parsed