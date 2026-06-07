# Simulation Term Project

안산시 교차로 15, 16 구간의 교통 데이터를 전처리하고, Arena DES 입력 파일을 만드는 프로젝트입니다.

이 저장소의 목적은 다음과 같습니다.

1. 원천 데이터를 구조별로 정리한다.
2. 교차로 15, 16, 15+16 구간의 차량 도착 이벤트를 만든다.
3. 5분 단위 EDA로 병목 시간대를 찾는다.
4. Arena 모델에 넣을 도착률, 도착 스케줄, 방향 비율, 차종 비율, 신호 계획, 검증 지표를 만든다.
5. 팀원이 결과를 빠르게 이해할 수 있도록 그림과 요약 보고서를 만든다.

## 분석 범위

- 분석 날짜: `2022-05-09`
- 교차로 15: `inter_id = 215173`
- 교차로 16: `inter_id = 215174`
- 교차로 15+16: 교차로 15와 16을 함께 본 연동 구간

현재 결과물은 비교 목적을 위해 **세 분석 대상 모두 같은 시간대**를 사용합니다.

- 공통 분석 시간대: `2022-05-09 08:00:00 ~ 09:00:00`
- 기준: `교차로 15+16`에서 가장 대표성이 높았던 1시간 병목 구간

## 현재 진행 상황 (먼저 읽어주세요)

Arena 입력 파일이 **신호까지 모두 준비 완료**되었습니다.
도착률, 도착 스케줄, 방향 비율, 차종 비율, 검증 지표, 그리고 신호(타이밍 + 방향 라벨)까지
바로 쓸 수 있습니다.

신호 데이터가 어떻게 완성되었는지 쉽게 풀면 이렇습니다.

- 신호 데이터(`signal_plan_as_is.csv`)에는 `grrrrrGGGGr...` 같은 **신호 문자열**이 있습니다.
  SUMO 교통 시뮬레이터의 신호 표기로, 글자 한 칸이 교차로의 한 "이동류(차로+방향)"
  신호등을 뜻합니다. (`G`/`g` = 녹색, `y` = 황색, `r` = 적색)
- **(1단계) 타이밍 풀기** — 문자열을 풀어 "몇 번째 칸이 언제 녹색/적색인지" 표로 만들었습니다.
  → [data_processed/signal_green_windows.csv](data_processed/signal_green_windows.csv)
- **(2단계) 방향 붙이기** — **네트워크 데이터(SUMO `net.xml`)** 의 연결 정의를 이용해
  "그 칸이 어느 방향(직진/좌회전/우회전)·어느 진입로인지"를 자동으로 매핑했습니다.
  → [data_processed/signal_green_windows_labeled.csv](data_processed/signal_green_windows_labeled.csv)

확인 결과, 대상 두 교차로 모두 **4개 진입로 × (직진 + 좌회전 + 우회전)** 구조이며,
신호 문자열의 모든 칸에 방향이 빠짐없이 매칭되었습니다.

| 교차로 | 이름 | inter_id | 신호 칸 수 | 진입로 |
| --- | --- | --- | --- | --- |
| 15 | 시청사거리 | 215173 | 21 | 4개 |
| 16 | 관평사거리 | 215174 | 23 | 4개 |

> 참고: 매핑에 사용한 네트워크 데이터는 `data/.../네트워크데이터/anyang9_4.net.xml` 입니다.
> 진입로 식별자(`approach_node`)는 SUMO 네트워크의 노드 ID라서, 회전교통량 데이터의
> `from_inter_id`와는 번호 체계가 다릅니다. (방향 라벨 자체는 정확합니다.)

## 폴더 구조

```text
project_root/
  data/                  # 원천 데이터
  data_processed/        # 전처리 결과 CSV
  figures/               # EDA 그림
  reports/               # 팀원용 요약 보고서
  src/                   # 단계별 파이프라인 스크립트
  (2-058) 데이터설명서...pdf  # 원본 데이터셋 공식 설명서 (교차로 ID, 신호 표기 정의 등)
  README.md
```

> 데이터 설명서 PDF에서 확인한 핵심: 교차로 15 = 시청사거리(`215173`),
> 교차로 16 = 관평사거리(`215174`)이고, `signal_state`는 "SUMO 신호입력값"입니다.
> 칸 ↔ 방향 매핑이 들어 있는 **네트워크데이터(`net.xml`)** 도 받아와서
> (`data/.../네트워크데이터/`) 신호 방향 매핑까지 완료했습니다.

