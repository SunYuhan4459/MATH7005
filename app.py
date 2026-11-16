import streamlit as st
import pandas as pd
import numpy as np
import folium
import streamlit.components.v1 as components
import json
import warnings

# 忽略警告以保持控制台整洁
warnings.filterwarnings('ignore')

# 必须放在第一句：设置页面布局为宽屏
st.set_page_config(page_title="TeaLocation HK", layout="wide")

# ==========================================
# 1. 语言切换与页面标题设置
# ==========================================
lang = st.sidebar.radio("語言 / Language", ["繁體中文", "English"], horizontal=True)
is_zh = (lang == "繁體中文")

if is_zh:
    st.title("TeaLocation HK - 茶飲選址分析系統")
    st.markdown("結合香港人口普查數據、家庭收入與競品分佈的選址評估與推薦工具")
else:
    st.title("TeaLocation HK - Site Selection System")
    st.markdown("Site selection and recommendation tool based on HK census data, income, and competitor density")

# ==========================================
# 2. 数据读取与预处理模块 (使用缓存提升性能)
# ==========================================
@st.cache_data
def load_and_process_data():
    # 各区茶饮店/餐饮店数量统计 (模拟食环署竞品数据)
    comp_data = {
        'Central and Western': 245, 'Wan Chai': 312, 'Eastern': 268, 'Southern': 95,
        'Yau Tsim Mong': 685, 'Sham Shui Po': 290, 'Kowloon City': 240, 'Wong Tai Sin': 115,
        'Kwun Tong': 310, 'Kwai Tsing': 175, 'Tsuen Wan': 230, 'Tuen Mun': 210,
        'Yuen Long': 340, 'North': 145, 'Tai Po': 155, 'Sha Tin': 285,
        'Sai Kung': 160, 'Islands': 85
    }
    comp_df = pd.DataFrame(list(comp_data.items()), columns=['Standard_District', 'Competitors'])

    # 读取统计处2021人口普查Excel表，跳过前3行说明文字
    raw_df = pd.read_excel('DC_21C.xlsx', sheet_name='DCD')
    df = raw_df.iloc[4:22].copy()
    df.columns = [str(c).strip() for c in raw_df.iloc[3].values]

    # 提取所需列，重命名并清洗数据
    # age_2: 15-24岁, age_3: 25-44岁, age_4: 45-64岁, age_5: 65岁以上
    cols = ['dc_eng', 'dc_chi', 't_pop', 'age_1', 'age_2', 'age_3', 'age_4', 'age_5', 'ma_hh', 'dm_r']
    df_clean = pd.DataFrame()
    for col in cols:
        df_clean[col] = df[col] if col in df.columns else 0

    for col in ['t_pop', 'age_2', 'age_3', 'age_4', 'age_5', 'ma_hh', 'dm_r']:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').fillna(0)

    # 计算各年龄段占该区总人口的百分比
    df_clean['15-24'] = ((df_clean['age_2'] / df_clean['t_pop']) * 100).round(2)
    df_clean['25-44'] = ((df_clean['age_3'] / df_clean['t_pop']) * 100).round(2)
    df_clean['45-64'] = ((df_clean['age_4'] / df_clean['t_pop']) * 100).round(2)
    df_clean['65+'] = ((df_clean['age_5'] / df_clean['t_pop']) * 100).round(2)

    # 整合人口数据与竞品数据
    matrix = pd.merge(df_clean, comp_df, left_on='dc_eng', right_on='Standard_District', how='left')

    # 字典映射，用于前台显示和 GeoJSON 匹配
    zh_map = {
        'Central and Western': '中西區', 'Wan Chai': '灣仔區', 'Eastern': '東區',
        'Southern': '南區', 'Yau Tsim Mong': '油尖旺區', 'Sham Shui Po': '深水埗區',
        'Kowloon City': '九龍城區', 'Wong Tai Sin': '黃大仙區', 'Kwun Tong': '觀塘區',
        'Kwai Tsing': '葵青區', 'Tsuen Wan': '荃灣區', 'Tuen Mun': '屯門區',
        'Yuen Long': '元朗區', 'North': '北區', 'Tai Po': '大埔區',
        'Sha Tin': '沙田區', 'Sai Kung': '西貢區', 'Islands': '離島區'
    }
    
    # 对应 GeoJSON 内部的简体区名字段
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
    matrix["Display_District"] = matrix["District_ZH"] if is_zh else matrix["District_EN"]

    # 加载空间边界文件
    with open("hk_districts.geojson", "r", encoding="utf-8") as f:
        geojson = json.load(f)

    return matrix, geojson

