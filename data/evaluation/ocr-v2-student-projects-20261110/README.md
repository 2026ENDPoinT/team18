# 학생 프로젝트 소개서·발표자료 OCR 평가

독립 프로젝트 12개, 평가 페이지 36장. 원 실험 `../ocr-v2-20261110/`을 보존한 추가 실험이다. 결과와 해석은 `REPORT.md`에 기록한다.

- 소개서: 본문형 6장, 소제목·불릿형 6장, 1240×1754 PNG.
- 슬라이드: 제목·불릿형 8장, 좌우 역할 비교형 8장, 화면·그래프 결과형 8장, 1600×900 PNG.
- 결과형 8장에는 막대그래프 5장과 합성 UI 화면 3장이 포함된다. 합성 UI는 실제 앱을 촬영한 화면이 아니다.
- 정답·이미지·읽기 순서·핵심 사실·채점 스크립트는 추론 전에 고정했다. `manifest.json`의 SHA-256과 `qa/visual_review.json` 참조.
- 실제 서비스 LocalOCR 기본 설정. Gemini·외부 LLM 채점·후처리·튜닝 없음. 원시 출력은 서비스가 반환한 문자열 그대로다.

## 저장 위치

| 경로 | 내용 |
|---|---|
| `sources/projects.json` | 가상 학생 프로젝트 12개의 생성 원문 |
| `sources/fonts/` | 두 글꼴과 OFL 라이선스 |
| `prepare.py` | 입력 PNG, 정답, 읽기 순서, 핵심 사실 생성 및 고정 |
| `images/*.png` | 추론에 실제 사용한 36개 원본 이미지 |
| `ground_truth/*.txt` | 화면에 보이는 전체 텍스트, 의도한 읽기 순서 |
| `ground_truth/*.reading_order.json` | 영역별 읽기 순서, 줄별 텍스트·좌표·글자 크기 |
| `key_facts/*.json` | 기술명, 팀/본인 역할, 성과 전후 관계의 사전 정의 |
| `protocol.md`, `manifest.json` | 사전 채점 기준 및 고정 해시 |
| `evaluate.py` | 실제 추론, 시간 측정, 기존 CER 재사용, 사실 채점 |
| `score_facts.py` | 외부 LLM 없이 소유자·지표 관계를 파싱하는 고정 규칙 |
| `verify_metrics.py` | 저장 출력에서 독립 DP CER·집계·해시 재검증 |
| `results/predictions/` | 가공하지 않은 OCR 문자열 |
| `results/inference_records/` | 원 반환값, 상태, 시간, 예외, 출력 해시 |
| `results/sample_scores/`, `results/scores.csv` | 페이지별 CER·사실 점수·시간 |
| `results/fact_scores.jsonl` | 사실별 4범주 판정과 실제 OCR 증거 구절 |
| `results/summary.json` | 전체, 소개서, 슬라이드, 세부 형식, 프로젝트별 집계 |
| `results/environment.json` | 현재 커밋, 코드/모델 해시, 기본값, 패키지, 이전 실험과 차이 |
| `results/verification.json` | 재계산 검증 결과 |
| `qa/`, `logs/` | 렌더링 검수와 실제 실행 로그 |

## 재실행

저장된 36장을 다시 추론한다. 저장 결과를 덮어쓰지 않도록 존재하지 않는 결과 디렉터리를 지정해야 한다. 저장소 루트에서:

```sh
EVAL_DIR=data/evaluation/ocr-v2-student-projects-20261110
OCR_PY=/private/tmp/team18-ocr-v2-env/bin/python
PYTHONDONTWRITEBYTECODE=1 "$OCR_PY" "$EVAL_DIR/evaluate.py" --output "$EVAL_DIR/results-rerun-01"
PYTHONDONTWRITEBYTECODE=1 "$OCR_PY" "$EVAL_DIR/verify_metrics.py" --results "$EVAL_DIR/results-rerun-01"
```

현재 저장된 점수만 재검증할 때:

```sh
PYTHONDONTWRITEBYTECODE=1 /private/tmp/team18-ocr-v2-env/bin/python data/evaluation/ocr-v2-student-projects-20261110/verify_metrics.py
```

임시 가상환경이 없으면 Python 3.12 가상환경에 `requirements.lock.txt`를 설치하고 `OCR_PY`를 바꾼다. `ai/models/ocr-v2`와 `ai/models/ocr-detector`의 로컬 파일이 필요하다. 인터넷 없이 실제 모델을 로드하도록 강제하며 모델 파일을 자동 다운로드하지 않는다. CPU/CUDA 선택은 서비스 코드에 따른다.

생성기는 고정 manifest 또는 결과가 있는 폴더의 변경을 거부한다. 원문을 변경한 새 실험을 만들 때는 `data/evaluation/` 아래 새 폴더에 스크립트·프로토콜·sources만 복사하고 `prepare.py` → 36장 시각 검수 기록 → `prepare.py --freeze` 순으로 진행한다. 이미 채점한 이미지/정답을 바꾸는 용도로 사용하지 않는다.

## 해석 범위

각 프로젝트의 세 페이지는 일부 사실을 공유한다. 페이지별/사실별 분모는 독립 학생 수가 아니다. 합성 자료 12개 프로젝트와 두 글꼴, 제한된 구성에 대한 결과이며 실제 학생 문서, 복잡한 앱 화면, 사진·스캔·손글씨·수식·복잡한 표는 별도 검증이 필요하다. 규칙 기반 사실 채점은 보수적이며 독립 사람 이중 검수를 대체하지 않는다. 기존 OCR/Gemini 비교 실험은 수행하지 않았다.

## 최종 보고서의 수치 채점 감사

`results/`는 최초 사전 고정 채점 결과를 보존한다. 최초 수치 파서에서 단위 경계 버그와 방향 표현 누락이 발견되어, 원문·정답·OCR 출력은 유지한 채 별도의 감사 결과를 만들었다. 보고서의 C 점수와 최종 페이지별 점수는 `results/audited/`를 사용한다. 사후 보완 사실과 최초 4/28, 감사 후 28/28의 차이는 `adjudication_policy.md` 및 `results/audited/metric_adjudications.json`에 공개했다.

재추론 결과에 같은 감사를 적용하려면 위 명령 다음에 실행한다.

```sh
PYTHONDONTWRITEBYTECODE=1 "$OCR_PY" "$EVAL_DIR/audit_metrics.py" --results "$EVAL_DIR/results-rerun-01"
PYTHONDONTWRITEBYTECODE=1 "$OCR_PY" "$EVAL_DIR/verify_audit.py" --results "$EVAL_DIR/results-rerun-01"
```

현재 저장된 최종 감사 결과는 `verify_audit.py`를 옵션 없이 실행해 검증한다. `report.py`는 현재 `results/audited/summary.json`에서 보고서·최종 CSV·페이지별 JSON·형식 간 대응 비교를 생성한다. 외부 LLM은 호출하지 않는다.
