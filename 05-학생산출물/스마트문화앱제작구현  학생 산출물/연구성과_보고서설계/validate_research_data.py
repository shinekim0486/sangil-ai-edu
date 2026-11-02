from pathlib import Path
import openpyxl, re, hashlib, json, zipfile
from collections import Counter
from statistics import mean
from docx import Document

ROOT = Path(r"C:\Users\AISW\Desktop\최종제출\05-연구결과및 효과검증자료")
DATA = ROOT / "원구결과 관련 원자료"
OUT = Path(__file__).resolve().parent / "데이터검증보고서.md"

def score(v):
    if isinstance(v, (int,float)) and not isinstance(v,bool) and 1 <= v <= 5: return float(v)
    m = re.match(r"\s*([①②③④⑤1-5])", str(v or ""))
    if not m: return None
    return float("①②③④⑤".find(m.group(1))+1) if m.group(1) in "①②③④⑤" else float(m.group(1))

def used_rows(ws, header_row, id_col):
    out=[]
    for r in ws.iter_rows(min_row=header_row+1, values_only=True):
        ident=str(r[id_col] or "").strip()
        if re.fullmatch(r"P\d+|\d{5}", ident): out.append(r)
    return out

results=[]
for p in sorted(DATA.glob("*.xlsx")):
    wbv=openpyxl.load_workbook(p,read_only=True,data_only=True)
    wbf=openpyxl.load_workbook(p,read_only=True,data_only=False)
    info={"file":p.name,"issues":[],"warnings":[],"pre_n":None,"post_n":None,"paired":None,"pre_mean":None,"post_mean":None,"summary_diff":None}
    formula_errors=[]; formula_count=0
    for ws in wbf.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.data_type=='f': formula_count+=1
                if isinstance(c.value,str) and any(e in c.value for e in ['#REF!','#DIV/0!','#VALUE!','#NAME?','#N/A','#NUM!']): formula_errors.append(f"{ws.title}!{c.coordinate}:{c.value}")
    if formula_errors: info["issues"].append(f"수식 오류 문자열 {len(formula_errors)}건")
    info["formula_count"]=formula_count
    if "스마트문화앱" in p.name:
        pre,post=wbv["사전 응답"],wbv["사후 응답"]; hr=1; idc=0; start=3
        info["warnings"].append("응답 시기가 '사전(모의)'·'사후(모의)'로 표시됨")
    elif "네트워크프로그래밍" in p.name:
        pre,post=wbv["사전응답"],wbv["사후응답"]; hr=0; idc=1; start=4
        pre_rows=used_rows(pre,hr,idc); post_rows=used_rows(post,hr,0)
        pre_ids=[str(r[idc]) for r in pre_rows]; post_ids=[str(r[0]) for r in post_rows]
        info.update(pre_n=len(pre_rows),post_n=len(post_rows),paired=len(set(pre_ids)&set(post_ids)))
        pv=[score(x) for r in pre_rows for x in r[start:start+20] if score(x) is not None]
        qv=[score(x) for r in post_rows for x in r[2:22] if score(x) is not None]
        info["pre_mean"]=mean(pv); info["post_mean"]=mean(qv)
        if len(pre_rows)!=len(post_rows): info["issues"].append(f"사전 {len(pre_rows)}명, 사후 {len(post_rows)}명으로 표본 수 불일치")
        if len(set(pre_ids)&set(post_ids))<len(post_rows): info["issues"].append("사전·사후 학생 코드가 완전히 대응하지 않음")
        info["warnings"].append("'수준' 시트가 산출물 기반 사후설문 추정 자료임을 명시")
        results.append(info); continue
    else:
        pre,post=wbv["사전응답"],wbv["사후응답"]
        hr=1; idc=1 if "응용프로그래밍" in p.name else 0; start=3 if "응용프로그래밍" in p.name else 2
    pre_rows=used_rows(pre,hr,idc); post_rows=used_rows(post,hr,idc)
    pre_ids=[str(r[idc]) for r in pre_rows]; post_ids=[str(r[idc]) for r in post_rows]
    info.update(pre_n=len(pre_rows),post_n=len(post_rows),paired=len(set(pre_ids)&set(post_ids)))
    if len(pre_ids)!=len(set(pre_ids)): info["issues"].append("사전 학생 코드 중복")
    if len(post_ids)!=len(set(post_ids)): info["issues"].append("사후 학생 코드 중복")
    if set(pre_ids)!=set(post_ids): info["issues"].append("사전·사후 학생 코드 집합 불일치")
    pv=[score(x) for r in pre_rows for x in r[start:start+20] if score(x) is not None]
    qv=[score(x) for r in post_rows for x in r[start:start+20] if score(x) is not None]
    info["pre_mean"]=mean(pv) if pv else None; info["post_mean"]=mean(qv) if qv else None
    expected=len(pre_rows)*20
    if len(pv)!=expected: info["issues"].append(f"사전 20문항 기준 유효값 {len(pv)}/{expected}")
    expected2=len(post_rows)*20
    if len(qv)!=expected2: info["issues"].append(f"사후 20문항 기준 유효값 {len(qv)}/{expected2}")
    summaries=[s for s in wbv.worksheets if "요약" in s.title]
    if summaries:
        vals=[]
        for row in summaries[-1].iter_rows(values_only=True):
            nums=[x for x in row if isinstance(x,(int,float)) and not isinstance(x,bool)]
            if len(nums)>=3 and 1<=nums[-3]<=5 and 1<=nums[-2]<=5: vals.append((float(nums[-3]),float(nums[-2])))
        if vals:
            sp,sq=mean(x for x,y in vals),mean(y for x,y in vals)
            info["summary_diff"]=(abs(sp-info["pre_mean"]),abs(sq-info["post_mean"]))
            if max(info["summary_diff"])>.002: info["issues"].append(f"원응답 재계산과 요약 평균 불일치: {info['summary_diff']}")
    results.append(info)