# 初始化全局数据
df, hk_geojson = load_and_process_data()

# ==========================================
# 3. 侧边栏交互控件 (参数输入)
# ==========================================
st.sidebar.header("篩選條件" if is_zh else "Filter Criteria")

# 解决原版绝对阈值滑块导致的崩溃问题，重构为“模块化多选”
age_groups = st.sidebar.multiselect(
    "1. 目標年齡層" if is_zh else "1. Age Groups",
    options=['15-24', '25-44', '45-64', '65+'],
    default=['15-24', '25-44', '45-64']
)
if not age_groups:
    age_groups = ['25-44'] # 默认值保护

# 动态计算目标客群比例
df['Selected_Age_Ratio'] = df[age_groups].sum(axis=1).round(2)
df['Age_Rank'] = df['Selected_Age_Ratio'].rank(method='min', ascending=False)

# 重构为 Rank-based 过滤，防止空数据崩溃
top_n_districts = st.sidebar.slider(
    "1. 按年齡佔比保留前 N 個區" if is_zh else "1. Top N Districts by Age Ratio",
    min_value=1, max_value=18, value=18, step=1
)

min_income = st.sidebar.select_slider(
    "2. 家庭月入中位數下限 (HKD)" if is_zh else "2. Min. Monthly Income (HKD)",
    options=[20000, 28000, 35000, 42000],
    value=28000
)

max_competitors = st.sidebar.slider(
    "3. 競品數量上限 (家)" if is_zh else "3. Max. Competitors",
    min_value=80, max_value=700, value=500, step=10
)

# ==========================================
# 4. 核心算法函数定义
# ==========================================
def min_max_scale(series):
    """特征归一化算法"""
    return (series - series.min()) / (series.max() - series.min())

def custom_kmeans(data_matrix, k=3, max_iters=100):
    """手写 K-Means 聚类算法 (计算欧氏距离)"""
    np.random.seed(42)
    centroids = data_matrix[np.random.choice(data_matrix.shape[0], k, replace=False)]
    for _ in range(max_iters):
        # 计算特征向量到簇中心的欧氏距离
        distances = np.linalg.norm(data_matrix[:, np.newaxis] - centroids, axis=2)
        labels = np.argmin(distances, axis=1)
        # 更新簇中心
        new_centroids = np.array([
            data_matrix[labels == i].mean(axis=0) if np.sum(labels == i) > 0 else centroids[i]
            for i in range(k)
        ])
        if np.allclose(centroids, new_centroids):
            break
        centroids = new_centroids
    return labels

def cosine_similarity(v1, v2):
    """计算余弦相似度"""
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

# 执行全局 K-Means 聚类 (将香港划分为 3 个商业梯队)
f1 = min_max_scale(df['t_pop']).values
f2 = min_max_scale(df['Selected_Age_Ratio']).values
X_matrix = np.column_stack((f1, f2))
cluster_labels = custom_kmeans(X_matrix, k=3)

# 根据语言环境动态分配标签名称
if is_zh:
    df['Cluster'] = [f"梯隊 {label + 1}" for label in cluster_labels]
else:
    df['Cluster'] = [f"Tier {label + 1}" for label in cluster_labels]

# ==========================================
# 5. 渲染页面主体面板
# ==========================================
if is_zh:
    tab1, tab2 = st.tabs(["選址綜合評分 (MCDA)", "相似商圈推薦 (Recommendation)"])
else:
    tab1, tab2 = st.tabs(["MCDA Score", "Similar District Recommendation"])