## 팀원이 처음 볼 파일

팀원에게 설명할 때는 아래 순서대로 보면 가장 이해가 쉽습니다.

1. [reports/eda_summary.md](reports/eda_summary.md)
   - 전체 분석 목적, 병목 시간대, 주요 결과를 요약한 문서
2. [reports/arena_input_summary.md](reports/arena_input_summary.md)
   - Arena 모델에 어떤 파일을 어떻게 연결하면 되는지 설명한 문서
3. [data_processed/candidate_window.csv](data_processed/candidate_window.csv)
   - 최종 분석 시간대가 무엇인지 확인하는 파일
4. [data_processed/arrival_input_arena.csv](data_processed/arrival_input_arena.csv)
   - 5분 단위 도착률 기반 Arena Create 입력
5. [data_processed/arrival_schedule_arena.csv](data_processed/arrival_schedule_arena.csv)
   - 실제 도착 시각 기반 Arena Schedule 입력
6. [data_processed/movement_ratio.csv](data_processed/movement_ratio.csv)
   - 유입 방향별 직진/좌회전/우회전 비율
7. [data_processed/vehicle_type_ratio.csv](data_processed/vehicle_type_ratio.csv)
   - 차종 비율
8. [data_processed/signal_green_windows_labeled.csv](data_processed/signal_green_windows_labeled.csv)
   - 신호 입력용 최종 파일: 이동류별 녹색 구간 + 방향(직진/좌/우) 라벨
   - 원본 신호 문자열은 [data_processed/signal_plan_as_is.csv](data_processed/signal_plan_as_is.csv) 참고
9. [data_processed/validation_targets.csv](data_processed/validation_targets.csv)
   - Arena 결과와 비교할 속도, 지체, 대기행렬 기준값

## 단계별 처리 흐름

### 1. 데이터 인벤토리

- 스크립트: [src/01_inventory.py](src/01_inventory.py)
- 결과:
  - [data_processed/data_inventory.csv](data_processed/data_inventory.csv)
  - [data_processed/column_profile.csv](data_processed/column_profile.csv)

원천 데이터 파일 종류, 컬럼 구조, 샘플 행을 정리합니다.

### 2. 차량 핵심 데이터 추출

- 스크립트: [src/02_make_vehicle_core.py](src/02_make_vehicle_core.py)
- 결과:
  - [data_processed/vehicle_core_20220509.csv](data_processed/vehicle_core_20220509.csv)

개별 차량 기반 원천 데이터에서 분석에 필요한 핵심 컬럼만 추출합니다.

주요 컬럼:

- `vhcl_id`
- `unix_time`
- `datetime`
- `to_inter_id`
- `from_inter_id`
- `turn_typ2to_inter`
- `vhcl_typ`
- `spd`
- `tl`
- `que_all`
- `que_200_500`
- `que_500`

### 3. 도착 이벤트 생성

- 스크립트: [src/03_make_arrival_events.py](src/03_make_arrival_events.py)
- 결과:
  - [data_processed/arrival_events.csv](data_processed/arrival_events.csv)

같은 차량이 같은 목적 교차로와 같은 접근 방향으로 여러 번 기록되어 있어도, 가장 이른 시각만 도착 이벤트로 남깁니다.

### 4. 5분 단위 스크리닝

- 스크립트: [src/04_screening_5min.py](src/04_screening_5min.py)
- 결과:
  - [data_processed/screening_5min.csv](data_processed/screening_5min.csv)

다음 지표를 5분 단위로 계산합니다.

- `vehicle_count`
- `arrival_rate_per_min`
- `mean_interarrival_sec`
- `avg_speed`
- `avg_delay`
- `queue_ratio`
- `long_queue_ratio`
- `direction_imbalance`
- `bottleneck_score`

#### 병목 점수(`bottleneck_score`)는 어떻게 계산하나

여러 혼잡 지표를 0~1로 맞춰 **가중 평균**한 값입니다. 1에 가까울수록 혼잡 가능성이 큽니다.

1. **각 지표를 0~1로 정규화** (전체 5분 구간에 대한 min-max 정규화)
   - 값이 클수록 혼잡한 지표(`positive`): `(값 − 최소) / (최대 − 최소)`
   - 값이 작을수록 혼잡한 지표(`inverse`, 속도): `(최대 − 값) / (최대 − 최소)`
