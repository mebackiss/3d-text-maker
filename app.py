import tkinter as tk
from tkinter import messagebox, filedialog
import numpy as np
import trimesh
from matplotlib.text import TextPath
from matplotlib.font_manager import FontProperties
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely.affinity import translate
import random
import os
import traceback

# ================= 配置参数 =================
FONT_SIZE = 80       
BEAM_LENGTH_MIN = 300
BEAM_LENGTH_MAX = 500

class DraggableText3DApp:
    def __init__(self, root):
        self.root = root
        self.root.title("3D 字体排版 (最终完美版 - 修复MultiPolygon错误)")
        self.root.geometry("1000x850")

        self.char_items = [] 
        self.char_data = []  
        self.drag_data = {"x": 0, "y": 0, "item": None}
        self.custom_font_path = None 
        self.last_error = "" 

        # --- 顶部控制区 ---
        frame_top = tk.Frame(root, pady=10, bg="#f0f0f0")
        frame_top.pack(side=tk.TOP, fill=tk.X)

        # 字体按钮
        btn_font = tk.Button(frame_top, text="1. 选择桌面上的 simhei.ttf", bg="#FF9800", fg="white",
                             font=("微软雅黑", 10, "bold"), command=self.choose_font_file)
        btn_font.pack(side=tk.LEFT, padx=10)
        
        self.lbl_font_status = tk.Label(frame_top, text="未选择", bg="#f0f0f0", fg="red")
        self.lbl_font_status.pack(side=tk.LEFT, padx=5)

        # 输入框
        tk.Label(frame_top, text="| 文字:", bg="#f0f0f0").pack(side=tk.LEFT, padx=5)
        self.entry_text = tk.Entry(frame_top, font=("微软雅黑", 14), width=15)
        self.entry_text.pack(side=tk.LEFT, padx=5)
        self.entry_text.insert(0, "业务V")

        # 画布按钮
        btn_init = tk.Button(frame_top, text="2. 生成画布", bg="#2196F3", fg="white",
                             font=("微软雅黑", 10), command=self.init_canvas_items)
        btn_init.pack(side=tk.LEFT, padx=10)

        # --- 画布 ---
        self.canvas_frame = tk.Frame(root)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.vbar = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.hbar = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.canvas = tk.Canvas(self.canvas_frame, bg="#E0E0E0", cursor="hand2",
                                scrollregion=(0, 0, 3000, 3000), 
                                yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.vbar.config(command=self.canvas.yview)
        self.hbar.config(command=self.canvas.xview)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)
        self.draw_grid_background()
        
        self.canvas.tag_bind("token", "<ButtonPress-1>", self.on_press)
        self.canvas.tag_bind("token", "<ButtonRelease-1>", self.on_release)
        self.canvas.tag_bind("token", "<B1-Motion>", self.on_motion)

        # --- 底部 ---
        btn_generate = tk.Button(root, text="3. 导出模型 (已修复报错)", bg="#4CAF50", fg="white",
                                 font=("微软雅黑", 14, "bold"), height=2,
                                 command=self.generate_3d_model)
        btn_generate.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=10)

    def choose_font_file(self):
        filename = filedialog.askopenfilename(
            title="请选择你复制到桌面的字体文件 (simhei.ttf)",
            filetypes=(("Font files", "*.ttf *.ttc *.otf"), ("All files", "*.*"))
        )
        if filename:
            self.custom_font_path = filename
            self.lbl_font_status.config(text=f"已选: {os.path.basename(filename)}", fg="green")
            if self.entry_text.get(): self.init_canvas_items()

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def draw_grid_background(self):
        for i in range(0, 3000, 200):
            self.canvas.create_line(0, i, 3000, i, fill="#d0d0d0", dash=(2, 4))
            self.canvas.create_line(i, 0, i, 3000, fill="#d0d0d0", dash=(2, 4))
        self.canvas.create_line(1000, 0, 1000, 3000, fill="#999", width=2, dash=(4, 4))
        self.canvas.create_line(0, 500, 3000, 500, fill="#999", width=2, dash=(4, 4))

    def init_canvas_items(self):
        self.canvas.delete("token")
        self.char_items, self.char_data = [], []
        text = self.entry_text.get()
        if not text: return
        
        # 画布显示字体
        font_style = ("Microsoft YaHei", 30, "bold")
        start_x, start_y = 1000, 500
        colors = ["#FF5722", "#FF9800", "#FFC107", "#8BC34A", "#4CAF50", "#009688", "#2196F3", "#3F51B5"]

        for i, char in enumerate(text):
            if char.strip() == "": continue
            x, y = start_x + (i * 60), start_y + (i * 80)
            rect_id = self.canvas.create_rectangle(x, y, x+80, y+80, fill=colors[i % 8], outline="black", width=2, tags=("token", f"item_{i}"))
            self.canvas.create_text(x+40, y+40, text=char, font=font_style, fill="white", tags=("token", f"item_{i}"))
            self.char_data.append({"char": char, "rect_id": rect_id})
        
        self.canvas.xview_moveto(0.3)
        self.canvas.yview_moveto(0.15)

    def on_press(self, event):
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        try:
            item = self.canvas.find_closest(cx, cy)[0]
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("item_"):
                    self.drag_data = {"x": cx, "y": cy, "item": tag}
                    break
        except: pass

    def on_motion(self, event):
        if self.drag_data["item"]:
            cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
            self.canvas.move(self.drag_data["item"], cx - self.drag_data["x"], cy - self.drag_data["y"])
            self.drag_data["x"], self.drag_data["y"] = cx, cy

    def on_release(self, event): self.drag_data["item"] = None

    def get_char_poly(self, char, size):
        try:
            prop = FontProperties(fname=self.custom_font_path)
            tp = TextPath((0, 0), char, size=size, prop=prop)
            polys_data = tp.to_polygons()
            
            if not polys_data: return None
            
            shapely_polys = []
            for points in polys_data:
                if len(points) > 2:
                    shapely_polys.append(Polygon(points))
            
            if not shapely_polys: return None
            
            combined = unary_union(shapely_polys)
            combined = combined.buffer(0) # 修复
            
            if combined.is_empty: return None

            minx, miny, maxx, maxy = combined.bounds
            combined = translate(combined, -minx, -miny)
            return combined
        except Exception as e:
            self.last_error = str(e)
            return None

    # --- 核心修复：处理 多部件几何体 (MultiPolygon) ---
    def extrude_safe(self, geometry, height):
        """
        这个函数能同时处理 '一块' 和 '多块' 的形状。
        """
        parts_meshes = []
        
        # 如果它是单独的一块 (Polygon)
        if geometry.geom_type == 'Polygon':
            m = trimesh.creation.extrude_polygon(geometry, height=height)
            parts_meshes.append(m)
            
        # 如果它是多块组成的 (MultiPolygon) —— 比如 '务'，'ii'
        elif geometry.geom_type == 'MultiPolygon':
            # 遍历里面的每一小块，分别拉伸
            for sub_poly in geometry.geoms:
                m = trimesh.creation.extrude_polygon(sub_poly, height=height)
                parts_meshes.append(m)
                
        return parts_meshes

    def generate_3d_model(self):
        if not self.char_data: return
        if not self.custom_font_path:
            messagebox.showwarning("警告", "请先选择桌面上的 simhei.ttf 字体文件！")
            return

        all_meshes = []
        origin_x, origin_y = 1000, 500
        success_count = 0
        
        print(f"正在生成...")

        for item in self.char_data:
            char = item["char"]
            coords = self.canvas.coords(item["rect_id"])
            world_x = (coords[0] - origin_x) * 1.5 
            world_y = -(coords[1] - origin_y) * 1.5 
            
            # 获取几何图形
            poly = self.get_char_poly(char, FONT_SIZE)
            
            if poly:
                # 移动到正确位置
                poly = translate(poly, world_x, world_y)
                length = random.uniform(BEAM_LENGTH_MIN, BEAM_LENGTH_MAX)
                
                try:
                    # 使用新的安全拉伸函数
                    char_mesh_parts = self.extrude_safe(poly, length)
                    
                    # 把这个字的各部分加到总列表里
                    all_meshes.extend(char_mesh_parts)
                    success_count += 1
                except Exception as e:
                    self.last_error = f"拉伸 '{char}' 失败: {e}"
                    print(self.last_error)

        if all_meshes:
            # 合并所有网格
            final_mesh = trimesh.util.concatenate(all_meshes)
            filename = f"Design_{random.randint(1000,9999)}.glb"
            final_mesh.export(filename)
            if messagebox.askyesno("成功", f"生成了 {success_count} 个字！\n文件: {filename}\n是否打开？"):
                try: os.startfile(filename)
                except: pass
        else:
            messagebox.showerror("生成失败", f"原因:\n{self.last_error}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DraggableText3DApp(root)
    root.mainloop()
