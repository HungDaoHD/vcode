"""
Session Manager — lưu / load toàn bộ session (codeframes + records) dưới dạng JSON.
Hỗ trợ:
- Lưu session mới
- Load session cũ để coding tiếp (không ghi đè records đã is_coded=True trừ khi recoding=True)
"""
import json
from pathlib import Path
from src.models import Codeframe, VerbatimRecord


class SessionManager:
    """Quản lý lưu/load session JSON"""

    def __init__(self, output_path: str):
        self.output_path = Path(output_path)

    # ------------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------------
    def save(
        self,
        codeframes: dict[str, Codeframe],
        records: dict[str, list[VerbatimRecord]],
        rules: dict = None,
        meta: dict = None
    ):
        """Lưu toàn bộ session ra file JSON"""
        data = {
            "meta": meta or {},
            "rules": rules or {},
            "codeframes": {q: cf.to_dict() for q, cf in codeframes.items()},
            "records": {
                q: [r.to_dict() for r in recs]
                for q, recs in records.items()
            }
        }
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✓ Đã lưu session: {self.output_path}")

    # ------------------------------------------------------------------
    # LOAD
    # ------------------------------------------------------------------
    def load(self) -> tuple[dict, dict, dict, dict]:
        """
        Load session từ file JSON.
        Trả về: (codeframes, records, rules, meta)
        """
        with open(self.output_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        codeframes = {
            q: Codeframe.from_dict(cf)
            for q, cf in data.get("codeframes", {}).items()
        }
        records = {
            q: [VerbatimRecord.from_dict(r) for r in recs]
            for q, recs in data.get("records", {}).items()
        }
        rules = data.get("rules", {})
        meta  = data.get("meta", {})
        print(f"✓ Đã load session: {self.output_path}")
        print(f"  Câu hỏi: {list(codeframes.keys())}")
        total = sum(len(v) for v in records.values())
        coded = sum(r.is_coded for recs in records.values() for r in recs)
        print(f"  Records: {coded}/{total} đã coding")
        return codeframes, records, rules, meta

    # ------------------------------------------------------------------
    # MERGE — Ghép records mới vào session cũ
    # ------------------------------------------------------------------
    def merge_new_records(
        self,
        existing_records: dict[str, list[VerbatimRecord]],
        new_records: dict[str, list[VerbatimRecord]],
        recoding: bool = False
    ) -> dict[str, list[VerbatimRecord]]:
        """
        Merge records mới vào records cũ.
        - Nếu record đã tồn tại (cùng res_id + question) và is_coded=True:
            - recoding=False: giữ nguyên
            - recoding=True: ghi đè bằng record mới
        - Records mới hoàn toàn được thêm vào
        """
        merged = {}
        all_questions = set(existing_records.keys()) | set(new_records.keys())

        for q in all_questions:
            old_list = existing_records.get(q, [])
            new_list = new_records.get(q, [])

            # Index existing by res_id
            old_index = {r.res_id: r for r in old_list}
            result = dict(old_index)  # copy

            added = skipped = overwritten = 0
            for new_rec in new_list:
                key = new_rec.res_id
                if key in result:
                    existing = result[key]
                    if existing.is_coded and not recoding:
                        skipped += 1
                        continue
                    else:
                        result[key] = new_rec
                        overwritten += 1
                else:
                    result[key] = new_rec
                    added += 1

            merged[q] = list(result.values())
            print(f"  [{q}] +{added} mới | {skipped} giữ nguyên | {overwritten} ghi đè")

        return merged

    # ------------------------------------------------------------------
    # STATS
    # ------------------------------------------------------------------
    @staticmethod
    def print_stats(records: dict[str, list[VerbatimRecord]]):
        print("\n── Thống kê session ──")
        for q, recs in records.items():
            total   = len(recs)
            coded   = sum(1 for r in recs if r.is_coded)
            review  = sum(1 for r in recs if r.needs_review)
            print(f"  {q}: {coded}/{total} coded | {review} cần review")
        print()
