# Auto Fishing Macro v2

`recovered_project`를 보존한 채 정확도와 성능을 개선한 실험 버전입니다.

## 주요 변경

- 초록/노란 막대 검출을 단순 색상 중심에서 형태 기반 connected component 선택으로 변경
- 사용자가 직접 캡처한 입질/성공 참조 이미지 기반 감지 적용
- 감지 영역 union 캡처 적용
- Tkinter 상태 업데이트를 `root.after()` 경로로 정리
- `디버그 보기` 기능 추가
- `analyze_examples.py` 오프라인 분석 스크립트 추가
- `custom2kinter` 기반 modern UI와 DPI 대응 레이아웃 적용
- 영역 선택 ESC 취소, 저장 toast, overlay 종료 흐름 개선
- 운영 대시보드형 UI, 감지 영역 설정 상태 카드, 슬라이더 기반 기본 튜닝 적용
- `디버그 보기`를 별도 창 대신 메인 UI 내장 패널로 표시
- 감지 설정 기본값 초기화와 디버그 이미지 비율 유지 표시 적용
- 설정한 시간 동안 감지되는 이미지가 없을 때 F를 한 번 누르는 복구 옵션 추가
- 무감지 복구 횟수 표시와 매크로 루프 MSS 전용 캡처 적용
- 영어/중국어 간체/한국어/일본어 UI 선택과 주요 기능 툴팁 추가
- 기술적인 영역/이미지 용어를 사용자용 `감지 영역`/`캡처 이미지`로 정리
- 입질/성공 정확도 기본값을 `0.65`로 조정하고, `?` 도움말은 hover와 click 모두 지원
- 감지 영역 도움말에 낚시바/입질/성공 캡처 예제 이미지를 표시
- 기존 `bite_template.png`, `success_template.png`, `success_templates.png` 파일이 있으면 캡처 이미지 fallback으로 사용
- 현재 감지 영역을 화면 위 색상 박스로 확인하는 `위치 확인` 기능 추가

## 실행

```powershell
python -m pip install -r requirements.txt
python main.py
```

입질/성공 감지는 사용자가 앱에서 직접 캡처한 이미지를 우선 사용합니다. 캡처 이미지는 `reference_images/` 폴더에 저장됩니다. 캡처 이미지가 없으면 호환용으로 `bite_template.png`, `success_template.png`, `success_templates.png`를 순서대로 찾아 사용합니다.

감지 영역 툴팁의 예제 이미지는 `assets/capture_examples/`에 포함되어 있습니다.

`위치 확인` 버튼을 누르면 메인 창을 잠시 숨긴 뒤 현재 화면 위에 낚시바/입질/성공 감지 영역을 색상 박스로 표시합니다. 이 기능은 확인 전용이며 설정 파일을 바꾸지 않습니다.

## 오프라인 분석

루트 폴더에서 실행:

```powershell
python auto_fishing_v2/analyze_examples.py --save-debug
```

결과 이미지는 `auto_fishing_v2/debug_outputs/`에 저장됩니다.

## 캡처 벤치마크

```powershell
python auto_fishing_v2/benchmark_capture.py
```

`mss`가 사용 가능하면 PyAutoGUI보다 높은 캡처 FPS가 출력됩니다. 런타임 매크로 캡처는 `mss` 전용이며, 실패하면 PyAutoGUI로 전환하지 않고 상태 영역에 오류를 표시한 뒤 재시도합니다.
