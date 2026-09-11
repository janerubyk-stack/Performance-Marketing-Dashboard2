import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import timedelta
import calendar
import html
from openai import OpenAI


# ============================================================
# 0. 페이지 설정
# ============================================================

st.set_page_config(
    page_title="성과 비교 분석",
    page_icon="📈",
    layout="wide"
)


# ============================================================
# 1. Google Sheets 설정
# ============================================================

SHEET_ID = "161bKPiv4X1mxBBg1JOD7Q_Ra4DED-LZ3mpatD9xrc3w"
GID = "0"

SHEET_URL = (
    f"https://docs.google.com/spreadsheets/d/"
    f"{SHEET_ID}/export?format=csv&gid={GID}"
)


# ============================================================
# 2. 제목
# ============================================================

st.title("📈 성과 비교 분석")

st.caption(
    "선택한 카테고리 / 매체 / 캠페인 기준으로 "
    "현재 기간과 비교 기간의 성과를 확인합니다."
)


# ============================================================
# 3. 데이터 불러오기
# ============================================================

@st.cache_data(ttl=300)
def load_data():

    df = pd.read_csv(
        SHEET_URL,
        encoding="utf-8-sig"
    )

    # --------------------------------------------------------
    # 컬럼명 정리
    # --------------------------------------------------------

    df.columns = [
        str(col).strip()
        for col in df.columns
    ]


    # --------------------------------------------------------
    # 컬럼 자동 검색
    # --------------------------------------------------------

    def find_column(candidates):

        # 정확히 일치
        for candidate in candidates:

            for col in df.columns:

                if (
                    str(col).strip().lower()
                    ==
                    str(candidate).strip().lower()
                ):
                    return col


        # 부분 일치
        for candidate in candidates:

            for col in df.columns:

                if (
                    str(candidate).strip().lower()
                    in
                    str(col).strip().lower()
                ):
                    return col


        return None


    date_col = find_column([
        "date",
        "날짜"
    ])


    category_col = find_column([
        "type",
        "TYPE",
        "광고유형",
        "유형",
        "카테고리",
        "category"
    ])


    media_col = find_column([
        "media",
        "MEDIA",
        "매체"
    ])


    campaign_col = find_column([
        "campaign",
        "CAMPAIGN",
        "캠페인"
    ])


    impress_col = find_column([
        "impress",
        "impression",
        "노출"
    ])


    click_col = find_column([
        "click",
        "클릭"
    ])


    spend_col = find_column([
        "spend",
        "광고비"
    ])


    conversion_col = find_column([
        "conversion",
        "db",
        "DB",
        "전환"
    ])


    required = {

        "DATE": date_col,
        "CATEGORY": category_col,
        "MEDIA": media_col,
        "CAMPAIGN": campaign_col,
        "IMPRESS": impress_col,
        "CLICK": click_col,
        "SPEND": spend_col,
        "CONVERSION": conversion_col

    }


    missing = [
        key
        for key, value in required.items()
        if value is None
    ]


    if missing:

        raise ValueError(
            f"필수 컬럼을 찾을 수 없습니다: {missing}"
        )


    # --------------------------------------------------------
    # 내부 표준 컬럼
    # --------------------------------------------------------

    df = df.rename(
        columns={

            date_col: "date",
            category_col: "category",
            media_col: "media",
            campaign_col: "campaign",
            impress_col: "impress",
            click_col: "click",
            spend_col: "spend",
            conversion_col: "conversion"

        }
    )


    # --------------------------------------------------------
    # 날짜
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce"
    )


    # --------------------------------------------------------
    # 숫자 컬럼
    # --------------------------------------------------------

    numeric_cols = [
        "impress",
        "click",
        "spend",
        "conversion"
    ]


    for col in numeric_cols:

        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("-", "0", regex=False)
        )

        df[col] = pd.to_numeric(
            df[col],
            errors="coerce"
        ).fillna(0)


    # --------------------------------------------------------
    # 문자 컬럼
    # --------------------------------------------------------

    for col in [
        "category",
        "media",
        "campaign"
    ]:

        df[col] = (
            df[col]
            .fillna("미분류")
            .astype(str)
            .str.strip()
        )

        df.loc[
            df[col] == "",
            col
        ] = "미분류"


    # --------------------------------------------------------
    # 날짜 없는 행 제거
    # --------------------------------------------------------

    df = df.dropna(
        subset=["date"]
    ).copy()


    df["date"] = df["date"].dt.normalize()


    # --------------------------------------------------------
    # 정렬
    # --------------------------------------------------------

    df = (
        df
        .sort_values("date")
        .reset_index(drop=True)
    )


    return df


# ============================================================
# 4. 데이터 로드
# ============================================================

try:

    df = load_data()

except Exception as e:

    st.error(
        f"Google Sheets 데이터를 불러오지 못했습니다.\n\n{e}"
    )

    st.stop()


if df.empty:

    st.warning("데이터가 없습니다.")

    st.stop()


# ============================================================
# 5. 공통 함수
# ============================================================

def safe_change(current, previous):

    if (
        pd.isna(current)
        or pd.isna(previous)
        or previous == 0
    ):

        return np.nan


    return (
        (current - previous)
        / previous
        * 100
    )


def fmt_money(value):

    if pd.isna(value):
        return "-"

    return f"{value:,.0f}원"


def fmt_number(value):

    if pd.isna(value):
        return "-"

    return f"{value:,.0f}건"


def fmt_percent(value):

    if pd.isna(value):
        return "-"

    return f"{value:.2f}%"


def fmt_change(value):

    if pd.isna(value):
        return "-"

    if value > 0:
        return f"▲ +{value:.1f}%"

    if value < 0:
        return f"▼ {value:.1f}%"

    return "─ 0.0%"


def fmt_change_with_new(
    current,
    previous,
    value
):

    if (
        pd.notna(previous)
        and previous == 0
        and pd.notna(current)
        and current > 0
    ):

        return "비교 0 → 신규"


    return fmt_change(value)


def change_class(value):

    if pd.isna(value):
        return "neutral"

    if value > 0:
        return "up"

    if value < 0:
        return "down"

    return "neutral"


# ============================================================
# 6. 기간 계산
# ============================================================

def get_periods(
    base_date,
    period_type
):

    base_date = pd.Timestamp(base_date)


    # --------------------------------------------------------
    # 전일
    # --------------------------------------------------------

    if period_type == "전일":

        current_start = base_date
        current_end = base_date

        previous_start = (
            base_date -
            timedelta(days=1)
        )

        previous_end = previous_start


    # --------------------------------------------------------
    # 전주
    # --------------------------------------------------------

    elif period_type == "전주":

        weekday = base_date.weekday()

        current_start = (
            base_date -
            timedelta(days=weekday)
        )

        current_end = base_date

        elapsed_days = (
            current_end -
            current_start
        ).days

        previous_end = (
            current_end -
            timedelta(days=7)
        )

        previous_start = (
            previous_end -
            timedelta(days=elapsed_days)
        )


    # --------------------------------------------------------
    # 전월
    # --------------------------------------------------------

    elif period_type == "전월":

        current_start = base_date.replace(
            day=1
        )

        current_end = base_date

        day_number = base_date.day

        previous_month_last = (
            base_date.replace(day=1)
            -
            timedelta(days=1)
        )

        previous_year = (
            previous_month_last.year
        )

        previous_month = (
            previous_month_last.month
        )

        previous_month_days = calendar.monthrange(
            previous_year,
            previous_month
        )[1]

        previous_day = min(
            day_number,
            previous_month_days
        )

        previous_start = pd.Timestamp(
            previous_year,
            previous_month,
            1
        )

        previous_end = pd.Timestamp(
            previous_year,
            previous_month,
            previous_day
        )


    else:

        raise ValueError(
            "잘못된 기간 유형입니다."
        )


    return (
        pd.Timestamp(current_start),
        pd.Timestamp(current_end),
        pd.Timestamp(previous_start),
        pd.Timestamp(previous_end)
    )


def format_period(
    start_date,
    end_date
):

    return (
        f"{pd.Timestamp(start_date).strftime('%Y-%m-%d')}"
        f" ~ "
        f"{pd.Timestamp(end_date).strftime('%Y-%m-%d')}"
    )


# ============================================================
# 7. 분석 조건
# ============================================================

st.subheader("🔎 분석 조건")


available_dates = sorted(
    df["date"]
    .dropna()
    .unique()
)


if not available_dates:

    st.warning(
        "분석 가능한 날짜 데이터가 없습니다."
    )

    st.stop()


min_date = pd.Timestamp(
    min(available_dates)
).date()


max_date = pd.Timestamp(
    max(available_dates)
).date()


col1, col2, col3 = st.columns(
    [1, 1.5, 2]
)


# ============================================================
# 기준일
# ============================================================

with col1:

    base_date = st.date_input(
        "기준일",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="base_date"
    )


# ============================================================
# 비교 기간
# ============================================================

