import streamlit as st
import numpy as np
import trimesh
from matplotlib.text import TextPath
from matplotlib.font_manager import FontProperties
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely.affinity import translate
import random
import os
import tempfile
import io

# ================= 1. 核心几何算法 (保持不变) =================

def get_char_poly(char, size, font_prop):
    try:
        tp = TextPath((0, 0), char, size=size, prop=font_prop)
        polys_data = tp.to_polygons()
        if not polys_data: return None
        shapely_polys = []
        for points in polys_data:
            if len(points) > 2:
                shapely_polys.append(Polygon(points))
        if not shapely_polys: return None
        combined = unary_union(shapely_polys)
        combined = combined.buffer(0) 
        if combined.is_empty: return None
        minx, miny, maxx, maxy = combined.bounds
        combined = translate(combined, -minx, -miny)
        return combined
    except Exception as e:
        return None

def extrude_safe(geometry, height):
    parts_meshes = []
    if geometry.geom_type == 'Polygon':
        m = trimesh.creation.extrude_polygon(geometry, height=height)
        parts_meshes.append(m)
    elif geometry.geom_type == 'MultiPolygon':
        for sub_poly in geometry.geoms:
            m = trimesh.creation.extrude_polygon(sub_poly, height=height)
            parts_meshes.append(m)
    return parts_meshes

# ================= 2. 网页界面逻辑 =================

st.set_page_config(page_title="3D 文字生成器", page_icon="🧊", layout="wide")

st.title("🧊 3D 文字阶梯生成器 (带预览)")

# --- 侧边栏 ---
st.sidebar.header("🛠️ 1. 基础设置")
uploaded_font = st.sidebar.file_uploader("上传字体文件 (.ttf/.ttc)", type=["ttf", "ttc", "otf"])

font_prop = None
if uploaded_font:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as tmp:
        tmp.write(uploaded_font.getvalue())
        tmp_font_path = tmp.name
    font_prop = FontProperties(fname=tmp_font_path)
    st.sidebar.success(f"已加载: {uploaded_font.name}")
else:
    st.sidebar.warning("⚠️ 请先上传字体文件 (否则无法生成3D)")

st.sidebar.header("📐 3D 参数")
beam_len_min = st.sidebar.slider("最小长度", 100, 800, 300)
beam_len_max = st.sidebar.slider("最大长度", 100, 800, 500)
font_size = st.sidebar.slider("字体大小", 50, 200, 80)

# --- 主界面 ---

col_input, col_preview = st.columns([1, 2])

with col_input:
    st.subheader("2. 输入与排版")
    user_text = st.text_input("输入文字", "RANYEJUN", max_chars=20)
    
    st.caption("调整排版 (实时看右侧预览 👉)")
    step_x = st.slider("水平间距 (X)", 0, 200, 50)
    step_y = st.slider("垂直落差 (Y)", 0, 200, 80)

# ================= 3. 实时预览区域 (新增功能) =================
# 只要上面的滑块动了，Streamlit 就会重新运行这里，实现实时预览

with col_preview:
    st.subheader("👀 布局预览图")
    if user_text:
        # 创建一个 Matplotlib 图表
        fig, ax = plt.subplots(figsize=(8, 5))
        
        # 颜色库 (和3D生成保持一致)
        colors = [
            '#FF5722', '#FF9800', '#FFC107', 
            '#8BC34A', '#4CAF50', '#009688', 
            '#2196F3', '#3F51B5'
        ]
        
        start_x, start_y = 0, 0
        min_x, max_x = 0, 0
        min_y, max_y = 0, 0
        
        # 模拟绘制每一个方块
        for i, char in enumerate(user_text):
            if char.strip() == "": continue
            
            # 计算位置
            x = start_x + (i * step_x)
            y = start_y - (i * step_y)
            
            # 绘制矩形 (代表字的位置)
            # 假设字是正方形的 (宽=font_size)，这只是预览，不用太精确
            rect_size = font_size
            color = colors[i % len(colors)]
            
            # 画方块
            rect = patches.Rectangle((x, y), rect_size, rect_size, linewidth=1, edgecolor='black', facecolor=color, alpha=0.7)
            ax.add_patch(rect)
            
            # 写字
            # 如果没上传字体，就用默认字体预览；上传了就尝试用它
            current_font = font_prop if font_prop else None
            
            # Matplotlib 显示中文也需要配置，为了预览稳定，这里我们只显示字符内容
            # 如果是中文字体且未正确配置matplotlib全局字体，可能显示方框，
            # 这里为了简单，预览图主要看位置，文字内容用通用字体显示
            ax.text(x + rect_size/2, y + rect_size/2, char, 
                    ha='center', va='center', fontsize=12, color='white', fontweight='bold')
            
            # 记录边界，为了调整视图范围
            min_x = min(min_x, x)
            max_x = max(max_x, x + rect_size)
            min_y = min(min_y, y)
            max_y = max(max_y, y + rect_size)

        # 设置坐标轴比例
        ax.set_aspect('equal')
        # 增加一点边距
        margin = 100
        ax.set_xlim(min_x - margin, max_x + margin)
        ax.set_ylim(min_y - margin, max_y + margin)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_title("文字排版示意图 (俯视/正视)", fontsize=10)
        
        # 在 Streamlit 中显示图表
        st.pyplot(fig)
    else:
        st.info("请输入文字以查看预览")

# ================= 4. 3D 生成按钮 =================

st.markdown("---")
st.caption("确认预览图的位置满意后，点击下方按钮生成最终模型")

if st.button("🚀 生成 3D 模型 (GLB)", type="primary", use_container_width=True):
    if not uploaded_font:
        st.error("❌ 必须在左侧上传字体文件才能生成 3D 模型！")
    elif not user_text:
        st.error("❌ 请输入文字！")
    else:
        with st.spinner("正在进行 3D 建模运算..."):
            meshes = []
            
            # 颜色库 (RGB 0-255)
            colors_rgb = [
                [255, 87, 34], [255, 152, 0], [255, 193, 7], 
                [139, 195, 74], [76, 175, 80], [0, 150, 136], 
                [33, 150, 243], [63, 81, 181]
            ]

            for i, char in enumerate(user_text):
                if char.strip() == "": continue
                
                # 和预览图一样的坐标逻辑
                x = 0 + (i * step_x)
                y = 0 - (i * step_y) 
                
                poly = get_char_poly(char, font_size, font_prop)
                
                if poly:
                    poly = translate(poly, x, y)
                    length = random.uniform(beam_len_min, beam_len_max)
                    try:
                        parts = extrude_safe(poly, length)
                        rgba = colors_rgb[i % len(colors_rgb)] + [255]
                        for p in parts:
                            p.visual.face_colors = rgba
                            meshes.extend(parts)
                    except Exception as e:
                        pass

            if meshes:
                final_mesh = trimesh.util.concatenate(meshes)
                file_stream = io.BytesIO()
                final_mesh.export(file_stream, file_type='glb')
                file_stream.seek(0)
                
                st.success(f"✅ 生成成功！")
                st.download_button(
                    label="📥 点击下载 .glb 文件",
                    data=file_stream,
                    file_name=f"Design_{user_text}.glb",
                    mime="model/gltf-binary",
                    type="primary"
                )
            else:
                st.error("生成失败。请检查字体文件是否有效。")
