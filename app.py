import streamlit as st
import pandas as pd
import numpy as np
import folium
import streamlit.components.v1 as components
import json
import warnings

warnings.filterwarnings('ignore')

# 1. 页面基本设置与语言切换
st.set_page_config(page_title="TeaLocation HK", layout="wide")

lang = st.sidebar.radio("🌐 語言 / Language", ["繁體中文", "English"], horizontal=True)
is_zh = (lang == "繁體中文")

if is_zh:
    st.title("🧋 TeaLocation HK - 智能商業選址系統")
    st.markdown("基於香港人口結構（15-65歲+）、家庭收入與競品密度的選址推薦與 K-Means 聚類平台")
else:
    st.title("🧋 TeaLocation HK - Smart Site Selection Platform")
    st.markdown("Site selection and K-Means clustering based on HK demographics, household income, and competitor density")

# 2. 核心数据读取与清洗
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
    df = raw_df.iloc[4:22].copy()
    df.columns = [str(c).strip() for c in raw_df.iloc[3].values]

    # 选取基础列与4个年龄区间 (age_2: 15-24, age_3: 25-44, age_4: 45-64, age_5: 65+)
    cols = ['dc_eng', 'dc_chi', 't_pop', 'age_2', 'age_3', 'age_4', 'age_5', 'ma_hh', 'dm_r']
    df_clean = pd.DataFrame()
    for col in cols:
        if col in df.columns:
            df_clean[col] = df[col]
        else:
            df_clean[col] = 0

    for col in ['t_pop', 'age_2', 'age_3', 'age_4', 'age_5', 'ma_hh', 'dm_r']:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)

    # 计算4个年龄段各自的百分比
    df_clean['15-24'] = ((df_clean['age_2'] / df_clean['t_pop']) * 100).round(2)
    df_clean['25-44'] = ((df_clean['age_3'] / df_clean['t_pop']) * 100).round(2)
    df_clean['45-64'] = ((df_clean['age_4'] / df_clean['t_pop']) * 100).round(2)
    df_clean['65+'] = ((df_clean['age_5'] / df_clean['t_pop']) * 100).round(2)

    matrix = pd.merge(df_clean, comp_df, left_on='dc_eng', right_on='Standard_District', how='left')

    # 繁体中文名称映射（用于界面表格显示）
    zh_map = {
        'Central and Western': '中西區', 'Wan Chai': '灣仔區', 'Eastern': '東區',
        'Southern': '南區', 'Yau Tsim Mong': '油尖旺區', 'Sham Shui Po': '深水埗區',
        'Kowloon City': '九龍城區', 'Wong Tai Sin': '黃大仙區', 'Kwun Tong': '觀塘區',
        'Kwai Tsing': '葵青區', 'Tsuen Wan': '荃灣區', 'Tuen Mun': '屯門區',
        'Yuen Long': '元朗區', 'North': '北區', 'Tai Po': '大埔區',
        'Sha Tin': '沙田區', 'Sai Kung': '西貢區', 'Islands': '離島區'
    }
    # 地图底图匹配专用字典（保持与 geojson 文件一致）
    geojson_name_map = {
        'Central and Western': '中西区', 'Wan Chai': '湾仔区', 'Eastern': '东区',
        'Southern': '南区', 'Yau Tsim Mong': '油尖旺区', 'Sham Shui Po': '深水埗区',
        'Kowloon City': '九龙城区', 'Wong Tai Sin': '黄大仙区', 'Kwun Tong': '观塘区',
        'Kwai Tsing': '葵青区', 'Tsuen Wan': '荃湾区', 'Tuen Mun': '屯门区',
        'Yuen Long': '元朗区', 'North': '北区', 'Tai Po': '大埔区',
        'Sha Tin': '沙田区', 'Sai Kung': '西贡区', 'Islands': '离岛区'
    }

    matrix["District_ZH"] = matrix["dc_eng"].map(zh_map)
    matrix["District_EN"] = matrix["dc_eng"]
    matrix["GeoJSON_Name"] = matrix["dc_eng"].map(geojson_name_map)

    with open("hk_districts.geojson", "r", encoding="utf-8") as f:
        geojson = json.load(f)

    return matrix, geojson

df, hk_geojson = load_and_process_data()

# 3. 侧边栏：筛选条件设置（纯数字区间与档位）
st.sidebar.header("🎯 篩選條件設定" if is_zh else "🎯 Filter Criteria")

age_groups = st.sidebar.multiselect(
    "1. 選擇目標年齡層" if is_zh else "1. Select Age Groups",
    options=['15-24', '25-44', '45-64', '65+'],
    default=['15-24', '25-44', '45-64']
)
if not age_groups:
    age_groups = ['25-44']

# 将勾选的年龄段占比相加
df['Selected_Age_Ratio'] = df[age_groups].sum(axis=1).round(2)