2. **가중 평균**으로 합칩니다. 지표별 가중치는 아래와 같습니다.

| 지표 | 방향 | 가중치 | 의미 |
| --- | --- | --- | --- |
| `vehicle_count` | 클수록↑ | 0.25 | 5분간 도착 차량 수 |
| `avg_speed` | 작을수록↑ | 0.20 | 평균 속도(느릴수록 혼잡) |
| `queue_ratio` | 클수록↑ | 0.20 | 대기행렬 관측 비율(`que_all`) |
| `avg_delay` | 클수록↑ | 0.20 | 평균 지체시간(`tl`) |
| `direction_imbalance` | 클수록↑ | 0.10 | 진입 방향 쏠림 정도 |
| `signal_imbalance` | 클수록↑ | 0.05 | 신호 배분 불균형 (**현재 0으로 고정**) |

3. **방향 쏠림(`direction_imbalance`)** 은 진입로(`from_inter_id`)별 차량 수의
   허핀달 지수(각 진입로 점유율을 제곱해 합산)입니다. 한 방향에 몰릴수록 1에 가깝습니다.
4. 정규화가 불가능한 지표(값이 모두 같아 분모가 0이 되는 경우)는 평균에서 빠지고,
   **남은 가중치만으로 다시 정규화**해 합산합니다.

> 한계: `signal_imbalance`는 현재 항상 `0`이라 점수에 실제로 반영되지 않습니다.
> 따라서 유효 가중치는 나머지 5개 지표에 재분배됩니다(분모 0.95).
> 원시 신호 로그만으로 모든 유입 방향의 차로별 배분을 안정적으로 비교하기 어려웠기 때문입니다.
> (이제 네트워크 데이터가 있으니 향후 신호 기반 불균형 지표를 추가할 여지가 있습니다.)

### 5. 후보 시간대 선택

- 스크립트: [src/05_select_candidate_window.py](src/05_select_candidate_window.py)
- 결과:
  - [data_processed/candidate_window.csv](data_processed/candidate_window.csv)

원래는 교차로별 최고 병목 시간대를 따로 고를 수 있지만, 현재 저장소 결과는 **비교 목적** 때문에 `15+16`의 대표 시간대를 기준으로 **세 그룹 모두 동일 시간대**를 선택하도록 설정되어 있습니다.

### 6. Arena 입력 파일 생성

- 스크립트: [src/06_make_arena_inputs.py](src/06_make_arena_inputs.py)
- 결과:
  - [data_processed/arrival_input_arena.csv](data_processed/arrival_input_arena.csv)
  - [data_processed/arrival_schedule_arena.csv](data_processed/arrival_schedule_arena.csv)
  - [data_processed/arrival_distribution_fit.csv](data_processed/arrival_distribution_fit.csv)
  - [data_processed/movement_ratio.csv](data_processed/movement_ratio.csv)
  - [data_processed/vehicle_type_ratio.csv](data_processed/vehicle_type_ratio.csv)

Arena 입력에 직접 쓰는 핵심 단계입니다.

### 7. 신호 계획 생성

- 스크립트: [src/07_make_signal_plan.py](src/07_make_signal_plan.py)
- 결과:
  - [data_processed/signal_plan_as_is.csv](data_processed/signal_plan_as_is.csv)

선택된 시간대 안에서 신호 상태(SUMO 신호 문자열)가 언제 바뀌는지 정리합니다.
각 행은 한 현시(phase) 구간이며, `offset_sec`은 시간대 시작부터 몇 초 뒤인지,
`signal_state`는 칸별 등화 상태입니다.

### 8. 검증 지표 생성

- 스크립트: [src/08_make_validation_targets.py](src/08_make_validation_targets.py)
- 결과:
  - [data_processed/validation_targets.csv](data_processed/validation_targets.csv)

Arena 결과와 실제 데이터를 비교하기 위한 기준표입니다.

### 9. 그림과 보고서 생성

