import streamlit as st
import numpy as np
import trimesh
from matplotlib.text import TextPath
from matplotlib.font_manager import FontProperties
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely.affinity import translate
import random
import os
import tempfile
import io

# ================= 核心逻辑 (保持不变) =================

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

# ================= 网页界面 (Streamlit) =================

st.set_page_config(page_title="3D 文字生成器", page_icon="🧊")

st.title("🧊 3D 文字阶梯生成器")
st.markdown("上传字体，输入文字，一键生成 GLB 模型！")

# 1. 侧边栏：设置参数
st.sidebar.header("🛠️ 参数设置")

# 字体上传 (必须上传，因为云端没有中文字体)
uploaded_font = st.sidebar.file_uploader("第一步：上传字体文件 (.ttf)", type=["ttf", "ttc", "otf"])

# 如果没有上传，提供一个默认提示
font_prop = None
if uploaded_font:
    # 保存到临时文件，因为 matplotlib 需要文件路径
    with tempfile.NamedTemporaryFile(delete=False, suffix=".ttf") as tmp:
        tmp.write(uploaded_font.getvalue())
        tmp_font_path = tmp.name
    font_prop = FontProperties(fname=tmp_font_path)
    st.sidebar.success(f"已加载字体: {uploaded_font.name}")
else:
    st.sidebar.warning("请先上传字体文件 (例如电脑里的 simhei.ttf)")

# 文字输入
user_text = st.text_input("第二步：输入文字", "RANYEJUN", max_chars=20)

# 排版控制 (代替之前的拖拽，用滑块控制)
st.subheader("🎨 排版控制")
col1, col2 = st.columns(2)
with col1:
    step_x = st.slider("水平间距 (X Step)", 0, 200, 50)
with col2:
    step_y = st.slider("垂直落差 (Y Step)", 0, 200, 80)

beam_len_min = st.sidebar.slider("最小长度", 100, 1000, 300)
beam_len_max = st.sidebar.slider("最大长度", 100, 1000, 500)
font_size = st.sidebar.slider("字体大小", 50, 200, 80)

# ================= 生成按钮 =================

if st.button("🚀 生成 3D 模型", type="primary"):
    if not uploaded_font:
        st.error("❌ 请先在左侧上传字体文件！")
    elif not user_text:
        st.error("❌ 请输入文字！")
    else:
        with st.spinner("正在计算几何体..."):
            meshes = []
            start_x, start_y = 0, 0
            
            # 颜色库
            colors = [
                [255, 87, 34], [255, 152, 0], [255, 193, 7], 
                [139, 195, 74], [76, 175, 80], [0, 150, 136], 
                [33, 150, 243], [63, 81, 181]
            ]

            for i, char in enumerate(user_text):
                if char.strip() == "": continue
                
                # 计算位置 (阶梯状)
                x = start_x + (i * step_x)
                y = start_y - (i * step_y) # 向下排
                
                # 获取2D形状
                poly = get_char_poly(char, font_size, font_prop)
                
                if poly:
                    # 移动
                    poly = translate(poly, x, y)
                    length = random.uniform(beam_len_min, beam_len_max)
                    
                    try:
                        # 拉伸
                        parts = extrude_safe(poly, length)
                        
                        # 上色
                        rgba = colors[i % len(colors)] + [255] # RGBA
                        for p in parts:
                            p.visual.face_colors = rgba
                            meshes.extend(parts)
                    except Exception as e:
                        st.warning(f"字符 '{char}' 生成出错")

            if meshes:
                # 合并
                final_mesh = trimesh.util.concatenate(meshes)
                
                # 导出到内存
                # 使用 BytesIO 避免在服务器上写文件
                file_stream = io.BytesIO()
                final_mesh.export(file_stream, file_type='glb')
                file_stream.seek(0)
                
                st.success(f"✅ 生成成功！包含了 {len(user_text)} 个字符。")
                
                # 下载按钮
                st.download_button(
                    label="📥 点击下载 .glb 文件",
                    data=file_stream,
                    file_name=f"Design_{user_text}.glb",
                    mime="model/gltf-binary"
                )
                
            else:
                st.error("生成失败，未能创建任何几何体。")