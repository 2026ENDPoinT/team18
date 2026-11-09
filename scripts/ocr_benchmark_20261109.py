"""Read-only comparison of the committed OCR recognizer and original Qota-OCR."""
import csv, hashlib, io, json, os, re, sys, time, unicodedata, urllib.request
from collections import defaultdict
from pathlib import Path
import torch
from PIL import Image, ImageDraw, ImageFont
from huggingface_hub import hf_hub_download, snapshot_download
import pypdfium2 as pdfium
sys.path.insert(0, str(Path("ai").resolve()))
from local.ocr import LocalOCR, MAX_PIXELS

torch.set_num_threads(2)
out=Path("ocr-benchmark-results"); out.mkdir(exist_ok=True)
snapshot_download("atonlee/Qota-OCR", local_dir="ai/models/qota-ocr", allow_patterns=["*.json","*.safetensors"])
font_path=out/"NanumGothic-Regular.ttf"
urllib.request.urlretrieve("https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf", font_path)
phrases=[
"서울과학기술대학교 컴퓨터공학과", "프로젝트명: 개인화 진로 로드맵",
"담당 역할: 백엔드 API 구현", "Python으로 데이터를 정리했습니다.",
"React와 JavaScript로 화면 구현", "학점 3.75 / 4.5, 취득 70학점",
"2026.11.09 ~ 2026.12.06", "모집 마감: 11월 30일 23:59",
"자료구조, 알고리즘, 인공지능개론", "팀원 3명 중 서버 개발 담당",
"사용자 인터뷰 12건을 진행함", "정확도 85.2%, 응답시간 120ms",
"GitHub: team18 / branch: main", "SQL JOIN과 REST API를 활용",
"테스트 24건 중 22건 통과", "선수과목: 프로그래밍입문(1)",
"이메일: student@example.com", "장학금 신청서 및 재학증명서",
"오류: 파일을 읽을 수 없습니다.", "데이터 분석가를 목표로 합니다."
]
def distance(a,b):
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt=[i]
        for j,y in enumerate(b,1): nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=nxt
    return row[-1]
def norm(s): return re.sub(r"\s+","",unicodedata.normalize("NFKC",s)).casefold()
samples=[]
for size in [24,32]:
    font=ImageFont.truetype(str(font_path),size)
    for text in phrases:
        box=font.getbbox(text)
        im=Image.new("RGB",(box[2]-box[0]+20,box[3]-box[1]+16),"white")
        ImageDraw.Draw(im).text((10-box[0],8-box[1]),text,font=font,fill="black")
        samples.append((text,size,im))
repo="ONTHEIT/KDoc-OCRBench-V2"; data=out/"dataset"
paths={name:Path(hf_hub_download(repo,name,repo_type="dataset",local_dir=data)) for name in ["licenses.csv","categories.jsonl","text_present.jsonl"]}
with paths["licenses.csv"].open(encoding="utf-8-sig",newline="") as f: licenses={r["filename"]:r for r in csv.DictReader(f)}
categories=[json.loads(line) for line in paths["categories.jsonl"].read_text(encoding="utf-8").splitlines() if line.strip()]
tests=defaultdict(list)
for line in paths["text_present.jsonl"].read_text(encoding="utf-8").splitlines():
    if not line.strip(): continue
    row=json.loads(line); text=row.get("text") or ""
    if row.get("checked")=="verified" and row.get("page")==1 and 8<=len(text)<=60: tests[row["pdf"]].append(row)
chosen=[]
for category in ["Notices","Manuals","Reports"]:
    matches=sorted(x["pdf"] for x in categories if x["category"]==category and x["pdf"] in licenses and len(tests[x["pdf"]])>=8)
    for index in [2,3]:
        name=matches[index]
        path=hf_hub_download(repo,"pdfs/"+name,repo_type="dataset",local_dir=data)
        chosen.append((category,index,name,path,tests[name][:8]))
report={"source_commit":"46e777ed1a1e180188c0f2ff17384fd58932a780","device":"cpu","torch":torch.__version__,"threads":2,
"synthetic_method":"20 fixed new phrases x font sizes 24,32; Nanum Gothic; direct line recognition, exact CER includes whitespace",
"real_method":"first-page NFKC/casefold/whitespace-normalized exact presence of 8 verified phrases; NOT full-page accuracy or CER",
"orientation":"auto for both models","selection":"sorted eligible index 2 (previous final) and 3 (additional) for each of 3 categories",
"dataset":repo,"dataset_metadata_sha256":{k:hashlib.sha256(p.read_bytes()).hexdigest() for k,p in paths.items()},
"results":[]}
for provider in ["open-source","local"]:
    started=time.perf_counter(); engine=LocalOCR(provider,orientation="auto")
    load_seconds=time.perf_counter()-started
    print(json.dumps({"event":"model_loaded","model":provider,"seconds":load_seconds}),flush=True)
    line_rows=[]; errors=chars=exact=0
    started=time.perf_counter()
    with torch.inference_mode():
        for text,size,im in samples:
            ts=time.perf_counter()
            inputs=engine.rp(images=im,return_tensors="pt")
            prediction=engine.rp.post_process_text_recognition(engine.rm(**{k:v.to(engine.device) for k,v in inputs.items()}))[0]["text"]
            e=distance(text,prediction); errors+=e; chars+=len(text); exact+=int(text==prediction)
            line_rows.append({"source":text,"font_size":size,"prediction":prediction,"edit_distance":e,"seconds":time.perf_counter()-ts})
    synthetic={"samples":len(samples),"exact_matches":exact,"exact_match_rate":exact/len(samples),"character_error_rate":errors/chars,"seconds":time.perf_counter()-started,"details":line_rows}
    print(json.dumps({"event":"synthetic_done","model":provider,**{k:v for k,v in synthetic.items() if k!="details"}},ensure_ascii=False),flush=True)
    real=[]
    for category,index,name,path,items in chosen:
        doc=pdfium.PdfDocument(path); page=doc[0]
        try:
            w,h=page.get_size(); scale=min(2.,(MAX_PIXELS/(w*h))**.5)
            im=page.render(scale=scale).to_pil().copy()
        finally: page.close(); doc.close()
        ts=time.perf_counter(); extracted=engine.read_image(im); seconds=time.perf_counter()-ts
        checks=[{"text":r["text"],"passed":norm(r["text"]) in norm(extracted)} for r in items]
        result={"category":category,"index":index,"subset":"previous_final" if index==2 else "additional","document":name,"checks":checks,"passed":sum(x["passed"] for x in checks),"total":len(checks),"seconds":seconds,"source":licenses[name],"extracted_text":extracted}
        real.append(result)
        print(json.dumps({"event":"page_done","model":provider,**{k:v for k,v in result.items() if k not in ["checks","source","extracted_text"]}},ensure_ascii=False),flush=True)
    report["results"].append({"model":provider,"load_seconds":load_seconds,"synthetic":synthetic,"real":real})
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    del engine
print("BENCHMARK_COMPLETE",flush=True)
