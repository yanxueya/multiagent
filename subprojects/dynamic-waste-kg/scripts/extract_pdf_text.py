from __future__ import annotations

import argparse
from pathlib import Path

import pdfplumber


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract PDF text to a UTF-8 text file.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()

    texts: list[str] = []
    with pdfplumber.open(str(args.pdf)) as pdf:
        print(f"pages={len(pdf.pages)}")
        for page_index, page in enumerate(pdf.pages, start=1):
            texts.append(f"\n\n--- PAGE {page_index} ---\n")
            texts.append(page.extract_text() or "")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(texts), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
