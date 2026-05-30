import bpy
import os
import sys
import subprocess
import math
from . import utils
from .core.export_core import do_export, ExportOptions
from datetime import datetime


# FBX/OBJ/GLTF export
class MultiExport(bpy.types.Operator):
	"""Export FBXs/OBJs/GLTFs to Unity/UE/Godot"""
	bl_idname = "object.multi_export"
	bl_label = "Export FBXs/OBJs/GLTFs"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		act = bpy.context.scene.poptools_props.export_tools_settings

		options = ExportOptions(
			export_path=act.export_path,
			custom_export_path=act.custom_export_path,
			export_format=act.export_format,
			fbx_export_mode=act.fbx_export_mode,
			export_target_engine=act.export_target_engine,
			apply_rot=act.apply_rot,
			apply_scale=act.apply_scale,
			apply_loc=act.apply_loc,
			apply_rot_rotated=act.apply_rot_rotated,
			delete_mats_before_export=act.delete_mats_before_export,
			triangulate_before_export=act.triangulate_before_export,
			export_combine_meshes=act.export_combine_meshes,
			set_custom_fbx_name=act.set_custom_fbx_name,
			custom_fbx_name=act.custom_fbx_name,
		)

		result = do_export(
			objects=list(context.selected_objects),
			format=act.export_format,
			mode=act.fbx_export_mode,
			options=options,
			context=context,
		)

		if not result.ok:
			utils.show_message_box(result.error, "Export Error", "ERROR")
			return {"CANCELLED"}

		act.export_dir = result.export_dir

		if result.incorrect_names:
			utils.show_message_box(
				"Object(s) has invalid characters in name. Some chars in export name have been replaced",
				"Incorrect Export Names",
			)

		self.report({"INFO"}, result.message)
		return {"FINISHED"}


# Open Export Directory
class OpenExportDir(bpy.types.Operator):
	"""Open Export Directory in OS"""
	bl_idname = "object.open_export_dir"
	bl_label = "Open Export Directory in OS"
	bl_options = {'REGISTER', 'UNDO'}

	def execute(self, context):
		start_time = datetime.now()
		act = bpy.context.scene.poptools_props.export_tools_settings

		if not os.path.exists(os.path.realpath(bpy.path.abspath(act.export_dir))):
			act.export_dir = ""
			utils.show_message_box('Directory not exist',
								   'Wrong Path',
								   'ERROR')

			return {'CANCELLED'}

		# Try open export dir in OS
		if len(act.export_dir) > 0:
			try:
				utils.open_directory(act.export_dir)
			except Exception as e:
				print(f"Failed to open export directory: {e}")
		else:
			utils.show_message_box('Export FBX\'s before',
								   'Info')
			return {'FINISHED'}

		utils.print_execution_time("Open Export Directory", start_time)
		return {'FINISHED'}


