# -*- coding: utf-8 -*-
"""
Vertex Baker Tools - 顶点到骨骼烘焙工具
Vertex to Bone Baking Tools

提供顶点到骨骼的绑定和烘焙功能。
Provides vertex to bone binding and baking functionality.
"""

import bpy
import bmesh
from mathutils import Vector
from bpy.types import Operator, Panel
from bpy.props import PointerProperty

# 导入工具函数
from .utils import show_message_box, get_addon_preferences

# ============================================================================
# 操作符定义 / Operator Definitions
# ============================================================================

class VTBB_OT_CreateEmptiesForBones(Operator):
    """为每根骨骼创建对应的空物体并设置约束 / Create Empties for Bones"""
    bl_idname = "vtbb.create_empties_for_bones"
    bl_label = "创建空物体并绑定到骨骼"
    bl_description = "为每根骨骼创建对应的空物体并设置约束"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # 获取当前选中的骨架对象
        armature = context.active_object
        
        if not armature or armature.type != 'ARMATURE':
            show_message_box("请先选择一个骨架对象", "错误", 'ERROR')
            return {'CANCELLED'}
        
        # 获取骨架中的所有骨骼
        bones = armature.data.bones
        
        # 创建一个空物体集合来存放所有创建的空物体
        if "VTBB_Empties" not in bpy.data.collections:
            empty_collection = bpy.data.collections.new("VTBB_Empties")
            bpy.context.scene.collection.children.link(empty_collection)
        else:
            empty_collection = bpy.data.collections["VTBB_Empties"]
        
        # 为每根骨骼创建一个空物体
        created_empties = []
        for bone in bones:
            # 创建空物体名称
            empty_name = f"empty_{bone.name}"
            
            # 检查是否已存在同名空物体
            if empty_name in bpy.data.objects:
                empty = bpy.data.objects[empty_name]
            else:
                # 创建一个箭头型空物体
                empty = bpy.data.objects.new(empty_name, None)
                empty.empty_display_type = 'ARROWS'
                empty.empty_display_size = 0.1
                
                # 将空物体添加到集合中
                empty_collection.objects.link(empty)
            
            # 记录创建的空物体
            created_empties.append(empty)
            
            # 设置空物体的位置为骨骼的头部位置
            # 需要将骨骼的本地坐标转换为世界坐标
            bone_head_world = armature.matrix_world @ bone.head_local
            empty.location = bone_head_world
            
            # 为空物体添加复制位置约束，使其跟随骨骼
            constraint = empty.constraints.new(type='COPY_LOCATION')
            constraint.target = armature
            constraint.subtarget = bone.name
            
            # 添加复制旋转约束
            rot_constraint = empty.constraints.new(type='COPY_ROTATION')
            rot_constraint.target = armature
            rot_constraint.subtarget = bone.name
        
        show_message_box(f"成功为 {len(created_empties)} 根骨骼创建了空物体", "创建完成", 'INFO')
        return {'FINISHED'}

