# 서울과기대 CSV 동작 시험

사용자가 제공한 CSV 68행(sha256 `9b511b63700f29e89c51c7662d4ae2736b72ba67b6400d03d3f50dea8dc6f16e`)과 E5 FP32 ONNX를 사용한 수동 스모크 테스트다. CSV에는 설명과 실제 과목 ID가 없다. `prepare.py`의 이름 기반 가설 태그는 **미검토**이며 58행에 과목당 최대 5개 범위로 태그를 붙이고 내용이 불명확한 10행은 보류했다. 23행은 1개, 26행은 2개, 8행은 3개, 1행은 4개다. 100개 진로 예시를 참고해 역량 사전을 41개로 확장했다. 4개 직무 및 우선순위도 시험용 가설이다. 과목명과 관련될 가능성이 있는 추가 태그는 실제 수업에서 다루는지 미확인이다. 제목 중심 태그는 1.0, 추가 가설은 0.5로 표시했지만 둘 다 강의계획서 검토가 필요하다. 예를 들어 데이터베이스 과목의 SQL 교육 여부는 원문이 없어 태깅하지 않았다. 새 과목명에 자동으로 태그를 생성하는 기능은 아직 없으며, 현재 매핑은 `prepare.py`에 직접 작성했다.

`csv-row-NNN`은 CSV 행 순서에만 유효한 임시 ID다. 사용자가 같은 내용을 배우는 한국어·영어 수업이라고 확인한 16개 과목 쌍을 명시적으로 묶었다. 추천에는 각 묶음의 한국어 행을 우선 반환하고, 어느 언어의 행을 이수해도 묶음 전체를 제외한다. 실제 과목 ID가 없으므로 이 관계는 CSV 행 ID에만 유효하다. 실제 과목 ID와 원문으로 연결한 후 목록·태그를 검토해야 한다.

모델 revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`; 임계값 0.9/0.9/0.05/0.01은 임시값이며 측정으로 확정하지 않았다. `results.json`은 10개 수동 입력의 출력이며 사람의 정답·추천 품질 점수가 아니다. 자연어 데이터 분석 목표에서 직무 선택 없이 `no_match`, SQL 목표에서 관련 과목 태그가 없어 `no_match`, 범위 밖 우주 비행사 목표에서 `no_match`가 관찰됐다. 백엔드 테스트에서 데이터베이스의 한국어 또는 영어 행을 이수로 선택하면 두 행 모두 제외된다. 점수는 임시 태그 가중합이지 정확도나 적합 확률이 아니다. 과목 이름과 태그를 함께 보려면 생성된 `artifacts/seoultech-data/course_tags_review.csv`를 확인한다.

저장소 루트에서, README의 모델 준비 후 재현:

```sh
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/evaluation/seoultech-2026/prepare.py
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/scripts/build_bundle.py --model modules/course-recommendation/artifacts/model --data modules/course-recommendation/artifacts/seoultech-data --output modules/course-recommendation/artifacts/seoultech-bundle --version seoultech-test-v4
modules/course-recommendation/artifacts/.venv/bin/python modules/course-recommendation/evaluation/seoultech-2026/run.py
```

CSV가 변경되면 행별 매핑의 잘못된 적용을 막기 위해 준비 스크립트가 중단된다. 실제 강의 설명·ID와 사용자 확인, 직무표, 임계값, 부정 표현, 별도 평가셋에 대한 검토가 필요하며 이 결과는 운영에 연결하지 않는다.