with col2:

    period_type = st.radio(
        "비교 기간",
        [
            "전일",
            "전주",
            "전월",
            "지정"
        ],
        horizontal=True,
        key="period_type"
    )


# ============================================================
# 기간 설정
# ============================================================

if period_type != "지정":

    (
        current_start,
        current_end,
        previous_start,
        previous_end
    ) = get_periods(
        base_date,
        period_type
    )

    elapsed_days = (
        current_end -
        current_start
    ).days + 1


else:

    st.markdown("### 📅 지정 기간")

    custom_col1, custom_col2 = st.columns(2)


    with custom_col1:

        custom_current_start = st.date_input(
            "기준 시작일",
            value=(
                pd.Timestamp(base_date)
                -
                timedelta(days=6)
            ).date(),
            min_value=min_date,
            max_value=base_date,
            key="custom_current_start"
        )


        custom_current_end = st.date_input(
            "기준 종료일",
            value=base_date,
            min_value=min_date,
            max_value=max_date,
            key="custom_current_end"
        )


    custom_elapsed_days = (
        pd.Timestamp(custom_current_end)
        -
        pd.Timestamp(custom_current_start)
    ).days + 1


    with custom_col2:

        st.markdown(
            f"**기준 기간 일수: {custom_elapsed_days}일**"
        )


        custom_previous_start = st.date_input(
            "비교 시작일",
            value=(
                pd.Timestamp(custom_current_start)
                -
                timedelta(
                    days=custom_elapsed_days
                )
            ).date(),
            min_value=min_date,
            max_value=max_date,
            key="custom_previous_start"
        )


        custom_previous_end = st.date_input(
            "비교 종료일",
            value=(
                pd.Timestamp(custom_previous_start)
                +
                timedelta(
                    days=custom_elapsed_days - 1
                )
            ).date(),
            min_value=min_date,
            max_value=max_date,
            key="custom_previous_end"
        )


    previous_elapsed_days = (
        pd.Timestamp(custom_previous_end)
        -
        pd.Timestamp(custom_previous_start)
    ).days + 1


    if custom_elapsed_days != previous_elapsed_days:

        st.error(
            f"⚠️ 기준 기간은 {custom_elapsed_days}일인데 "
            f"비교 기간은 {previous_elapsed_days}일입니다. "
            f"동일한 일수로 설정해주세요."
        )

        st.stop()


    current_start = pd.Timestamp(
        custom_current_start
    )

    current_end = pd.Timestamp(
        custom_current_end
    )

    previous_start = pd.Timestamp(
        custom_previous_start
    )

    previous_end = pd.Timestamp(
        custom_previous_end
    )

    elapsed_days = custom_elapsed_days


# ============================================================
# 기간 표시
# ============================================================

current_period_text = format_period(
    current_start,
    current_end
)


previous_period_text = format_period(
    previous_start,
    previous_end
)


with col3:

    st.info(
        f"""
**기준 기간:** {current_period_text}

**비교 기간:** {previous_period_text}

**동일 진행일수:** {elapsed_days}일
"""
    )


# ============================================================
# 8. 종속 필터
# ============================================================

# ------------------------------------------------------------
# 8-1. 카테고리
# ------------------------------------------------------------

category_options = sorted(
    df["category"]
    .dropna()
    .unique()
    .tolist()
)

if not category_options:
    st.warning("선택 가능한 카테고리가 없습니다.")
    st.stop()


# 이전 카테고리 선택값 확인
previous_categories = st.session_state.get(
    "_previous_categories",
    None
)


filter_col1, filter_col2, filter_col3 = st.columns(
    [1, 2, 2]
)


with filter_col1:

    selected_categories = st.multiselect(
        "카테고리",
        options=category_options,
        default=(
            st.session_state.get(
                "category_filter",
                category_options
            )
        ),
        key="category_filter"
    )


# ------------------------------------------------------------
# 8-2. 카테고리에 종속된 매체 목록
# ------------------------------------------------------------

media_source_df = df[
    df["category"].isin(
        selected_categories
    )
].copy()


media_options = sorted(
    media_source_df["media"]
    .dropna()
    .unique()
    .tolist()
)


# ------------------------------------------------------------
# 카테고리가 변경되었는지 확인
# ------------------------------------------------------------

category_changed = (
    previous_categories is not None
    and set(previous_categories)
    != set(selected_categories)
)


# ------------------------------------------------------------
# 기존 매체 선택값 보정
# ------------------------------------------------------------

current_media_selection = st.session_state.get(
    "media_filter",
    None
)


if category_changed:

    # 카테고리가 바뀌면
    # 해당 카테고리에서 사용할 수 있는 매체를 전체 선택
    st.session_state["media_filter"] = (
        media_options.copy()
    )

else:

    if current_media_selection is None:

        # 최초 실행
        st.session_state["media_filter"] = (
            media_options.copy()
        )

    else:

        # 현재 카테고리에서 존재하는 매체만 유지
        st.session_state["media_filter"] = [
            media
            for media in current_media_selection
            if media in media_options
        ]


with filter_col2:

    selected_media = st.multiselect(
        "매체",
        options=media_options,
        key="media_filter"
    )


# ------------------------------------------------------------
# 8-3. 카테고리 + 매체에 종속된 캠페인 목록
# ------------------------------------------------------------

campaign_source_df = df[
    df["category"].isin(
        selected_categories
    )
    &
    df["media"].isin(
        selected_media
    )
].copy()


campaign_options = sorted(
    campaign_source_df["campaign"]
    .dropna()
    .unique()
    .tolist()
)


# ------------------------------------------------------------
# 기존 캠페인 선택값 보정
# ------------------------------------------------------------

current_campaign_selection = st.session_state.get(
    "campaign_filter",
    None
)


if category_changed:

    # 카테고리가 변경되면
    # 새롭게 연결된 캠페인을 전체 선택
    st.session_state["campaign_filter"] = (
        campaign_options.copy()
    )

else:

    if current_campaign_selection is None:

        # 최초 실행
        st.session_state["campaign_filter"] = (
            campaign_options.copy()
        )

    else:

        # 현재 카테고리 + 매체에서 존재하는
        # 캠페인만 유지
        st.session_state["campaign_filter"] = [
            campaign
            for campaign in current_campaign_selection
            if campaign in campaign_options
        ]


with filter_col3:

    selected_campaigns = st.multiselect(
        "캠페인",
        options=campaign_options,
        key="campaign_filter"
    )


# ------------------------------------------------------------
# 현재 선택값 저장
# ------------------------------------------------------------

st.session_state["_previous_categories"] = (
    selected_categories.copy()
)


# ============================================================
# 8-4. 전체 선택 버튼
# ============================================================

button_col1, button_col2, button_col3 = st.columns(3)


with button_col1:

    if st.button(
        "📌 카테고리 전체 선택",
        use_container_width=True
    ):

        st.session_state[
            "category_filter"
        ] = category_options

        # 전체 카테고리에 연결된 매체
        all_media = sorted(
            df[
                df["category"].isin(
                    category_options
                )
            ]["media"]
            .dropna()
            .unique()
            .tolist()
        )

        st.session_state[
            "media_filter"
        ] = all_media

        # 전체 카테고리에 연결된 캠페인
        all_campaigns = sorted(
            df[
                df["category"].isin(
                    category_options
                )
            ]["campaign"]
            .dropna()
            .unique()
            .tolist()
        )

        st.session_state[
            "campaign_filter"
        ] = all_campaigns

        st.session_state[
            "_previous_categories"
        ] = category_options

        st.rerun()


with button_col2:

    if st.button(
        "📌 매체 전체 선택",
        use_container_width=True
    ):

        # 현재 선택된 카테고리 안에서만 전체 선택
        current_media_options = sorted(
            df[
                df["category"].isin(
                    selected_categories
                )
            ]["media"]
            .dropna()
            .unique()
            .tolist()
        )

        st.session_state[
            "media_filter"
        ] = current_media_options

        # 선택된 매체에 연결된 캠페인도 전체 선택
        current_campaign_options = sorted(
            df[
                df["category"].isin(
                    selected_categories
                )
                &
                df["media"].isin(
                    current_media_options
                )
            ]["campaign"]
            .dropna()
            .unique()
            .tolist()
        )

        st.session_state[
            "campaign_filter"
        ] = current_campaign_options

        st.rerun()


with button_col3:

    if st.button(
        "📌 캠페인 전체 선택",
        use_container_width=True
    ):

        # 현재 선택된 카테고리 + 매체 안에서
        # 캠페인 전체 선택
        current_campaign_options = sorted(
            df[
                df["category"].isin(
                    selected_categories
                )
                &
                df["media"].isin(
                    selected_media
                )
            ]["campaign"]
            .dropna()
            .unique()
            .tolist()
        )

        st.session_state[
            "campaign_filter"
        ] = current_campaign_options

        st.rerun()


# ============================================================
# 9. 필터 데이터
# ============================================================

filtered_df = df[
    df["category"].isin(
        selected_categories
    )
    &
    df["media"].isin(
        selected_media
    )
    &
    df["campaign"].isin(
        selected_campaigns
    )
].copy()