doc_checks=[]
for p in sorted(DATA.glob("*.docx")):
    d=Document(p); text="\n".join(x.text for x in d.paragraphs)+"\n"+"\n".join(c.text for t in d.tables for row in t.rows for c in row.cells)
    flags=[w for w in ["모의","추정","예시","미작성","TODO"] if w in text]
    doc_checks.append((p.name,len(d.paragraphs),len(d.tables),", ".join(flags) or "없음"))
for p in sorted(DATA.glob("*.hwpx")):
    try:
        with zipfile.ZipFile(p) as z: text="".join(z.read(n).decode('utf-8','ignore') for n in z.namelist() if n.endswith('.xml'))
        flags=[w for w in ["모의","추정","예시","미작성","TODO"] if w in text]
        doc_checks.append((p.name,"HWPX",len(z.namelist()) if 'z' in locals() else 0,", ".join(flags) or "없음"))
    except Exception as e: doc_checks.append((p.name,"검사 실패",0,str(e)))

media=[p for p in ROOT.rglob('*') if p.suffix.lower() in {'.jpg','.jpeg','.png','.mp4'}]
hashes={}
for p in media:
    h=hashlib.sha256(p.read_bytes()).hexdigest(); hashes.setdefault(h,[]).append(p.name)
dups=[v for v in hashes.values() if len(v)>1]

lines=["# 연구결과 및 효과검증자료 데이터 검증 보고서","",f"검증 대상: `{ROOT}`", "", "## 종합 판정", ""]
fail=sum(bool(x['issues']) for x in results); warn=sum(bool(x['warnings']) for x in results)
lines += [f"- 엑셀 파일 {len(results)}개 중 중대한 정합성 이슈가 있는 파일: **{fail}개**",f"- 자료 성격 또는 해석 주의가 필요한 파일: **{warn}개**",f"- 사진·영상 파일: **{len(media)}개**, 완전 동일 해시 중복 묶음: **{len(dups)}개**","- 현재 상태에서는 모든 교과를 하나의 대응표본 연구효과로 합산하면 안 됩니다.",""]
lines += ["## 엑셀 파일별 검증 결과","", "| 파일 | 사전 N | 사후 N | 대응 N | 사전 평균 | 사후 평균 | 판정 |", "|---|---:|---:|---:|---:|---:|---|"]
for x in results:
    status="FAIL" if x['issues'] else ("WARN" if x['warnings'] else "PASS")
    lines.append(f"| {x['file']} | {x['pre_n']} | {x['post_n']} | {x['paired']} | {x['pre_mean']:.3f} | {x['post_mean']:.3f} | {status} |")
lines += ["", "## 확인된 이슈와 주의사항", ""]
for x in results:
    if x['issues'] or x['warnings']:
        lines.append(f"### {x['file']}")
        for s in x['issues']: lines.append(f"- FAIL: {s}")
        for s in x['warnings']: lines.append(f"- WARN: {s}")
        if x['summary_diff'] is not None: lines.append(f"- 요약 평균 재계산 오차: 사전 {x['summary_diff'][0]:.6f}, 사후 {x['summary_diff'][1]:.6f}")
        lines.append("")
lines += ["## 교사 관찰 기록 형식 점검","", "| 파일 | 문단/형식 | 표/항목 | 모의·추정·예시 표기 |", "|---|---:|---:|---|"]
for a,b,c,d in doc_checks: lines.append(f"| {a} | {b} | {c} | {d} |")
lines += ["", "## 사진 및 영상 증거자료", "", f"- 전체 미디어 파일 수: {len(media)}", f"- 완전 동일 파일 중복 묶음 수: {len(dups)}"]
for d in dups[:20]: lines.append("- 중복: "+", ".join(d))
lines += ["", "## 최종 사용 권고", "", "1. 스마트문화앱의 모의 응답은 실제 연구효과 산출에서 제외합니다.", "2. 네트워크프로그래밍은 사전 67명과 사후 34명의 학생 코드를 먼저 대응시키고, 추정 사후자료와 실제 응답을 분리합니다.", "3. 나머지 34명 설문도 실제 응답인지 담당 교사의 확인 서명을 받습니다.", "4. 보고서에는 교과별 N, 대응 N, 결측 처리, 자료 유형을 함께 표기합니다.", "5. 루브릭 점수와 전문교과 성취도 원자료가 없으므로 해당 성과를 설문 결과로 대체하지 않습니다."]
OUT.write_text("\n".join(lines),encoding="utf-8")
print(json.dumps({"output":str(OUT),"excel_files":len(results),"fail":fail,"warn":warn,"media":len(media),"duplicate_groups":len(dups)},ensure_ascii=False))
