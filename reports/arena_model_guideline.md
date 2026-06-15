# Arena 모델링 가이드라인 — 교차로 15+16 (Tier 1)

이 문서는 전처리된 데이터를 Arena 모델로 옮기는 **모듈별 설정 지침**입니다.
범위는 **Tier 1**(두 교차로를 한 모델에 두되 교차로 간 entity 라우팅 없음; 관측 도착 + 동기 신호),
통과 용량은 **표준 포화교통류율**(1900 veh/h/차로, 헤드웨이 1.9s)을 가정합니다.

> 배경·근거는 계획서 `quirky-mixing-yao.md` 참조. 데이터 산출 스크립트: `src/13~16`.

---

## 0. 입력 파일 한눈에

| 파일 | 용도 | 키 |
| --- | --- | --- |
| `leg_arrival_5min.csv` | Create 5분 도착률 | (inter, approach_node) × 5분 bin |
| `leg_arrival_signal_bridge.csv` | leg별 회전비율·요약 | (inter, approach_node) |
| `vehicle_type_ratio.csv` | 차종 비율 | (group, from_inter_id, vhcl_typ) |
| `leg_service_params.csv` | Process 차로수·서비스시간 | (inter, approach_node, dir) |
| `signal_schedule_arena.csv` | 신호 녹/적 토글 | movement_key × event |
| `layout_coords.csv`, `layout_routes.csv` | Station 좌표·Route 주행시간 | node / movement |
| `validation_targets.csv` | 검증 기준 | (group, from_inter, turn) |

- **movement** = 진입 leg × 회전 = `inter_id_approachnode_dircode` (예: `215173_216288_s`). 총 21개.
- **8개 진입 leg**: 교차로15 = 216151/216286/216287/216288, 교차로16 = 215431/215432/215433/215434.

---

## 1. 모듈 흐름 (leg당, Station/Route 기반)

```
Station ENTER[leg]
Create(leg, 5분 Schedule)
  → Assign: VehType = DISC(...)  +  Entity.Picture(차종 아이콘)
  → Assign: Turn   = DISC(...)                      (1=좌,2=직,3=우)
  → Route(approach_time) → Station STOPLINE[leg]
  → Decide(by Turn): L / S / R
      ├─ Hold(Scan: Green[movement]==1)             (우회전·int15는 Hold 생략)
      ├─ Seize laneRes[movement] (cap=차로수)
      ├─ Delay(1.9s) → Release
      └─ Route(exit_time) → Station EXIT[exit_node] → Record → Dispose
```

두 교차로 모듈을 한 모델에 배치하고 같은 시계(0초=08:00)를 쓰면 신호 offset이 보존됩니다.

---

## 2. Create — 5분 단위 도착 (leg 8개)

각 leg에 Create 1개. **Arrival Type = Schedule**, 5분(300초) 12스텝의 rate를 `leg_arrival_5min.csv`
`arrival_per_min`에서 가져옵니다. (또는 Interarrival = `EXPO(mean_interarrival_sec)`를 구간별로.)

예시 — 216288 (교차로15, NE, 연동 leg)의 12스텝 (대/분):

| 시작(초) | 0 | 300 | 600 | 900 | 1200 | 1500 | 1800 | 2100 | 2400 | 2700 | 3000 | 3300 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rate | 32.0 | 126.8 | 98.2 | 35.0 | 160.6 | 89.8 | 44.8 | 112.4 | 110.2 | 51.6 | 128.0 | 76.8 |

나머지 7개 leg의 12스텝은 `leg_arrival_5min.csv`에서 `approach_node`로 필터해 그대로 사용.
Arena Schedule 단위가 시간(hour)이면 rate×60(대/시)로 환산.

---

## 3. Assign — 회전(Turn)과 차종(VehType)

### Turn (1=좌, 2=직, 3=우)  ← `leg_arrival_signal_bridge.csv`

| leg | DISC(누적확률, 값) |
| --- | --- |
| 15/216151 (SW) | `DISC(0.147,1, 1.0,2)` (우회전 없음) |
| 15/216286 (NW) | `DISC(0.278,1, 1.0,2)` |
| 15/216287 (S) | `DISC(0.234,1, 1.0,2)` |
| 15/216288 (NE) | `DISC(0.166,1, 0.908,2, 1.0,3)` |
| 16/215431 (NW) | `DISC(0.085,1, 0.792,2, 1.0,3)` |
| 16/215432 (E) | `DISC(0.155,1, 0.893,2, 1.0,3)` |
| 16/215433 (S) | `DISC(0.267,1, 0.739,2, 1.0,3)` |
| 16/215434 (SW) | `DISC(0.172,1, 0.828,2, 1.0,3)` |

### VehType (1=승용, 2=버스, 3=화물, 4=특수, 5=특수차, 6=이륜)  ← `vehicle_type_ratio.csv` leg 합산

| leg | DISC(누적확률, 값) |
| --- | --- |
| 15/216151 | `DISC(0.888,1, 0.917,2, 0.958,3, 0.981,4, 0.982,5, 1.0,6)` |
| 15/216286 | `DISC(0.868,1, 0.901,2, 0.975,3, 0.986,4, 1.0,6)` |
| 15/216287 | `DISC(0.915,1, 0.934,2, 0.972,3, 0.990,4, 0.990,5, 1.0,6)` |
| 15/216288 | `DISC(0.890,1, 0.912,2, 0.965,3, 0.986,4, 1.0,6)` |
| 16/215431 | `DISC(0.927,1, 0.930,2, 0.976,3, 0.987,4, 1.0,6)` |
| 16/215432 | `DISC(0.918,1, 0.930,2, 0.976,3, 0.988,4, 0.988,5, 1.0,6)` |
| 16/215433 | `DISC(0.924,1, 0.944,2, 0.981,3, 0.991,4, 0.992,5, 1.0,6)` |
| 16/215434 | `DISC(0.892,1, 0.919,2, 0.956,3, 0.980,4, 0.981,5, 1.0,6)` |