# ============================================================
# 10. 성과 집계
# ============================================================

def aggregate_performance(
    data,
    start_date,
    end_date
):

    temp = data[
        (data["date"] >= pd.Timestamp(start_date))
        &
        (data["date"] <= pd.Timestamp(end_date))
    ].copy()


    if temp.empty:

        return pd.DataFrame(
            columns=[
                "category",
                "media",
                "campaign",
                "impress",
                "click",
                "spend",
                "conversion",
                "CPA",
                "CVR"
            ]
        )


    result = (
        temp
        .groupby(
            [
                "category",
                "media",
                "campaign"
            ],
            as_index=False
        )
        .agg(
            impress=("impress", "sum"),
            click=("click", "sum"),
            spend=("spend", "sum"),
            conversion=("conversion", "sum")
        )
    )


    result["CPA"] = np.where(
        result["conversion"] > 0,
        result["spend"] /
        result["conversion"],
        np.nan
    )


    result["CVR"] = np.where(
        result["click"] > 0,
        result["conversion"] /
        result["click"] *
        100,
        np.nan
    )


    return result


current_df = aggregate_performance(
    filtered_df,
    current_start,
    current_end
)


previous_df = aggregate_performance(
    filtered_df,
    previous_start,
    previous_end
)


# ============================================================
# 11. 매체별 집계
# ============================================================

def aggregate_by_media(data):

    if data.empty:

        return pd.DataFrame(
            columns=[
                "media",
                "impress",
                "click",
                "spend",
                "conversion",
                "CPA",
                "CVR"
            ]
        )


    result = (
        data
        .groupby(
            "media",
            as_index=False
        )
        .agg(
            impress=("impress", "sum"),
            click=("click", "sum"),
            spend=("spend", "sum"),
            conversion=("conversion", "sum")
        )
    )


    result["CPA"] = np.where(
        result["conversion"] > 0,
        result["spend"] /
        result["conversion"],
        np.nan
    )


    result["CVR"] = np.where(
        result["click"] > 0,
        result["conversion"] /
        result["click"] *
        100,
        np.nan
    )


    return result


current_media = aggregate_by_media(
    current_df
)


previous_media = aggregate_by_media(
    previous_df
)


# ============================================================
# 12. 캠페인별 집계
# ============================================================

def aggregate_by_campaign(data):

    if data.empty:

        return pd.DataFrame(
            columns=[
                "campaign",
                "spend",
                "click",
                "conversion",
                "CPA",
                "CVR"
            ]
        )


    result = (
        data
        .groupby(
            "campaign",
            as_index=False
        )
        .agg(
            spend=("spend", "sum"),
            click=("click", "sum"),
            conversion=("conversion", "sum")
        )
    )


    result["CPA"] = np.where(
        result["conversion"] > 0,
        result["spend"] /
        result["conversion"],
        np.nan
    )


    result["CVR"] = np.where(
        result["click"] > 0,
        result["conversion"] /
        result["click"] *
        100,
        np.nan
    )


    return result


current_campaign = aggregate_by_campaign(
    current_df
)


previous_campaign = aggregate_by_campaign(
    previous_df
)


# ============================================================
# 13. 비교 데이터
# ============================================================

def create_comparison(
    current,
    previous,
    group_col
):

    current = current.copy()
    previous = previous.copy()


    if current.empty:

        current = pd.DataFrame(
            columns=[
                group_col,
                "spend",
                "click",
                "conversion"
            ]
        )


    if previous.empty:

        previous = pd.DataFrame(
            columns=[
                group_col,
                "spend",
                "click",
                "conversion"
            ]
        )


    current = current.set_index(
        group_col
    )


    previous = previous.set_index(
        group_col
    )


    groups = sorted(
        set(current.index)
        |
        set(previous.index)
    )


    rows = []


    for group in groups:

        c = (
            current.loc[group]
            if group in current.index
            else pd.Series(dtype=float)
        )


        p = (
            previous.loc[group]
            if group in previous.index
            else pd.Series(dtype=float)
        )


        c_spend = float(
            c.get("spend", 0)
        )


        p_spend = float(
            p.get("spend", 0)
        )


        c_click = float(
            c.get("click", 0)
        )


        p_click = float(
            p.get("click", 0)
        )


        c_conversion = float(
            c.get("conversion", 0)
        )


        p_conversion = float(
            p.get("conversion", 0)
        )


        c_cpa = (
            c_spend /
            c_conversion
            if c_conversion > 0
            else np.nan
        )


        p_cpa = (
            p_spend /
            p_conversion
            if p_conversion > 0
            else np.nan
        )


        c_cvr = (
            c_conversion /
            c_click *
            100
            if c_click > 0
            else np.nan
        )


        p_cvr = (
            p_conversion /
            p_click *
            100
            if p_click > 0
            else np.nan
        )


        rows.append({

            group_col: group,

            "spend_current":
                c_spend,

            "spend_previous":
                p_spend,

            "click_current":
                c_click,

            "click_previous":
                p_click,

            "conversion_current":
                c_conversion,

            "conversion_previous":
                p_conversion,

            "CPA_current":
                c_cpa,

            "CPA_previous":
                p_cpa,

            "CVR_current":
                c_cvr,

            "CVR_previous":
                p_cvr

        })


    result = pd.DataFrame(rows)


    if result.empty:
        return result


    result["spend_change"] = result.apply(
        lambda x: safe_change(
            x["spend_current"],
            x["spend_previous"]
        ),
        axis=1
    )


    result["conversion_change"] = result.apply(
        lambda x: safe_change(
            x["conversion_current"],
            x["conversion_previous"]
        ),
        axis=1
    )


    result["CPA_change"] = result.apply(
        lambda x: safe_change(
            x["CPA_current"],
            x["CPA_previous"]
        ),
        axis=1
    )


    result["CVR_change"] = result.apply(
        lambda x: safe_change(
            x["CVR_current"],
            x["CVR_previous"]
        ),
        axis=1
    )


    return result


comparison = create_comparison(
    current_media,
    previous_media,
    "media"
)


campaign_comparison = create_comparison(
    current_campaign,
    previous_campaign,
    "campaign"
)


# ============================================================
# 14. 전체 성과 요약
# ============================================================

st.divider()

st.header("📊 전체 성과 요약")


total_current_spend = (
    current_df["spend"].sum()
)


total_previous_spend = (
    previous_df["spend"].sum()
)


total_current_conversion = (
    current_df["conversion"].sum()
)


total_previous_conversion = (
    previous_df["conversion"].sum()
)


total_current_click = (
    current_df["click"].sum()
)


total_previous_click = (
    previous_df["click"].sum()
)


total_current_cpa = (
    total_current_spend /
    total_current_conversion
    if total_current_conversion > 0
    else np.nan
)


total_previous_cpa = (
    total_previous_spend /
    total_previous_conversion
    if total_previous_conversion > 0
    else np.nan
)


total_current_cvr = (
    total_current_conversion /
    total_current_click *
    100
    if total_current_click > 0
    else np.nan
)


total_previous_cvr = (
    total_previous_conversion /
    total_previous_click *
    100
    if total_previous_click > 0
    else np.nan
)


total_spend_change = safe_change(
    total_current_spend,
    total_previous_spend
)


total_conversion_change = safe_change(
    total_current_conversion,
    total_previous_conversion
)


total_cpa_change = safe_change(
    total_current_cpa,
    total_previous_cpa
)


total_cvr_change = safe_change(
    total_current_cvr,
    total_previous_cvr
)


summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)


with summary_col1:

    st.metric(
        "광고비",
        fmt_money(
            total_current_spend
        ),
        (
            f"{total_spend_change:+.1f}%"
            if pd.notna(total_spend_change)
            else "-"
        )
    )


with summary_col2:

    st.metric(
        "전환수",
        fmt_number(
            total_current_conversion
        ),
        (
            f"{total_conversion_change:+.1f}%"
            if pd.notna(total_conversion_change)
            else "-"
        )
    )


with summary_col3:

    st.metric(
        "CPA",
        fmt_money(
            total_current_cpa
        ),
        (
            f"{total_cpa_change:+.1f}%"
            if pd.notna(total_cpa_change)
            else "-"
        ),
        delta_color="inverse"
    )


with summary_col4:

    st.metric(
        "CVR",
        fmt_percent(
            total_current_cvr
        ),
        (
            f"{total_cvr_change:+.1f}%"
            if pd.notna(total_cvr_change)
            else "-"
        )
    )


# ============================================================
# 16. 성과 비교
# ============================================================

st.divider()

st.header("📊 성과 비교")

st.caption(
    f"기준 기간: {current_period_text} | "
    f"비교 기간: {previous_period_text} | "
    f"동일 진행일수: {elapsed_days}일"
)


chart_df = comparison[
    comparison["media"].isin(
        selected_media
    )
].copy()


chart_df = chart_df.sort_values(
    "conversion_current",
    ascending=False
)


x_labels = chart_df[
    "media"
].tolist()


