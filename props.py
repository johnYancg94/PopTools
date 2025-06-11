# -*- coding: utf-8 -*-
"""
PopTools Properties
统一的属性定义文件
"""

import bpy
from bpy.props import (
    StringProperty,
    BoolProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    PointerProperty
)
# TranslationToolsSettings在translation_tools.py中定义

# Export Tools Properties
class ExportToolsSettings(bpy.types.PropertyGroup):
    """导出工具设置 / Export Tools Settings"""
    
    # 导出模式 / Export Mode
    fbx_export_mode: EnumProperty(
        name="",
        description="选择导出模式 / Select export mode",
        items=[
            ('ALL', "合并导出", "导出所有选中对象到一个FBX"),
            ('INDIVIDUAL', "逐个导出", "每个选中对象导出为单独文件"),
            ('PARENT', "父级", "导出父级及其所有子级"),
            ('COLLECTION', "集合", "按集合导出对象")
        ],
        default='ALL'
    )
    
    # 导出格式 / Export Format
    export_format: EnumProperty(
        name="",
        description="选择导出格式 / Select export format",
        items=[
            ('FBX', "FBX", "导出为FBX"),
            ('OBJ', "OBJ", "导出为OBJ"),
            ('GLTF', "GLTF", "导出为")
        ],
        default='FBX'
    )
    
    # 目标引擎 / Target Engine
    export_target_engine: EnumProperty(
        name="",
        description="选择目标引擎 / Select target engine",
        items=[
            ('UNITY', "Unity", "Export for Unity"),
            ('UNITY2023', "Unity 2023+", "Export for Unity 2023 and newer"),
            ('UNREAL', "Unreal", "Export for Unreal Engine"),
            ('GODOT', "Godot", "Export for Godot Engine"),
            ('3DCOAT', "3DCoat", "Export for 3DCoat")
        ],
        default='3DCOAT'
    )
    
    # 应用变换 / Apply Transforms
    apply_rot: BoolProperty(
        name="Apply Rotation",
        description="Apply rotation before export",
        default=True
    )
    
    apply_scale: BoolProperty(
        name="Apply Scale",
        description="Apply scale before export",
        default=True
    )
    
    apply_loc: BoolProperty(
        name="Apply Location",
        description="Apply location before export",
        default=False
    )
    
    apply_rot_rotated: BoolProperty(
        name="Apply Rotation Only to Rotated Objects",
        description="Apply rotation only to objects with non-zero rotation",
        default=True
    )
    
    # Export Options
    delete_mats_before_export: BoolProperty(
        name="Delete All Materials",
        description="Delete all materials before export",
        default=False
    )
    
    export_combine_meshes: BoolProperty(
        name="Combine All Meshes",
        description="Combine all meshes before export",
        default=False
    )
    
    triangulate_before_export: BoolProperty(
        name="Triangulate Meshes",
        description="Triangulate meshes before export",
        default=False
    )
    
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers before export",
        default=True
    )
    
    export_materials: BoolProperty(
        name="Export Materials",
        description="Include materials when exporting",
        default=True
    )
    
    # 自定义名称 / Custom Naming
    set_custom_fbx_name: BoolProperty(
        name="Custom Name for File",
        description="Use custom name for exported file",
        default=False
    )
    
    custom_fbx_name: StringProperty(
        name="Custom Name",
        description="Custom name for exported file",
        default=""
    )
    
    # 自定义导出选项 / Custom Export Options
    export_custom_options: BoolProperty(
        name="Custom Export Options",
        description="Use custom export options",
        default=False
    )
    
    # FBX平滑选项 / FBX Smoothing Options
    export_smoothing: EnumProperty(
        name="Smoothing",
        description="Smoothing type for export",
        items=[
            ('FACE', "Face", "Export face smoothing"),
            ('EDGE', "Edge", "Export edge smoothing"),
            ('OFF', "Off", "Disable smoothing")
        ],
        default='FACE'
    )
    
    export_loose_edges: BoolProperty(
        name="松散边 / Loose Edges",
        description="导出松散边 / Export loose edges",
        default=False
    )
    
    export_tangent_space: BoolProperty(
        name="切线空间 / Tangent Space",
        description="导出切线空间 / Export tangent space",
        default=False
    )
    
    export_only_deform_bones: BoolProperty(
        name="仅变形骨骼 / Only Deform Bones",
        description="仅导出变形骨骼 / Export only deform bones",
        default=True
    )
    
    export_add_leaf_bones: BoolProperty(
        name="添加叶子骨骼 / Add Leaf Bones",
        description="添加叶子骨骼 / Add leaf bones",
        default=False
    )
    
    export_vc_color_space: EnumProperty(
        name="顶点颜色空间 / VC Color Space",
        description="导出的顶点颜色空间 / Vertex color space for export",
        items=[
            ('SRGB', "sRGB", "在sRGB颜色空间中导出顶点颜色 / Export vertex colors in sRGB color space"),
            ('LINEAR', "线性 / Linear", "在线性颜色空间中导出顶点颜色 / Export vertex colors in linear color space")
        ],
        default='SRGB'
    )
    
    export_custom_props: BoolProperty(
        name="自定义属性 / Custom Props",
        description="导出自定义属性 / Export custom properties",
        default=False
    )
    
    # OBJ选项 / OBJ Options
    obj_separate_by_materials: BoolProperty(
        name="按材质分离 / Separate By Materials",
        description="OBJ导出时按材质分离对象 / Separate objects by materials for OBJ export",
        default=False
    )
    
    obj_export_smooth_groups: BoolProperty(
        name="平滑组 / Smooth Groups",
        description="为OBJ导出平滑组 / Export smooth groups for OBJ",
        default=False
    )
    
    # 自定义缩放 / Custom Scale
    use_custom_export_scale: BoolProperty(
        name="使用自定义缩放 / Use Custom Scale",
        description="为导出使用自定义缩放 / Use custom scale for export",
        default=False
    )
    
    custom_export_scale_value: FloatProperty(
        name="缩放 / Scale",
        description="导出的自定义缩放值 / Custom scale value for export",
        default=1.0,
        min=0.001,
        max=1000.0
    )
    
    # 自定义轴 / Custom Axes
    use_custom_export_axes: BoolProperty(
        name="使用自定义轴 / Use Custom Axes",
        description="为导出使用自定义轴 / Use custom axes for export",
        default=False
    )
    
    custom_export_forward_axis: EnumProperty(
        name="前向 / Forward",
        description="导出的前向轴 / Forward axis for export",
        items=[
            ('X', "X", "X轴 / X axis"),
            ('Y', "Y", "Y轴 / Y axis"),
            ('Z', "Z", "Z轴 / Z axis"),
            ('-X', "-X", "负X轴 / Negative X axis"),
            ('-Y', "-Y", "负Y轴 / Negative Y axis"),
            ('-Z', "-Z", "负Z轴 / Negative Z axis")
        ],
        default='Y'
    )
    
    custom_export_up_axis: EnumProperty(
        name="上向 / Up",
        description="导出的上向轴 / Up axis for export",
        items=[
            ('X', "X", "X轴 / X axis"),
            ('Y', "Y", "Y轴 / Y axis"),
            ('Z', "Z", "Z轴 / Z axis"),
            ('-X', "-X", "负X轴 / Negative X axis"),
            ('-Y', "-Y", "负Y轴 / Negative Y axis"),
            ('-Z', "-Z", "负Z轴 / Negative Z axis")
        ],
        default='Z'
    )
    
    # GLTF选项 / GLTF Options
    gltf_export_image_format: EnumProperty(
        name="打包图像 / Pack Images",
        description="GLTF导出的图像格式 / Image format for GLTF export",
        items=[
            ('AUTO', "自动 / Automatic", "自动图像格式 / Automatic image format"),
            ('JPEG', "JPEG", "JPEG格式 / JPEG format"),
            ('PNG', "PNG", "PNG格式 / PNG format"),
            ('NONE', "无 / None", "不打包图像 / No image packing")
        ],
        default='AUTO'
    )
    
    gltf_export_deform_bones_only: BoolProperty(
        name="仅变形骨骼 / Deform Bones Only",
        description="GLTF仅导出变形骨骼 / Export only deform bones for GLTF",
        default=True
    )
    
    gltf_export_custom_properties: BoolProperty(
        name="自定义属性 / Custom Properties",
        description="GLTF导出自定义属性 / Export custom properties for GLTF",
        default=False
    )
    
    gltf_export_tangents: BoolProperty(
        name="切线 / Tangents",
        description="GLTF导出切线 / Export tangents for GLTF",
        default=False
    )
    
    gltf_export_attributes: BoolProperty(
        name="属性 / Attributes",
        description="GLTF导出属性 / Export attributes for GLTF",
        default=False
    )
    
    # 自定义导出路径 / Custom Export Path
    custom_export_path: BoolProperty(
        name="自定义导出路径 / Custom Export Path",
        description="使用自定义导出路径 / Use custom export path",
        default=True
    )
    
    export_path: StringProperty(
        name="",
        description="导出的自定义路径 / Custom path for export",
        default="",
        subtype='DIR_PATH'
    )
    
    export_dir: StringProperty(
        name="导出目录 / Export Directory",
        description="文件导出的目录 / Directory where files were exported",
        default=""
    )
    
    # 调试模式 / Debug Mode (兼容性)
    # debug: BoolProperty(
    #     name="调试模式 / Debug Mode", 
    #     description="启用调试输出 / Enable debug output",
    #     default=False
    # )

