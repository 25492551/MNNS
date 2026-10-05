# `data` 보유 요약

확인 시점은 2026-10-04이다. 식 (R1)의 변수 대응은 `docs/베트남_쌀농가_식단다양성_제안식.md` 5절이다. 여기에는 그 식에 쓰기 위해 폴더에 들어 있는 파일의 범위만 적는다.

## 1. 구성

| 위치 | 내용 | 크기 |
| --- | --- | --- |
| `data/VARHS-2008-16` | 2008·2010·2012·2014·2016 가구·commune 조사. `.dta` 462개, 설문지 10개 | — |
| `data/chirps-v2.0.monthly.nc` | CHIRPS v2.0 전지구 월강수 | 7.2GB |
| `data/gadm41_VNM_shp-.../gadm41_VNM_2` | GADM 4.1 베트남 2단계 경계 | 성 63, 구역 710 |
| `data/external` | 벼 작기, 쌀 가격, 물가, 비료 국제가 | 아래 3절 |

`VARHS-2008-16` 안의 `__MACOSX`는 압축을 풀 때 생긴 부가 파일이라 분석에 쓰지 않는다.

## 2. VARHS

설문지는 `VARHS-2008-16Questionnaires/Questionnaires`에 파동별 가구·commune 파일이 있다. 2014 가구 설문 파일명만 `VARHS2014_Hosuehold.xlsx`이다.

마이크로데이터는 `VARHS-2008-16Clean/2008-16Clean`이다. 파동 폴더는 `2008_new`부터 `2016_new`이고, commune은 `commune_clean`에 다섯 파일이다.

가구 표지 행 수와, 성 코드·commune 코드를 묶은 개수는 다음과 같다.

| 파동 | 표지 파일 | 행 | 성 | commune |
| --- | --- | --- | --- | --- |
| 2008 | `Phieu_1_New_08.dta` | 2,278 | 12 | 230 |
| 2010 | `Phieu_1_New_10.dta` | 2,245 | 12 | 231 |
| 2012 | `Phieu1_New_12.dta` | 2,760 | 12 | 233 |
| 2014 | `Phieu1_New_14.dta` | 2,725 | 12 | 237 |
| 2016 | `Phieu1_New_16.dta` | 2,669 | 12 | 236 |

성·commune 코드는 표지의 `tinh_*`, `xa_*`이다. 별도 `panelid.dta`는 없다. `panel0816`은 표지에 있으나 이 다섯 표지 안에서는 값이 모두 1이다. 가구를 잇는 번호는 성·commune과 가구 번호의 조합이다.

식에 쓰는 모듈은 파동마다 같은 자리에 있다.

| 식의 항목 | 파일 |
| --- | --- |
| 가구원·출생연도 | 2008 `Q1a_New.dta`. 2010–2016 `Q1_New_*.dta` |
| 작물·작기 수량 | 2008 `Q3a`·`Q3b`. 2010–2016 `Q3A`·`Q3B` |
| 투입 사용액 | 2008 `Q3c`. 2010–2016 `Q3C` |
| 식품군·소비 | 각 파동 `Phieu_2` |
| 비주식 시장가격 | 각 파동 `Q7A` |
| 면접월, 수확 일당 | `commune_08_clean.dta`부터 `commune_16_clean.dta`. 행 수는 448, 457, 460, 460, 465 |

이 파일들은 문항 원자료이다. 쌀 가구 명단, HDDS-11, ASF-4, 연령대 인원, 한 작기의 쌀 수확가치, kg당 투입재 가격은 만들어 둔 열이 아니다.

## 3. 강우, 경계, 외부 가격

`chirps-v2.0.monthly.nc`는 UCSB CHIRPS v2.0 전지구 월강수 단일 파일이다. 제품 기간은 1981년 1월부터이다. district 작기 편차 \(D\), \(W\)로 자른 파일은 아직 없다. 경계는 `gadm41_VNM_2`이고 2단계 구역이 710개, 성이 63개이다.

`data/external`은 2026-10-04에 받은 공개 자료이다. 파일별 출처는 `data/external/sources.txt`에 있다.

| 폴더 | 쓰는 파일 | 범위 |
| --- | --- | --- |
| `riceatlas/vietnam` | `rice_calendar_vnm.csv`, `RiceCalendar_VNM.shp` | 베트남 60개 하위 행정구역. 작기별 파종·수확의 연중 일수. 1–3작기 |
| `faostat` | `vnm_rice_producer_price_lcu.csv` | 쌀 농가수취가, 동/톤. 연간 1991–2025, 월간 2011–2025 |
| `faostat` | `vnm_cpi_monthly.csv` | 식품·일반 소비자물가지수, 2015=100, 월별 |
| `fpma` | `vnm_rice_wholesale_monthly.csv` | 안장·동탑·박리우 도매가, 동/kg. 25% 쇄미는 2008-01부터, 5% 쇄미는 2018-10부터 |
| `worldbank` | `fertilizer_and_rice_monthly.csv` | 요소·DAP·TSP·염화칼륨 국제가, 달러/톤, 1960-01부터. 베트남 쌀 5% 수출가는 2008-06부터 |

RiceAtlas 전 세계 원본은 `riceatlas/RiceCalendar_v1.zip`이다. FAOSTAT 품목 전체 생산자가격과 생산자물가 디플레이터, Pink Sheet 원본 `CMO-Historical-Data-Monthly.xlsx`, 연간 CPI `vnm_cpi_annual.csv`도 같은 폴더에 있다.

## 4. 아직 없는 것

VHLSS 마이크로데이터는 통계청 신청 자료라 받지 못했다. 살충제·제초제 kg당 국내 가격의 2008–2016 공개 지역 계열은 없다. 가구 면접 일자는 조사 밖에 없다. 쌀 소비자가격의 지역 단가도 이 폴더에는 없고, 있는 쌀 가격은 전국 농가수취가, 메콩 델타 도매가, 수출가이다.
