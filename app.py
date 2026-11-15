import streamlit as st
import pandas as pd
import numpy as np
import folium
import streamlit.components.v1 as components
import json
import warnings

warnings.filterwarnings('ignore')

# 页面基础配置与容器样式
st.set_page_config(page_title="TeaLocation HK", page_icon="🧋", layout="wide")

st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    div[data-testid="stMetric"] {
        background-color: #f8fafc;
        border: 1px solid #e2e8f0;
        padding: 12px 16px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
</style>
""", unsafe_allow_html=True)

# 侧边栏语言切换与多语言文本配置
lang = st.sidebar.radio("🌐 語言 / Language", ["繁體中文", "English"], horizontal=True)
is_zh = (lang == "繁體中文")

TEXT = {
    "title": "🧋 TeaLocation HK - 智能商業選址與數據挖掘系統" if is_zh else "🧋 TeaLocation HK - Smart Site Selection & Data Mining System",
    "subtitle": "融合香港全齡人口分層、收入分檔、手寫 K-Means 聚類及多元回歸租金估值模型的商業決策平台" if is_zh else "Commercial Decision Platform integrating HK Age Brackets, Income Tiers, Custom K-Means, and OLS Rent Valuation",
    "sidebar_header": "🎯 篩選與權重設定" if is_zh else "🎯 Filter & Weight Console",
    "sec_age": "👥 1. 年齡區間選擇" if is_zh else "👥 1. Age Brackets Selection",
    "age_select_label": "勾選目標年齡層（可多選）" if is_zh else "Select Age Groups (Multi-select)",
    "age_slider_label": "所選年齡層合計最低佔比 (%)" if is_zh else "Min. Combined Age Ratio (%)",
    "sec_inc": "💰 2. 家庭月入中位數門檻 (HKD)" if is_zh else "💰 2. Median Household Income (HKD)",
    "inc_tier_label": "選擇最低月入門檻 (HKD)" if is_zh else "Select Min. Monthly Income (HKD)",
    "sec_market": "🏪 3. 競品與租金上限" if is_zh else "🏪 3. Competition & Rent Limits",
    "comp_label": "同類競品數量上限 (家)" if is_zh else "Max. Competitor Stores",
    "comp_note": "📍 區間點位：80 | 160 | 280 | 450 | 700" if is_zh else "📍 Reference Points: 80 | 160 | 280 | 450 | 700",
    "rent_label": "區位租金指數上限 (HKD)" if is_zh else "Max. Location Rent Index (HKD)",
    "rent_note": "📍 區間點位：2,500 | 3,500 | 7,000 | 15,000 | 18,000" if is_zh else "📍 Reference Points: 2,500 | 3,500 | 7,000 | 15,000 | 18,000",
    "sec_weight": "⚖️ 4. 多準則決策權重分配 (MCDA)" if is_zh else "⚖️ 4. MCDA Scoring Weights",
    "w_age": "年齡人口佔比權重" if is_zh else "Demographic Ratio Weight",
    "w_inc": "家庭月入水平權重" if is_zh else "Household Income Weight",
    "w_cost": "租金成本控制權重" if is_zh else "Rent Cost Control Weight",
    "w_comp": "競品密度規避權重" if is_zh else "Competition Avoidance Weight",
    "kpi_count": "符合條件行政區" if is_zh else "Qualified Districts",
    "kpi_top": "首選推薦行政區" if is_zh else "Top Recommended District",
    "kpi_score": "最高綜合評分" if is_zh else "Highest Composite Score",
    "kpi_undervalued": "首選區租金估值偏差" if is_zh else "Top District Rent Deviation",
    "map_title": "📍 商業選址空間熱力圖" if is_zh else "📍 Site Selection Spatial Heatmap",
    "table_title": "📊 綜合排名、聚類分級與租金估值" if is_zh else "📊 Ranking, Cluster Tiers & Rent Valuation",
    "col_dist": "行政區" if is_zh else "District",
    "col_score": "推薦綜合得分" if is_zh else "Composite Score",
    "col_score_help": "依據設定權重動態計算的多準則得分（0-100）" if is_zh else "Weighted MCDA composite score (0-100)",
    "col_cluster": "K-Means 聚類分組" if is_zh else "K-Means Cluster",
    "col_val": "OLS 租金估值偏差" if is_zh else "OLS Rent Deviation",
    "col_age": "所選年齡佔比(%)" if is_zh else "Selected Age (%)",
    "col_inc": "家庭月入(HKD)" if is_zh else "Median Income (HKD)",
    "col_comp": "競品數(家)" if is_zh else "Competitors",
    "empty_warn": "💡 當前篩選條件過於嚴格，暫無匹配的行政區。請在左側調低月入門檻、年齡佔比或放寬競品上限。" if is_zh else "💡 No districts match your strict criteria. Please adjust the thresholds in the sidebar.",
    "tooltip_prefix": "行政區: " if is_zh else "District: ",
    "expander_title": "🔍 展開查看全港 18 區四年齡層分佈與數據挖掘底層明細" if is_zh else "🔍 View All 18 Districts 4-Age-Bracket Data & Mining Details"
}

st.title(TEXT["title"])
st.markdown(TEXT["subtitle"])


# 数据加载与四个年龄层特征提取
@st.cache_data
def load_and_process_data():
    comp_data = {
        'Central and Western': 245, 'Wan Chai': 312, 'Eastern': 268, 'Southern': 95,
        'Yau Tsim Mong': 685, 'Sham Shui Po': 290, 'Kowloon City': 240, 'Wong Tai Sin': 115,
        'Kwun Tong': 310, 'Kwai Tsing': 175, 'Tsuen Wan': 230, 'Tuen Mun': 210,
        'Yuen Long': 340, 'North': 145, 'Tai Po': 155, 'Sha Tin': 285,
        'Sai Kung': 160, 'Islands': 85
    }
    comp_df = pd.DataFrame(list(comp_data.items()), columns=['Standard_District', 'Competitors'])

    raw_df = pd.read_excel('DC_21C.xlsx', sheet_name='DCD')
    df_slice = raw_df.iloc[4:22].copy()
    df_slice.columns = [str(c).strip() for c in raw_df.iloc[3].values]

    # 提取基础字段与全部可用年龄层字段 (age_1: 0-14, age_2: 15-24, age_3: 25-44, age_4: 45-64, age_5: 65+)
    df_clean = pd.DataFrame()
    df_clean['dc_eng'] = df_slice['dc_eng'].astype(str).str.strip()
    df_clean['dc_chi'] = df_slice['dc_chi'].astype(str).str.strip()

    for col in ['t_pop', 'age_1', 'age_2', 'age_3', 'age_4', 'age_5', 'ma_hh', 'dm_r']:
        if col in df_slice.columns:
            df_clean[col] = pd.to_numeric(df_slice[col], errors='coerce')
        else:
            df_clean[col] = np.nan

    # 兼容处理：若表格缺失 age_4 或 age_5，依据香港人口普查结构进行插补计算
    if df_clean['age_4'].isna().all():
        df_clean['age_4'] = (df_clean['t_pop'] * 0.31).round(0)
    if df_clean['age_5'].isna().all():
        if not df_clean['age_1'].isna().all():
            rem = df_clean['t_pop'] - (df_clean['age_1'] + df_clean['age_2'] + df_clean['age_3'] + df_clean['age_4'])
            df_clean['age_5'] = np.maximum(rem, (df_clean['t_pop'] * 0.20).round(0))
        else:
            df_clean['age_5'] = (df_clean['t_pop'] * 0.21).round(0)

    # 计算四个独立年龄区间的占比 (%)
    df_clean['r_15_24'] = ((df_clean['age_2'] / df_clean['t_pop']) * 100).round(2)
    df_clean['r_25_44'] = ((df_clean['age_3'] / df_clean['t_pop']) * 100).round(2)
    df_clean['r_45_64'] = ((df_clean['age_4'] / df_clean['t_pop']) * 100).round(2)
    df_clean['r_65_up'] = ((df_clean['age_5'] / df_clean['t_pop']) * 100).round(2)

    matrix = pd.merge(df_clean, comp_df, left_on='dc_eng', right_on='Standard_District', how='left')

    zh_hk_map = {
        'Central and Western': '中西區', 'Wan Chai': '灣仔區', 'Eastern': '東區',
        'Southern': '南區', 'Yau Tsim Mong': '油尖旺區', 'Sham Shui Po': '深水埗區',
        'Kowloon City': '九龍城區', 'Wong Tai Sin': '黃大仙區', 'Kwun Tong': '觀塘區',
        'Kwai Tsing': '葵青區', 'Tsuen Wan': '荃灣區', 'Tuen Mun': '屯門區',
        'Yuen Long': '元朗區', 'North': '北區', 'Tai Po': '大埔區',
        'Sha Tin': '沙田區', 'Sai Kung': '西貢區', 'Islands': '離島區'
    }
    geojson_name_map = {
        'Central and Western': '中西区', 'Wan Chai': '湾仔区', 'Eastern': '东区',
        'Southern': '南区', 'Yau Tsim Mong': '油尖旺区', 'Sham Shui Po': '深水埗区',
        'Kowloon City': '九龙城区', 'Wong Tai Sin': '黄大仙区', 'Kwun Tong': '观塘区',
        'Kwai Tsing': '葵青区', 'Tsuen Wan': '荃湾区', 'Tuen Mun': '屯门区',
        'Yuen Long': '元朗区', 'North': '北区', 'Tai Po': '大埔区',
        'Sha Tin': '沙田区', 'Sai Kung': '西贡区', 'Islands': '离岛区'
    }

    matrix["District_ZH"] = matrix["dc_eng"].map(zh_hk_map).fillna(matrix["dc_chi"])
    matrix["District_EN"] = matrix["dc_eng"]
    matrix["GeoJSON_Name"] = matrix["dc_eng"].map(geojson_name_map)

    with open("hk_districts.geojson", "r", encoding="utf-8") as f:
        geojson = json.load(f)

    return matrix, geojson


df, hk_geojson = load_and_process_data()


# 算法模块一：手写 Min-Max 归一化与多维 K-Means 聚类算法
def min_max_scale(series):
    denom = series.max() - series.min()
    if denom == 0:
        return np.zeros(len(series))
    return (series - series.min()) / denom


def run_kmeans(data_matrix, k=3, max_iters=100):
    np.random.seed(42)
    centroids = data_matrix[np.random.choice(data_matrix.shape[0], k, replace=False)]
    for _ in range(max_iters):
        distances = np.linalg.norm(data_matrix[:, np.newaxis] - centroids, axis=2)
        labels = np.argmin(distances, axis=1)
        new_centroids = np.array([
            data_matrix[labels == i].mean(axis=0) if np.sum(labels == i) > 0 else centroids[i]
            for i in range(k)
        ])
        if np.allclose(centroids, new_centroids):
            break
        centroids = new_centroids
    return labels, centroids


# 算法模块二：手写多元线性回归 (OLS Normal Equation) 计算理论租金偏差百分比
def run_ols_rent_valuation(data):
    x1 = min_max_scale(data['t_pop']).values
    x2 = min_max_scale(data['ma_hh']).values
    x3 = min_max_scale(data['Competitors']).values
    y = data['dm_r'].values

    X_mat = np.column_stack([np.ones(len(data)), x1, x2, x3])
    beta = np.linalg.pinv(X_mat.T @ X_mat) @ X_mat.T @ y
    y_pred = X_mat @ beta
    residual_pct = ((y - y_pred) / y_pred) * 100

    val_str = [f"{r:+.1f}%" for r in residual_pct]
    return val_str


# 侧边栏第一部分：四个年龄区间（仅标注纯数字范围）与动态点位滑块
st.sidebar.header(TEXT["sidebar_header"])

AGE_OPTIONS = {
    "r_15_24": "15 - 24",
    "r_25_44": "25 - 44",
    "r_45_64": "45 - 64",
    "r_65_up": "65+"
}

with st.sidebar.expander(TEXT["sec_age"], expanded=True):
    selected_age_keys = st.multiselect(
        TEXT["age_select_label"],
        options=list(AGE_OPTIONS.keys()),
        default=["r_15_24", "r_25_44", "r_45_64"],
        format_func=lambda k: AGE_OPTIONS[k]
    )
    if not selected_age_keys:
        selected_age_keys = ["r_25_44"]

    # 动态计算用户所勾选年龄层的合计人口占比
    df["selected_age_ratio"] = df[selected_age_keys].sum(axis=1).round(2)

    q25 = float(np.round(df["selected_age_ratio"].quantile(0.25), 1))
    q50 = float(np.round(df["selected_age_ratio"].median(), 1))
    q75 = float(np.round(df["selected_age_ratio"].quantile(0.75), 1))
    min_bound = float(max(5.0, np.floor(df["selected_age_ratio"].min() - 1.0)))
    max_bound = float(min(98.0, np.ceil(df["selected_age_ratio"].max() + 1.0)))

    st.caption(f"📍 25%: `{q25}%` | 50%: `{q50}%` | 75%: `{q75}%`")
    min_age_ratio = st.slider(
        TEXT["age_slider_label"],
        min_value=min_bound,
        max_value=max_bound,
        value=q25,
        step=0.2
    )

# 侧边栏第二部分：家庭月入四档阶梯滑块（仅标注纯数字）
INCOME_VALUES = [20000, 28000, 35000, 42000]

with st.sidebar.expander(TEXT["sec_inc"], expanded=True):
    st.caption("📍 20,000 | 28,000 | 35,000 | 42,000")
    min_income = st.select_slider(
        TEXT["inc_tier_label"],
        options=INCOME_VALUES,
        value=28000,
        format_func=lambda x: f"{x:,}"
    )

# 侧边栏第三部分：竞品与租金点位滑块
with st.sidebar.expander(TEXT["sec_market"], expanded=True):
    st.caption(TEXT["comp_note"])
    max_competitors = st.slider(
        TEXT["comp_label"],
        min_value=80,
        max_value=700,
        value=450,
        step=10
    )
    st.caption(TEXT["rent_note"])
    max_rent = st.slider(
        TEXT["rent_label"],
        min_value=2500,
        max_value=18000,
        value=16500,
        step=250
    )

# 侧边栏第四部分：评分权重设置
with st.sidebar.expander(TEXT["sec_weight"], expanded=False):
    w_age = st.slider(TEXT["w_age"], 0, 100, 35, 5)
    w_inc = st.slider(TEXT["w_inc"], 0, 100, 35, 5)
    w_cost = st.slider(TEXT["w_cost"], 0, 100, 15, 5)
    w_comp = st.slider(TEXT["w_comp"], 0, 100, 15, 5)


# 运行 K-Means 聚类与 OLS 租金回归估值
f_pop = min_max_scale(df['t_pop']).values
f_age = min_max_scale(df['selected_age_ratio']).values
f_inc = min_max_scale(df['ma_hh']).values
X_features = np.column_stack((f_pop, f_age, f_inc))

raw_labels, centers = run_kmeans(X_features, k=3)
center_ranks = np.argsort(centers.sum(axis=1))[::-1]
tier_zh = {
    center_ranks[0]: "Cluster 1",
    center_ranks[1]: "Cluster 2",
    center_ranks[2]: "Cluster 3"
}
tier_en = {
    center_ranks[0]: "Cluster 1",
    center_ranks[1]: "Cluster 2",
    center_ranks[2]: "Cluster 3"
}

df["Cluster_ZH"] = [tier_zh[val] for val in raw_labels]
df["Cluster_EN"] = [tier_en[val] for val in raw_labels]
df["Display_Val"] = run_ols_rent_valuation(df)

df["Display_District"] = df["District_ZH"] if is_zh else df["District_EN"]
df["Display_Cluster"] = df["Cluster_ZH"] if is_zh else df["Cluster_EN"]


# 多准则加权推荐得分计算
def get_recommendations(data, min_age, min_inc, max_comp, max_r, wa, wi, wc, wcp):
    filtered = data[
        (data["selected_age_ratio"] >= min_age) &
        (data["ma_hh"] >= min_inc) &
        (data["Competitors"] <= max_comp) &
        (data["dm_r"] <= max_r)
    ].copy()

    if not filtered.empty:
        total_w = wa + wi + wc + wcp
        if total_w == 0:
            total_w = 1

        s_age = (filtered["selected_age_ratio"] / data["selected_age_ratio"].max()) * (wa / total_w * 100)
        s_inc = (filtered["ma_hh"] / data["ma_hh"].max()) * (wi / total_w * 100)
        s_cost = (1 - (filtered["dm_r"] / data["dm_r"].max())) * (wc / total_w * 100)
        s_comp = (1 - (filtered["Competitors"] / data["Competitors"].max())) * (wcp / total_w * 100)

        filtered["Recommendation Score"] = (s_age + s_inc + s_cost + s_comp).round(2)
        filtered = filtered.sort_values(by="Recommendation Score", ascending=False)

    return filtered


recommended_districts = get_recommendations(
    df, min_age_ratio, min_income, max_competitors, max_rent,
    w_age, w_inc, w_cost, w_comp
)


# 顶部动态指标卡片
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
if not recommended_districts.empty:
    top_row = recommended_districts.iloc[0]
    kpi1.metric(TEXT["kpi_count"], f"{len(recommended_districts)} / 18")
    kpi2.metric(TEXT["kpi_top"], top_row["Display_District"])
    kpi3.metric(TEXT["kpi_score"], f"{top_row['Recommendation Score']:.2f}")
    kpi4.metric(TEXT["kpi_undervalued"], top_row["Display_Val"])
else:
    kpi1.metric(TEXT["kpi_count"], "0 / 18")
    kpi2.metric(TEXT["kpi_top"], "-")
    kpi3.metric(TEXT["kpi_score"], "0.00")
    kpi4.metric(TEXT["kpi_undervalued"], "-")

st.markdown("---")


# 空间地图与右侧综合数据看板
col1, col2 = st.columns([1.65, 1.35])

with col1:
    st.subheader(TEXT["map_title"])
    m = folium.Map(location=[22.33, 114.15], zoom_start=10.5, tiles="CartoDB positron")

    if not recommended_districts.empty:
        choro = folium.Choropleth(
            geo_data=hk_geojson,
            name="choropleth",
            data=recommended_districts,
            columns=["GeoJSON_Name", "Recommendation Score"],
            key_on="feature.properties.name",
            fill_color="YlOrRd",
            fill_opacity=0.75,
            line_opacity=0.3,
            nan_fill_color="#cbd5e1",
            nan_fill_opacity=0.35,
            legend_name=TEXT["col_score"]
        )
        choro.add_to(m)

        choro.geojson.add_child(
            folium.features.GeoJsonTooltip(
                fields=['name'],
                aliases=[TEXT["tooltip_prefix"]],
                style="background-color: rgba(255, 255, 255, 0.95); color: #1e293b; font-family: sans-serif; font-size: 13px; padding: 8px 12px; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.15);"
            )
        )
    else:
        st.warning(TEXT["empty_warn"])

    components.html(m._repr_html_(), height=500)

with col2:
    st.subheader(TEXT["table_title"])
    if not recommended_districts.empty:
        display_df = recommended_districts[[
            "Display_District", "Recommendation Score", "Display_Cluster",
            "Display_Val", "selected_age_ratio", "ma_hh", "Competitors"
        ]].reset_index(drop=True)

        display_df.columns = [
            TEXT["col_dist"], TEXT["col_score"], TEXT["col_cluster"],
            TEXT["col_val"], TEXT["col_age"], TEXT["col_inc"], TEXT["col_comp"]
        ]

        st.dataframe(
            display_df,
            column_config={
                TEXT["col_score"]: st.column_config.ProgressColumn(
                    TEXT["col_score"],
                    help=TEXT["col_score_help"],
                    format="%.2f",
                    min_value=0,
                    max_value=100,
                ),
                TEXT["col_age"]: st.column_config.NumberColumn(format="%.1f%%"),
                TEXT["col_inc"]: st.column_config.NumberColumn(format="HK$ %d"),
                TEXT["col_comp"]: st.column_config.NumberColumn(format="%d"),
            },
            hide_index=True,
            use_container_width=True,
            height=465
        )
    else:
        st.info(TEXT["empty_warn"])

# 底部全港 18 区完整四年龄段与模型明细表
with st.expander(TEXT["expander_title"]):
    full_view = df[[
        "Display_District", "t_pop", "r_15_24", "r_25_44", "r_45_64", "r_65_up",
        "ma_hh", "dm_r", "Competitors", "Display_Cluster", "Display_Val"
    ]].copy()
    if is_zh:
        full_view.columns = [
            "行政區", "總人口", "15-24 (%)", "25-44 (%)", "45-64 (%)", "65+ (%)",
            "家庭月入(HKD)", "租金指數(HKD)", "競品數(家)", "K-Means 聚類", "OLS 租金偏差"
        ]
    else:
        full_view.columns = [
            "District", "Total Pop", "15-24 (%)", "25-44 (%)", "45-64 (%)", "65+ (%)",
            "Median Income", "Rent Index", "Competitors", "K-Means Cluster", "OLS Deviation"
        ]
    st.dataframe(full_view, hide_index=True, use_container_width=True)