# ReTex Properties
class ReTexSettings(bpy.types.PropertyGroup):
    """ReTex设置 / ReTex Settings"""
    
    # 替换前缀设置
    replace_prefix: BoolProperty(
        name="替换为'tex'前缀",
        description="将纹理名称的前缀替换为'tex'",
        default=True
    )
    
    # 分辨率预设
    resolution_preset: EnumProperty(
        items=[
            ('128', '128 x 128', ''),
            ('256', '256 x 256', ''),
            ('512', '512 x 512', ''),
            ('1024', '1024 x 1024', '')
        ],
        name="分辨率预设",
        description="纹理调整大小的预设分辨率",
        default='1024'
    )
    
    # ItemLand输入框
    item_land: StringProperty(
        name="ItemLand",
        description="智能对象重命名的前缀",
        default="land"
    )
    
    # 自定义体型存储
    custom_body_types: StringProperty(
        name="自定义体型",
        description="用户添加的自定义体型，以逗号分隔",
        default=""
    )
    
    # 动态生成体型选项
    def get_body_type_items(self, context):
        default_types = [
            ('man', '标准男性', '标准男性'),
            ('woman', '标准女性', '标准女性'),
            ('fatman', '胖男性', '胖男性'),
            ('fatwoman', '胖女性', '胖女性'),
            ('kid', '小孩', '小孩'),
            ('fishtail', '鱼尾人形', '鱼尾人形')
        ]
        custom_types_str = self.custom_body_types
        custom_types_list = []
        if custom_types_str:
            custom_types_list = [(t.strip(), t.strip().capitalize(), f'自定义: {t.strip()}') for t in custom_types_str.split(',') if t.strip()]
        return default_types + custom_types_list
    
    character_body_type: EnumProperty(
        name="体型",
        description="选择角色体型",
        items=get_body_type_items
    )
    
    character_serial_number: StringProperty(
        name="序号",
        description="输入角色序号",
        default="01"
    )
    
    character_suffix: StringProperty(
        name="后缀",
        description="添加角色后缀,为空则不添加",
        default=""
    )
    
    texture_suffix: StringProperty(
        name="贴图后缀",
        description="添加贴图后缀,为空则不添加",
        default=""
    )
    
    # 动物重命名属性
    animal_body_type: EnumProperty(
        name="动物体型",
        description="选择动物体型",
        items=[
            ('bird', '鸟类', '鸟类'),
            ('pigeon', '家禽', '鸽子'),
            ('cow', '牛羊马', '牛')
        ],
        default='bird'
    )
    
    # 翻译工具属性
    translate_input_text: StringProperty(
        name="输入文本",
        description="要翻译的中文文本",
        default=""
    )
    
    translate_output_text: StringProperty(
        name="输出文本",
        description="翻译后的英文文本",
        default=""
    )
    
    translate_source_lang: EnumProperty(
        name="源语言",
        description="选择源语言",
        items=[
            ('zh', '中文', '中文'),
            ('en', '英文', '英文'),
            ('ja', '日文', '日文'),
            ('ko', '韩文', '韩文')
        ],
        default='zh'
    )
    
    translate_target_lang: EnumProperty(
        name="目标语言",
        description="选择目标语言",
        items=[
            ('en', '英文', '英文'),
            ('zh', '中文', '中文'),
            ('ja', '日文', '日文'),
            ('ko', '韩文', '韩文')
        ],
        default='en'
    )
    
    animal_serial_number: StringProperty(
        name="动物序号",
        description="输入动物序号",
        default="01"
    )
    
    # 建筑重命名属性
    building_type: EnumProperty(
        name="建筑类型",
        description="选择建筑类型",
        items=[
            ('buildpart', '静态建筑', '静态建筑'),
            ('anibuild', '动画建筑', '动画建筑')
        ],
        default='buildpart'
    )
    
    building_island_name: StringProperty(
        name="海岛名",
        description="输入海岛名称",
        default=""
    )
    
    building_name: StringProperty(
        name="建筑名",
        description="输入建筑名称",
        default=""
    )
    
    # 移除序号选择，改为自动递增
    
    # UV检查相关属性
    uv_check_triggered: BoolProperty(
        name="UV检查已触发",
        description="标记UV检查是否已执行",
        default=False
    )
    
    uv_check_results: StringProperty(
        name="UV检查结果",
        description="存储UV检查的结果信息",
        default=""
    )