# ============================================================
# CPA + 전환수
# ============================================================

fig_cpa = go.Figure()


fig_cpa.add_trace(
    go.Bar(
        x=x_labels,
        y=chart_df["CPA_current"],
        name="기준 CPA",
        text=[
            (
                f"{v:,.0f}원"
                if pd.notna(v)
                else "-"
            )
            for v in chart_df["CPA_current"]
        ],
        textposition="outside"
    )
)


fig_cpa.add_trace(
    go.Bar(
        x=x_labels,
        y=chart_df["CPA_previous"],
        name="비교 CPA",
        text=[
            (
                f"{v:,.0f}원"
                if pd.notna(v)
                else "-"
            )
            for v in chart_df["CPA_previous"]
        ],
        textposition="outside"
    )
)


fig_cpa.add_trace(
    go.Scatter(
        x=x_labels,
        y=chart_df["conversion_current"],
        name="기준 전환수",
        mode="lines+markers",
        yaxis="y2"
    )
)


fig_cpa.add_trace(
    go.Scatter(
        x=x_labels,
        y=chart_df["conversion_previous"],
        name="비교 전환수",
        mode="lines+markers",
        yaxis="y2"
    )
)


fig_cpa.update_layout(

    title="CPA + 전환수",

    barmode="group",

    height=390,

    margin=dict(
        l=50,
        r=50,
        t=70,
        b=100
    ),

    xaxis=dict(
        title="매체",
        type="category",
        tickangle=-35,
        automargin=True
    ),

    yaxis=dict(
        title="CPA"
    ),

    yaxis2=dict(
        title="전환수",
        overlaying="y",
        side="right"
    ),

    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.30,
        xanchor="center",
        x=0.5
    ),

    hovermode="x unified"
)


# ============================================================
# 광고비 + 전환수
# ============================================================

fig_spend = go.Figure()


fig_spend.add_trace(
    go.Bar(
        x=x_labels,
        y=chart_df["spend_current"],
        name="기준 광고비",
        text=[
            f"{v:,.0f}"
            for v in chart_df["spend_current"]
        ],
        textposition="outside"
    )
)


fig_spend.add_trace(
    go.Bar(
        x=x_labels,
        y=chart_df["spend_previous"],
        name="비교 광고비",
        text=[
            f"{v:,.0f}"
            for v in chart_df["spend_previous"]
        ],
        textposition="outside"
    )
)


fig_spend.add_trace(
    go.Scatter(
        x=x_labels,
        y=chart_df["conversion_current"],
        name="기준 전환수",
        mode="lines+markers",
        yaxis="y2"
    )
)


fig_spend.add_trace(
    go.Scatter(
        x=x_labels,
        y=chart_df["conversion_previous"],
        name="비교 전환수",
        mode="lines+markers",
        yaxis="y2"
    )
)


fig_spend.update_layout(

    title="광고비 + 전환수",

    barmode="group",

    height=390,

    margin=dict(
        l=50,
        r=50,
        t=70,
        b=100
    ),

    xaxis=dict(
        title="매체",
        type="category",
        tickangle=-35,
        automargin=True
    ),

    yaxis=dict(
        title="광고비"
    ),

    yaxis2=dict(
        title="전환수",
        overlaying="y",
        side="right"
    ),

    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=-0.30,
        xanchor="center",
        x=0.5
    ),

    hovermode="x unified"
)


graph_col1, graph_col2 = st.columns(2)


with graph_col1:

    st.plotly_chart(
        fig_cpa,
        use_container_width=True,
        config={
            "displayModeBar": False
        }
    )


with graph_col2:

    st.plotly_chart(
        fig_spend,
        use_container_width=True,
        config={
            "displayModeBar": False
        }
    )


# ============================================================
# 17. 매체별 상세 성과 비교
# ============================================================

st.divider()

st.header("📋 매체별 상세 성과 비교")

st.caption(
    "매체를 가로로 배치하고 성과 지표를 세로로 비교합니다."
)


media_table = comparison[
    comparison["media"].isin(
        selected_media
    )
].copy()


media_table = media_table.sort_values(
    "conversion_current",
    ascending=False
)


metric_rows = [

    (
        "광고비",
        "spend_current",
        "spend_previous",
        "spend_change",
        "money"
    ),

    (
        "전환수",
        "conversion_current",
        "conversion_previous",
        "conversion_change",
        "number"
    ),

    (
        "CPA",
        "CPA_current",
        "CPA_previous",
        "CPA_change",
        "cpa"
    ),

    (
        "CVR",
        "CVR_current",
        "CVR_previous",
        "CVR_change",
        "percent"
    )

]


# ============================================================
# HTML 테이블
# ============================================================

if media_table.empty:

    st.info(
        "선택한 매체의 성과 데이터가 없습니다."
    )

else:

    table_html = """
    <style>

    .performance-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }

    .performance-table th,
    .performance-table td {
        border: 1px solid #dddddd;
        padding: 10px;
        text-align: center;
        white-space: nowrap;
    }

    .performance-table th {
        background-color: #f5f5f5;
        font-weight: 700;
    }

    .performance-table td.metric {
        text-align: left;
        font-weight: 700;
        background-color: #fafafa;
        min-width: 80px;
    }

    .up {
        color: #d62728;
        font-weight: 700;
    }

    .down {
        color: #2468c7;
        font-weight: 700;
    }

    .neutral {
        color: #666666;
        font-weight: 700;
    }

    </style>

    <table class="performance-table">

    <tr>

    <th>지표</th>
    """


    for media in media_table["media"]:

        table_html += (
            f"<th>{html.escape(str(media))}</th>"
        )


    table_html += "</tr>"


    for (
        metric_name,
        current_col,
        previous_col,
        change_col,
        fmt_type
    ) in metric_rows:

        table_html += (
            "<tr>"
            f'<td class="metric">{metric_name}</td>'
        )


        for _, row in media_table.iterrows():

            current_value = row[current_col]

            previous_value = row[previous_col]

            change_value = row[change_col]


            if fmt_type in [
                "money",
                "cpa"
            ]:

                current_text = fmt_money(
                    current_value
                )

                previous_text = fmt_money(
                    previous_value
                )


            elif fmt_type == "number":

                current_text = fmt_number(
                    current_value
                )

                previous_text = fmt_number(
                    previous_value
                )


            else:

                current_text = fmt_percent(
                    current_value
                )

                previous_text = fmt_percent(
                    previous_value
                )


            change_text = fmt_change_with_new(
                current_value,
                previous_value,
                change_value
            )


            css_class = change_class(
                change_value
            )


            table_html += f"""
            <td>
                <div>
                    기준: <b>{current_text}</b>
                </div>

                <div style="color:#888;">
                    비교: {previous_text}
                </div>

                <div style="margin-top:4px;">
                    <span class="{css_class}">
                        {html.escape(change_text)}
                    </span>
                </div>
            </td>
            """


        table_html += "</tr>"


    table_html += """
    </table>
    """


    st.html(table_html)


# ============================================================
# 18. 매체별 성과 코멘트
# ============================================================

st.subheader("📝 매체별 성과 코멘트")


if media_table.empty:

    st.info(
        "선택한 매체의 성과 데이터가 없습니다."
    )

