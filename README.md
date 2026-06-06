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

Arena 입력 파일은 **신호를 빼고는 거의 다 준비**되어 있습니다.
도착률, 도착 스케줄, 방향 비율, 차종 비율, 검증 지표는 바로 쓸 수 있습니다.

**신호 데이터만 아직 미완성입니다.** 이유를 쉽게 풀면 이렇습니다.

- 우리가 가진 신호 데이터(`signal_plan_as_is.csv`)에는 `grrrrrGGGGr...` 같은
  **신호 문자열**이 들어 있습니다. 이건 SUMO라는 교통 시뮬레이터의 신호 표기로,
  글자 한 칸이 교차로의 한 "이동류(차로+방향)" 신호등을 뜻합니다.
  (`G`/`g` = 녹색, `y` = 황색, `r` = 적색)
- 이 문자열만으로 **"몇 번째 칸이 언제 녹색/적색인지"는 이미 계산해 두었습니다.**
  → [data_processed/signal_green_windows.csv](data_processed/signal_green_windows.csv)
- 하지만 **"그 칸이 실제로 어느 방향(직진/좌회전/우회전)·어느 진입로인지"** 는
  이 데이터만으로는 알 수 없습니다.
  이 매핑은 **네트워크 데이터(SUMO `net.xml`)** 안의 연결 정의에만 들어 있습니다.

### 그래서 다음에 필요한 것: 네트워크 데이터

- 데이터 설명서(`(2-058) 데이터설명서...pdf`)에도 별도 항목인 **"네트워크데이터(.xml)"** 로
  명시되어 있습니다. (안양시 7개)
- 현재 우리 `data/` 폴더에는 이 네트워크 데이터가 **빠져 있습니다.**
- **팀원에게서 안양시 네트워크 데이터(`net.xml`)를 받아오면**, 신호 칸 ↔ 방향 매핑을
  자동으로 완성하여 신호 입력을 마무리할 수 있습니다.

> 한 줄 요약: 신호의 "타이밍"은 끝났고, 신호의 "방향 의미"를 붙이려면 네트워크 데이터가 필요합니다.

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
> 칸 ↔ 방향 매핑이 들어 있는 **네트워크데이터(.xml)** 는 별도 항목으로, 현재 우리 폴더에는 없습니다.

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
8. [data_processed/signal_plan_as_is.csv](data_processed/signal_plan_as_is.csv)
   - 선택 시간대의 실제 신호 상태 변화 정보
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

### 10. 신호 → Arena 변환 (신호 타이밍까지만 완료)

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
  (Arena에 바로 넣는 핵심 파일)

> ⚠️ 미완성 부분: 위 `movement`(칸 번호)가 **어느 방향·진입로인지**는 아직 붙이지 못했습니다.
> 이 단계를 끝내려면 **네트워크 데이터(`net.xml`)** 가 필요합니다. (위 "현재 진행 상황" 참고)

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
| `signal_green_windows.csv` | 칸별 녹색 구간 (Arena 신호 입력용 핵심) |
| `validation_targets.csv` | Arena 검증용 기준 지표 |

> `signal_movement_state.csv` / `signal_green_windows.csv`는 신호 "타이밍"까지만 완료된 파일입니다.
> 칸 번호에 방향(직진/좌/우)을 붙이려면 네트워크 데이터(`net.xml`)가 필요합니다.

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

## 참고

- 병목 점수 계산에서 `signal_imbalance`는 현재 `0`으로 두었습니다.
- 이유는 원시 신호 로그만으로 모든 유입 방향에 대해 직접 비교 가능한 차로/현시 불균형 지표를 안정적으로 만들기 어려웠기 때문입니다.
- 자세한 해석은 [reports/eda_summary.md](reports/eda_summary.md)와 [reports/arena_input_summary.md](reports/arena_input_summary.md)를 보면 됩니다.
