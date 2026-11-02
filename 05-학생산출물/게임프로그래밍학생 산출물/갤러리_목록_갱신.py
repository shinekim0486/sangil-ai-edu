"""이미지 원본은 보존하고 동일한 파일 내용은 전시 카드 하나로 묶습니다."""
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parent


def main():
    groups = {}
    for path in sorted(ROOT.glob("*.png")):
        raw = path.read_bytes()
        if raw[:8] != b"\x89PNG\r\n\x1a\n":
            raise ValueError(f"올바르지 않은 PNG: {path.name}")
        fingerprint = hashlib.sha256(raw).hexdigest()
        if fingerprint in groups:
            groups[fingerprint]["files"].append(path.name)
            continue
        width, height = struct.unpack(">II", raw[16:24])
        groups[fingerprint] = {"files": [path.name], "width": width, "height": height, "bytes": len(raw)}
    if not groups:
        raise ValueError("PNG 이미지가 없습니다.")
    records = list(groups.values())
    for index, item in enumerate(records, 1):
        # 제공된 원본의 넓은 이미지는 조작 화면 캡처입니다.
        item["category"] = "screen" if item["width"] >= 1000 else "camera"
        item["title"] = f"{'주행 기록 화면' if item['category'] == 'screen' else '도로 영상 기록'} {index:02d}"
        item["id"] = index
    payload = json.dumps(records, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    (ROOT / "gallery-data.js").write_text("window.GAME_GALLERY = " + payload + ";\n", encoding="utf-8")
    print(f"Files: {sum(len(item['files']) for item in records)} / Unique images: {len(records)}")


if __name__ == "__main__":
    main()