else:

    current_total_conversion = (
        media_table["conversion_current"].sum()
    )


    valid_media = media_table[
        media_table["conversion_current"] > 0
    ].copy()


    if valid_media.empty:

        st.info(
            "현재 기간에 전환이 발생한 매체가 없습니다."
        )

    else:

        st.markdown(
            f"""
📊 **전체 매체 성과:** 현재 기간 전체 전환은
**{total_current_conversion:,.0f}건**이며,
광고비는 **{total_current_spend:,.0f}원**,
전체 CPA는 **{fmt_money(total_current_cpa)}**입니다.
비교 기간 대비 전환수는
**{fmt_change(total_conversion_change)}**,
CPA는 **{fmt_change(total_cpa_change)}** 변화했습니다.
"""
        )


        # ----------------------------------------------------
        # 전환수 최다 매체
        # ----------------------------------------------------

        top_media = valid_media.loc[
            valid_media[
                "conversion_current"
            ].idxmax()
        ]


        top_media_share = (
            top_media["conversion_current"]
            /
            current_total_conversion
            *
            100
            if current_total_conversion > 0
            else np.nan
        )


        st.markdown(
            f"""
🏆 **전환수 최다 매체:** `{top_media['media']}` —
전환 **{top_media['conversion_current']:,.0f}건**,
CPA **{fmt_money(top_media['CPA_current'])}**
(전체 전환의 **{top_media_share:.1f}%**)
"""
        )


        # ----------------------------------------------------
        # CPA 최우수 매체
        # ----------------------------------------------------

        media_cpa_valid = valid_media[
            valid_media["CPA_current"].notna()
            &
            (valid_media["CPA_current"] > 0)
        ]


        if not media_cpa_valid.empty:

            best_cpa_media = media_cpa_valid.loc[
                media_cpa_valid[
                    "CPA_current"
                ].idxmin()
            ]


            best_cpa_share = (
                best_cpa_media[
                    "conversion_current"
                ]
                /
                current_total_conversion
                *
                100
            )


            st.markdown(
                f"""
💰 **CPA 최우수 매체:** `{best_cpa_media['media']}` —
CPA **{best_cpa_media['CPA_current']:,.0f}원**,
전환 **{best_cpa_media['conversion_current']:,.0f}건**
(전체 전환의 **{best_cpa_share:.1f}%**)
"""
            )


        # ----------------------------------------------------
        # 매체별 상세 분석
        # ----------------------------------------------------

        st.markdown("### 🔎 매체별 상세 분석")


        for _, row in valid_media.iterrows():

            media_name = row["media"]

            conversion = row[
                "conversion_current"
            ]

            cpa = row[
                "CPA_current"
            ]

            cvr = row[
                "CVR_current"
            ]

            spend = row[
                "spend_current"
            ]

            spend_change = row[
                "spend_change"
            ]

            conversion_change = row[
                "conversion_change"
            ]

            cpa_change = row[
                "CPA_change"
            ]

            cvr_change = row[
                "CVR_change"
            ]


            share = (
                conversion /
                current_total_conversion *
                100
                if current_total_conversion > 0
                else np.nan
            )


            comment_parts = []


            comment_parts.append(
                f"현재 {conversion:,.0f}건의 전환을 확보하며 "
                f"전체 전환의 {share:.1f}%를 담당하고 있습니다."
            )


            if pd.notna(cpa):

                comment_parts.append(
                    f"현재 CPA는 {cpa:,.0f}원"
                )


            if pd.notna(cvr):

                comment_parts.append(
                    f"CVR은 {cvr:.2f}%"
                )


            # ------------------------------------------------
            # 광고비 변화
            # ------------------------------------------------

            if pd.notna(spend_change):

                if spend_change > 10:

                    comment_parts.append(
                        f"광고비는 비교 기간 대비 "
                        f"{spend_change:+.1f}% 증가했습니다."
                    )

                elif spend_change < -10:

                    comment_parts.append(
                        f"광고비는 비교 기간 대비 "
                        f"{spend_change:+.1f}% 감소했습니다."
                    )

                else:

                    comment_parts.append(
                        f"광고비는 비교 기간 대비 "
                        f"{spend_change:+.1f}%로 큰 변화가 없습니다."
                    )

            elif row["spend_previous"] == 0:

                comment_parts.append(
                    "비교 기간에는 광고비 집행이 없어 "
                    "현재 기간 신규 집행 성과로 볼 수 있습니다."
                )


            # ------------------------------------------------
            # 전환 변화
            # ------------------------------------------------

            if pd.notna(conversion_change):

                if conversion_change > 20:

                    comment_parts.append(
                        f"전환수는 비교 기간 대비 "
                        f"{conversion_change:+.1f}% 증가해 "
                        f"볼륨 확대가 뚜렷합니다."
                    )

                elif conversion_change < -20:

                    comment_parts.append(
                        f"전환수는 비교 기간 대비 "
                        f"{conversion_change:+.1f}% 감소해 "
                        f"유입량과 전환 효율을 함께 점검할 필요가 있습니다."
                    )

                else:

                    comment_parts.append(
                        f"전환수는 비교 기간 대비 "
                        f"{conversion_change:+.1f}% 변화했습니다."
                    )

            elif row["conversion_previous"] == 0:

                comment_parts.append(
                    "비교 기간 전환 0건에서 현재 전환이 발생해 "
                    "신규 성과가 확인됩니다."
                )


            # ------------------------------------------------
            # CPA 변화
            # ------------------------------------------------

            if pd.notna(cpa_change):

                if cpa_change < -10:

                    comment_parts.append(
                        f"CPA는 {cpa_change:+.1f}% 개선되어 "
                        f"동일한 전환 확보에 필요한 비용 효율이 좋아졌습니다."
                    )

                elif cpa_change > 10:

                    comment_parts.append(
                        f"CPA는 {cpa_change:+.1f}% 상승해 "
                        f"예산 확대 또는 전환 효율 저하 여부를 확인할 필요가 있습니다."
                    )


            # ------------------------------------------------
            # CVR 변화
            # ------------------------------------------------

            if pd.notna(cvr_change):

                if cvr_change > 10:

                    comment_parts.append(
                        f"CVR은 {cvr_change:+.1f}% 개선되어 "
                        f"클릭 이후 전환 효율이 좋아진 것으로 판단됩니다."
                    )

                elif cvr_change < -10:

                    comment_parts.append(
                        f"CVR은 {cvr_change:+.1f}% 하락해 "
                        f"랜딩페이지, 타겟팅, 소재와 유입 품질을 점검할 필요가 있습니다."
                    )


            # ------------------------------------------------
            # 액션
            # ------------------------------------------------

            if (
                pd.notna(cpa_change)
                and cpa_change < -10
                and pd.notna(conversion_change)
                and conversion_change > 0
            ):

                action = (
                    "전환 증가와 CPA 개선이 동시에 나타나는 만큼 "
                    "우수 캠페인의 예산 확대를 우선 검토할 수 있습니다."
                )

            elif (
                pd.notna(cpa_change)
                and cpa_change > 10
            ):

                action = (
                    "효율 악화가 확인되는 만큼 "
                    "캠페인별 CPA 편차를 확인한 뒤 "
                    "저효율 캠페인의 예산 조정과 소재·타겟 재점검이 필요합니다."
                )

            elif (
                pd.notna(conversion_change)
                and conversion_change > 20
            ):

                action = (
                    "전환 볼륨이 빠르게 증가하고 있으므로 "
                    "현재 CPA 수준이 유지되는지 확인하면서 "
                    "점진적인 예산 확대를 검토하는 것이 좋습니다."
                )

            else:

                action = (
                    "현재 성과를 유지하면서 "
                    "캠페인별 CPA와 CVR 편차를 추가로 확인해 "
                    "예산 재배분 기회를 찾는 것이 좋습니다."
                )


            st.markdown(
                f"""
**📌 `{media_name}`**

- **현재 성과:** {" ".join(comment_parts)}
- **운영 제안:** {action}
"""
            )


# ============================================================
# 19. 캠페인별 상세 성과 비교
# ============================================================

st.divider()

st.header("🔍 캠페인별 상세 성과 비교")

st.caption(
    "선택한 카테고리 / 매체 / 캠페인 조건 안에서 "
    "캠페인별 상세 성과를 비교합니다."
)


campaign_table = campaign_comparison[
    campaign_comparison["campaign"].isin(
        selected_campaigns
    )
].copy()


campaign_table = campaign_table.sort_values(
    "conversion_current",
    ascending=False
)


# ============================================================
# 캠페인 상세표
# ============================================================

if campaign_table.empty:

    st.info(
        "선택한 캠페인의 성과 데이터가 없습니다."
    )

else:

    campaign_html = """
    <style>

    .campaign-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }

    .campaign-table th,
    .campaign-table td {
        border: 1px solid #dddddd;
        padding: 9px;
        text-align: center;
        white-space: nowrap;
    }

    .campaign-table th {
        background-color: #f5f5f5;
        font-weight: 700;
    }

    .campaign-table td.metric {
        text-align: left;
        font-weight: 700;
        background-color: #fafafa;
    }

    .up {
        color: #d62728;
        font-weight: 700;
    }

    .down {
        color: #2468c7;
        font-weight: 700;
    }

    .neutral {
        color: #666666;
        font-weight: 700;
    }

    </style>

    <table class="campaign-table">

    <tr>

    <th>지표</th>
    """


    for campaign in campaign_table["campaign"]:

        campaign_html += (
            f"<th>{html.escape(str(campaign))}</th>"
        )


    campaign_html += "</tr>"


    for (
        metric_name,
        current_col,
        previous_col,
        change_col,
        fmt_type
    ) in metric_rows:

        campaign_html += (
            "<tr>"
            f'<td class="metric">{metric_name}</td>'
        )


        for _, row in campaign_table.iterrows():

            current_value = row[
                current_col
            ]

            previous_value = row[
                previous_col
            ]

            change_value = row[
                change_col
            ]


            if fmt_type in [
                "money",
                "cpa"
            ]:

                current_text = fmt_money(
                    current_value
                )

                previous_text = fmt_money(
                    previous_value
                )


            elif fmt_type == "number":

                current_text = fmt_number(
                    current_value
                )

                previous_text = fmt_number(
                    previous_value
                )


            else:

                current_text = fmt_percent(
                    current_value
                )

                previous_text = fmt_percent(
                    previous_value
                )


            change_text = fmt_change_with_new(
                current_value,
                previous_value,
                change_value
            )


            css_class = change_class(
                change_value
            )


            campaign_html += f"""
            <td>
                <div>
                    기준: <b>{current_text}</b>
                </div>

                <div style="color:#888;">
                    비교: {previous_text}
                </div>

                <div style="margin-top:4px;">
                    <span class="{css_class}">
                        {html.escape(change_text)}
                    </span>
                </div>
            </td>
            """


        campaign_html += "</tr>"


    campaign_html += """
    </table>
    """


    st.html(campaign_html)


