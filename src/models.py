# -*- coding: utf-8 -*-
"""
Data models cho vcode — Verbatim Coding Tool
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CodeEntry:
    """Một mã trong codeframe"""
    code_id: str        # VD: "01", "02", "99"
    label: str          # Tên mã, VD: "Giá cả tốt"
    description: str = ""  # Mô tả / ví dụ cho mã này
    net1: str = ""         # Net 1 label
    net2: str = ""         # Net 2 label
    net3: str = ""         # Net 3 label

    def to_dict(self):
        return {
            "code_id":     self.code_id,
            "label":       self.label,
            "description": self.description,
            "net1":        self.net1,
            "net2":        self.net2,
            "net3":        self.net3,
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            code_id=d["code_id"],
            label=d["label"],
            description=d.get("description", ""),
            net1=d.get("net1", ""),
            net2=d.get("net2", ""),
            net3=d.get("net3", ""),
        )


@dataclass
class Codeframe:
    """Bảng mã cho một câu hỏi"""
    question_code: str          # VD: "Q1", "Q2"
    question_text: str = ""     # Nội dung câu hỏi (nếu có)
    codes: list[CodeEntry] = field(default_factory=list)

    def to_dict(self):
        return {
            "question_code": self.question_code,
            "question_text": self.question_text,
            "codes": [c.to_dict() for c in self.codes]
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            question_code=d["question_code"],
            question_text=d.get("question_text", ""),
            codes=[CodeEntry.from_dict(c) for c in d.get("codes", [])]
        )

    def get_code_by_id(self, code_id: str) -> Optional[CodeEntry]:
        for c in self.codes:
            if c.code_id == code_id:
                return c
        return None

    def summary(self) -> str:
        lines = [f"[{self.question_code}] {self.question_text}"]
        for c in self.codes:
            lines.append(f"  {c.code_id}: {c.label}" + (f" — {c.description}" if c.description else ""))
        return "\n".join(lines)


@dataclass
class VerbatimRecord:
    """Một câu trả lời verbatim đã/chưa được coding"""
    res_id: str                         # RespondentID
    question: str                       # Mã câu hỏi, VD: "Q1"
    verbatim: str                       # Nội dung câu trả lời gốc
    codes: list[str] = field(default_factory=list)       # Mảng code_id đã gán
    code_labels: list[str] = field(default_factory=list) # Nhãn tương ứng
    confidence: float = 0.0             # Độ tin cậy 0.0 – 1.0
    is_coded: bool = False              # Đã coding chưa
    needs_review: bool = False          # Cần review (confidence thấp)
    note: str = ""                      # Ghi chú thêm

    def to_dict(self):
        return {
            "ResID": self.res_id,
            "question": self.question,
            "verbatim": self.verbatim,
            "codes": self.codes,
            "code_labels": self.code_labels,
            "confidence": round(self.confidence, 4),
            "is_coded": self.is_coded,
            "needs_review": self.needs_review,
            "note": self.note
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            res_id=str(d["ResID"]),
            question=d["question"],
            verbatim=d["verbatim"],
            codes=d.get("codes", []),
            code_labels=d.get("code_labels", []),
            confidence=float(d.get("confidence", 0.0)),
            is_coded=d.get("is_coded", False),
            needs_review=d.get("needs_review", False),
            note=d.get("note", "")
        )