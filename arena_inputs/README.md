# Arena 입력 파일 (교차로 15+16 연동 코리더, Tier 1)

Arena 모델에 **직접 쓰이는 파일만** 모은 폴더입니다. (원본은 `../data_processed/`에 있고,
이 폴더는 복사본입니다. 재생성은 `src/13~16` 스크립트.)

모델 구성 지침: [../reports/arena_model_guideline.md](../reports/arena_model_guideline.md)

| 파일 | Arena 모듈 | 용도 |
| --- | --- | --- |
| `leg_arrival_5min.csv` | **Create** | leg별 5분 단위 도착률 (Schedule 입력) |
| `leg_arrival_signal_bridge.csv` | **Assign (Turn)** | leg별 회전비율(`ratio_left/straight/right`) → DISC |
| `vehicle_type_ratio.csv` | **Assign (VehType)** | 차종 비율 → DISC + Entity Picture |
| `signal_schedule_arena.csv` | **Hold (신호 로직)** | 이동류별 녹/적 토글 이벤트 → `Green[movement]` |
| `leg_service_params.csv` | **Process** | 이동류별 차로수(자원 cap)·서비스시간(1.9s) |
| `layout_coords.csv` | **Station (애니)** | Station 화면 좌표(축척) |
| `layout_routes.csv` | **Route (애니)** | 진입/진출 Route 주행시간 |
| `validation_targets.csv` | **검증** | 통과량·속도·지체·대기행렬 기준값 |

- movement key = `inter_id_approachnode_dircode` (예: `215173_216288_s`), 총 21개.
- 8개 진입 leg: 교차로15 = 216151/216286/216287/216288, 교차로16 = 215431/215432/215433/215434.
- 검증치 단위 주의: `avg_speed`=m/s, queue=분율, `avg_delay`는 단위 확정 필요(가이드라인 8절).
