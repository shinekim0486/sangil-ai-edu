from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Cm, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "AI에이전츠교육혁신연구회_4대연구성과_표준보고서.docx"
CHART = ROOT / "survey_change.png"

subjects = [
    ("3D프린터용품제작", 2.628, 2.823, "확인 필요"),
    ("게임프로그래밍", 2.691, 2.946, "확인 필요"),
    ("네트워크프로그래밍", 2.567, 3.828, "표본 불일치·추정 포함"),
    ("스마트문화앱콘텐츠제작", 2.709, 3.776, "모의 데이터"),
    ("시스템·네트워크 운영", 3.384, 3.582, "확인 필요"),
    ("응용프로그래밍개발", 3.050, 3.472, "확인 필요"),
    ("인공지능모델링", 3.357, 3.550, "확인 필요"),
]

font_path = r"C:\Windows\Fonts\malgun.ttf"
font = ImageFont.truetype(font_path, 24) if Path(font_path).exists() else ImageFont.load_default()
small = ImageFont.truetype(font_path, 19) if Path(font_path).exists() else ImageFont.load_default()
img = Image.new("RGB", (1500, 780), "white")
draw = ImageDraw.Draw(img)
draw.text((40, 25), "교과별 학생 인식 사전·사후 평균", fill="#17253A", font=font)
draw.rectangle((980, 28, 1010, 48), fill="#9EB4D0"); draw.text((1020, 24), "사전", fill="#17253A", font=small)
draw.rectangle((1110, 28, 1140, 48), fill="#2563EB"); draw.text((1150, 24), "사후", fill="#17253A", font=small)
left, top, barw = 360, 95, 950
for i, (name, a, b, status) in enumerate(subjects):
    y = top + i * 90
    draw.text((35, y+20), name, fill="#17253A", font=small)
    draw.rectangle((left, y, left + int(barw*a/5), y+25), fill="#9EB4D0")
    draw.rectangle((left, y+33, left + int(barw*b/5), y+58), fill="#2563EB")
    draw.text((left + int(barw*a/5)+8, y-2), f"{a:.2f}", fill="#41556E", font=small)
    draw.text((left + int(barw*b/5)+8, y+31), f"{b:.2f}", fill="#173E8C", font=small)
img.save(CHART)

doc = Document()
sec = doc.sections[0]
sec.top_margin = Cm(2.0); sec.bottom_margin = Cm(1.8)
sec.left_margin = Cm(2.2); sec.right_margin = Cm(2.2)

styles = doc.styles
for name, size, bold in [("Normal", 10.5, False), ("Title", 24, True), ("Heading 1", 17, True), ("Heading 2", 13, True), ("Heading 3", 11, True)]:
    st = styles[name]
    st.font.name = "맑은 고딕"; st._element.rPr.rFonts.set(qn("w:eastAsia"), "맑은 고딕")
    st.font.size = Pt(size); st.font.bold = bold; st.font.color.rgb = RGBColor(0,0,0)
styles["Normal"].paragraph_format.space_after = Pt(6)
styles["Normal"].paragraph_format.line_spacing = 1.22

def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr(); shd = OxmlElement("w:shd"); shd.set(qn("w:fill"), fill); tcPr.append(shd)

def borders(cell, color="D9D9D9"):
    tcPr = cell._tc.get_or_add_tcPr(); b = tcPr.first_child_found_in("w:tcBorders")
    if b is None: b = OxmlElement("w:tcBorders"); tcPr.append(b)
    for edge in ("top","left","bottom","right","insideH","insideV"):
        e = OxmlElement(f"w:{edge}"); e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), color); b.append(e)

def set_cell_text(cell, text, bold=False, color=None, align=None):
    cell.text = ""; p = cell.paragraphs[0]
    if align: p.alignment = align
    r = p.add_run(str(text)); r.bold = bold; r.font.name="맑은 고딕"; r._element.rPr.rFonts.set(qn("w:eastAsia"),"맑은 고딕"); r.font.size=Pt(9)
    if color: r.font.color.rgb = RGBColor(*color)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER; borders(cell)

def add_table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.alignment = WD_TABLE_ALIGNMENT.CENTER; t.autofit = False
    for i,h in enumerate(headers):
        set_cell_text(t.rows[0].cells[i], h, True, (255,255,255), WD_ALIGN_PARAGRAPH.CENTER); shade(t.rows[0].cells[i], "17365D")
    for ri,row in enumerate(rows):
        cells=t.add_row().cells
        for i,val in enumerate(row):
            set_cell_text(cells[i], val, False, None, WD_ALIGN_PARAGRAPH.CENTER if len(str(val))<20 else WD_ALIGN_PARAGRAPH.LEFT)
            if ri%2: shade(cells[i], "F3F7FB")
    if widths:
        for row in t.rows:
            for i,w in enumerate(widths): row.cells[i].width=Cm(w)
    doc.add_paragraph()
    return t

def bullet(text):
    p=doc.add_paragraph(style="List Bullet"); p.add_run(text); return p