class VTBB_OT_BindEmptiesToVertices(Operator):
    """将空物体绑定到网格顶点 / Bind Empties to Vertices"""
    bl_idname = "vtbb.bind_empties_to_vertices"
    bl_label = "绑定空物体到顶点"
    bl_description = "将空物体绑定到最近的网格顶点"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.poptools_props.vertex_baker_settings
        target_mesh = props.target_mesh
        
        if not target_mesh or target_mesh.type != 'MESH':
            show_message_box("请先选择一个目标网格对象", "错误", 'ERROR')
            return {'CANCELLED'}
        
        # 获取VTBB_Empties集合中的所有空物体
        if "VTBB_Empties" not in bpy.data.collections:
            show_message_box("未找到空物体集合，请先创建空物体", "错误", 'ERROR')
            return {'CANCELLED'}
        
        empty_collection = bpy.data.collections["VTBB_Empties"]
        empties = [obj for obj in empty_collection.objects if obj.type == 'EMPTY']
        
        if not empties:
            show_message_box("未找到空物体，请先创建空物体", "错误", 'ERROR')
            return {'CANCELLED'}
        
        # 进入编辑模式获取网格顶点
        bpy.context.view_layer.objects.active = target_mesh
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 创建bmesh实例
        bm = bmesh.from_mesh(target_mesh.data)
        bm.verts.ensure_lookup_table()
        
        # 退出编辑模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        bound_count = 0
        
        # 为每个空物体找到最近的顶点
        for empty in empties:
            empty_location = empty.location
            closest_vert = None
            min_distance = float('inf')
            
            # 遍历所有顶点找到最近的
            for vert in bm.verts:
                vert_world = target_mesh.matrix_world @ vert.co
                distance = (empty_location - vert_world).length
                
                if distance < min_distance:
                    min_distance = distance
                    closest_vert = vert
            
            if closest_vert:
                # 将空物体位置设置为最近顶点的位置
                vert_world_pos = target_mesh.matrix_world @ closest_vert.co
                empty.location = vert_world_pos
                bound_count += 1
        
        # 清理bmesh
        bm.free()
        
        show_message_box(f"成功绑定 {bound_count} 个空物体到顶点", "绑定完成", 'INFO')
        return {'FINISHED'}

class VTBB_OT_BakeVertexWeights(Operator):
    """烘焙顶点权重 / Bake Vertex Weights"""
    bl_idname = "vtbb.bake_vertex_weights"
    bl_label = "烘焙顶点权重"
    bl_description = "将空物体位置烘焙为顶点权重"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.poptools_props.vertex_baker_settings
        target_mesh = props.target_mesh
        
        if not target_mesh or target_mesh.type != 'MESH':
            show_message_box("请先选择一个目标网格对象", "错误", 'ERROR')
            return {'CANCELLED'}
        
        # 获取VTBB_Empties集合中的所有空物体
        if "VTBB_Empties" not in bpy.data.collections:
            show_message_box("未找到空物体集合，请先创建空物体", "错误", 'ERROR')
            return {'CANCELLED'}
        
        empty_collection = bpy.data.collections["VTBB_Empties"]
        empties = [obj for obj in empty_collection.objects if obj.type == 'EMPTY']
        
        if not empties:
            show_message_box("未找到空物体，请先创建空物体", "错误", 'ERROR')
            return {'CANCELLED'}
        
        # 确保目标网格有顶点组
        for empty in empties:
            group_name = empty.name.replace("empty_", "")
            if group_name not in target_mesh.vertex_groups:
                target_mesh.vertex_groups.new(name=group_name)
        
        # 进入编辑模式
        bpy.context.view_layer.objects.active = target_mesh
        bpy.ops.object.mode_set(mode='EDIT')
        
        # 创建bmesh实例
        bm = bmesh.from_mesh(target_mesh.data)
        bm.verts.ensure_lookup_table()
        
        # 退出编辑模式
        bpy.ops.object.mode_set(mode='OBJECT')
        
        baked_count = 0
        
        # 为每个空物体烘焙权重
        for empty in empties:
            group_name = empty.name.replace("empty_", "")
            vertex_group = target_mesh.vertex_groups.get(group_name)
            
            if vertex_group:
                empty_location = empty.location
                
                # 计算每个顶点到空物体的距离并设置权重
                for vert in bm.verts:
                    vert_world = target_mesh.matrix_world @ vert.co
                    distance = (empty_location - vert_world).length
                    
                    # 使用距离的倒数作为权重（距离越近权重越大）
                    if distance > 0:
                        weight = 1.0 / (1.0 + distance)
                    else:
                        weight = 1.0
                    
                    # 限制权重范围
                    weight = max(0.0, min(1.0, weight))
                    
                    # 设置顶点权重
                    vertex_group.add([vert.index], weight, 'REPLACE')
                
                baked_count += 1
        
        # 清理bmesh
        bm.free()
        
        show_message_box(f"成功烘焙 {baked_count} 个顶点组的权重", "烘焙完成", 'INFO')
        return {'FINISHED'}

