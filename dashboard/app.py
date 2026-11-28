"""Read-only dashboard over validated BigQuery marts."""

import os
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from google.cloud import bigquery


st.set_page_config(page_title="SKKU Finder 분석", layout="wide")
st.title("SKKU Finder 분석")

project = os.environ.get("GCP_PROJECT_ID", "")
dataset = os.environ.get("BIGQUERY_ANALYTICS_DATASET", "")
location = os.environ.get("BIGQUERY_LOCATION", "asia-northeast3")
if "_test_" in dataset:
    st.warning("합성 검증 데이터입니다. 운영 성과가 아닙니다.")
else:
    st.caption("운영 데이터 기준 · 한국 시간(Asia/Seoul) · 이벤트 기록 실패 시 실제 행동보다 적을 수 있음")
if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", project) or not re.fullmatch(
    r"[A-Za-z_][A-Za-z0-9_]{0,1023}", dataset
):
    st.error("GCP_PROJECT_ID와 BIGQUERY_ANALYTICS_DATASET을 설정하세요.")
    st.stop()

client = bigquery.Client(project=project)


@st.cache_data(ttl=300)
def read_table(name: str, version: str) -> pd.DataFrame:
    allowed = {"mart_service_daily", "mart_recommendation_daily",
               "mart_algorithm_daily", "mart_confirmed_pair_rank", "mart_raw_health",
               "mart_post_inventory", "mart_recommendation_generation"}
    if name not in allowed:
        raise ValueError("Unknown mart")
    rows = client.query(f"SELECT * FROM `{project}.{dataset}.{name}`",
                        location=location).result()
    return pd.DataFrame([dict(row.items()) for row in rows])


try:
    status = list(client.query(
        f"SELECT state, recorded_at FROM `{project}.{dataset}.pipeline_status` "
        "ORDER BY recorded_at DESC LIMIT 1", location=location).result())
except Exception as exc:
    st.error("분석 실행 상태를 읽지 못했습니다. 데이터 세트와 접근 권한을 확인하세요.")
    st.caption(type(exc).__name__)
    st.stop()
if not status or status[0].state != "READY":
    state = status[0].state if status else "아직 실행 없음"
    st.warning(f"검증된 분석 결과가 준비되지 않았습니다. 현재 상태: {state}")
    st.stop()

st.success(f"Raw 적재와 dbt 검사 완료: {status[0].recorded_at}")
if datetime.now(timezone.utc) - status[0].recorded_at > timedelta(hours=36):
    st.warning("마지막 성공 실행이 36시간을 넘었습니다. Airflow 예약 실행과 오류를 확인하세요.")
version = status[0].recorded_at.isoformat()
try:
    service = read_table("mart_service_daily", version)
    recommendation = read_table("mart_recommendation_daily", version)
    algorithm = read_table("mart_algorithm_daily", version)
    pairs = read_table("mart_confirmed_pair_rank", version)
    health = read_table("mart_raw_health", version)
    posts = read_table("mart_post_inventory", version)
    generation = read_table("mart_recommendation_generation", version)
except Exception as exc:
    st.error("Mart 조회에 실패했습니다. 대시보드가 이전 결과를 보여주지 않습니다.")
    st.caption(type(exc).__name__)
    st.stop()

open_posts = int(posts["open_posts"].sum()) if not posts.empty else 0
completed_posts = int(posts["completed_posts"].sum()) if not posts.empty else 0
generated_runs = int(generation["generated_runs"].sum()) if not generation.empty else 0
generated_items = int(generation["generated_items"].sum()) if not generation.empty else 0
columns = st.columns(4)
columns[0].metric("진행 중 게시글", open_posts)
columns[1].metric("완료 게시글", completed_posts)
columns[2].metric("추천 생성 기록", generated_runs)
columns[3].metric("생성된 추천 후보", generated_items)

st.subheader("게시글 현황")
if posts.empty:
    st.info("적재된 게시글이 없습니다.")
else:
    st.dataframe(posts.sort_values("post_type"), hide_index=True)
    st.caption("삭제 표시된 게시글은 진행 중·완료 건수에서 제외합니다. AI 보조 작성은 삭제되지 않은 게시글만 셉니다.")

st.subheader("추천 생성 현황")
if generation.empty:
    st.info("저장된 추천 생성 기록이 없습니다.")
else:
    st.dataframe(generation.sort_values("generated_runs", ascending=False), hide_index=True)
    st.caption("추천 생성 기록과 후보 수는 실제 화면 노출·클릭 횟수가 아닙니다. 캐시된 실행 ID는 다시 쓰일 수 있습니다.")

st.subheader("서비스 이용")
if service.empty:
    st.info("수집된 서비스 이벤트가 없습니다.")
else:
    st.dataframe(service.sort_values("activity_date", ascending=False), hide_index=True)
    st.caption("채팅 시작·반환 완료는 전체 건수입니다. 추천 클릭의 결과로 연결된 건수는 아닙니다.")

st.subheader("추천 노출과 클릭")
if recommendation.empty:
    st.info("추천 노출·클릭 이벤트가 없습니다. 추천 실행 기록을 노출로 대신 세지 않습니다.")
else:
    st.dataframe(recommendation.sort_values("event_date", ascending=False), hide_index=True)
    st.caption("클릭/노출 = 기록된 추천 클릭 이벤트 수 ÷ 기록된 후보 노출 이벤트 수. 노출 0이면 비율이 비어 있습니다.")

st.subheader("알고리즘 버전별 결과")
if algorithm.empty:
    st.info("버전에 연결된 추천 노출·클릭 이벤트가 없습니다.")
else:
    st.dataframe(algorithm.sort_values("event_date", ascending=False), hide_index=True)

st.subheader("확인된 반환 쌍의 추천 순위")
if pairs.empty:
    st.info("추천 실행과 연결되는 양측 확인 반환 쌍이 없습니다.")
else:
    pair_summary = (pairs.assign(
        rank_label=pairs["matched_rank"].fillna("미노출").astype(str)
    ).groupby(["algorithm_version", "rank_label"], dropna=False)
        .agg(recommendation_runs=("run_id", "count"),
             confirmed_pairs=("pair_id", "nunique"))
        .reset_index())
    st.dataframe(pair_summary, hide_index=True)
    st.caption("확인된 쌍이 연결된 추천 실행만 집계합니다. 전체 반환 성과로 일반화할 수 없습니다.")

st.subheader("데이터 품질과 최신성")
st.dataframe(health, hide_index=True)
st.caption("latest_source_at은 원본 데이터의 마지막 시각입니다. 적재 성공 시각은 위의 검사 완료 시각을 보세요. 빈 테이블의 최신 시각은 비어 있습니다.")
