"""
VCode — Orchestrator chính
Điều phối toàn bộ workflow:
  Step 1: Load Excel + Rule
  Step 2: Sinh / chỉnh codeframe
  Step 3: AI Coding
  Step 4: Review low-confidence
  Step 5: Save JSON
  Step 6: Load session cũ để coding tiếp
"""
import json
from pathlib import Path
from datetime import datetime

from src.models import Codeframe, VerbatimRecord
from src.excel_reader import ExcelReader
from src.base_coder import BaseCoder
from src.session_manager import SessionManager
from src.review_cli import ReviewCLI


class VCode:
    """Tool coding câu hỏi mở — hỗ trợ Gemini (free) và GPT (paid)"""

    PROVIDERS = ["gemini", "gpt"]

    def __init__(
        self,
        ai_provider: str = "gemini",    # "gemini" hoặc "gpt"
        api_key: str = None,
        model: str = None,              # None = dùng model mặc định của provider
        confidence_threshold: float = 0.9
    ):
        self.coder     = self._init_coder(ai_provider, api_key, model)
        self.reviewer  = ReviewCLI(threshold=confidence_threshold)
        self.threshold = confidence_threshold

        self.codeframes:  dict[str, Codeframe] = {}
        self.records:     dict[str, list[VerbatimRecord]] = {}
        self.rules:       dict = {}
        self.session_mgr: SessionManager = None

    # ------------------------------------------------------------------
    # KHỞI TẠO CODER THEO PROVIDER
    # ------------------------------------------------------------------
    @staticmethod
    def _init_coder(provider: str, api_key: str, model: str) -> BaseCoder:
        provider = provider.lower().strip()
        if provider == "gemini":
            from src.gemini_coder import GeminiCoder
            return GeminiCoder(
                api_key=api_key,
                model=model or "gemini-2.5-flash"
            )
        elif provider == "gpt":
            from src.gpt_coder import GPTCoder
            return GPTCoder(
                api_key=api_key,
                model=model or "gpt-4o"
            )
        else:
            raise ValueError(
                f"ai_provider không hợp lệ: '{provider}'\n"
                f"Chọn một trong: {VCode.PROVIDERS}"
            )

    # ══════════════════════════════════════════════════════════════════
    # STEP 1: Load Excel + Rule
    # ══════════════════════════════════════════════════════════════════
    def load_excel(self, filepath: str):
        """Load file Excel mới"""
        print(f"\n[Step 1] Đọc file Excel: {filepath}")
        reader = ExcelReader(filepath)
        new_records, dup_warnings = reader.read_all_sheets()
        total = sum(len(v) for v in new_records.values())
        print(f"  Tổng: {total} verbatim từ {len(new_records)} sheet(s)")
        if dup_warnings:
            for sheet, dups in dup_warnings.items():
                print(f"  ⚠ Sheet '{sheet}': {len(dups)} cặp ResID+Question trùng — giữ dòng đầu tiên")
        print()
        return new_records

    def load_rules(self, filepath: str):
        """Load rule coding từ file JSON hoặc TXT"""
        p = Path(filepath)
        if not p.exists():
            print(f"  ⚠ Không tìm thấy file rule: {filepath}")
            return {}
        if p.suffix.lower() == ".json":
            with open(p, encoding="utf-8") as f:
                rules = json.load(f)
        else:
            rules = {}
            with open(p, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" in line:
                        k, _, v = line.partition(":")
                        rules[k.strip()] = v.strip()
                    else:
                        rules[f"rule_{i}"] = line
        print(f"  ✓ Đã load {len(rules)} rules từ {filepath}")
        self.rules = rules
        return rules

    # ══════════════════════════════════════════════════════════════════
    # STEP 2: Sinh + Edit Codeframe
    # ══════════════════════════════════════════════════════════════════
    def build_codeframes(self, records: dict[str, list[VerbatimRecord]]):
        """Sinh codeframe cho tất cả câu hỏi chưa có codeframe"""
        print("\n[Step 2] Sinh codeframe...")
        for q, recs in records.items():
            if q in self.codeframes:
                print(f"  [{q}] Dùng codeframe có sẵn")
                continue
            verbatims = [r.verbatim for r in recs]
            print(f"  [{q}] Đang sinh codeframe từ {len(verbatims)} verbatim...")
            cf = self.coder.generate_codeframe(
                question_code=q,
                verbatims=verbatims,
                rules=self.rules
            )
            self.codeframes[q] = cf
            print(f"  [{q}] Sinh xong {len(cf.codes)} mã")
            print(cf.summary())
            print()

    def show_codeframes(self):
        print("\n── Codeframe hiện tại ──")
        for q, cf in self.codeframes.items():
            print(cf.summary())
            print()

    def edit_codeframe(self, question_code: str):
        if question_code not in self.codeframes:
            print(f"  ⚠ Không tìm thấy codeframe cho {question_code}")
            return
        self.codeframes[question_code] = self.reviewer.edit_codeframe_cli(
            self.codeframes[question_code]
        )

    def edit_codeframe_json(self, question_code: str, json_path: str):
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        self.codeframes[question_code] = Codeframe.from_dict(data)
        print(f"  ✓ Đã load codeframe [{question_code}] từ {json_path}")

    def export_codeframes(self, output_dir: str = "output"):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        for q, cf in self.codeframes.items():
            path = out / f"codeframe_{q}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cf.to_dict(), f, ensure_ascii=False, indent=2)
            print(f"  ✓ Xuất: {path}")

    # ══════════════════════════════════════════════════════════════════
    # STEP 3: AI Coding
    # ══════════════════════════════════════════════════════════════════
    def run_coding(self, records: dict[str, list[VerbatimRecord]]) -> dict[str, list[VerbatimRecord]]:
        print("\n[Step 3] AI Coding...")
        coded_all = {}
        for q, recs in records.items():
            pending = [r for r in recs if not r.is_coded]
            already = [r for r in recs if r.is_coded]
            if not pending:
                print(f"  [{q}] Tất cả đã coded, bỏ qua")
                coded_all[q] = recs
                continue
            if q not in self.codeframes:
                print(f"  [{q}] Chưa có codeframe, bỏ qua")
                coded_all[q] = recs
                continue
            print(f"  [{q}] Coding {len(pending)} verbatim...")
            coded = self.coder.dedup_and_code(pending, self.codeframes[q], self.rules)
            coded_all[q] = already + coded
            low = sum(1 for r in coded if r.needs_review)
            print(f"  [{q}] Xong. {low} records cần review (confidence < {self.threshold})\n")
        return coded_all

    # ══════════════════════════════════════════════════════════════════
    # STEP 4: Review low-confidence
    # ══════════════════════════════════════════════════════════════════
    def review_all(self):
        print("\n[Step 4] Review low-confidence records...")
        for q, recs in self.records.items():
            needs = [r for r in recs if r.needs_review]
            if not needs:
                continue
            print(f"\n  Câu hỏi: {q} — {len(needs)} records cần review")
            cf = self.codeframes.get(q)
            if not cf:
                continue
            self.records[q] = self.reviewer.review_low_confidence(recs, cf)

    # ══════════════════════════════════════════════════════════════════
    # STEP 5: Save JSON
    # ══════════════════════════════════════════════════════════════════
    def save(self, output_path: str = None):
        if output_path:
            self.session_mgr = SessionManager(output_path)
        if not self.session_mgr:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.session_mgr = SessionManager(f"output/session_{ts}.json")
        meta = {
            "saved_at": datetime.now().isoformat(),
            "total_records": sum(len(v) for v in self.records.values()),
            "questions": list(self.records.keys())
        }
        self.session_mgr.save(self.codeframes, self.records, self.rules, meta)

    # ══════════════════════════════════════════════════════════════════
    # STEP 6: Load session cũ + coding tiếp
    # ══════════════════════════════════════════════════════════════════
    def load_session(self, json_path: str):
        print(f"\n[Step 6] Load session: {json_path}")
        self.session_mgr = SessionManager(json_path)
        self.codeframes, self.records, self.rules, _ = self.session_mgr.load()

    def continue_coding(self, excel_path: str, recoding: bool = False):
        print(f"\n[Continue] Coding tiếp — recoding={recoding}")
        new_raw = self.load_excel(excel_path)
        self.build_codeframes(new_raw)
        merged = self.session_mgr.merge_new_records(self.records, new_raw, recoding=recoding)
        self.records = self.run_coding(merged)

    # ══════════════════════════════════════════════════════════════════
    # FULL WORKFLOW
    # ══════════════════════════════════════════════════════════════════
    def run_full_workflow(
        self,
        excel_path: str,
        rule_path: str = None,
        output_path: str = None,
        skip_codeframe_edit: bool = False
    ):
        if rule_path:
            self.load_rules(rule_path)
        new_records = self.load_excel(excel_path)
        self.build_codeframes(new_records)
        self.show_codeframes()
        self.export_codeframes()

        if not skip_codeframe_edit:
            print("\nBạn có thể:")
            print("  - Edit file output/codeframe_*.json, rồi load lại bằng tool.edit_codeframe_json()")
            print("  - Hoặc chỉnh trực tiếp qua terminal: tool.edit_codeframe('Q1')")
            input("\n  Nhấn Enter để tiếp tục AI Coding sau khi đã review codeframe...")

        self.records = self.run_coding(new_records)
        SessionManager.print_stats(self.records)
        self.review_all()
        self.save(output_path)
        print("\n✅ Hoàn thành!")