# ============================================================
# 20. 캠페인별 성과 코멘트
# ============================================================

st.subheader("📝 캠페인별 성과 코멘트")


if campaign_table.empty:

    st.info(
        "선택한 캠페인의 성과 데이터가 없습니다."
    )

else:

    valid_campaigns = campaign_table[
        campaign_table[
            "conversion_current"
        ] > 0
    ].copy()


    if valid_campaigns.empty:

        st.info(
            "현재 기간에 전환이 발생한 캠페인이 없습니다."
        )

    else:

        current_campaign_total = (
            valid_campaigns[
                "conversion_current"
            ].sum()
        )


        # ----------------------------------------------------
        # 전체 캠페인 성과
        # ----------------------------------------------------

        st.markdown(
            f"""
📊 **전체 캠페인 성과:** 현재 선택된 캠페인에서
총 **{current_campaign_total:,.0f}건**의 전환이 발생했습니다.
전체 광고비는 **{total_current_spend:,.0f}원**,
전체 CPA는 **{fmt_money(total_current_cpa)}**입니다.
비교 기간 대비 전체 전환수는
**{fmt_change(total_conversion_change)}** 변화했습니다.
"""
        )


        # ----------------------------------------------------
        # CPA 최우수
        # ----------------------------------------------------

        cpa_valid = valid_campaigns[
            valid_campaigns["CPA_current"].notna()
            &
            (
                valid_campaigns["CPA_current"] > 0
            )
        ].copy()


        if not cpa_valid.empty:

            best = cpa_valid.loc[
                cpa_valid[
                    "CPA_current"
                ].idxmin()
            ]


            best_share = (
                best["conversion_current"]
                /
                current_campaign_total
                *
                100
            )


            st.markdown(
                f"""
🏆 **CPA 최우수 캠페인:** `{best['campaign']}` —
CPA **{best['CPA_current']:,.0f}원**,
전환 **{best['conversion_current']:,.0f}건**
(전체 전환의 **{best_share:.1f}%**)
"""
            )


        # ----------------------------------------------------
        # 전환수 최다
        # ----------------------------------------------------

        best_conversion = valid_campaigns.loc[
            valid_campaigns[
                "conversion_current"
            ].idxmax()
        ]


        best_conversion_share = (
            best_conversion[
                "conversion_current"
            ]
            /
            current_campaign_total
            *
            100
        )


        st.markdown(
            f"""
📈 **전환수 최다 캠페인:** `{best_conversion['campaign']}` —
전환 **{best_conversion['conversion_current']:,.0f}건**,
CPA **{fmt_money(best_conversion['CPA_current'])}**
(전체 전환의 **{best_conversion_share:.1f}%**)
"""
        )


        # ----------------------------------------------------
        # 전환 증가폭 최대
        # ----------------------------------------------------

        growth = campaign_table[
            campaign_table[
                "conversion_change"
            ].notna()
        ].copy()


        growth = growth[
            growth["conversion_current"] > 0
        ]


        if not growth.empty:

            growth_best = growth.loc[
                growth[
                    "conversion_change"
                ].idxmax()
            ]


            if (
                pd.notna(
                    growth_best[
                        "conversion_change"
                    ]
                )
                and
                growth_best[
                    "conversion_change"
                ] > 0
            ):

                growth_share = (
                    growth_best[
                        "conversion_current"
                    ]
                    /
                    current_campaign_total
                    *
                    100
                )


                st.markdown(
                    f"""
🚀 **전환 증가폭 최대 캠페인:** `{growth_best['campaign']}` —
전환 **{growth_best['conversion_change']:+,.1f}%** 증가,
현재 **{growth_best['conversion_current']:,.0f}건**
(전체 전환의 **{growth_share:.1f}%**)
"""
                )


        # ----------------------------------------------------
        # CPA 개선폭 최대
        # ----------------------------------------------------

        cpa_improved = campaign_table[
            campaign_table[
                "CPA_change"
            ].notna()
            &
            (
                campaign_table[
                    "CPA_change"
                ] < 0
            )
        ].copy()


        if not cpa_improved.empty:

            cpa_best_improved = cpa_improved.loc[
                cpa_improved[
                    "CPA_change"
                ].idxmin()
            ]


            st.markdown(
                f"""
💰 **CPA 개선폭 최대 캠페인:** `{cpa_best_improved['campaign']}` —
CPA **{cpa_best_improved['CPA_change']:+,.1f}%** 개선,
현재 CPA **{fmt_money(cpa_best_improved['CPA_current'])}**,
전환 **{cpa_best_improved['conversion_current']:,.0f}건**
"""
            )


        # ----------------------------------------------------
        # CPA 악화
        # ----------------------------------------------------

        cpa_worsened = campaign_table[
            campaign_table[
                "CPA_change"
            ].notna()
            &
            (
                campaign_table[
                    "CPA_change"
                ] > 0
            )
        ].copy()


        if not cpa_worsened.empty:

            worst = cpa_worsened.loc[
                cpa_worsened[
                    "CPA_change"
                ].idxmax()
            ]


            st.markdown(
                f"""
⚠️ **CPA 악화 주의 캠페인:** `{worst['campaign']}` —
CPA **{worst['CPA_change']:+,.1f}%** 상승,
현재 CPA **{fmt_money(worst['CPA_current'])}**,
전환 **{worst['conversion_current']:,.0f}건**
"""
            )


        # ----------------------------------------------------
        # CVR 개선
        # ----------------------------------------------------

        cvr_improved = campaign_table[
            campaign_table[
                "CVR_change"
            ].notna()
            &
            (
                campaign_table[
                    "CVR_change"
                ] > 0
            )
        ].copy()


        if not cvr_improved.empty:

            best_cvr = cvr_improved.loc[
                cvr_improved[
                    "CVR_change"
                ].idxmax()
            ]


            if best_cvr[
                "CVR_change"
            ] > 10:

                st.markdown(
                    f"""
📈 **CVR 개선폭 최대 캠페인:** `{best_cvr['campaign']}` —
CVR **{best_cvr['CVR_change']:+,.1f}%** 개선,
현재 CVR **{fmt_percent(best_cvr['CVR_current'])}**,
전환 **{best_cvr['conversion_current']:,.0f}건**
"""
                )


        # ----------------------------------------------------
        # 캠페인별 상세 분석
        # ----------------------------------------------------

        st.markdown("### 🔎 캠페인별 상세 분석")


        for _, row in valid_campaigns.iterrows():

            campaign_name = row[
                "campaign"
            ]

            conversion = row[
                "conversion_current"
            ]

            spend = row[
                "spend_current"
            ]

            cpa = row[
                "CPA_current"
            ]

            cvr = row[
                "CVR_current"
            ]

            spend_change = row[
                "spend_change"
            ]

            conversion_change = row[
                "conversion_change"
            ]

            cpa_change = row[
                "CPA_change"
            ]

            cvr_change = row[
                "CVR_change"
            ]


            share = (
                conversion /
                current_campaign_total *
                100
                if current_campaign_total > 0
                else np.nan
            )


            details = []


            details.append(
                f"현재 전환 {conversion:,.0f}건으로 "
                f"선택 캠페인 전체 전환의 {share:.1f}%를 차지합니다."
            )


            details.append(
                f"광고비 {spend:,.0f}원"
            )


            if pd.notna(cpa):

                details.append(
                    f"CPA {cpa:,.0f}원"
                )


            if pd.notna(cvr):

                details.append(
                    f"CVR {cvr:.2f}%"
                )


            # ------------------------------------------------
            # 광고비 변화
            # ------------------------------------------------

            if pd.notna(spend_change):

                if spend_change > 10:

                    details.append(
                        f"광고비는 비교 기간 대비 "
                        f"{spend_change:+.1f}% 증가했습니다."
                    )

                elif spend_change < -10:

                    details.append(
                        f"광고비는 비교 기간 대비 "
                        f"{spend_change:+.1f}% 감소했습니다."
                    )

                else:

                    details.append(
                        f"광고비는 비교 기간 대비 "
                        f"{spend_change:+.1f}% 변화했습니다."
                    )

            elif row[
                "spend_previous"
            ] == 0:

                details.append(
                    "비교 기간 광고비가 0원으로 "
                    "현재 기간 신규 집행 성과입니다."
                )


            # ------------------------------------------------
            # 전환 변화
            # ------------------------------------------------

            if pd.notna(conversion_change):

                if conversion_change > 20:

                    details.append(
                        f"전환수는 비교 기간 대비 "
                        f"{conversion_change:+.1f}% 증가해 "
                        f"볼륨 성장세가 강하게 나타났습니다."
                    )

                elif conversion_change < -20:

                    details.append(
                        f"전환수는 비교 기간 대비 "
                        f"{conversion_change:+.1f}% 감소해 "
                        f"전환 볼륨 저하 원인을 확인할 필요가 있습니다."
                    )

                else:

                    details.append(
                        f"전환수는 비교 기간 대비 "
                        f"{conversion_change:+.1f}% 변화했습니다."
                    )

            elif row[
                "conversion_previous"
            ] == 0:

                details.append(
                    "비교 기간 전환 0건에서 "
                    "현재 전환이 발생했습니다."
                )


            # ------------------------------------------------
            # CPA
            # ------------------------------------------------

            if pd.notna(cpa_change):

                if cpa_change < -10:

                    details.append(
                        f"CPA는 {cpa_change:+.1f}% 개선되어 "
                        f"비용 효율이 좋아졌습니다."
                    )

                elif cpa_change > 10:

                    details.append(
                        f"CPA는 {cpa_change:+.1f}% 상승해 "
                        f"효율 악화가 확인됩니다."
                    )

                else:

                    details.append(
                        f"CPA는 {cpa_change:+.1f}%로 "
                        f"비교 기간과 유사한 수준입니다."
                    )


            # ------------------------------------------------
            # CVR
            # ------------------------------------------------

            if pd.notna(cvr_change):

                if cvr_change > 10:

                    details.append(
                        f"CVR은 {cvr_change:+.1f}% 개선되어 "
                        f"클릭 이후 전환 효율이 좋아졌습니다."
                    )

                elif cvr_change < -10:

                    details.append(
                        f"CVR은 {cvr_change:+.1f}% 하락해 "
                        f"랜딩페이지와 유입 품질 점검이 필요합니다."
                    )


            # ------------------------------------------------
            # 운영 액션
            # ------------------------------------------------

            if (
                pd.notna(cpa_change)
                and cpa_change < -10
                and pd.notna(conversion_change)
                and conversion_change > 0
            ):

                action = (
                    "전환 증가와 CPA 개선이 동시에 나타나고 있어 "
                    "현재 효율을 유지할 수 있는 범위에서 "
                    "예산 확대를 우선 검토할 수 있습니다."
                )

            elif (
                pd.notna(cpa_change)
                and cpa_change > 20
            ):

                action = (
                    "CPA 상승폭이 큰 만큼 해당 캠페인의 "
                    "소재별·타겟별 성과를 분해해 저효율 구간의 "
                    "예산 축소 또는 소재 교체를 검토하는 것이 좋습니다."
                )

            elif (
                pd.notna(conversion_change)
                and conversion_change > 20
            ):

                action = (
                    "전환 볼륨이 증가하고 있어 우선 성과를 유지하되 "
                    "예산을 단계적으로 확대하면서 CPA 상승 여부를 "
                    "모니터링하는 전략이 적절합니다."
                )

            elif (
                pd.notna(cvr_change)
                and cvr_change < -10
            ):

                action = (
                    "클릭 대비 전환 효율이 하락하고 있으므로 "
                    "광고 소재보다는 랜딩페이지와 유입 타겟의 "
                    "적합성을 우선 점검할 필요가 있습니다."
                )

            else:

                action = (
                    "현재 성과를 유지하면서 매체·소재·타겟별로 "
                    "CPA와 CVR 편차를 추가 확인해 "
                    "예산 재배분 가능성을 검토하는 것이 좋습니다."
                )


            st.markdown(
                f"""
**📌 `{campaign_name}`**

- **성과:** {" ".join(details)}
- **운영 제안:** {action}
"""
            )


