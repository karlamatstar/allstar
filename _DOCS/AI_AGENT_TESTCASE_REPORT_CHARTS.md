# AI 에이전트 테스트케이스 보고서 그래프

> 작성일: 2026-07-17
> 대상: `_OUTPUT/reports/ai_agent/batch/final_quality_report.md`
> 상태: 구현·기존 6건 결과 재생성·시각 검증 완료

## 1. 목적

`AI 챗봇 품질관리 최종 비교 보고서`의 표와 상세 목록보다 앞에서 전체 품질 차이를 빠르게 파악할 수 있도록 데이터 기반 PNG 그래프를 추가한다. VOC 테스트케이스 정식 보고서와 같은 한글 글꼴·색상·PNG 저장 방식을 사용하되 AI 보고서가 가진 규칙 기반·API 기반 비교 데이터에 맞게 항목을 구성한다.

## 2. 그래프 구성

1. `case_score_comparison.png`
   - 테스트케이스별 규칙 기반·API 기반 총점 비교
   - 25점 만점
   - N/A는 0점이나 FAIL로 표시하지 않고 점수 막대에서 제외
2. `quality_axis_average.png`
   - 정확성·근거성·유용성·안전성·이해가능성 평균점수 비교
   - 항목별 5점 만점
   - PASS·REVIEW·FAIL처럼 실제 채점 가능한 결과만 평균에 포함
3. `decision_distribution.png`
   - 모델별 PASS·REVIEW·FAIL·N/A 건수 비교
   - N/A를 FAIL과 별도로 표시

보고서의 `3. 품질 결과 그래프`에 위 순서로 표시하고, 케이스 상세와 종합 요약은 그 아래에 둔다.

## 3. 최신본과 이력본

```text
_OUTPUT/reports/ai_agent/batch/
├─ final_quality_report.md
├─ assets/
│  ├─ case_score_comparison.png
│  ├─ quality_axis_average.png
│  └─ decision_distribution.png
└─ history/
   ├─ {실행시각}_final_quality_report.md
   └─ assets/{실행시각}/*.png
```

- 최신 그래프는 고정 파일명으로 덮어쓴다.
- 이력 보고서는 실행 시각별 그래프 폴더를 사용해 당시 보고서와 이미지 연결을 보존한다.
- 기존 `evaluation_result.json`으로 보고서를 재생성할 때 외부 AI API를 다시 호출하지 않는다.

## 4. 글꼴과 화면 표시

- Windows에서는 맑은 고딕, Docker Linux에서는 Noto Sans CJK를 우선 사용한다.
- Markdown 상대 이미지 경로를 통합 대시보드가 실제 로컬 PNG로 해석한다.
- Markdown에 선언된 위치에서 이미지를 표시하고 하단에 같은 이미지를 중복 출력하지 않는다.

## 5. 검증 결과

- 대표 목 데이터로 최신본·이력본 PNG 각 3개와 Markdown 상대 경로를 자동 검증했다.
- 기존 6개 AI 테스트케이스 결과 JSON으로 최신 보고서를 실제 재생성했다.
- 세 PNG의 한글 제목·부제·범례·축 이름과 규칙 기반·API 기반 막대를 직접 확인했다.
- 외부 AI 호출 파일을 제외한 전체 비API 회귀 `214개`가 통과했다.
- 외부 AI API는 호출하지 않았다.
