"""Build the report and page-level audited exports from immutable saved results."""
import csv,json,statistics
from pathlib import Path
from evaluate import save,sha
BASE=Path(__file__).resolve().parent;OUT=BASE/'results';AUD=OUT/'audited'
NAMES={'all_inputs':'전체','introduction':'소개서','slides':'슬라이드 전체','intro_prose':'소개서 본문형','intro_bullets':'소개서 소제목·불릿형','slide_bullets':'불릿형 슬라이드','slide_compare':'좌우 비교 슬라이드','slide_results':'화면·그래프 슬라이드'}
def pct(x):return f'{x*100:.2f}%'
def cer(g,k):
    m=g[k];return f"{pct(m['cer'])} ({m['errors']:,}/{m['reference_characters']:,})"
def fact(g,k):
    m=g[k];return f"{pct(m['rate'])} ({m['success']}/{m['total']})" if m['total'] else '— (0/0)'
def main():
    summary=json.loads((AUD/'summary.json').read_text());old=json.loads((OUT/'summary.json').read_text());env=json.loads((OUT/'environment.json').read_text());manifest=json.loads((BASE/'manifest.json').read_text());projects=json.loads((BASE/'sources/projects.json').read_text());groups=summary['groups'];rows=summary['samples'];by={r['id']:r for r in rows}
    first=['| 형식 | 페이지 | CER 공백 포함 | CER 공백 제거 | A 기술명 | B 역할 귀속 | C 성과 수치* | 처리시간 중앙값 |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for k in ['introduction','slide_bullets','slide_compare','slide_results']:
        g=groups[k];first.append(f"| {NAMES[k]} | {g['evaluation_pages']} | {cer(g,'with_whitespace')} | {cer(g,'without_whitespace')} | {fact(g,'technology')} | {fact(g,'roles')} | {fact(g,'metrics')} | {g['median_seconds']:.3f}초 |")
    detailed=['| 집계 | 페이지 | 공백 포함: 편집거리/정답 문자 | 공백 제거: 편집거리/정답 문자 |','|---|---:|---:|---:|']
    for k in NAMES:
        g=groups[k];detailed.append(f"| {NAMES[k]} | {g['evaluation_pages']} | {cer(g,'with_whitespace')} | {cer(g,'without_whitespace')} |")
    states=['| 집계 | B 보존/잘못 연결/누락/판단 불가 | C 보존/잘못 연결/누락/판단 불가* |','|---|---:|---:|']
    for k in ['all_inputs','intro_prose','intro_bullets','slide_bullets','slide_compare','slide_results']:
        g=groups[k];vals=[' / '.join(str(g[c]['states'][s]) for s in ['preserved','mislinked','missing','indeterminate']) for c in ['roles','metrics']];states.append(f'| {NAMES[k]} | {vals[0]} | {vals[1]} |')
    worst=sorted(rows,key=lambda r:r['with_whitespace']['errors'],reverse=True)[:6]
    concentration={'comparison_and_results':{'pages':16,'errors':sum(groups[k]['with_whitespace']['errors'] for k in ['slide_compare','slide_results']),'total_errors':groups['all_inputs']['with_whitespace']['errors']},'top_six_pages':[{'page':r['id'],'errors':r['with_whitespace']['errors'],'reference_characters':r['with_whitespace']['reference_characters'],'cer':r['with_whitespace']['cer']} for r in worst]}
    arrow_pages=[r['id'] for r in rows if '→' in (BASE/r['ground_truth']).read_text() and '→' not in (OUT/r['prediction']).read_text()]
    concentration['arrow_missing_pages']=arrow_pages;save(OUT/'error_concentration.json',concentration)
    # Exact quotes checked against saved prediction, not reconstructed or corrected snippets.
    examples=[
      {'page':'p02_slide_compare','reference':'팀 전체 구현 → 추천 모델을 개발했다 / 내가 맡은 역할 → 데이터 수집 API를 구현했다','prediction':'팀 전체 구현\n내가 맡은 역할\n추천 모델을 개발했다\n데이터 수집 API를 구현했다','interpretation':'마지막 제목인 본인 역할 아래 두 작업이 이어진 것으로 읽으면, 학생이 추천 모델까지 개발했다고 과대평가할 수 있다. 실제로는 팀 모델 개발과 본인 API 구현이 분리된 사실이다. 출력이 명시적으로 소유자를 반전했다고 단정하지 않고 판단 불가로 판정했다.'},
      {'page':'p01_slide_compare','reference':'왼쪽: 예약 화면과 관리자 승인 기능을 개발했다 / 오른쪽: 중복 예약 차단 API와 트랜잭션 처리를 구현했다','prediction':'예약 화면과 관리자 승인 기능을\n중복 예약 차단 API와 트랜잭션 처리를\n개발했다\n구현했다','interpretation':'두 작업의 목적어와 서술어가 열을 가로질러 나열된다. 화면 구현과 트랜잭션 구현을 같은 주체의 작업으로 합치거나 학생의 백엔드 기여를 놓칠 수 있다. 역할 2개 모두 판단 불가다.'},
      {'page':'p09_slide_compare','reference':'컴파일 실패와 실행 시간 초과를 서로 다른\n결과로 반환한다.','prediction':'컴파일 실패와 실행 시간 조과를 서로 다른\n담당자: 임예린\n결과로 반환한다.','interpretation':'초과가 조과로 바뀌고 담당자 줄이 문장 사이에 끼었다. 시간 초과 상태를 구분하는 처리 기능을 키워드 기반 역량 분석에서 놓칠 수 있다. 이 부수 기능은 사전 핵심 168항목 밖이므로 핵심 점수에 새 실패 항목을 추가하지 않았다.'}
    ]
    for e in examples:assert e['prediction'] in (OUT/by[e['page']]['prediction']).read_text()
    save(OUT/'error_examples.json',examples)
    example_lines=[]
    for i,e in enumerate(examples,1):
        example_lines+= [f"{i}. **[{e['page']}](images/{e['page']}.png)** → 원문: {e['reference']} → OCR 출력:", '', '```text',e['prediction'],'```','',e['interpretation'],'']
    paired=[]
    for p in projects:
        intro=by[p['id']+'_intro'];intro_f={f['category']+':'+f['id']:f for f in intro['fact_scores']}
        for r in [x for x in rows if x['project_id']==p['id'] and x['format']=='slide']:
            shared=[f for f in r['fact_scores'] if f['category']+':'+f['id'] in intro_f]
            paired.append({'project':p['id'],'slide':r['id'],'layout':r['layout'],'shared_facts':len(shared),'intro_preserved':sum(intro_f[f['category']+':'+f['id']]['state']=='preserved' for f in shared),'slide_preserved':sum(f['state']=='preserved' for f in shared)})
    save(OUT/'paired_format_comparison.json',paired)
    (AUD/'sample_scores').mkdir(exist_ok=True)
    columns=['id','project_id','layout','status','seconds','cer_with_whitespace','cer_without_whitespace','edit_distance_with_whitespace','reference_characters_with_whitespace','technology_success','technology_total','roles_success','roles_total','metrics_success','metrics_total']
    with (AUD/'scores.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for r in rows:
            save(AUD/'sample_scores'/f"{r['id']}.json",r)
            data={k:r[k] for k in columns[:5]};data.update(cer_with_whitespace=r['with_whitespace']['cer'],cer_without_whitespace=r['without_whitespace']['cer'],edit_distance_with_whitespace=r['with_whitespace']['errors'],reference_characters_with_whitespace=r['with_whitespace']['reference_characters'])
            for cat in ['technology','roles','metrics']:
                fs=[x for x in r['fact_scores'] if x['category']==cat];data[cat+'_total']=len(fs);data[cat+'_success']=sum(x['state']=='preserved' for x in fs)
            writer.writerow(data)
    init=env['model_load_seconds'];total=groups['all_inputs'];conc=concentration['comparison_and_results'];topshare=sum(r['with_whitespace']['errors'] for r in worst)/total['with_whitespace']['errors']
    text=f'''# 학생 프로젝트 합성 자료 ocr-v2 추가 평가

**독립 프로젝트 12개, 평가 페이지 36장.** `ocr_test`의 현재 커밋 `{env['commit']}`에서 실제 서비스 기본 LocalOCR를 실행했다. 아래 CER은 낮을수록 좋으며, 핵심 항목은 높을수록 좋다. 괄호는 CER의 경우 총 편집거리/총 정답 문자 수, A/B/C는 성공 항목 수/평가 항목 수다.

{chr(10).join(first)}

*C는 아래 설명한 **추론 후 채점기 감사 결과**다. 최초 사전 고정 파서는 C를 4/28(14.29%)로 산출했지만 단위 경계 버그 및 방향 표현 처리 한계가 확인되었다. 최초 결과는 `results/summary.json`, 최종 감사 결과는 `results/audited/summary.json`에 모두 보존한다. 정답·이미지·OCR 출력은 바꾸지 않았다. 0/0은 해당 유형에 그 사실을 넣지 않았다는 뜻이다. 문장·레이아웃·글꼴이 함께 달라 순수한 형식 인과효과를 뜻하지 않는다.

## 핵심 결론과 실행 상태

소개서와 한 줄씩 주어를 명시한 불릿 슬라이드는 낮은 CER과 핵심 사실 보존을 보였다. 좌우 역할 비교는 글자가 상당 부분 남아도 두 열이 섞여 **16/16개 역할 귀속이 판단 불가**였다. 결과 슬라이드는 읽기 순서 CER이 높았지만, 지표/전후 값/단위를 설명한 문장 또는 명시적인 개선 전·후 라벨 덕분에 이번 8개 성과 관계는 보존되었다. 그래프 자체를 해석한 점수는 아니다.

- 36/36장 실행, 비어 있지 않은 반환 **36장**, 빈 출력 **0장**, 추론 오류 **0장**. 성공은 텍스트 반환 성공이며 정확한 전사를 뜻하지 않는다.
- 전체 공백 포함 CER **{cer(total,'with_whitespace')}**, 공백 제거 CER **{cer(total,'without_whitespace')}**. 삽입/삭제/치환은 각각 460/635/265, 공백 제거는 333/440/239이다.
- A 기술명 **{fact(total,'technology')}**. C++, C#, Next.js, PostgreSQL 등을 기호·대소문자까지 비교했고 이번 표본에서 기술명 실패는 없었다. 페이지마다 해당 기술명이 한 번 이상 온전히 남는지 평가했다.
- B 역할 귀속 **{fact(total,'roles')}**. 명시적으로 잘못 연결됨 0, 누락 0, 판단 불가 16. 팀 작업을 본인 작업으로 확정해 잘못 읽었다고 주장하지 않는다. 추출 텍스트만으로 안전하게 귀속할 수 없다는 결과다.
- C 성과 관계 **{fact(total,'metrics')}**, 잘못 연결됨/누락/판단 불가 0/0/0(감사 후). 지표명·전후 값·단위·방향이 연결된 사실 단위다. 조건 표본 수 등 부수 숫자는 별도 성과로 세지 않았다.
- 장당 시간 중앙값 **{total['median_seconds']:.3f}초** (최소 {total['min_seconds']:.3f}, 최대 {total['max_seconds']:.3f}). 모델 초기화 **{init:.3f}초**, import {env['import_seconds']:.3f}초, 별도 warmup {env['warmup_seconds']:.3f}초. 모델 초기화/파일 읽기/렌더링/채점은 장당 시간에 포함하지 않는다.
- 실행 시각: 2026-11-10 13:55:13–13:56:27 KST. Apple M4, 16 GB, CPU, torch thread 2 / interop 1. 입력별 한 번의 측정이며 동시 처리량이나 운영 p95가 아니다.

## 표본, 정답, 입력 격리

소개서 본문형 6장과 소제목·불릿형 6장, 슬라이드 각 8장으로 구성했다. 웹·앱·통계 분석·AI·게임·임베디드·검색·시스템 프로젝트를 포함했다. 결과 슬라이드는 막대그래프 5장과 합성 UI 화면 3장이다. UI는 실제 앱을 촬영한 캡처가 아니라 가상 시험 화면을 래스터로 만든 예시다. 두 글꼴(Nanum Gothic, Nanum Myeongjo), 서로 다른 본문/라벨 구성과 색상을 사용했다. 소개서 1240×1754, 슬라이드 1600×900이며 축소·흐림 변형은 없다.

모든 보이는 텍스트와 줄 순서를 `ground_truth/`에, 핵심 기술·기여·성과 168항목을 `key_facts/`에 나누어 저장했다. 좌우 비교는 상단 공통 내용 → 왼쪽 제목/본문 전체 → 오른쪽 제목/본문 전체 순서다. 결과형은 왼쪽 증거 영역 → 오른쪽 설명 순서다. 미표기 그래프 값은 넣지 않았다. 실제 문자 상자 좌표와 읽기 순서도 별도 JSON에 있다.

36개 원본 PNG와 연락판 6개를 실행 에이전트가 직접 시각 검수했다. 글리프 누락·잘림·글자 겹침 검사 0건이며 수정이 필요한 페이지는 없었다. `{manifest['frozen_at_utc']}`에 이미지/정답/핵심 사실/읽기 순서/생성 원문/프로토콜/최초 채점 스크립트 해시를 고정했다. 모델 추론 시작은 그 이후다. 독립 사람 이중 검수는 아니다.

추론에는 `LocalOCR('local').extract('png', image_bytes)`만 호출했다. PDF를 생성하지 않았고 텍스트 레이어도 없다. 생성 원문이나 정답은 OCR 입력 인자로 들어가지 않았으며 채점은 모든 추론이 끝난 뒤 수행했다. 반환 문자열은 그대로 저장했고 Gemini·외부 LLM/API·후처리·모델 튜닝은 사용하지 않았다.

## 이전 실험과 동일한 점 / 달라진 점

이전 커밋은 `46e777ed1a1e180188c0f2ff17384fd58932a780`, 이번 커밋은 `{env['commit']}`다. 이전 evaluate.py의 커밋 고정 실행 함수는 호출하지 않고, 해당 파일의 NFC CER 계산과 micro 집계 코드를 재사용했다. 독립 DP 검증 방식도 새 데이터 전체에 적용했다.

코드/모델 파일 비교에서 바뀐 항목은 **0개**이며 기본 설정도 같다: model=local, orientation=auto, layout=rows, crop_padding=0. torch/torchvision/transformers/Pillow/numpy/OpenCV/PDFium/RapidFuzz 버전도 기존 환경과 같다. 주요 SHA-256:

```text
ai/local/ocr.py
3099cc18827c0720d4e6a64add51b6f31962be0985787fd14bb6bd8dac44fb2b
ai/models/ocr-v2/model.safetensors
0bd0f071a847dd55468333f25b10e4bd9a639c2b492c2540860d4049952d2e6d
ai/models/ocr-detector/model.safetensors
89a96a8adc4e9cd0c994098edc76022e496d35844392562b4694c8fbc583f2da
```

모든 설정/가중치 파일 해시는 `results/environment.json`에 있다. 이번 초기화는 1.788초, 이전은 19.283초였다. 모델/설정은 동일하지만 초기화는 파일 캐시 등 실행 조건에 영향을 받으므로 이를 최적화 성과로 해석하지 않는다. 데이터는 이전의 실제 문서/축소/흐림 혼합과 다르므로 과거 CER과 직접 우열 비교하지 않는다. 이전 평가 폴더 전체의 파일 해시와 서비스 코드/모델 불변을 실행 후와 검증 시 다시 확인했다.

## 세부 CER와 사실 범주

NFC만 적용하며 공백 제거는 `str.isspace()`에 해당하는 문자만 제거한다. 모든 합계는 Σ편집거리/Σ정답 문자 수다. 같은 프로젝트에서 온 세 페이지는 서로 상관된 자료다.

{chr(10).join(detailed)}

{chr(10).join(states)}

역할과 수치에 키워드 포함 여부만 사용하지 않았다. B는 작업 구절과 문장 주어/열 제목의 관계를 판정한다. C는 값/단위/방향을 튜플로 파싱한다. 모든 사실에 상태와 OCR 증거 구절이 있으며, 특히 잘못 연결됨/판단 불가는 원시 출력의 실제 부분 문자열로 검증했다. A/B/C는 주요 선언 사실에 대한 점수이며 부수 서술·모든 등장 횟수·학생의 실제 역량 정확도 전체를 평가하는 지표는 아니다.

같은 프로젝트의 공유 사실만 비교하면 불릿 8장에서는 소개서 48/48, 슬라이드 48/48이었다. 좌우 비교 8장에서는 소개서 40/40, 슬라이드 24/40(기술 24, 역할 0)이었다. 결과 8장에서는 소개서 8/8, 슬라이드 8/8(성과)이었다. 대응 자료는 `results/paired_format_comparison.json`에 있다. 표본을 36개 독립 프로젝트로 확대 해석하지 않는다.

## 수치 채점 감사와 최초 결과 보존

최초 고정 파서의 C는 보존 4, 잘못 연결됨 2, 누락 0, 판단 불가 22였다. 감사 과정에서 p07/p10 결과 페이지의 다음 줄 한국어가 단위 토큰에 붙는 **채점기 버그**를 발견했다. 이 두 건을 실제 OCR 수치 연결 오류로 보고하지 않는다. 또 화살표가 없어도 `420ms 180ms로 감소`처럼 목적지 조사와 방향 술어가 연결된 관계를 최초 파서는 인정하지 않았다. 단순한 `420ms 180ms`와 구별할 필요가 있었다.

원 파일을 고치지 않고 `audit_metrics.py`와 `adjudication_policy.md`를 추가했다. 모든 28개 사실에 동일한 연결 규칙을 적용했고, 24개 판정이 바뀌었다. 긍정/부정 구문 10개(값 반전, 단위 오류, 방향 반전, 숫자만 존재 등)를 확인했다. 감사 후 28/28은 **사후 파서 보완을 거친 의미 보존 점수**이며 사전 등록된 최초 점수와 구분해야 한다. 사후 판단의 확증 편향 가능성은 독립 검수로 검증할 사항이다. 실제 모델 출력은 단 한 번만 생성했다.

화살표가 사라진 페이지는 **{len(arrow_pages)}/28장**이었다. 이 표기 오류는 CER에 남아 있다. 소개서/불릿의 `로 감소/증가`, 결과형의 명시적 전후 라벨 등으로 방향을 복원할 근거가 있어서 의미 보존 점수는 같지 않다. 숫자만 찾았다는 이유로 성공한 항목은 없다. 예를 들어 p12 결과는 `개선 전\n18fps`, `개선 후\n27fps`가 각각 붙어 있고 단일 지표인 영상 처리 속도 범위에 있어 보존으로 판정했다.

감사 전후 모든 판정과 증거는 `results/audited/metric_adjudications.json`, 사용 코드/정책 해시는 `results/audited/provenance.json`에 있다. 최초 및 감사 결과는 모두 재계산 검증을 통과했다. 의미 검증은 규칙 재실행·튜플/증거 확인이며 독립 사람의 자연어 판정과 동등하지 않다.

## 오류 집중과 실제로 관찰된 해석 위험

좌우 비교와 화면·그래프 **16/36장**에 편집거리 **{conc['errors']}/{conc['total_errors']} ({pct(conc['errors']/conc['total_errors'])})**가 집중됐다. 편집거리 상위 6장은 전체 오류의 {pct(topshare)}를 차지했다: {', '.join(r['id']+' '+str(r['with_whitespace']['errors'])+'자' for r in worst)}. 따라서 몇 장만의 우연한 문제라기보다 열/도표 구성 전반의 읽기 순서 문제가 관찰됐다. 기본 `layout=rows`가 원문에서 의도한 열 순서와 다르므로 높은 CER에는 순서 오류가 포함된다. CER 41%를 글자 41%가 각각 오인식됐다는 뜻으로 읽으면 안 된다.

아래는 최대 5개 중 실제 영향이 분명한 3개만 제시한다. 기술명이 틀린 사례나 실제 수치 반전은 관찰되지 않았으므로 만들어 넣지 않았다.

{chr(10).join(example_lines)}
## MVP 적용 판단과 남은 검증

**현재 MVP에 적용할 입력 안내:** 선명한 한 단 소개서(본문형 또는 소제목·불릿형), 그리고 `팀은 …`, `나는 …`를 각 문장에 명시한 제목·불릿 슬라이드를 우선 권장할 수 있다. 이번 범위에서 소개서 CER은 공백 포함 2.12%, 불릿 슬라이드는 2.91%였고 주요 기술·역할·성과가 보존됐다. OCR 초안을 사용자에게 보여 주고 기술명·역할·성과를 확인하는 기존 검토 흐름에 적합하다. 자동 역량 확정까지 검증된 것은 아니다.

**추가 검증/개선이 필요한 입력:** 역할을 열 제목과 좌표만으로 나누는 좌우 비교 슬라이드는 현재 텍스트 출력만으로 역량 귀속에 바로 사용하기 어렵다. 작업 문장에 주어를 반복하게 하거나, 향후 영역/열 구조를 보존하는 추출을 검증해야 한다. 화면·그래프 자료도 읽기 순서 CER 41.34%이므로 일반적인 복합 레이아웃 지원을 확정할 수 없다. 이번에는 단일 지표와 설명 문장이 중복되어 수치 사실을 복원할 수 있었으며, 숫자만 있는 그래프·여러 지표가 섞인 표·작은 실제 앱 화면의 성능은 입증하지 않았다. 중요한 성과는 지표·전후 값·단위·증가/감소를 같은 문장으로 병기하는 입력 형식이 적절하다.

모든 결과는 합성 프로젝트 12개, 두 글꼴, 제한된 레이아웃에서 나왔다. 실제 학생의 자연스러운 문장/생략된 주어/복잡한 표/수식/코드/브랜드 글꼴/사진 촬영/스캔/낮은 대비/압축된 캡처는 별도로 검증해야 한다. 같은 프로젝트 페이지의 반복 사실은 독립 표본이 아니다. 특히 C=100%는 실제 학생 자료의 100% 정확도 보증이 아니며 사후 감사 파서를 독립 검수해야 한다. 기존 OCR이나 Gemini를 이번 자료에서 비교 실행하지 않았으므로 우수하다고 결론 내리지 않는다.

## 저장 경로와 재실행

평가 루트: `data/evaluation/ocr-v2-student-projects-20261110/`.

- 데이터: `images/`, `ground_truth/`, `key_facts/`, `sources/projects.json`, `manifest.json`.
- 실제 추론과 원시 출력: `evaluate.py`, `results/predictions/`, `results/inference_records/`, `logs/inference.log`.
- 최초 점수: `results/scores.csv`, `results/sample_scores/`, `results/summary.json`.
- 보고서에 사용한 감사 후 페이지 점수: `results/audited/scores.csv`, `results/audited/sample_scores/`, `results/audited/summary.json`, `results/audited/fact_scores.jsonl`.
- 검증: `verify_metrics.py`, `verify_audit.py`, 두 `verification.json` 파일.
- 보고서: `REPORT.md` (생성: `report.py`), 안내/의존성: `README.md`, `requirements.lock.txt`.

저장소 루트에서, 기존 결과를 덮어쓰지 않는 새 출력 폴더로 실행한다.

```sh
EVAL_DIR=data/evaluation/ocr-v2-student-projects-20261110
OCR_PY=/private/tmp/team18-ocr-v2-env/bin/python
PYTHONDONTWRITEBYTECODE=1 "$OCR_PY" "$EVAL_DIR/evaluate.py" --output "$EVAL_DIR/results-rerun-01"
PYTHONDONTWRITEBYTECODE=1 "$OCR_PY" "$EVAL_DIR/verify_metrics.py" --results "$EVAL_DIR/results-rerun-01"
PYTHONDONTWRITEBYTECODE=1 "$OCR_PY" "$EVAL_DIR/audit_metrics.py" --results "$EVAL_DIR/results-rerun-01"
PYTHONDONTWRITEBYTECODE=1 "$OCR_PY" "$EVAL_DIR/verify_audit.py" --results "$EVAL_DIR/results-rerun-01"
```

저장 점수만 확인하려면 `verify_metrics.py`와 `verify_audit.py`를 옵션 없이 실행한다. 임시 가상환경이 없으면 Python 3.12 환경에 `requirements.lock.txt`를 설치하고 실행 경로를 바꾼다. 코드·모델 해시 차이는 재실행 환경에 기록되며 입력/정답 변경은 거부한다. 이번 작업에서 서비스 코드 변경, 커밋, 푸시는 하지 않았다.
'''
    (BASE/'REPORT.md').write_text(text,encoding='utf-8')
    print('Wrote REPORT.md, audited page scores, paired comparison and exact error examples.')
if __name__=='__main__':main()