# ============================================================
# 21. NVIDIA AI 분석
# ============================================================

st.divider()

st.header("🤖 AI 성과 분석")

st.caption(
    "현재 선택한 카테고리 / 매체 / 캠페인 / 분석기간의 "
    "성과 데이터를 NVIDIA AI가 분석합니다."
)


# ============================================================
# AI 분석용 데이터 생성
# ============================================================

def make_ai_data():

    # --------------------------------------------------------
    # ① 기본 분석 조건
    # --------------------------------------------------------

    lines = []

    lines.append(
        f"분석 기간: {current_period_text}"
    )

    lines.append(
        f"비교 기간: {previous_period_text}"
    )

    lines.append(
        f"카테고리: {', '.join(selected_categories)}"
    )

    lines.append(
        f"선택 매체 수: {len(selected_media)}개"
    )

    lines.append(
        f"선택 캠페인 수: {len(selected_campaigns)}개"
    )

    lines.append("")


    # ========================================================
    # ② 전체 성과
    # ========================================================

    lines.append(
        "=============================="
    )

    lines.append(
        "=== 전체 성과 데이터 ==="
    )

    lines.append(
        "=============================="
    )

    lines.append(
        f"광고비: {total_current_spend:,.0f}원"
    )

    lines.append(
        f"전환: {total_current_conversion:,.0f}건"
    )

    lines.append(
        f"CPA: {fmt_money(total_current_cpa)}"
    )

    lines.append(
        f"CVR: {fmt_percent(total_current_cvr)}"
    )

    lines.append(
        f"광고비 변화: {fmt_change(total_spend_change)}"
    )

    lines.append(
        f"전환 변화: {fmt_change(total_conversion_change)}"
    )

    lines.append(
        f"CPA 변화: {fmt_change(total_cpa_change)}"
    )

    lines.append(
        f"CVR 변화: {fmt_change(total_cvr_change)}"
    )

    lines.append("")


    # ========================================================
    # ③ 매체 데이터
    #
    # 중요:
    # 매체 분석에 필요한 데이터만 전달
    # campaign 컬럼/캠페인명은 여기 없음
    # ========================================================

    lines.append(
        "=========================================="
    )

    lines.append(
        "=== MEDIA_DATA : 매체별 성과 데이터 ==="
    )

    lines.append(
        "=========================================="
    )

    lines.append(
        "주의: 아래 영역은 오직 '매체' 단위 데이터이다."
    )

    lines.append(
        "매체 분석에서는 아래 데이터만 사용한다."
    )

    lines.append("")

    for _, row in media_table.iterrows():

        lines.append(
            f"""
[매체]
매체명: {row['media']}
광고비: {row['spend_current']:,.0f}원
전환: {row['conversion_current']:,.0f}건
CPA: {fmt_money(row['CPA_current'])}
CVR: {fmt_percent(row['CVR_current'])}
광고비 변화: {fmt_change(row['spend_change'])}
전환 변화: {fmt_change(row['conversion_change'])}
CPA 변화: {fmt_change(row['CPA_change'])}
CVR 변화: {fmt_change(row['CVR_change'])}
"""
        )


    lines.append("")


    # ========================================================
    # ④ 캠페인 데이터
    #
    # 캠페인 분석에서만 사용
    # ========================================================

    lines.append(
        "=============================================="
    )

    lines.append(
        "=== CAMPAIGN_DATA : 캠페인별 성과 데이터 ==="
    )

    lines.append(
        "=============================================="
    )

    lines.append(
        "주의: 아래 영역은 '캠페인' 단위 데이터이다."
    )

    lines.append(
        "캠페인 분석에서만 사용한다."
    )

    lines.append("")

    for _, row in campaign_table.iterrows():

        lines.append(
            f"""
[캠페인]
캠페인명: {row['campaign']}
광고비: {row['spend_current']:,.0f}원
전환: {row['conversion_current']:,.0f}건
CPA: {fmt_money(row['CPA_current'])}
CVR: {fmt_percent(row['CVR_current'])}
광고비 변화: {fmt_change(row['spend_change'])}
전환 변화: {fmt_change(row['conversion_change'])}
CPA 변화: {fmt_change(row['CPA_change'])}
CVR 변화: {fmt_change(row['CVR_change'])}
"""
        )


    return "\n".join(lines)


# ============================================================
# AI 분석 실행
# ============================================================

if (
    not selected_categories
    or not selected_media
    or not selected_campaigns
):

    st.info(
        "카테고리 → 매체 → 캠페인을 선택한 후 "
        "AI 분석을 실행할 수 있습니다."
    )

