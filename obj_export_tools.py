# -*- coding: utf-8 -*-
"""
配方道具OBJ导出工具 / Recipe Props OBJ Export Tools

从easymesh_batch_exporter模块迁移的OBJ导出功能，
删除了LOD功能，只保留基本的OBJ批量导出功能。
"""

import bpy
import os
import time
import contextlib
import logging
from bpy.types import Operator, Panel
from bpy.props import StringProperty, EnumProperty, FloatProperty, BoolProperty
from .utils import get_addon_preferences

# --- Setup Logger ---
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(name)s:%(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# --- Core Functions ---

@contextlib.contextmanager
def temp_selection_context(context, active_object=None, selected_objects=None):
    """
    临时设置活动对象和选择状态
    
    Args:
        context (bpy.context): 当前Blender上下文
        active_object (bpy.types.Object, optional): 要设置为活动的对象
        selected_objects (list, optional): 要选择的对象列表
    """
    # 存储原始状态
    original_active = context.view_layer.objects.active
    original_selected = [obj for obj in context.scene.objects 
                         if obj.select_get()]
    
    try:
        # 取消选择所有对象
        for obj in context.scene.objects:
            if obj.select_get():
                obj.select_set(False)
        
        # 选择请求的对象
        if selected_objects:
            if not isinstance(selected_objects, list):
                selected_objects = [selected_objects]
            
            for obj in selected_objects:
                if obj and obj.name in context.scene.objects:
                    try:
                        obj.select_set(True)
                    except ReferenceError:
                        logger.warning(f"无法选择'{obj.name}' - 对象引用无效")
        
        # 设置活动对象
        if active_object and active_object.name in context.scene.objects:
            context.view_layer.objects.active = active_object
        elif selected_objects:
            for obj in selected_objects:
                if obj and obj.name in context.scene.objects:
                    context.view_layer.objects.active = obj
                    break
        
        yield
    
    finally:
        # 恢复原始状态
        for obj in context.scene.objects:
            obj.select_set(False)
            
        for obj in original_selected:
            if obj and obj.name in context.scene.objects:
                try:
                    obj.select_set(True)
                except ReferenceError:
                    pass
        
        if original_active and original_active.name in context.scene.objects:
            try:
                context.view_layer.objects.active = original_active
            except ReferenceError:
                pass


def create_export_copy(original_obj, context):
    """
    创建用于导出的对象副本
    
    Args:
        original_obj (bpy.types.Object): 原始对象
        context (bpy.context): Blender上下文
    
    Returns:
        bpy.types.Object: 复制的对象
    """
    # 创建对象副本
    mesh_copy = original_obj.data.copy()
    obj_copy = original_obj.copy()
    obj_copy.data = mesh_copy
    
    # 添加到场景
    context.collection.objects.link(obj_copy)
    
    # 复制变换
    obj_copy.matrix_world = original_obj.matrix_world.copy()
    
    return obj_copy


def setup_export_object(obj, original_obj_name, scene_props):
    """
    设置导出对象的名称和属性
    
    Args:
        obj (bpy.types.Object): 要设置的对象
        original_obj_name (str): 原始对象名称
        scene_props: 场景属性
    
    Returns:
        tuple: (导出对象名称, 基础名称)
    """
    # 清理对象名称
    clean_name = original_obj_name.replace(".", "_")
    
    # 坐标归零
    if hasattr(scene_props, 'obj_export_zero_location') and scene_props.obj_export_zero_location:
        obj.location = (0, 0, 0)
    
    # 应用缩放
    if hasattr(scene_props, 'obj_export_scale'):
        obj.scale = (scene_props.obj_export_scale,) * 3
    
    # 设置对象名称
    base_name = f"{clean_name}.obj"
    obj.name = f"export_{clean_name}"
    
    return obj.name, base_name


def apply_mesh_modifiers(obj):
    """
    应用网格修改器
    
    Args:
        obj (bpy.types.Object): 要应用修改器的对象
    """
    # 确保对象处于编辑模式外
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    
    # 选择对象
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    
    # 应用所有修改器
    for modifier in obj.modifiers:
        try:
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        except Exception as e:
            logger.warning(f"无法应用修改器 {modifier.name}: {e}")


def triangulate_mesh(obj, method='BEAUTY', keep_normals=True):
    """
    三角化网格
    
    Args:
        obj (bpy.types.Object): 要三角化的对象
        method (str): 三角化方法
        keep_normals (bool): 是否保持法线
    """
    # 进入编辑模式
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    
    # 选择所有面
    bpy.ops.mesh.select_all(action='SELECT')
    
    # 三角化
    bpy.ops.mesh.quads_convert_to_tris(quad_method=method, ngon_method=method)
    
    # 返回对象模式
    bpy.ops.object.mode_set(mode='OBJECT')


def export_object(obj, file_path, scene_props):
    """
    导出单个对象为OBJ格式
    
    Args:
        obj (bpy.types.Object): 要导出的对象
        file_path (str): 导出文件路径
        scene_props: 场景属性
    
    Returns:
        bool: 导出是否成功
    """
    # 确保文件路径使用UTF-8编码，处理中文字符
    try:
        file_path.encode('utf-8').decode('utf-8')
    except UnicodeError:
        logger.warning(f"文件路径'{file_path}'包含无法编码的字符，将使用替代路径")
        dir_path = os.path.dirname(file_path)
        safe_name = f"object_{hash(obj.name) % 10000:04d}"
        file_path = os.path.join(dir_path, safe_name)
    
    # 设置导出文件路径
    export_filepath = f"{file_path}.obj"
    
    logger.info(f"导出 {os.path.basename(export_filepath)} (OBJ)...")
    
    with temp_selection_context(bpy.context, active_object=obj, selected_objects=[obj]):
        try:
            # 坐标轴映射：将用户界面的值转换为API需要的枚举值
            axis_mapping = {
                'X': 'X',
                'Y': 'Y', 
                'Z': 'Z',
                '-X': 'NEGATIVE_X',
                '-Y': 'NEGATIVE_Y',
                '-Z': 'NEGATIVE_Z'
            }
            
            forward_axis_value = getattr(scene_props, 'obj_export_coord_forward', 'Z')
            up_axis_value = getattr(scene_props, 'obj_export_coord_up', 'Y')
            
            # 转换为API需要的枚举值
            forward_axis_enum = axis_mapping.get(forward_axis_value, 'NEGATIVE_Z')
            up_axis_enum = axis_mapping.get(up_axis_value, 'Y')
            
            # 导出OBJ格式
            bpy.ops.wm.obj_export(
                filepath=export_filepath,
                export_selected_objects=True,
                global_scale=getattr(scene_props, 'obj_export_scale', 1.0),
                forward_axis=forward_axis_enum,
                up_axis=up_axis_enum,
                export_materials=getattr(scene_props, 'obj_export_materials', True),
                path_mode="COPY",
                export_normals=True,
                export_smooth_groups=True,
                apply_modifiers=False,  # 由apply_mesh_modifiers处理
                export_triangulated_mesh=False,  # 由triangulate_mesh处理
            )
            
            logger.info(f"成功导出 {os.path.basename(export_filepath)}")
            return True
            
        except Exception as e:
            logger.error(f"导出失败 {os.path.basename(export_filepath)}: {e}")
            return False


def cleanup_object(obj, obj_name=None):
    """
    清理临时对象
    
    Args:
        obj (bpy.types.Object): 要清理的对象
        obj_name (str, optional): 对象名称（用于日志）
    """
    if obj and obj.name in bpy.data.objects:
        try:
            # 删除网格数据
            if obj.data:
                bpy.data.meshes.remove(obj.data)
            # 删除对象
            bpy.data.objects.remove(obj)
        except Exception as e:
            name = obj_name or (obj.name if obj else "Unknown")
            logger.warning(f"清理对象 {name} 时出错: {e}")


# --- Operators ---

class OBJ_OT_batch_export(Operator):
    """批量导出选中的网格对象为OBJ格式"""
    bl_idname = "obj.batch_export"
    bl_label = "批量导出OBJ"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """仅在选择了网格对象时启用"""
        return any(obj.type == "MESH" for obj in context.selected_objects)

    def execute(self, context):
        """执行批量导出过程"""
        scene = context.scene
        scene_props = scene.poptools_props.obj_export_settings
        wm = context.window_manager
        start_time = time.time()

        objects_to_export = [
            obj for obj in context.selected_objects if obj.type == "MESH"
        ]
        total_objects = len(objects_to_export)

        if not objects_to_export:
            self.report({"WARNING"}, "未选择网格对象")
            logger.warning("导出取消：未选择网格对象")
            return {"CANCELLED"}

        # 验证导出路径
        export_base_path = bpy.path.abspath(scene_props.obj_export_path)
        if not os.path.isdir(export_base_path):
            try:
                os.makedirs(export_base_path)
                logger.info(f"创建导出目录: {export_base_path}")
            except Exception as e:
                err_msg = f"导出路径无效/无法创建: {export_base_path}. 错误: {e}"
                self.report({"ERROR"}, err_msg)
                logger.error(err_msg)
                return {"CANCELLED"}

        successful_exports = 0
        failed_exports = []
        overall_success = True

        logger.info(f"开始批量导出 {total_objects} 个对象到 {export_base_path}")
        wm.progress_begin(0, total_objects)
        
        try:
            # --- 主导出循环 ---
            for index, original_obj in enumerate(objects_to_export):
                wm.progress_update(index + 1)
                logger.info(f"处理 ({index + 1}/{total_objects}): {original_obj.name}")
                object_processed_successfully = True

                export_obj = None
                export_obj_name = None
                
                try:
                    logger.info("处理单个导出（无LOD）...")
                    export_obj = create_export_copy(original_obj, context)
                    (export_obj_name, base_name) = setup_export_object(
                        export_obj, original_obj.name, scene_props
                    )
                    apply_mesh_modifiers(export_obj)
                    
                    if scene_props.obj_export_triangulate:
                        triangulate_mesh(
                            export_obj,
                            scene_props.obj_export_tri_method,
                            scene_props.obj_export_keep_normals
                        )

                    file_path = os.path.join(export_base_path, base_name.replace('.obj', ''))
                    if export_object(export_obj, file_path, scene_props):
                        successful_exports += 1
                    else:
                        object_processed_successfully = False
                        failed_exports.append(original_obj.name)

                except Exception as e:
                    object_processed_successfully = False
                    log_name = export_obj_name if export_obj_name else original_obj.name
                    logger.error(f"处理失败 {log_name}: {e}")
                    failed_exports.append(f"{original_obj.name} (处理错误)")
                    
                finally:
                    cleanup_object(export_obj, export_obj_name)

                if not object_processed_successfully:
                    overall_success = False

        finally:
            wm.progress_end()

        # 报告结果
        end_time = time.time()
        duration = end_time - start_time
        
        if overall_success:
            msg = f"成功导出 {successful_exports} 个对象 (耗时 {duration:.2f}s)"
            self.report({"INFO"}, msg)
            logger.info(msg)
        else:
            msg = f"导出完成，但有错误。成功: {successful_exports}, 失败: {len(failed_exports)}"
            self.report({"WARNING"}, msg)
            logger.warning(msg)
            if failed_exports:
                logger.warning(f"失败的对象: {', '.join(failed_exports)}")

        return {"FINISHED"}


class OBJ_OT_open_export_directory(Operator):
    """打开导出目录"""
    bl_idname = "obj.open_export_directory"
    bl_label = "打开导出目录"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene_props = context.scene.poptools_props.obj_export_settings
        export_path = bpy.path.abspath(scene_props.obj_export_path)
        
        if os.path.exists(export_path):
            os.startfile(export_path)
        else:
            self.report({"WARNING"}, f"导出目录不存在: {export_path}")
            
        return {"FINISHED"}


# --- Panels ---

class OBJ_PT_export_panel(Panel):
    """配方道具OBJ导出面板"""
    bl_label = "配方道具OBJ导出"
    bl_idname = "OBJ_PT_export_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PopTools"
    bl_order = 3
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        prefs = get_addon_preferences()
        return prefs and prefs.enable_obj_export_tools

    def draw(self, context):
        layout = self.layout
        props = context.scene.poptools_props.obj_export_settings
        
        layout.use_property_split = True
        layout.use_property_decorate = False

        # 导出路径设置
        layout.prop(props, "obj_export_path")

        # 坐标系设置
        col = layout.column(heading="坐标系", align=True)
        row = col.row(align=True)
        row.prop(props, "obj_export_coord_up", expand=True)
        row = col.row(align=True)
        row.prop(props, "obj_export_coord_forward", expand=True)

        # 坐标归零设置
        layout.prop(props, "obj_export_zero_location")

        # 缩放设置
        layout.prop(props, "obj_export_scale")

        # 材质设置
        layout.prop(props, "obj_export_materials")

        # 三角化设置
        layout.prop(props, "obj_export_triangulate")
        if props.obj_export_triangulate:
            col = layout.column()
            col.prop(props, "obj_export_tri_method")
            col.prop(props, "obj_export_keep_normals")

        # 分隔线
        layout.separator()

        # 导出按钮
        col = layout.column(align=True)
        col.scale_y = 1.2
        
        # 检查是否有选中的网格对象
        selected_meshes = [obj for obj in context.selected_objects if obj.type == "MESH"]
        if selected_meshes:
            col.operator("obj.batch_export", text=f"导出选中的 {len(selected_meshes)} 个对象", icon="EXPORT")
        else:
            col.operator("obj.batch_export", text="导出选中对象", icon="EXPORT")
            col.label(text="请选择要导出的网格对象", icon="INFO")

        # 打开目录按钮
        layout.separator()
        layout.operator("obj.open_export_directory", text="打开导出目录", icon="FILE_FOLDER")


# ============================================================================
# Registration
# ============================================================================

classes = (
    OBJ_OT_batch_export,
    OBJ_OT_open_export_directory,
    OBJ_PT_export_panel,
)


def register():
    """注册所有类"""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """注销所有类"""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)