min_age_ratio = st.sidebar.slider(
    "所選年齡合計最低佔比 (%)" if is_zh else "Min. Selected Age Ratio (%)",
    min_value=10.0, max_value=85.0, value=50.0, step=1.0
)

min_income = st.sidebar.select_slider(
    "2. 最低家庭月入中位數 (HKD)" if is_zh else "2. Min. Monthly Income (HKD)",
    options=[20000, 28000, 35000, 42000],
    value=28000
)

max_competitors = st.sidebar.slider(
    "3. 最高同類競品數量 (家)" if is_zh else "3. Max. Competitor Density",
    min_value=80, max_value=700, value=500, step=10
)

# 4. 手写 K-Means 聚类算法（不使用 sklearn）
def min_max_scale(series):
    return (series - series.min()) / (series.max() - series.min())

def custom_kmeans(data_matrix, k=3, max_iters=100):
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
    return labels

# 提取总人口与所选年龄占比进行聚类
f1 = min_max_scale(df['t_pop']).values
f2 = min_max_scale(df['Selected_Age_Ratio']).values
X_matrix = np.column_stack((f1, f2))

cluster_labels = custom_kmeans(X_matrix, k=3)
df['Cluster'] = [f"Cluster {label + 1}" for label in cluster_labels]
df['Display_District'] = df['District_ZH'] if is_zh else df['District_EN']

# 5. 综合推荐得分计算（40% 年龄 + 40% 收入 + 20% 租金成本）
def get_recommendations(data, min_age, min_inc, max_comp):
    filtered = data[
        (data["Selected_Age_Ratio"] >= min_age) &
        (data["ma_hh"] >= min_inc) &
        (data["Competitors"] <= max_comp)
    ].copy()

    if not filtered.empty:
        age_score = (filtered["Selected_Age_Ratio"] / data["Selected_Age_Ratio"].max()) * 40
        income_score = (filtered["ma_hh"] / data["ma_hh"].max()) * 40
        cost_score = (1 - (filtered["dm_r"] / data["dm_r"].max())) * 20
        filtered["Recommendation Score"] = (age_score + income_score + cost_score).round(2)
        filtered = filtered.sort_values(by="Recommendation Score", ascending=False)
    return filtered

recommended_districts = get_recommendations(df, min_age_ratio, min_income, max_competitors)

# 6. 地图与数据表格展示（还原 OpenStreetMap 干净效果）
col1, col2 = st.columns([1.8, 1.2])

with col1:
    st.subheader("📍 推薦選址地圖" if is_zh else "📍 Recommended Locations Map")
    # 还原之前的 OpenStreetMap，彻底去掉 API KEY 水印
    m = folium.Map(location=[22.3193, 114.1694], zoom_start=11, tiles="OpenStreetMap")

    if not recommended_districts.empty:
        choro = folium.Choropleth(
            geo_data=hk_geojson,
            name="choropleth",
            data=recommended_districts,
            columns=["GeoJSON_Name", "Recommendation Score"],
            key_on="feature.properties.name",
            fill_color="YlOrRd",
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name="Recommendation Score"
        )
        choro.add_to(m)

        choro.geojson.add_child(
            folium.features.GeoJsonTooltip(
                fields=['name'],
                aliases=['行政區: ' if is_zh else 'District: '],
                style="background-color: white; color: #333333; font-family: arial; font-size: 14px; padding: 8px;"
            )
        )
    else:
        st.warning("暫無符合條件的行政區，請調低左側篩選門檻。" if is_zh else "No districts meet your criteria. Try adjusting the sliders.")

    components.html(m._repr_html_(), height=500)

with col2:
    st.subheader("📊 推薦行政區排名" if is_zh else "📊 Top Recommendations")
    if not recommended_districts.empty:
        show_df = recommended_districts[[
            "Display_District", "Recommendation Score", "Cluster", "Selected_Age_Ratio", "ma_hh"
        ]].reset_index(drop=True)

        col_name_dist = "行政區" if is_zh else "District"
        col_name_score = "推薦綜合得分" if is_zh else "Score"
        col_name_cluster = "聚類分組" if is_zh else "Cluster"
        col_name_age = "年齡佔比(%)" if is_zh else "Age Ratio(%)"
        col_name_inc = "家庭月入(HKD)" if is_zh else "Income(HKD)"

        show_df.columns = [col_name_dist, col_name_score, col_name_cluster, col_name_age, col_name_inc]

        st.dataframe(
            show_df,
            column_config={
                col_name_score: st.column_config.ProgressColumn(
                    col_name_score,
                    format="%.2f",
                    min_value=0,
                    max_value=100,
                )
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("請在左側放寬篩選條件。" if is_zh else "Please relax the filter criteria on the left.")