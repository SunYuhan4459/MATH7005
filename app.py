import streamlit as st
import pandas as pd
import folium
import streamlit.components.v1 as components
import json
import warnings

warnings.filterwarnings('ignore')

# 1. 页面基本设置
st.set_page_config(page_title="TeaLocation HK", layout="wide")
st.title("🧋 TeaLocation HK - Smart Site Selection Platform")
st.markdown("基于人口结构、消费能力与竞品密度的智能选址推荐系统")

# 2. 核心数据加载与处理
@st.cache_data
def load_and_process_data():
    comp_data = {
        'Central and Western': 245, 'Wan Chai': 312, 'Eastern': 268, 'Southern': 95,
        'Yau Tsim Mong': 685, 'Sham Shui Po': 290, 'Kowloon City': 240, 'Wong Tai Sin': 115,
        'Kwun Tong': 310, 'Kwai Tsing': 175, 'Tsuen Wan': 230, 'Tuen Mun': 210,
        'Yuen Long': 340, 'North': 145, 'Tai Po': 155, 'Sha Tin': 285,
        'Sai Kung': 160, 'Islands': 85
    }
    comp_df = pd.DataFrame(list(comp_data.items()), columns=['Standard_District', '同类竞品密度(家)'])

    raw_df = pd.read_excel('DC_21C.xlsx', sheet_name='DCD')
    df = raw_df.iloc[4:22].copy()
    df.columns = raw_df.iloc[3].values

    df_clean = df[['dc_eng', 'dc_chi', 't_pop', 'age_2', 'age_3', 'ma_hh', 'dm_r']].copy()
    for col in ['t_pop', 'age_2', 'age_3', 'ma_hh', 'dm_r']:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

    df_clean['15-44岁客群数'] = df_clean['age_2'] + df_clean['age_3']
    df_clean['年轻客群占比(%)'] = ((df_clean['15-44岁客群数'] / df_clean['t_pop']) * 100).round(2)

    matrix = pd.merge(df_clean, comp_df, left_on='dc_eng', right_on='Standard_District', how='left')
    matrix = matrix[['dc_chi', 'dc_eng', 't_pop', '15-44岁客群数', '年轻客群占比(%)', 'ma_hh', 'dm_r', '同类竞品密度(家)']].copy()
    matrix.columns = ['行政区', 'District_EN', '总人口', '15-44岁客群数', '年轻客群占比(%)', '家庭月入中位数(HKD)', '区位成本指数_月租(HKD)', '同类竞品密度(家)']

    # 翻译字典
    geojson_name_map = {
        'Central and Western': '中西区', 'Wan Chai': '湾仔区', 'Eastern': '东区',
        'Southern': '南区', 'Yau Tsim Mong': '油尖旺区', 'Sham Shui Po': '深水埗区',
        'Kowloon City': '九龙城区', 'Wong Tai Sin': '黄大仙区', 'Kwun Tong': '观塘区',
        'Kwai Tsing': '葵青区', 'Tsuen Wan': '荃湾区', 'Tuen Mun': '屯门区',
        'Yuen Long': '元朗区', 'North': '北区', 'Tai Po': '大埔区', 
        'Sha Tin': '沙田区', 'Sai Kung': '西贡区', 'Islands': '离岛区'
    }
    matrix["GeoJSON_Name"] = matrix["District_EN"].map(geojson_name_map)

    with open("hk_districts.geojson", "r", encoding="utf-8") as f:
        geojson = json.load(f)
        
    return matrix, geojson

df, hk_geojson = load_and_process_data()

# 3. 侧边栏：交互拖拽条
st.sidebar.header("🎯 Define Your Criteria")
min_age_ratio = st.sidebar.slider("Min. Young Demographic (%)", 20.0, 50.0, 30.0, 1.0)
min_income = st.sidebar.slider("Min. Median Monthly Income (HKD)", 15000, 60000, 25000, 1000)
max_competitors = st.sidebar.slider("Max. Competitor Density", 50, 1000, 500, 10)

# 4. 推荐计算模块
def get_recommendations(data, min_age, min_inc, max_comp):
    filtered = data[
        (data["年轻客群占比(%)"] >= min_age) & 
        (data["家庭月入中位数(HKD)"] >= min_inc) &
        (data["同类竞品密度(家)"] <= max_comp)
    ].copy()
    
    if not filtered.empty:
        age_score = (filtered["年轻客群占比(%)"] / filtered["年轻客群占比(%)"].max()) * 40
        income_score = (filtered["家庭月入中位数(HKD)"] / filtered["家庭月入中位数(HKD)"].max()) * 40
        cost_score = (1 - (filtered["区位成本指数_月租(HKD)"] / filtered["区位成本指数_月租(HKD)"].max())) * 20
        filtered["Recommendation Score"] = (age_score + income_score + cost_score).round(2)
        filtered = filtered.sort_values(by="Recommendation Score", ascending=False)
    return filtered

recommended_districts = get_recommendations(df, min_age_ratio, min_income, max_competitors)

# 5. 可视化模块
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📍 Recommended Locations Map")
    m = folium.Map(location=[22.3193, 114.1694], zoom_start=11, tiles="OpenStreetMap")
    
    if not recommended_districts.empty:
        folium.Choropleth(
            geo_data=hk_geojson,
            name="choropleth",
            data=recommended_districts,
            columns=["GeoJSON_Name", "Recommendation Score"], 
            key_on="feature.properties.name",
            fill_color="YlOrRd",
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name="Recommendation Score"
        ).add_to(m)
    else:
        st.warning("No districts meet your strict criteria. Try adjusting the sliders.")

    # 绝招：直接把地图暴力渲染成网页代码，避开所有组件报错
    components.html(m._repr_html_(), height=500)

with col2:
    st.subheader("📊 Top Recommendations")
    if not recommended_districts.empty:
    # 假设你想展示这两个核心列，你可以根据需要增减
     display_cols = ["行政区", "Recommendation Score"] 
    
    st.dataframe(
        recommended_districts[display_cols].reset_index(drop=True),
        column_config={
            "Recommendation Score": st.column_config.ProgressColumn(
                "推荐综合得分", # 显示在表头的名字
                help="基于人口、收入与竞品密度的综合计算结果",
                format="%.2f",
                min_value=0,   # 进度条的最小值
                max_value=100, # 进度条的最大值
            ),
        },
        hide_index=True, # 隐藏最左边难看的 0,1,2,3 索引号
        use_container_width=True # 让表格自动撑满右侧栏宽度
        )
    st.info("Waiting for valid criteria...")