# OBJ Export Tools Properties
class ObjExportSettings(bpy.types.PropertyGroup):
    """OBJ导出工具设置 / OBJ Export Tools Settings"""
    
    # 导出路径
    obj_export_path: StringProperty(
        name="导出路径",
        description="OBJ文件导出路径",
        default="//exported_objs/",
        subtype="DIR_PATH"
    )
    
    # 缩放
    obj_export_scale: FloatProperty(
        name="缩放",
        description="导出时的缩放因子",
        default=1.0,
        min=0.001,
        max=1000.0,
        soft_min=0.01,
        soft_max=100.0
    )
    
    # 坐标系设置
    obj_export_coord_up: EnumProperty(
        name="上轴",
        description="导出网格的上轴",
        items=[
            ("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", ""),
            ("-X", "-X", ""), ("-Y", "-Y", ""), ("-Z", "-Z", "")
        ],
        default="Y"
    )
    
    obj_export_coord_forward: EnumProperty(
        name="前轴",
        description="导出网格的前轴",
        items=[
            ("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", ""),
            ("-X", "-X", ""), ("-Y", "-Y", ""), ("-Z", "-Z", "")
        ],
        default="-Z"
    )
    
    # 材质导出
    obj_export_materials: BoolProperty(
        name="导出材质",
        description="是否导出材质信息",
        default=False
    )
    
    # 三角化设置
    obj_export_triangulate: BoolProperty(
        name="三角化网格",
        description="导出前是否三角化网格",
        default=False
    )
    
    obj_export_tri_method: EnumProperty(
        name="三角化方法",
        description="三角化方法",
        items=[
            ('BEAUTY', '美观', '美观三角化'),
            ('CLIP', '裁剪', '裁剪三角化'),
            ('QUAD', '四边形', '四边形三角化'),
            ('FIXED', '固定', '固定三角化'),
            ('FIXED_ALTERNATE', '固定交替', '固定交替三角化'),
        ],
        default='BEAUTY'
    )
    
    obj_export_keep_normals: BoolProperty(
        name="保持法线",
        description="三角化时是否保持法线",
        default=True
    )
    
    # 坐标归零设置
    obj_export_zero_location: BoolProperty(
        name="导出前坐标归零",
        description="导出前将对象副本的坐标归零",
        default=True
    )

