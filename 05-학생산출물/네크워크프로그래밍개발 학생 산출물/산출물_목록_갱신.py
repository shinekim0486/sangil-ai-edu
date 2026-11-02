"""원본 Markdown을 수정하지 않고 오프라인 전시관 데이터를 갱신합니다."""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGES = {"packet_format_v1": 1, "net_protocol_v2": 2, "safety_protocol_v3": 3}


def main():
    documents = []
    for folder in sorted(ROOT.glob("student_outputs_*")):
        if not folder.is_dir():
            continue
        class_name = folder.name.removeprefix("student_outputs_")
        for source in sorted(folder.glob("*.md")):
            match = re.fullmatch(r"(\d+)_(CAR\d+)_(packet_format_v1|net_protocol_v2|safety_protocol_v3)\.md", source.name)
            if not match:
                raise ValueError(f"지원하지 않는 파일명: {source.name}")
            student, team, kind = match.groups()
            documents.append({
                "student": student,
                "team": team,
                "stage": STAGES[kind],
                "className": class_name,
                "filename": source.name,
                "path": source.relative_to(ROOT).as_posix(),
                "content": source.read_text(encoding="utf-8-sig"),
            })
    if not documents:
        raise ValueError("학급 폴더에서 Markdown 산출물을 찾지 못했습니다.")
    payload = json.dumps(documents, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    target = ROOT / "gallery-data.js"
    target.write_text("window.GALLERY_DATA = " + payload + ";\n", encoding="utf-8")
    print(f"완료: {len(documents)}개 산출물, 학생 코드 {len({doc['student'] for doc in documents})}개")
    for name, count in sorted(Counter(doc["className"] for doc in documents).items()):
        print(f"  {name} 폴더: {count}개")


if __name__ == "__main__":
    main()
