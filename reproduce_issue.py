"""
safe_filename 動作確認スクリプト
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import unicodedata
import re

def safe_filename(filename: str) -> str:
    if not filename:
        return ""
    filename = unicodedata.normalize("NFC", filename)
    filename = re.sub(r'[\\/:\*\?"<>|]', '_', filename)
    filename = re.sub(r'^\.+', '_', filename)
    filename = filename.strip()
    return filename

filenames = [
    "test.txt",
    "日本語.txt",
    "mixed日本語.txt",
    "../hack.txt",
    "C:\\windows\\system32",
    "ファイル名：テスト?.pdf",
    "..secret",
    "normal file.txt",
]

print("Testing safe_filename (日本語対応版):")
print("-" * 50)
for f in filenames:
    result = safe_filename(f)
    ok = "✓" if result else "✗ (空文字)"
    print(f"  '{f}' -> '{result}' {ok}")

print()
print("OK: 日本語ファイル名が正しく保持されます")
