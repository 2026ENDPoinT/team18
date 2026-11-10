# ocr-v2 독립 OCR 실측

대상: `2026ENDPoinT/team18`, `ocr_test`, `46e777ed1a1e180188c0f2ff17384fd58932a780`.
이 디렉터리만 추가했다. 서비스 코드, 모델, Git 브랜치·커밋·원격 저장소는 변경하지 않았다.

## 재실행

저장소 루트에서 아래 명령을 실행한다. 평가 폴더 자체는 커밋하지 않았으므로 다른 체크아웃에는 이 폴더를 먼저 복사해야 한다. 원본 가중치가 해당 커밋의 `ai/models/ocr-v2`, `ai/models/ocr-detector`에 있어야 한다. 디스크에서 `AI`로 보이기도 하나 Git 경로는 소문자 `ai`다. 대소문자를 구분하는 환경에서는 Git 경로를 유지한다.

```bash
git rev-parse HEAD
python3.12 -m venv /tmp/team18-ocr-v2-env
/tmp/team18-ocr-v2-env/bin/python -m pip install -r data/evaluation/ocr-v2-20261110/requirements.lock.txt
PYTHONDONTWRITEBYTECODE=1 /tmp/team18-ocr-v2-env/bin/python data/evaluation/ocr-v2-20261110/evaluate.py --output /tmp/team18-ocr-v2-rerun
/tmp/team18-ocr-v2-env/bin/python data/evaluation/ocr-v2-20261110/verify_metrics.py --results /tmp/team18-ocr-v2-rerun
```

위 `--output`은 아직 존재하지 않는 경로여야 한다. 기존 측정 결과를 덮어쓰지 않는다. 현재 머신의 가상환경 실제 경로는 `/private/tmp/team18-ocr-v2-env`이다. 패키지 설치에만 네트워크를 사용하며 추론은 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `local_files_only=True`로 실행한다. Gemini 키는 필요하지 않다. 다른 장치·라이브러리 버전의 실행시간/일부 인식 결과는 달라질 수 있다.

측정에는 이미 검수·고정된 `manifest.json`의 PNG와 정답을 사용한다. PDF 파일, 벤치마크 부분 정답, PDF 디지털 텍스트 참고 파일은 추론 스크립트에서 읽지 않는다. Python 런타임 import와 모델 초기화/준비 시간은 `results/environment.json`에 따로 기록한다.

## 입력 재생성

`prepare.py`가 고정 원문 JSON, 공개 한글 폰트, 원 PDF로 PNG를 생성한다. `prepare.py --freeze`는 시각 검수 기록과 이미지/정답 해시를 고정한다. 결과가 존재하는 폴더에서는 입력 재생성을 거부한다. 이미지 생성 코드의 검수는 `qa/render_checks.json`, 시각 검수는 `qa/visual_review.json`에 있다. 재측정에는 재생성보다 포함된 해시 고정 PNG를 그대로 사용하는 것이 적절하다.

실제 정답은 PDF 원문 디지털 텍스트를 참고하고 렌더링을 직접 보면서 표의 순서·공백·줄바꿈을 정리했다. 데이터셋의 OCR/LLM 부분 정답을 전사 정답으로 사용하지 않았고 평가 모델의 출력도 보지 않은 상태에서 정답을 고정했다. 사람 이중 검수가 아니므로 실제 문서 전사의 잔여 오류 가능성은 있다. 자세한 규칙은 `protocol.md`를 참조한다.

## 파일

| 경로 | 내용 |
|---|---|
| `REPORT.md` | 실측 결과와 해석 |
| `evaluate.py` | 원 서비스 OCR 호출, 시간 측정, NFC CER, I/D/S 집계 |
| `verify_metrics.py` | 독립 DP 구현으로 모든 저장 점수 검증 |
| `prepare.py` | PDF 이미지화, 고정 합성 문서 렌더링 |
| `manifest.json` | 원본/변형 구분, 정답·이미지 SHA-256 |
| `ground_truth/<original_id>.txt` | 샘플별 독립 정답. 변형본은 원본의 정답 공유 |
| `images/<sample_id>.png` | 실제 입력 이미지 |
| `results/predictions/<sample_id>.txt` | 보정 없는 실제 OCR 출력 |
| `results/sample_scores/<sample_id>.json` | 샘플별 CER·I/D/S·시간·상태 |
| `results/scores.csv` | 샘플별 점수 표 |
| `results/summary.json` | micro 집계와 전체 샘플 점수 |
| `results/environment.json` | 장치·버전·시간 정의·모델/코드 해시 |
| `results/verification.json` | 점수 교차검증 결과 |
| `data_audit.json` | 기존 평가·학습과의 중복 점검 및 한계 |
| `sources/real_sources.json` | 실제 PDF의 고정 URL·출처·해시·이용조건 |
| `sources/synthetic_sources.json` | 렌더링 전에 작성한 합성 원문 |
| `logs/` | 설치, 초기 메타데이터 수집 실패, 최종 추론 원문 로그 |

## 출처

실제 PDF: [ONTHEIT/KDoc-OCRBench-V2](https://huggingface.co/datasets/ONTHEIT/KDoc-OCRBench-V2), revision `e94ba5be6b3c6ec4fed85b0789fc73395f6930fb`에서 3쪽만 사용. 출처 기관은 제주특별자치도교육청, 한국산업기술시험원, 국가공무원인재개발원이다. 개별 원문 URL 및 이용허락범위 제한없음 표시는 `sources/real_sources.json`에 보존했다. 이 평가 점수는 해당 벤치마크의 공식 점수가 아니다. 부분 정답 파일은 과거 평가 샘플 선택과의 중복 확인에만 이용했다.

합성 글꼴: Google Fonts 배포 Nanum Gothic / Nanum Myeongjo, SIL Open Font License. 폰트와 해당 OFL 문서를 `sources/fonts/`에 포함했다. AI 이미지 생성기는 사용하지 않고 Pillow로 확정 원문을 렌더링했다.

## 준비 중 복구한 문제

1. 기본 샌드박스에서 pip 다운로드는 DNS 제한으로 실패했다. 승인된 네트워크 설치로 동일 의존성을 `/private/tmp`의 전용 가상환경에 설치하여 해결했다. `logs/install.log`, `logs/install-network.log` 참조.
2. 첫 평가 시작 시 하드웨어 정보 수집용 `sysctl -n machdep.cpu.brand_string`이 샌드박스에서 거부되어 모델/샘플 추론 전에 중단됐다. 평가 스크립트의 메타데이터 수집만 실패 허용 `system_profiler` 방식으로 바꾸었다. `logs/startup-failure.log` 참조. 서비스 코드와 모델은 수정하지 않았다. 이 준비 실패는 장당 추론 오류 건수에 포함되지 않는다.