class VTBB_OT_ClearEmpties(Operator):
    """清理空物体 / Clear Empties"""
    bl_idname = "vtbb.clear_empties"
    bl_label = "清理空物体"
    bl_description = "删除所有创建的空物体"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        # 获取VTBB_Empties集合
        if "VTBB_Empties" not in bpy.data.collections:
            show_message_box("未找到空物体集合", "警告", 'WARNING')
            return {'CANCELLED'}
        
        empty_collection = bpy.data.collections["VTBB_Empties"]
        empties = list(empty_collection.objects)
        
        if not empties:
            show_message_box("集合中没有空物体", "警告", 'WARNING')
            return {'CANCELLED'}
        
        # 删除所有空物体
        for empty in empties:
            bpy.data.objects.remove(empty, do_unlink=True)
        
        # 删除集合
        bpy.data.collections.remove(empty_collection)
        
        show_message_box(f"成功删除 {len(empties)} 个空物体", "清理完成", 'INFO')
        return {'FINISHED'}

# ============================================================================
# 面板定义 / Panel Definitions
# ============================================================================

class VTBB_PT_MainPanel(Panel):
    """顶点烘焙主面板 / Vertex Baking Main Panel"""
    bl_label = "Vertex to Bone Baker"
    bl_idname = "VTBB_PT_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PopTools'
    bl_order = 4
    bl_options = {'DEFAULT_CLOSED'}
    
    @classmethod
    def poll(cls, context):
        prefs = get_addon_preferences()
        return prefs and prefs.enable_vertex_baker_tools
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.poptools_props.vertex_baker_settings
        
        # 目标网格选择
        box = layout.box()
        box.label(text="目标设置：")
        box.prop(props, "target_mesh", text="目标网格")
        
        # 分隔线
        layout.separator()
        
        # 操作按钮
        box = layout.box()
        box.label(text="操作：")
        
        col = box.column(align=True)
        col.operator("vtbb.create_empties_for_bones", text="创建空物体", icon='EMPTY_ARROWS')
        col.operator("vtbb.bind_empties_to_vertices", text="绑定到顶点", icon='SNAP_VERTEX')
        col.operator("vtbb.bake_vertex_weights", text="烘焙权重", icon='MOD_VERTEX_WEIGHT')
        
        # 分隔线
        layout.separator()
        
        # 清理操作
        box = layout.box()
        box.label(text="清理：")
        box.operator("vtbb.clear_empties", text="清理空物体", icon='TRASH')
        
        # 使用说明
        box = layout.box()
        box.label(text="使用说明：")
        col = box.column(align=True)
        col.label(text="1. 选择骨架对象")
        col.label(text="2. 点击'创建空物体'")
        col.label(text="3. 选择目标网格")
        col.label(text="4. 点击'绑定到顶点'")
        col.label(text="5. 点击'烘焙权重'")

# ============================================================================
# 注册和注销 / Registration and Unregistration
# ============================================================================

classes = [
    VTBB_OT_CreateEmptiesForBones,
    VTBB_OT_BindEmptiesToVertices,
    VTBB_OT_BakeVertexWeights,
    VTBB_OT_ClearEmpties,
    VTBB_PT_MainPanel,
]

def register():
    """注册所有类 / Register all classes"""
    for cls in classes:
        bpy.utils.register_class(cls)
    print("Vertex Baker Tools registered successfully")

def unregister():
    """注销所有类 / Unregister all classes"""
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception as e:
            print(f"Error unregistering {cls.__name__}: {e}")
    print("Vertex Baker Tools unregistered successfully")

if __name__ == "__main__":
    register()