else:

    ai_button_col1, ai_button_col2 = st.columns(
        [1, 4]
    )


    # --------------------------------------------------------
    # AI 실행 버튼
    # --------------------------------------------------------

    with ai_button_col1:

        run_ai = st.button(
            "✨ AI 분석 실행",
            type="primary",
            use_container_width=True
        )


    with ai_button_col2:

        st.caption(
            "※ 버튼을 눌렀을 때만 NVIDIA API가 호출됩니다."
        )


    # ========================================================
    # 필터 변경 감지
    # ========================================================

    current_ai_signature = (
        tuple(selected_categories),
        tuple(selected_media),
        tuple(selected_campaigns),
        str(current_start),
        str(current_end),
        str(previous_start),
        str(previous_end)
    )


    if (
        "ai_signature" not in st.session_state
        or
        st.session_state["ai_signature"]
        != current_ai_signature
    ):

        st.session_state["ai_result"] = None

        st.session_state[
            "ai_signature"
        ] = current_ai_signature


    # ========================================================
    # AI 버튼 클릭
    # ========================================================

    if run_ai:

        try:

            # ------------------------------------------------
            # NVIDIA API Key
            # ------------------------------------------------

            NVIDIA_API_KEY = st.secrets[
                "NVIDIA_API_KEY"
            ]


            # ------------------------------------------------
            # NVIDIA Client
            # ------------------------------------------------

            client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=NVIDIA_API_KEY
            )


            # ------------------------------------------------
            # AI 데이터 생성
            # ------------------------------------------------

            data_for_ai = make_ai_data()


            # =================================================
            # Prompt
            # =================================================

            prompt = f"""
너는 10년차 퍼포먼스 마케팅 전문가다.

아래 데이터를 기반으로 광고 성과를 분석해줘.

{data_for_ai}


============================================================
가장 중요한 분석 원칙
============================================================

이 데이터에는 '매체 데이터'와 '캠페인 데이터'가 함께 존재한다.

하지만 반드시 분석 대상을 구분해야 한다.

[매체 분석]
- MEDIA_DATA만 사용한다.
- 매체명을 기준으로 분석한다.
- 매체별 광고비 / 전환 / CPA / CVR / 증감률을 기준으로 판단한다.
- CAMPAIGN_DATA의 캠페인명을 매체 분석에 사용하지 않는다.

[캠페인 분석]
- CAMPAIGN_DATA를 사용한다.
- 캠페인명을 기준으로 분석한다.
- 캠페인별 광고비 / 전환 / CPA / CVR / 증감률을 기준으로 판단한다.

============================================================
절대 지켜야 하는 규칙
============================================================

1. '잘하고 있는 매체'에서는 반드시 매체명만 작성한다.

2. '개선이 필요한 매체'에서도 반드시 매체명만 작성한다.

3. 매체 분석 영역에서 캠페인명, 상품명, 보종명을 사용하지 않는다.

4. 특정 캠페인의 성과가 좋다는 이유로
   그 캠페인명을 '잘하고 있는 매체'에 작성하면 안 된다.

5. 특정 캠페인의 성과가 나쁘다는 이유로
   그 캠페인명을 '개선이 필요한 매체'에 작성하면 안 된다.

6. 매체 분석의 모든 판단 근거는 MEDIA_DATA에서 가져온다.

7. 캠페인 분석의 모든 판단 근거는 CAMPAIGN_DATA에서 가져온다.

8. 데이터에 없는 내용을 사실처럼 만들어내지 않는다.

9. 원인을 확정할 수 없는 경우
   "가능성이 있습니다"라고 표현한다.

10. CPA가 낮다는 이유만으로 무조건 예산 확대를 제안하지 않는다.

11. 전환 규모를 반드시 함께 고려한다.

12. CPA 상승과 전환 증가가 동시에 나타나는 경우
    무조건 예산 축소를 제안하지 않는다.

13. 숫자는 제공된 데이터를 그대로 사용한다.

14. 답변은 한국어로 작성한다.


============================================================
분석 결과 작성
============================================================

## 1. 📊 전체 성과 요약

전체 성과를 2~4문장으로 설명한다.

반드시 다음을 포함한다.

- 현재 성과의 가장 중요한 특징
- 비교 기간 대비 핵심 변화
- CPA / CVR / 전환의 변화
- 종합적인 성과 판단


============================================================

## 2. 🏆 잘하고 있는 매체

반드시 MEDIA_DATA만 사용한다.

성과가 좋은 매체를 최대 3개 선정한다.

표 형식으로 작성한다.

| 매체 | CPA | 전환 | CVR | 왜 좋은가? |
|---|---:|---:|---:|---|
| 실제 매체명 | 실제 CPA | 실제 전환 | 실제 CVR | 매체 성과를 근거로 설명 |

### 매우 중요한 규칙

이 표의 '매체' 컬럼에는
반드시 MEDIA_DATA의 '매체명'만 작성한다.

절대로 캠페인명을 작성하지 않는다.

예:

잘못된 표현:
- 간병인보험4080 캠페인
- 시그니처여성암플랜

올바른 표현:
- 네이버_피드_특약
- Pmax_cov
- 네이버_피드

위 예시는 형식 설명을 위한 예시이며,
실제 답변에서는 제공된 MEDIA_DATA의 매체명만 사용한다.


### 예산 확대 가능 여부

각 매체에 대해 다음 형식으로 작성한다.

- 매체명: 예산 확대 / 유지 / 테스트
  - 근거: CPA / 전환 / CVR 기준


============================================================

## 3. ⚠️ 개선이 필요한 매체

반드시 MEDIA_DATA만 사용한다.

성과가 좋지 않은 매체를 최대 3개 선정한다.

표 형식:

| 매체 | 문제점 | 우선 확인할 부분 |
|---|---|---|
| 실제 매체명 | CPA / CVR / 전환 문제 | 확인 및 개선 방향 |

### 매우 중요한 규칙

여기에서도 반드시 '매체명'만 작성한다.

캠페인명이나 상품명을 작성하지 않는다.

문제의 원인을 확정할 수 없는 경우
"가능성이 있습니다"라고 표현한다.


============================================================

## 4. 🎯 캠페인 분석

이번 섹션에서는 CAMPAIGN_DATA를 사용한다.

다음 항목을 분석한다.

- 우수 캠페인
- 저효율 캠페인
- CPA가 개선된 캠페인
- CPA가 악화된 캠페인
- 전환 규모가 큰 캠페인

이 영역에서는 캠페인명을 사용할 수 있다.


============================================================

## 5. 💰 예산 운영 제안

CAMPAIGN_DATA를 기준으로 캠페인을 다음 중 하나로 분류한다.

- 예산 확대
- 유지
- 축소
- 테스트 필요

각 캠페인에 대해 판단 근거를 함께 설명한다.

CPA뿐만 아니라 전환 규모와 변화 추이를 함께 고려한다.


============================================================

## 6. 🚀 우선 실행 액션 TOP 3

실무자가 바로 실행할 수 있는 액션을
우선순위 순으로 3개 제안한다.

각 액션에는 다음을 포함한다.

1. 무엇을 변경할지
2. 왜 변경해야 하는지
3. 어떤 지표를 모니터링할지


============================================================
최종 출력 검증
============================================================

답변을 작성하기 전에 반드시 스스로 검증한다.

특히 2번과 3번 '매체 분석' 영역을 확인한다.

- 매체 분석에 캠페인명이 들어갔는가?
- 들어갔다면 제거한다.
- 매체 분석의 모든 대상이 실제 매체명인가?
- 매체 분석의 판단 근거가 MEDIA_DATA인가?

2번과 3번에는 캠페인명이 절대 등장하지 않도록 한다.
"""


            # =================================================
            # NVIDIA API 호출
            # =================================================

            with st.spinner(
                "🤖 NVIDIA AI가 성과 데이터를 분석하고 있습니다..."
            ):

                response = client.chat.completions.create(

                    model="openai/gpt-oss-20b",

                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "너는 데이터 기반 퍼포먼스 "
                                "마케팅 분석 전문가다. "
                                "매체 분석과 캠페인 분석을 "
                                "절대로 혼동하지 않는다. "
                                "특히 매체 분석에서는 "
                                "캠페인명을 사용하지 않는다."
                            )
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],

                    temperature=0.2,

                    max_tokens=2500,

                    stream=False
                )


            # =================================================
            # 결과 저장
            # =================================================

            st.session_state[
                "ai_result"
            ] = response.choices[
                0
            ].message.content


        except KeyError:

            st.error(
                "NVIDIA_API_KEY가 Streamlit Secrets에 없습니다."
            )


        except Exception as e:

            st.error(
                f"NVIDIA AI 분석 중 오류가 발생했습니다.\n\n{e}"
            )


    # ========================================================
    # AI 결과 출력
    # ========================================================

    if st.session_state.get(
        "ai_result"
    ):

        st.markdown(
            "### 🤖 NVIDIA AI 분석 결과"
        )

        st.markdown(
            st.session_state[
                "ai_result"
            ]
        )
# ============================================================
# 22. 데이터 정보
# ============================================================

st.divider()

with st.expander("📌 데이터 정보"):

    st.write(
        f"전체 데이터: {len(df):,}건"
    )

    st.write(
        f"분석 데이터: {len(filtered_df):,}건"
    )

    st.write(
        f"데이터 시작일: "
        f"{df['date'].min().strftime('%Y-%m-%d')}"
    )

    st.write(
        f"데이터 최신일: "
        f"{df['date'].max().strftime('%Y-%m-%d')}"
    )

    st.write(
        f"기준 기간: "
        f"{current_period_text}"
    )

    st.write(
        f"비교 기간: "
        f"{previous_period_text}"
    )

    st.write(
        f"동일 진행일수: "
        f"{elapsed_days}일"
    )

    st.write(
        f"선택 카테고리: "
        f"{', '.join(selected_categories) if selected_categories else '없음'}"
    )

    st.write(
        f"선택 매체: "
        f"{len(selected_media)}개"
    )

    st.write(
        f"선택 캠페인: "
        f"{len(selected_campaigns)}개"
    )