- 스크립트: [src/09_make_figures.py](src/09_make_figures.py)
- 결과:
  - [figures/traffic_volume_5min.png](figures/traffic_volume_5min.png)
  - [figures/avg_speed_5min.png](figures/avg_speed_5min.png)
  - [figures/avg_delay_5min.png](figures/avg_delay_5min.png)
  - [figures/queue_ratio_5min.png](figures/queue_ratio_5min.png)
  - [figures/bottleneck_score_5min.png](figures/bottleneck_score_5min.png)
  - [figures/movement_ratio.png](figures/movement_ratio.png)
  - [figures/vehicle_type_ratio.png](figures/vehicle_type_ratio.png)
  - [figures/interarrival_histogram.png](figures/interarrival_histogram.png)
  - [figures/distribution_fit_comparison.png](figures/distribution_fit_comparison.png)
  - [reports/eda_summary.md](reports/eda_summary.md)
  - [reports/arena_input_summary.md](reports/arena_input_summary.md)

### 10. 신호 → Arena 변환 (신호 타이밍 풀기)

- 스크립트: [src/10_signal_to_arena.py](src/10_signal_to_arena.py)
- 결과:
  - [data_processed/signal_movement_state.csv](data_processed/signal_movement_state.csv)
  - [data_processed/signal_green_windows.csv](data_processed/signal_green_windows.csv)

신호 문자열을 Arena가 쓸 수 있는 형태로 풀어주는 단계입니다.
Arena에는 신호등 객체가 없어서, "이동류(칸)별로 언제 녹색/적색인가"를
미리 표로 만들어 두고 Hold(Wait for Signal) 로직에 넣어 차량을 잡았다 풀었다 합니다.

- `signal_movement_state.csv`: 모든 칸 × 모든 구간을 풀어쓴 상세 표
  (`movement`=칸 번호, `state`=green/yellow/red)
- `signal_green_windows.csv`: 칸별로 녹색이 이어지는 구간만 합친 표

### 11. 신호 칸 ↔ 방향 매핑 (네트워크 데이터 사용)

- 스크립트: [src/11_map_signal_movements.py](src/11_map_signal_movements.py)
- 입력: `data/.../네트워크데이터/anyang9_4.net.xml`
- 결과:
  - [data_processed/signal_movement_map.csv](data_processed/signal_movement_map.csv)
  - [data_processed/signal_green_windows_labeled.csv](data_processed/signal_green_windows_labeled.csv)
  - [data_processed/signal_movement_state_labeled.csv](data_processed/signal_movement_state_labeled.csv)

네트워크 데이터(SUMO `net.xml`)의 `<connection ... linkIndex=N from=.. to=.. dir=s/l/r>`
정의를 읽어, 신호 문자열의 N번째 칸이 **어느 진입로에서 어느 방향(직진/좌/우)인지**를 붙입니다.

- `signal_movement_map.csv`: 칸 ↔ 방향·접근로 매핑 사전
- `signal_green_windows_labeled.csv`: 10단계의 녹색 구간 표에 방향 라벨을 결합한 **최종 신호 입력 파일**
- `signal_movement_state_labeled.csv`: 상세 상태 표 + 방향 라벨

> Arena에서 접근로별 Hold(Wait for Signal)에 신호를 연결할 때, 이 파일의
> `direction`(직진/좌/우)과 `green_start_sec`/`green_end_sec`를 그대로 쓰면 됩니다.

## 실행 순서

아래 순서대로 실행하면 전체 파이프라인을 다시 만들 수 있습니다.

```bash
python src/01_inventory.py
python src/02_make_vehicle_core.py
python src/03_make_arrival_events.py
python src/04_screening_5min.py
python src/05_select_candidate_window.py
python src/06_make_arena_inputs.py
python src/07_make_signal_plan.py
python src/08_make_validation_targets.py
python src/09_make_figures.py
python src/10_signal_to_arena.py
python src/11_map_signal_movements.py
```

## 실행 환경

현재 작업 환경에서 확인한 주요 패키지는 아래와 같습니다.

- Python `3.12`
- pandas
- numpy
- matplotlib
- scipy
- pyarrow

별도 `requirements.txt`는 아직 없습니다.

## 파일별 용도 빠르게 보기

