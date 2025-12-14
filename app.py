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

# ================= 0. 密码验证模块 (新增) =================

def check_password():
    """如果不通过验证，返回 False，否则返回 True"""
    
    # 1. 检查是否已经登录成功
    if st.session_state.get('password_correct', False):
        return True

    # 2. 显示输入框
    st.title("🔒 访问受限")
    st.markdown("请输入密码以访问此工具。")
    
    password_input = st.text_input("密码", type="password")
    
    if st.button("登录"):
        # 3. 比对密码 (从 Secrets 获取)
        # 注意：这里需要你在 Streamlit 后台配置 "PASSWORD"
        if password_input == st.secrets["PASSWORD"]:
            st.session_state['password_correct'] = True
            st.rerun()  # 刷新页面进入主程序
        else:
            st.error("❌ 密码错误，请重试。")
            
    return False

# ================= 1. 初始化设置 =================

# 必须放在最前面
st.set_page_config(page_title="3D 文字生成器", page_icon="🧊", layout="wide")

# ---> 这里是关键：如果没有通过密码检查，直接停止运行 <---
if not check_password():
    st.stop()

# ================= 2. 下面是原本的主程序 =================
# (只有密码正确，才会执行到这里的代码)

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

# --- 主界面开始 ---

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

# --- 输入与预览 ---

col_input, col_preview = st.columns([1, 2])

with col_input:
    st.subheader("2. 输入与排版")
    user_text = st.text_input("输入文字", "RANYEJUN", max_chars=20)
    
    st.caption("调整排版 (实时看右侧预览 👉)")
    step_x = st.slider("水平间距 (X)", 0, 200, 50)
    step_y = st.slider("垂直落差 (Y)", 0, 200, 80)

with col_preview:
    st.subheader("👀 布局预览图")
    if user_text:
        fig, ax = plt.subplots(figsize=(8, 5))
        colors = ['#FF5722', '#FF9800', '#FFC107', '#8BC34A', '#4CAF50', '#009688', '#2196F3', '#3F51B5']
        
        start_x, start_y = 0, 0
        min_x, max_x = 0, 0
        min_y, max_y = 0, 0
        
        for i, char in enumerate(user_text):
            if char.strip() == "": continue
            x = start_x + (i * step_x)
            y = start_y - (i * step_y)
            rect_size = font_size
            color = colors[i % len(colors)]
            
            rect = patches.Rectangle((x, y), rect_size, rect_size, linewidth=1, edgecolor='black', facecolor=color, alpha=0.7)
            ax.add_patch(rect)
            
            # 预览文字
            ax.text(x + rect_size/2, y + rect_size/2, char, 
                    ha='center', va='center', fontsize=12, color='white', fontweight='bold')
            
            min_x = min(min_x, x)
            max_x = max(max_x, x + rect_size)
            min_y = min(min_y, y)
            max_y = max(max_y, y + rect_size)

        ax.set_aspect('equal')
        margin = 100
        ax.set_xlim(min_x - margin, max_x + margin)
        ax.set_ylim(min_y - margin, max_y + margin)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_title("文字排版示意图 (俯视/正视)", fontsize=10)
        st.pyplot(fig)
    else:
        st.info("请输入文字以查看预览")

# --- 3D 生成按钮 ---

st.markdown("---")
if st.button("🚀 生成 3D 模型 (GLB)", type="primary", use_container_width=True):
    if not uploaded_font:
        st.error("❌ 必须在左侧上传字体文件才能生成 3D 模型！")
    elif not user_text:
        st.error("❌ 请输入文字！")
    else:
        with st.spinner("正在进行 3D 建模运算..."):
            meshes = []
            colors_rgb = [[255, 87, 34], [255, 152, 0], [255, 193, 7], [139, 195, 74], [76, 175, 80], [0, 150, 136], [33, 150, 243], [63, 81, 181]]

            for i, char in enumerate(user_text):
                if char.strip() == "": continue
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