차종은 Entity.Picture에 연결(승용/버스/화물 아이콘). (정교화 시 화물·버스 Delay에 PCE≈2 적용.)

---

## 4. Hold — 신호 (Wait for Signal)

- movement별 상태변수 `Green[movement]`(0/1)을 두고, Hold 모듈을 **Scan: `Green[movement]==1`** 로.
- **신호 컨트롤 로직**: movement(21개)당 제어 entity 1개를 0초에 Create →
  `signal_schedule_arena.csv`의 (event_time_sec, green) 순서대로 Delay 후 `Green` 변수 set 반복.
  - 이 파일은 movement별 녹색 시작=1, 종료=0 이벤트를 시간순으로 담음(총 1,298 이벤트).
- **우회전·교차로15 상시우회전**(green 윈도우 없음): Hold 생략하고 곧장 Process.
- 두 교차로가 같은 0초 원점을 공유 → 실제 신호 offset 자동 보존(연동 표현의 핵심).

---

## 5. Process — 포화 방출  ← `leg_service_params.csv`

movement별 Process: **Seize `laneRes[movement]`(capacity=`resource_capacity`) → Delay(`service_delay_sec`) → Release**.

- 직진: 차로수 4 → cap 4, Delay 1.895s → 방출률 ≈ 2.11 veh/s (포화류 7600 veh/h)
- 좌·우: 차로수 1 → cap 1, Delay 1.895s → ≈ 0.53 veh/s (1900 veh/h)
- (교차로16 215433 직진만 차로수 3) — 값은 파일대로 사용.

---

## 6. Station / Route — 배치와 주행  ← `layout_coords.csv`, `layout_routes.csv`

- **Station 좌표**: `layout_coords.csv`의 `screen_x/y`(0~100, 종횡비 보존)로 교차로 중심 2개 +
  leg 노드 8개를 실제 배치 비율대로 배치. (두 교차로는 실제 ~430m 떨어져 있어 화면상 x≈6 vs x≈92로
  멀리 떨어짐 → **교차로별 확대 패널**로 그리면 디테일이 잘 보임.)
- **Route 주행시간**: `layout_routes.csv`의 `approach_time_sec`(진입), `exit_time_sec`(진출).
  진입로 stub이 짧아(8~22m → 0.5~2초) 보기엔 짧으므로, 시각적으로 길이를 늘려도 로직 무관.

---

## 7. 애니메이션 요소

| 요소 | Arena 기능 | 설정 |
| --- | --- | --- |
| 배경 | Picture import / Draw | 교차로 위성·도식, `screen_x/y` 축척에 맞춤 |
| 차량 | Entity > Picture | VehType별 아이콘(승용/버스/화물) |
| 대기행렬 | Animate > Queue | 각 Hold Queue를 STOPLINE에 진입로 방향으로 배치 |
| 신호등 | Animate > Variable/Level | movement별 `Green` 변수에 녹/적 색 박스 |
| 통계 | Clock / Plot / Variable | 시뮬 시계, leg 통과량 카운터, 대기행렬 길이 Plot |

---

## 8. 실행 · 검증

- **웜업**: 5~10분 warm-up 후 통계 수집(초기 빈 네트워크 효과 제거).
- **Replication**: 다회(예: 10) 반복, 1시간(+웜업) 구동.
- **검증** (`validation_targets.csv`, leg/방향별):
  - 통과량: movement Dispose 수 ≈ `vehicle_count` (±10%)
  - 속도/지체/대기행렬: `avg_speed`, `avg_delay`, `queue_ratio` 추세와 정합
- **애니메이션 육안**: 진입→정지선 대기(행렬)→녹색 방출→회전별 진출로 이탈, 신호색-녹색창 동기 확인.

### ⚠️ 검증치 단위 (비교 전 확정)
- `avg_speed` = **m/s** (야간 free-flow ≈ 13 ≈ 제한속도 13.89m/s로 확인). km/h 비교 시 ×3.6.
- `queue_ratio`, `long_queue_ratio` = **분율(0~1)**.
- `avg_delay`(원천 `tl`) = 0.036~0.56 범위로 **단위 모호**(분 또는 정규화 비율). 정량 지체 비교
  전 `traffic_pipeline.py`의 `tl` 집계부로 단위를 확정할 것. 확정 전에는 상대 추세 비교만 권장.

---

## 9. Tier 1의 한계 (보고서에 명시)

- 교차로 간 entity를 라우팅하지 않으므로 **신호 offset을 바꿔도 하류 도착이 반응하지 않음**
  (progression 최적화 실험 불가). 연동 효과는 관측 도착 + 실제 offset으로만 표현.
- 외곽/이웃 진출로는 싱크(Dispose) — 하류 막힘 미모델.
- 황색·손실시간 미반영(녹색만 통행). 우회전 비보호 가정.
- 두 교차로 검지 데이터셋 간 통과량 보존은 성립하지 않으나, Tier 1은 라우팅이 없어 영향 없음.