p=doc.add_paragraph(style="Title"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run("AI에이전츠교육혁신연구회 4대 연구성과 표준보고서")
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run("수행평가 루브릭 결과 AI 활용 전후 산출물 전문교과 성취도 학생 인식 변화").bold=True
p=doc.add_paragraph(); p.alignment=WD_ALIGN_PARAGRAPH.CENTER; p.add_run("원자료 검증 기반 작성본").italic=True
doc.add_paragraph("본 보고서는 현재 제공된 사전·사후 설문과 교사 관찰 기록을 기준으로 연구성과의 증거 상태를 점검하고, 1·2·3단계 실행 로드맵과 그래프·대시보드 설계를 제시한다. 원자료에서 확인되지 않은 루브릭 점수와 전문교과 성취도는 확정 성과로 제시하지 않았다.")
doc.add_page_break()

doc.add_heading("I. 연구 개요", 1)
doc.add_heading("I-1. 연구회 운영 체계와 추진 일정", 2)
doc.add_paragraph("연구회는 전문교과 수업에 AI 에이전트를 적용하고, 학생의 문제 정의, 협업 구현, 오류 검증, 결과물 완성도와 인식 변화를 동일 준거로 확인한다. 데이터 관리 담당은 실제·모의·추정 자료를 구분하고 분석 대상 수와 학생 대응키를 확정한다.")
add_table(["단계","핵심 업무","담당 역할","완료 기준"], [
    ["1단계","사전 기준선과 KPI 확정","연구 총괄·데이터 담당","동일 척도와 대응키 확정"],
    ["2단계","수업·루브릭 개발과 실행","교과 담당·평가 담당","전후 산출물과 채점 근거 수집"],
    ["3단계","사후 분석과 환류","분석 담당·보고서 담당","확정 수치 역반영과 한계 명시"],
], [2.0,5.5,4.0,4.5])
doc.add_heading("I-2. 연구 산출물 및 평가", 2)
add_table(["연구성과","현재 증거 상태","보고서 처리"], [
    ["수행평가 루브릭 채점 결과","학생별 원점수 없음","원점수 확보 전 확정 수치 제시 금지"],
    ["AI 활용 전후 결과물 비교","관찰 기록은 있으나 학생별 대응표 없음","동일 학생 전후 파일 인덱스 추가"],
    ["전문교과 성취도 변화","A~E와 40% 미만 원자료 없음","평가 원점수와 분류 기준 확보"],
    ["학생 인식 변화","교과별 설문 존재","실제·모의·추정 구분 후 분석"],
], [4.0,5.0,7.0])

doc.add_heading("II. 연구 실행", 1)
doc.add_heading("II-1. 사전 분석 개요와 현황 및 요구 분석 결과", 2)
doc.add_paragraph("7개 교과 설문 요약을 검토한 결과, 다수 교과에서 사후 평균이 사전 평균보다 높았다. 그러나 자료 유형과 표본 구성이 동일하지 않아 모든 변화량을 하나의 연구효과로 합산할 수 없다.")
doc.add_picture(str(CHART), width=Cm(15.8))
p=doc.add_paragraph("그림 1. 교과별 학생 인식 사전·사후 평균과 증거 상태"); p.alignment=WD_ALIGN_PARAGRAPH.CENTER
add_table(["교과","사전","사후","변화","증거 상태"], [[s,f"{a:.3f}",f"{b:.3f}",f"{b-a:+.3f}",st] for s,a,b,st in subjects], [5.2,2.0,2.0,2.0,4.8])
doc.add_paragraph("주의: 스마트문화앱 자료는 모의 데이터로 표시되어 있으며, 네트워크프로그래밍은 사전 67명과 사후 34명으로 표본이 다르고 추정 자료가 포함된다. 이 두 자료는 실제 동일 학생의 대응 변화로 해석하지 않는다.")

doc.add_heading("II-2. 개선 방향 및 핵심 연구과제 도출", 2)
add_table(["교육 공백","개선 기본 방향성","핵심 연구과제"], [
    ["결과 중심 평가","과정과 수정 근거를 평가","공통 100점 루브릭 적용"],
    ["AI 답변의 무비판적 수용","전공지식 기반 검증 강화","오류 검증·디버깅 증거 수집"],
    ["전후 자료의 연결 부족","학생 코드와 과제 ID 통일","동일 학생 전후 대응 분석"],
    ["자료 유형 혼재","실제·모의·추정 구분","검증 상태가 보이는 대시보드"],
], [4.2,5.2,6.6])

doc.add_heading("II-3. 교수·학습 및 평가 개선안 설계", 2)
add_table(["기존 방식","AI 에이전트 활용 개선 방식","기대 효과"], [
    ["교사 시범을 따라 하는 실습","학생이 문제·조건·시도를 구조화하고 AI와 반복 협업","자기주도적 문제해결 과정 강화"],
    ["최종 결과물 중심 평가","프롬프트·수정·검증 로그를 포함한 과정 평가","피드백과 평가 근거의 투명성 확보"],
    ["오류 발생 후 정답 안내","실행 로그와 전공지식으로 원인 후보를 좁힘","디버깅 역량과 직무 적합성 강화"],
], [4.5,7.0,4.5])

doc.add_heading("II-4. 교수·학습 및 평가 자료 개발", 2)
add_table(["평가 요소","배점","상 수준","중 수준","하 수준"], [
    ["문제 정의 및 프롬프트·워크플로우 설계",25,"요구와 제약을 구조화하고 반복 가능한 흐름 설계","기본 요구와 흐름 제시","단편적 질문 또는 요구 누락"],
    ["AI 에이전트 협업 및 산출물 구현",30,"반복 피드백으로 기능과 예외 처리 구현","기본 기능 구현","복사 중심 또는 기능 미완성"],
    ["전공 지식 기반 오류 검증·디버깅",25,"전공지식과 실행 근거로 오류 수정","주요 오류 확인과 수정","검증 근거 부족"],
    ["최종 결과물 완성도 및 발표",20,"요구·사용성·문서화·발표 충족","핵심 요구 충족","주요 산출물 누락"],
], [4.0,1.5,4.0,3.5,3.5])
doc.add_paragraph("평가계획은 성취기준 연계, 평가요소 타당성, 배점 합계, 급간 균등성, 최소 성취수준, 재평가 절차, 기록·환류의 7개 항목을 PASS, WARN, FAIL로 점검한다. FAIL 항목이 있으면 적용본으로 확정하지 않는다.")

doc.add_heading("II-5. 수업 적용과 공개수업 운영", 2)
bullet("파일명은 학생코드 교과 과제 시점 버전 순으로 통일한다.")
bullet("동일 학생의 초기 결과물과 최종 결과물에 같은 루브릭을 적용한다.")
bullet("AI 피드백 로그, 수정 이유, 전후 화면 또는 코드 차이, 소요 시간을 함께 저장한다.")
bullet("공개수업 참관 의견은 관찰 사실, 해석, 개선 제안으로 분리한다.")

doc.add_heading("II-6. 사후평가 실시 및 수업 환류", 2)
add_table(["성과","그래프","핵심 표시"], [
    ["루브릭 결과","영역별 그룹 막대","평균·SD·N·변화량"],
    ["전후 결과물","품질 차트와 대조 카드","정확성·완성도·오류율·시간·첨삭"],
    ["전문교과 성취도","100% 누적 가로 막대","A~E 비율과 40% 미만 보조 KPI"],
    ["학생 인식","수평 비교 막대와 KPI 카드","사전·사후·변화량·자료 유형"],
], [4.0,5.0,7.0])
doc.add_paragraph("분석은 대응키와 결측·중복 검사를 먼저 수행한다. 동일 학생 대응 자료에는 대응 분석과 효과크기를 적용하고, 비대응 표본은 별도 집단 비교로 표시한다. 모의·추정 자료는 본 연구 효과 KPI에서 제외한다.")

doc.add_heading("III. 연구 결과와 확산 방안", 1)
doc.add_paragraph("현재 자료는 학생 인식 변화의 일부 기술통계를 제공하지만, 4대 성과를 모두 확정하기에는 부족하다. 학생별 루브릭 원점수, 전문교과 평가 원점수, 40% 미만 학생의 재평가 결과, 동일 학생의 전후 산출물 대응표를 추가 확보한 뒤 최종 수치를 I-2에 역반영해야 한다.")
doc.add_heading("추가 확보 자료", 2)
for x in ["학생별 사전·사후 수행평가 루브릭 원점수","전문교과 사전·사후 평가 점수와 A~E 기준","40% 미만 학생 코드와 재평가 결과","동일 학생의 전후 산출물 파일 대응표","설문 파일별 실제·모의·추정 여부 확인서","네트워크프로그래밍 사전 67명과 사후 34명의 대응 관계"]: bullet(x)

doc.add_heading("부록 1. 대시보드 구현 원칙", 1)
doc.add_paragraph("대시보드는 교과 필터, 자료 유형 필터, 분석 대상 수, 사전·사후 평균, 변화량과 한계 문구를 제공한다. 원점수가 없는 영역은 빈 그래프를 만들지 않고 자료 미확보 상태를 표시한다. 모의 또는 추정 자료는 배지와 주의 문구를 사용하고 KPI 합계에서 제외한다.")
doc.add_heading("부록 2. Back-Patching 점검", 1)
add_table(["점검 항목","확인 방법"], [
    ["I-2 KPI와 II-6 결과 일치","동일 셀 또는 동일 분석 테이블에서 값 연결"],
    ["분모 일치","N, 결측 제외 수, 대응 표본 수를 함께 표기"],
    ["자료 유형 일치","실제·모의·추정 배지가 앞뒤 섹션에서 동일"],
    ["해석 일치","기술통계, 통계적 유의성, 교육적 의미를 구분"],
], [6.0,10.0])

footer=doc.sections[0].footer.paragraphs[0]; footer.alignment=WD_ALIGN_PARAGRAPH.CENTER; footer.add_run("AI에이전츠교육혁신연구회 4대 연구성과 보고서")
doc.save(OUT)
print(OUT)