# Import Export UI Panel
class VIEW3D_PT_export_tools_panel(bpy.types.Panel):
	bl_label = "导出FBX"
	bl_space_type = "VIEW_3D"
	bl_region_type = "UI"
	bl_category = "PopTools"
	bl_options = {'DEFAULT_CLOSED'}

	@classmethod
	def poll(cls, context):
		# If this panel not hidden in preferences
		try:
			preferences = bpy.context.preferences.addons['PopTools'].preferences
			return (context.object is not None and context.mode == 'OBJECT') and preferences.export_import_enable
		except:
			return context.object is not None and context.mode == 'OBJECT'

	def draw(self, context):
		try:
			act = bpy.context.scene.poptools_props.export_tools_settings
		except AttributeError:
			# PopTools属性未正确初始化
			layout = self.layout
			row = layout.row()
			row.label(text="PopTools未正确初始化，请重新启用插件")
			return
		
		layout = self.layout

		if context.object is not None:
			if context.mode == 'OBJECT':
				# 3DCoat导出前整理部分
				coat_box = layout.box()
				coat_box.label(text="3DCoat导出前整理：", icon='TOOL_SETTINGS')
				
				# 材质整理部分
				mat_row = coat_box.row()
				mat_row.operator("rt.organize_selected_materials", text="一键整理选中模型材质", icon='MATERIAL')
				
				# UV检查部分
				uv_row = coat_box.row()
				uv_row.operator("rt.check_uvs", text="一键检查UV", icon='UV_DATA')
				
				# 显示UV检查结果
				try:
					props = context.scene.poptools_props.retex_settings
					if props.uv_check_results:
						results_box = coat_box.box()
						if props.uv_check_results == "所有模型UV正常，无重复UV Map":
							row = results_box.row()
							row.label(text="无重复UV模型", icon='CHECKMARK')
						else:
							results_box.label(text="存在多个UV Map的模型：")
							# 创建一个水平布局来显示模型名称
							flow = results_box.column_flow(columns=4, align=True)
							# 将结果字符串拆分为列表
							items = props.uv_check_results.split('\n')
							for item in items:
								if item.strip():
									# 每个模型名称占据单独一行
									flow.label(text=item)
					elif props.uv_check_triggered:
						results_box = coat_box.box()
						# 如果检查已触发但结果为空（可能在操作符中被清空表示无问题）
						row = results_box.row()
						row.label(text="无重复UV模型", icon='CHECKMARK')
				except AttributeError:
					# 如果retex_settings不存在，忽略UV检查结果显示
					pass
				
				# 分隔线
				layout.separator()
				# Export Mode
				row = layout.row(align=True)
				row.label(text="导出模式:")
				row.prop(act, 'fbx_export_mode', expand=False)

				# Export Format (FBX or OBJ)
				row = layout.row(align=True)
				row.label(text="文件格式:")
				row.prop(act, "export_format", expand=False)

				if act.export_format == 'FBX':
					# Target Engine
					row = layout.row(align=True)
					row.label(text="目标引擎:")
					row.prop(act, "export_target_engine", expand=False)

				if not (act.export_format == 'OBJ' and (
						act.fbx_export_mode == 'ALL' or act.fbx_export_mode == 'COLLECTION')):
					# Apply Transforms
					box = layout.box()
					row = box.row()
					row.label(text="应用变换:")

					row = box.row(align=True)
					if act.export_format == 'FBX' or act.export_format == 'GLTF':
						if act.apply_rot:
							row.prop(act, "apply_rot", text="旋转", icon="CHECKBOX_HLT")
						else:
							row.prop(act, "apply_rot", text="旋转", icon="CHECKBOX_DEHLT")
						if act.apply_scale:
							row.prop(act, "apply_scale", text="缩放", icon="CHECKBOX_HLT")
						else:
							row.prop(act, "apply_scale", text="缩放", icon="CHECKBOX_DEHLT")

					if act.fbx_export_mode == 'INDIVIDUAL' or act.fbx_export_mode == 'PARENT':
						if act.apply_loc:
							row.prop(act, "apply_loc", text="位置", icon="CHECKBOX_HLT")
						else:
							row.prop(act, "apply_loc", text="位置", icon="CHECKBOX_DEHLT")

					if act.export_format == 'FBX':
						if act.apply_rot and act.fbx_export_mode == 'PARENT' and act.export_target_engine != 'UNITY2023':
							row = box.row()
							row.prop(act, "apply_rot_rotated")

			row = layout.row()
			row.prop(act, "delete_mats_before_export", text="删除所有材质")

			if act.fbx_export_mode != 'INDIVIDUAL':
				row = layout.row()
				row.prop(act, "export_combine_meshes", text="合并所有网格")

			row = layout.row()
			row.prop(act, "triangulate_before_export", text="三角化网格")

			if act.fbx_export_mode == 'ALL':
				box = layout.box()
				row = box.row()
				row.prop(act, "set_custom_fbx_name", text="自定义文件名")
				if act.set_custom_fbx_name:
					row = box.row(align=True)
					row.label(text="文件名:")
					row.prop(act, "custom_fbx_name")

			# Custom Export Options
			box = layout.box()
			row = box.row()
			row.prop(act, "export_custom_options", text="自定义导出选项")
			if act.export_custom_options:
				if act.export_format == 'FBX':
					row = box.row(align=True)
					row.label(text=" 平滑")
					row.prop(act, "export_smoothing", expand=False)

					row = box.row(align=True)
					row.label(text=" 松散边")
					row.prop(act, "export_loose_edges", text="")

					row = box.row(align=True)
					row.label(text=" 切线空间")
					row.prop(act, "export_tangent_space", text="")

					row = box.row(align=True)
					row.label(text=" 仅变形骨骼")
					row.prop(act, "export_only_deform_bones", text="")

					row = box.row(align=True)
					row.label(text=" 添加叶骨骼")
					row.prop(act, "export_add_leaf_bones", text="")

					row = box.row(align=True)
					row.label(text=" 顶点色彩空间")
					row.prop(act, "export_vc_color_space", expand=False)

					row = box.row(align=True)
					row.label(text=" 自定义属性")
					row.prop(act, "export_custom_props", text="")

				if act.export_format == 'OBJ':
					row = box.row(align=True)
					row.label(text=" 按材质分离")
					row.prop(act, "obj_separate_by_materials", text="")

					row = box.row(align=True)
					row.label(text=" 平滑组")
					row.prop(act, "obj_export_smooth_groups", text="")

					if act.export_format == 'FBX' or act.export_format == 'OBJ':
						row = box.row(align=True)
					row.label(text="使用自定义缩放")
					row.prop(act, "use_custom_export_scale", text="")
					if act.use_custom_export_scale:
						row = box.row(align=True)
						row.prop(act, "custom_export_scale_value", text="缩放")
					row = box.row(align=True)
					row.label(text="使用自定义轴向")
					row.prop(act, "use_custom_export_axes", text="")
					if act.use_custom_export_axes:
						row = box.row(align=True)
						row.label(text=" 前向")
						row.prop(act, "custom_export_forward_axis", expand=False)
						row = box.row(align=True)
						row.label(text=" 上向")
						row.prop(act, "custom_export_up_axis", expand=False)


				if act.export_format == 'GLTF':
					row = box.row(align=True)
					row.label(text=" 打包图像")
					row.prop(act, "gltf_export_image_format", text="")

					row = box.row(align=True)
					row.label(text=" 仅变形骨骼")
					row.prop(act, "gltf_export_deform_bones_only", text="")

					row = box.row(align=True)
					row.label(text=" 自定义属性")
					row.prop(act, "gltf_export_custom_properties", text="")

					row = box.row(align=True)
					row.label(text=" 切线")
					row.prop(act, "gltf_export_tangents", text="")

					row = box.row(align=True)
					row.label(text=" 属性")
					row.prop(act, "gltf_export_attributes", text="")

			box = layout.box()
			row = box.row()
			row.prop(act, "custom_export_path", text="自定义导出路径")
			if act.custom_export_path:
				row = box.row(align=True)
				row.label(text="导出路径:")
				row.prop(act, "export_path")

				row = layout.row()
				if act.export_format == 'FBX':
					if act.export_target_engine == 'UNITY' or act.export_target_engine == 'UNITY2023':
						row.operator("object.multi_export", text="导出 FBX 到 Unity")
					elif act.export_target_engine == '3DCOAT':
						row.operator("object.multi_export", text="导出 FBX 到 3DCoat")
					else:
						row.operator("object.multi_export", text="导出 FBX 到 Unreal")
				elif act.export_format == 'OBJ':
					row.operator("object.multi_export", text="导出 OBJ")
				elif act.export_format == 'GLTF':
					row.operator("object.multi_export", text="导出 GLTF")

				if len(act.export_dir) > 0:
					row = layout.row()
					row.operator("object.open_export_dir", text="Open Export Directory")

				# 调试模式选项 / Debug Mode Option
				row = layout.row()
				row.prop(act, "debug", text="Debug Mode")

		else:
			row = layout.row()
			row.label(text=" ")


classes = (
	MultiExport,
	OpenExportDir,
	VIEW3D_PT_export_tools_panel
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
