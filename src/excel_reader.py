# -*- coding: utf-8 -*-
"""
Đọc file Excel đầu vào
Mỗi sheet = 1 câu hỏi mở
Cột bắt buộc: RespondentID, QuestionCode, Verbatim (không phân biệt hoa thường)

Validation:
- ResID có thể trùng nhau (1 respondent trả lời nhiều câu)
- ResID + Question KHÔNG được trùng nhau trong cùng 1 sheet
"""
import pandas as pd
from src.models import VerbatimRecord


class ExcelReader:
    """Đọc file Excel chứa verbatim data"""

    ALIAS_RESID    = ["respondentid", "res_id", "resid", "respondent_id", "id"]
    ALIAS_QCODE    = ["questioncode", "question_code", "q_code", "mã câu hỏi", "question", "câu hỏi"]
    ALIAS_VERBATIM = ["verbatim", "câu trả lời", "answer", "response", "nội dung"]

    def __init__(self, filepath: str):
        self.filepath = filepath
        self._xls = pd.ExcelFile(filepath)

    @property
    def sheet_names(self) -> list[str]:
        return self._xls.sheet_names

    def _find_col(self, df: pd.DataFrame, aliases: list[str]) -> str:
        """Tìm tên cột trong df theo danh sách alias (không phân biệt hoa thường)"""
        lower_map = {c.lower().strip(): c for c in df.columns}
        for alias in aliases:
            if alias in lower_map:
                return lower_map[alias]
        raise ValueError(
            f"Không tìm thấy cột. Cần một trong: {aliases}\n"
            f"Cột hiện có: {list(df.columns)}"
        )

    def _validate_unique_key(
        self,
        df: pd.DataFrame,
        col_res: str,
        col_q: str,
        sheet_name: str
    ) -> list[str]:
        """
        Kiểm tra ResID + Question không trùng nhau.
        Trả về danh sách các cặp bị trùng (để hiển thị warning).
        """
        key_col = df[col_res].str.strip() + " | " + df[col_q].str.strip()
        duplicates = key_col[key_col.duplicated(keep=False)]
        if duplicates.empty:
            return []

        dup_list = sorted(set(duplicates.tolist()))
        return dup_list

    def read_sheet(self, sheet_name: str) -> tuple[list[VerbatimRecord], list[str]]:
        """
        Đọc một sheet, trả về (records, warnings).
        - records: danh sách VerbatimRecord chưa coding
        - warnings: danh sách cặp ResID+Question bị trùng (nếu có)
        """
        df = self._xls.parse(sheet_name, dtype=str).fillna("")

        col_res = self._find_col(df, self.ALIAS_RESID)
        col_q   = self._find_col(df, self.ALIAS_QCODE)
        col_vb  = self._find_col(df, self.ALIAS_VERBATIM)

        # Validate unique key
        dup_keys = self._validate_unique_key(df, col_res, col_q, sheet_name)

        # Đọc records — với key trùng, giữ dòng đầu tiên, bỏ dòng sau
        seen_keys = set()
        records   = []
        skipped   = 0

        for _, row in df.iterrows():
            res_id   = str(row[col_res]).strip()
            question = str(row[col_q]).strip()
            verbatim = str(row[col_vb]).strip()

            if not verbatim:
                continue

            key = f"{res_id}|{question}"
            if key in seen_keys:
                skipped += 1
                continue

            seen_keys.add(key)
            records.append(VerbatimRecord(
                res_id=res_id,
                question=question,
                verbatim=verbatim
            ))

        return records, dup_keys

    def read_all_sheets(self) -> tuple[dict[str, list[VerbatimRecord]], dict[str, list[str]]]:
        """
        Đọc toàn bộ sheets.
        Trả về:
          - records:  {sheet_name: [VerbatimRecord]}
          - warnings: {sheet_name: [duplicate_keys]} — rỗng nếu không có lỗi
        """
        result   = {}
        warnings = {}

        for sheet in self.sheet_names:
            try:
                recs, dups = self.read_sheet(sheet)
                result[sheet] = recs
                if dups:
                    warnings[sheet] = dups
                    print(f"  ⚠ Sheet '{sheet}': {len(recs)} verbatim | {len(dups)} cặp ResID+Question trùng")
                else:
                    print(f"  ✓ Sheet '{sheet}': {len(recs)} verbatim")
            except ValueError as e:
                print(f"  ✗ Sheet '{sheet}' bỏ qua — {e}")

        return result, warnings