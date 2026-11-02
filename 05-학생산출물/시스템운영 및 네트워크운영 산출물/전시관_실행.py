"""웹페이지와 원본 문서를 포함한 Windows 단일 실행파일 진입점."""
import ctypes
import hashlib
import os
from pathlib import Path
import shutil
import sys
import webbrowser


ASSETS = ("index.html", "gallery.css", "gallery.js", "gallery-data.js", "사용안내.txt")


def prepare_site():
    if getattr(sys, "frozen", False):
        source = Path(sys._MEIPASS) / "site"
    else:
        source = Path(__file__).resolve().parent
    files = [source / name for name in ASSETS]
    files.extend(sorted(source.glob("student_outputs_*/*.md")))
    if len(files) <= len(ASSETS) or any(not path.is_file() for path in files):
        raise FileNotFoundError("웹페이지 또는 학생 산출물 파일이 누락되었습니다.")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(source).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    cache = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    destination = cache / "AUTO-NET-LAB" / "StudentShowcase" / digest.hexdigest()[:16]
    # 브라우저가 나중에 읽을 수 있도록 임시 압축 해제 폴더 밖에 보관합니다.
    for path in files:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_bytes() != path.read_bytes():
            shutil.copyfile(path, target)
    return destination / "index.html"


def main():
    try:
        index = prepare_site()
        if "--check" not in sys.argv and not webbrowser.open(index.as_uri(), new=2):
            raise RuntimeError("기본 웹브라우저를 열지 못했습니다. Windows 기본 브라우저 설정을 확인해 주세요.")
        return 0
    except Exception as error:
        if "--check" not in sys.argv:
            ctypes.windll.user32.MessageBoxW(None, str(error), "학생 산출물 전시관 실행 오류", 0x10)
        return 1


if __name__ == "__main__":
    sys.exit(main())