| 파일 | 용도 |
| --- | --- |
| `data_inventory.csv` | 원천 파일 종류와 구조 확인 |
| `column_profile.csv` | 컬럼별 샘플과 후보 역할 확인 |
| `vehicle_core_20220509.csv` | 핵심 차량 데이터 |
| `arrival_events.csv` | 중복 제거된 도착 이벤트 |
| `screening_5min.csv` | 5분 단위 병목 스크리닝 |
| `candidate_window.csv` | 최종 시간대 선택 결과 |
| `arrival_input_arena.csv` | 5분 평균 도착률 기반 Arena 입력 |
| `arrival_schedule_arena.csv` | 실제 도착 시각 기반 Arena 입력 |
| `movement_ratio.csv` | 이동 방향 비율 |
| `vehicle_type_ratio.csv` | 차종 비율 |
| `signal_plan_as_is.csv` | 신호 상태 변화 정보 (SUMO 신호 문자열) |
| `signal_movement_state.csv` | 칸(이동류)별 녹/황/적 상세 표 |
| `signal_green_windows.csv` | 칸별 녹색 구간 (타이밍만) |
| `signal_movement_map.csv` | 칸 ↔ 방향·접근로 매핑 사전 (net.xml 기반) |
| `signal_green_windows_labeled.csv` | 녹색 구간 + 방향 라벨 (**Arena 신호 입력용 최종 파일**) |
| `signal_movement_state_labeled.csv` | 상세 상태 표 + 방향 라벨 |
| `validation_targets.csv` | Arena 검증용 기준 지표 |

## GitHub에 올릴 때 주의할 점

이 저장소에는 GitHub 업로드 한도를 넘는 큰 파일이 있습니다.

예시:

- `data/` 원천 데이터
- `data_processed/vehicle_core_20220509.csv`
- `data_processed/arrival_events.csv`

GitHub 기본 업로드 한도 때문에 그대로는 push가 안 될 수 있습니다.

권장 방식:

1. 코드와 문서 중심으로 저장소를 올린다.
2. 큰 CSV와 원천 데이터는 제외하거나 별도 저장소를 쓴다.
3. 꼭 올려야 하면 Git LFS를 사용한다.

팀 공유용으로는 아래만 먼저 올려도 충분합니다.

- `src/`
- `reports/`
- `figures/`
- 작은 결과 CSV
  - `candidate_window.csv`
  - `arrival_input_arena.csv`
  - `movement_ratio.csv`
  - `vehicle_type_ratio.csv`
  - `signal_plan_as_is.csv`
  - `validation_targets.csv`

## 팀 논의 필요 (미해결 이슈)

### 회전방향 `unknown` 처리 방법

- [data_processed/movement_ratio.csv](data_processed/movement_ratio.csv)에서 회전방향
  `unknown`이 **전체의 약 43.5%** 를 차지합니다. (세 그룹 모두 비슷)
- 원인: 원본 개별차량 데이터의 `turn_typ2to_inter`(회전방향) 필드가 **비어 있던** 기록입니다.
  (측정/분류가 안 된 누락 데이터)
- **네트워크 데이터(net.xml)로는 해결되지 않습니다.** 회전을 기하학적으로 계산하려면
  "이전 교차로 → 현재 교차로 → 다음 교차로" 3개 점이 필요한데, 우리 가공 데이터는
  분석 교차로(215173/215174)에서 경로가 끝나 "다음 방향"이 없습니다.
  (좌표는 net.xml에 다 있지만 3번째 점이 없어 계산 불가)

선택지 (팀이 함께 결정):

| 안 | 방법 | 노력 | 비고 |
| --- | --- | --- | --- |
| A | `unknown`을 빼고 알려진 직진/좌/우 비율로 **재정규화** | 작음 | Arena 라우팅 확률로 충분, 표준적 처리 |
| B | 원본 궤적(`개별차량 tra.csv`)의 heading(`agl`)으로 **회전 재계산** | 큼 (GB 재처리) | 더 정확하나 부분 복원, 검증 필요 |
| C | `unknown`을 그대로 두고 진행 | 없음 | 비율이 왜곡된 채로 사용 |

> Arena의 회전 확률(Decide 모듈) 용도로는 보통 **A안**으로 충분합니다.
> 정확도를 끝까지 올리려면 B안이지만 추가 작업과 불확실성이 있습니다.

## 참고

- 병목 점수 계산 방법과 `signal_imbalance=0` 한계는 위 "4. 5분 단위 스크리닝"의
  "병목 점수는 어떻게 계산하나"에 정리되어 있습니다.
- 자세한 해석은 [reports/eda_summary.md](reports/eda_summary.md)와 [reports/arena_input_summary.md](reports/arena_input_summary.md)를 보면 됩니다.
