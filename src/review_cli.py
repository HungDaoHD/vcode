"""
Review CLI — cho phép user review và chỉnh sửa các verbatim có confidence < threshold
Chạy trong terminal (VS Code integrated terminal)
"""
from src.models import Codeframe, VerbatimRecord


class ReviewCLI:
    """Giao diện terminal để review và re-code verbatim"""

    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold

    # ------------------------------------------------------------------
    # REVIEW LOW-CONFIDENCE
    # ------------------------------------------------------------------
    def review_low_confidence(
        self,
        records: list[VerbatimRecord],
        codeframe: Codeframe
    ) -> list[VerbatimRecord]:
        """
        Hiển thị từng verbatim cần review, cho user xác nhận hoặc re-code.
        Trả về records đã được cập nhật.
        """
        low = [r for r in records if r.needs_review and r.is_coded]
        if not low:
            print(f"  ✓ Không có verbatim nào dưới ngưỡng {self.threshold}")
            return records

        print(f"\n{'═'*60}")
        print(f"  REVIEW: {len(low)} verbatim có confidence < {self.threshold}")
        print(f"  Câu hỏi: {codeframe.question_code} — {codeframe.question_text}")
        print(f"{'═'*60}\n")

        for i, rec in enumerate(low, 1):
            print(f"[{i}/{len(low)}] ResID: {rec.res_id}")
            print(f"  Verbatim : {rec.verbatim}")
            print(f"  AI codes : {', '.join(rec.codes)} ({', '.join(rec.code_labels)})")
            print(f"  Confidence: {rec.confidence:.2f}")
            if rec.note:
                print(f"  AI note  : {rec.note}")
            print()
            self._show_codeframe(codeframe)

            choice = self._prompt_choice()
            if choice == "k":
                # Giữ nguyên, đánh dấu đã review
                rec.needs_review = False
                print("  ✓ Giữ nguyên\n")
            elif choice == "r":
                rec = self._recode(rec, codeframe)
            elif choice == "s":
                print("  ⏭ Bỏ qua (vẫn cần review)\n")
                continue

        return records

    # ------------------------------------------------------------------
    # EDIT CODEFRAME QUA TERMINAL
    # ------------------------------------------------------------------
    def edit_codeframe_cli(self, codeframe: Codeframe) -> Codeframe:
        """Cho phép user chỉnh sửa codeframe qua terminal"""
        print(f"\n{'═'*60}")
        print(f"  EDIT CODEFRAME: {codeframe.question_code}")
        print(f"{'═'*60}")
        self._show_codeframe(codeframe)

        while True:
            print("\nTùy chọn: [a] Thêm mã  [e] Sửa mã  [d] Xóa mã  [q] Xong")
            action = input("  > ").strip().lower()

            if action == "q":
                break
            elif action == "a":
                codeframe = self._add_code(codeframe)
            elif action == "e":
                codeframe = self._edit_code(codeframe)
            elif action == "d":
                codeframe = self._delete_code(codeframe)
            else:
                print("  Không hợp lệ, thử lại.")

        print(f"\n  ✓ Codeframe [{codeframe.question_code}] đã cập nhật")
        return codeframe

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------
    def _show_codeframe(self, codeframe: Codeframe):
        print("  Bảng mã:")
        for c in codeframe.codes:
            print(f"    {c.code_id}: {c.label}" + (f"  ({c.description})" if c.description else ""))

    def _prompt_choice(self) -> str:
        while True:
            c = input("  [k] Giữ nguyên  [r] Re-code  [s] Bỏ qua > ").strip().lower()
            if c in ("k", "r", "s"):
                return c
            print("  Nhập k, r hoặc s")

    def _recode(self, rec: VerbatimRecord, codeframe: Codeframe) -> VerbatimRecord:
        print("  Nhập mã mới (cách nhau bằng dấu phẩy, VD: 01,03): ")
        raw = input("  > ").strip()
        code_ids = [x.strip() for x in raw.split(",") if x.strip()]

        valid_ids = {c.code_id for c in codeframe.codes}
        final_ids = []
        final_labels = []
        for cid in code_ids:
            if cid in valid_ids:
                entry = codeframe.get_code_by_id(cid)
                final_ids.append(cid)
                final_labels.append(entry.label if entry else cid)
            else:
                print(f"  ⚠ Mã '{cid}' không có trong codeframe, bỏ qua")

        if not final_ids:
            print("  Không có mã hợp lệ, giữ nguyên AI coding")
            return rec

        rec.codes        = final_ids
        rec.code_labels  = final_labels
        rec.confidence   = 1.0   # User đã xác nhận
        rec.needs_review = False
        rec.note         = rec.note + " [manually recoded]"
        print(f"  ✓ Đã re-code: {', '.join(final_ids)}\n")
        return rec

    def _add_code(self, codeframe: Codeframe) -> Codeframe:
        from src.models import CodeEntry
        code_id = input("  Mã ID mới (VD: 10): ").strip()
        if any(c.code_id == code_id for c in codeframe.codes):
            print(f"  ⚠ Mã {code_id} đã tồn tại")
            return codeframe
        label = input("  Tên mã: ").strip()
        desc  = input("  Mô tả (Enter để bỏ qua): ").strip()
        codeframe.codes.append(CodeEntry(code_id=code_id, label=label, description=desc))
        print(f"  ✓ Đã thêm mã {code_id}: {label}")
        return codeframe

    def _edit_code(self, codeframe: Codeframe) -> Codeframe:
        code_id = input("  Nhập mã ID cần sửa: ").strip()
        entry = codeframe.get_code_by_id(code_id)
        if not entry:
            print(f"  ⚠ Không tìm thấy mã {code_id}")
            return codeframe
        new_label = input(f"  Tên mới (hiện tại: {entry.label}, Enter giữ nguyên): ").strip()
        new_desc  = input(f"  Mô tả mới (hiện tại: {entry.description}, Enter giữ nguyên): ").strip()
        if new_label:
            entry.label = new_label
        if new_desc:
            entry.description = new_desc
        print(f"  ✓ Đã cập nhật mã {code_id}")
        return codeframe

    def _delete_code(self, codeframe: Codeframe) -> Codeframe:
        code_id = input("  Nhập mã ID cần xóa: ").strip()
        before = len(codeframe.codes)
        codeframe.codes = [c for c in codeframe.codes if c.code_id != code_id]
        if len(codeframe.codes) < before:
            print(f"  ✓ Đã xóa mã {code_id}")
        else:
            print(f"  ⚠ Không tìm thấy mã {code_id}")
        return codeframe