# ------------------------------------
# 面板 1: MCDA 综合评分与热力图
# ------------------------------------
with tab1:
    def get_recommendations(data, top_n, min_inc, max_comp):
        """MCDA 多准则决策分析函数"""
        filtered = data[
            (data["Age_Rank"] <= top_n) &
            (data["ma_hh"] >= min_inc) &
            (data["Competitors"] <= max_comp)
        ].copy()

        if not filtered.empty:
            # 根据商业逻辑设定 40-40-20 权重
            age_score = (filtered["Selected_Age_Ratio"] / data["Selected_Age_Ratio"].max()) * 40
            income_score = (filtered["ma_hh"] / data["ma_hh"].max()) * 40
            cost_score = (1 - (filtered["dm_r"] / data["dm_r"].max())) * 20
            filtered["Recommendation Score"] = (age_score + income_score + cost_score).round(2)
            filtered = filtered.sort_values(by="Recommendation Score", ascending=False)
        return filtered

    # 执行过滤与评分
    recommended_districts = get_recommendations(df, top_n_districts, min_income, max_competitors)

    col1, col2 = st.columns([1.8, 1.2])
    with col1:
        st.subheader("選址分佈地圖" if is_zh else "Locations Map")
        
        # 为了保证热力图颜色对比度，舍弃官方复杂底图，采用高对比度的 OpenStreetMap
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
                legend_name="Score"
            )
            choro.add_to(m)
            choro.geojson.add_child(
                folium.features.GeoJsonTooltip(
                    fields=['name'],
                    aliases=['行政區: ' if is_zh else 'District: '],
                    style="background-color: white; color: #333333; font-size: 14px; padding: 8px;"
                )
            )
        else:
            st.warning("沒有符合條件的行政區，請放寬篩選條件。" if is_zh else "No matching districts.")
        
        components.html(m._repr_html_(), height=500)

    with col2:
        st.subheader("行政區排名" if is_zh else "District Ranking")
        if not recommended_districts.empty:
            show_df = recommended_districts[["Display_District", "Recommendation Score", "Cluster", "Selected_Age_Ratio", "ma_hh"]].reset_index(drop=True)
            show_df.columns = [
                "行政區" if is_zh else "District", 
                "綜合得分" if is_zh else "Score", 
                "聚類梯隊" if is_zh else "Tier", 
                "年齡佔比(%)" if is_zh else "Age Ratio(%)", 
                "家庭月入(HKD)" if is_zh else "Income(HKD)"
            ]
            
            st.dataframe(
                show_df,
                column_config={("綜合得分" if is_zh else "Score"): st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=100)},
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("請調整左側篩選條件。" if is_zh else "Please adjust the filters.")

# ------------------------------------
# 面板 2: 基于余弦相似度的同类商圈推荐
# ------------------------------------
with tab2:
    st.subheader("相似商圈推薦" if is_zh else "Similar District Recommendation")
    st.markdown("選擇一個基準行政區，根據年齡佔比、收入、租金負擔與競品數計算餘弦相似度，找出最接近的 3 個區。" if is_zh else "Select a district to find the top 3 most similar districts using Cosine Similarity.")
    
    # 组合 4 个归一化特征作为比较向量
    f_age = min_max_scale(df['Selected_Age_Ratio']).values
    f_inc = min_max_scale(df['ma_hh']).values
    f_rent = min_max_scale(df['dm_r']).values
    f_comp = min_max_scale(df['Competitors']).values
    feature_matrix = np.column_stack((f_age, f_inc, f_rent, f_comp))
    
    target_district = st.selectbox("選擇基準區域 / Select Benchmark District:", df['Display_District'].tolist())
    
    if target_district:
        target_idx = df[df['Display_District'] == target_district].index[0]
        target_vector = feature_matrix[target_idx]
        
        similarities = []
        for i in range(len(feature_matrix)):
            if i == target_idx:
                similarities.append(0.0) # 排除自己
            else:
                sim = cosine_similarity(target_vector, feature_matrix[i])
                similarities.append(sim)
                
        df['Similarity'] = np.array(similarities) * 100
        # 截取前3名最相似的区
        top3_df = df.sort_values(by='Similarity', ascending=False).head(3).reset_index(drop=True)
        
        st.write(f"與 **{target_district}** 最相似的 3 個區域：" if is_zh else f"Top 3 similar districts to **{target_district}**:")
        
       # 【已修改】这里针对 Tab 2 的推荐表头进行中英文动态适配
        col_names = [
            "相似度" if is_zh else "Similarity", 
            "行政區" if is_zh else "District", 
            "年齡佔比(%)" if is_zh else "Age Ratio(%)", 
            "家庭月入(HKD)" if is_zh else "Income(HKD)", 
            "競品數量" if is_zh else "Competitors"
        ]
        rec_show = top3_df[["Similarity", "Display_District", "Selected_Age_Ratio", "ma_hh", "Competitors"]]
        rec_show.columns = col_names
        
        st.dataframe(
            rec_show,
            column_config={col_names[0]: st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100)},
            hide_index=True,
            use_container_width=True
        )