# Vertex Baker Properties
class VertexBakerSettings(bpy.types.PropertyGroup):
    """顶点烘焙设置 / Vertex Baker Settings"""
    
    # 目标网格对象
    target_mesh: PointerProperty(
        name="目标网格",
        description="选择要烘焙权重的目标网格对象",
        type=bpy.types.Object,
        poll=lambda self, obj: obj.type == 'MESH'
    )
    
    # 烘焙精度
    bake_precision: FloatProperty(
        name="烘焙精度",
        description="权重烘焙的精度设置",
        default=0.01,
        min=0.001,
        max=1.0
    )
    
    # 自动清理
    auto_cleanup: BoolProperty(
        name="自动清理",
        description="烘焙完成后自动清理临时对象",
        default=True
    )

# Main PopTools Properties
class PopToolsProperties(bpy.types.PropertyGroup):
    """PopTools主属性组 / PopTools Main Property Group"""
    
    # 导出工具设置
    export_tools_settings: PointerProperty(type=ExportToolsSettings)
    
    # ReTex设置
    retex_settings: PointerProperty(type=ReTexSettings)
    
    # OBJ导出工具设置
    obj_export_settings: PointerProperty(type=ObjExportSettings)
    
    # 顶点烘焙设置
    vertex_baker_settings: PointerProperty(type=VertexBakerSettings)
    
    # 翻译工具设置（在translation_tools.py中定义）
    # translation_tools: PointerProperty(type=TranslationToolsSettings)
    
    # 动作命名工具属性
    action_animation_type: StringProperty(
        name="动画类型",
        description="当前选择的动画类型",
        default=""
    )
    
    action_animation_name: StringProperty(
        name="动画名称",
        description="用户输入的动画名称",
        default=""
    )
    
    action_chinese_comment: StringProperty(
        name="中文备注",
        description="动作的中文备注，用于修改Ac_Settings.tags",
        default=""
    )
    
    # 海岛动画专用属性
    island_name: StringProperty(
        name="海岛名",
        description="海岛动画的海岛名称",
        default=""
    )
    
    # 动作命名工具说明显示控制
    show_action_naming_help: BoolProperty(
        name="显示说明",
        description="控制动作命名工具说明的显示/隐藏",
        default=False
    )
    
    # 纹理管理工具说明显示控制
    show_retex_help: BoolProperty(
        name="显示纹理管理工具说明",
        description="控制纹理管理工具智能重命名说明的显示/隐藏",
        default=False
    )
    
    # 四个重命名box的折叠状态控制
    show_island_rename_box: BoolProperty(
        name="显示海岛配方道具智能重命名",
        description="控制海岛配方道具智能重命名框的展开/收起",
        default=False
    )
    
    show_character_rename_box: BoolProperty(
        name="显示角色重命名",
        description="控制角色重命名框的展开/收起",
        default=False
    )
    
    show_animal_rename_box: BoolProperty(
        name="显示动物重命名",
        description="控制动物重命名框的展开/收起",
        default=False
    )
    
    show_building_rename_box: BoolProperty(
        name="显示建筑重命名",
        description="控制建筑重命名框的展开/收起",
        default=False
    )

# 注册的类列表
classes = [
    ExportToolsSettings,
    ReTexSettings,
    ObjExportSettings,
    VertexBakerSettings,
    # TranslationToolsSettings在translation_tools.py中注册
    PopToolsProperties,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)