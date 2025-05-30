# PopTools 3.0 - 重构版本说明

## 概述 / Overview

PopTools 3.0 采用了全新的简化架构，参考了 ACT Game Asset Creation Toolset 的组织方式，将原本复杂的嵌套模块结构重构为扁平化的单文件模块结构。

## 新架构特点 / New Architecture Features

### 1. 扁平化结构 / Flat Structure
- 所有功能模块直接位于插件根目录
- 消除了复杂的子目录嵌套
- 每个模块职责单一，易于维护

### 2. 统一的属性管理 / Unified Property Management
- 所有属性集中在 `props.py` 中定义
- 通过 `PopToolsProperties` 主类统一管理
- 各模块通过 `context.scene.poptools` 访问属性

### 3. 集中化偏好设置 / Centralized Preferences
- 插件偏好设置统一在 `preferences.py` 中
- 支持各模块的启用/禁用控制
- 全局设置和UI定制选项

### 4. 共享工具函数 / Shared Utilities
- 通用功能集中在 `utils.py` 中
- 避免代码重复，提高维护性
- 包含消息显示、文件处理、对象操作等工具

## 文件结构 / File Structure

```
PopTools/
├── __init__.py              # 主入口文件，模块注册管理
├── props.py                 # 所有属性定义
├── preferences.py           # 插件偏好设置
├── utils.py                 # 共享工具函数
├── mesh_exporter.py         # 网格导出工具（原 easymesh_batch_exporter）
├── export_tools.py          # 多格式导出工具（原 export_fbx）
├── retex_tools.py           # 纹理管理工具（原 retex）
├── vertex_baker_tools.py    # 顶点烘焙工具（原 vertex_to_bone_baker）
├── modules/                 # 原始模块（保留作为参考）
└── README_new_structure.md  # 本说明文件
```

## 模块功能说明 / Module Functions

### 1. 网格导出器 (mesh_exporter.py)
- 批量网格导出功能
- LOD生成和优化
- 支持OBJ和GLTF格式
- 导出状态跟踪和指示器

### 2. 导出工具 (export_tools.py)
- 多格式导出支持（FBX/OBJ/GLTF）
- 游戏引擎预设（Unity/Unreal/Godot）
- 批量导出和路径管理
- 自定义导出参数

### 3. ReTex工具 (retex_tools.py)
- 智能对象重命名
- 纹理批量重命名
- 纹理大小调整
- 自定义体型管理

### 4. 顶点烘焙工具 (vertex_baker_tools.py)
- 顶点到骨骼的绑定
- 权重烘焙功能
- 空物体管理
- 自动化烘焙流程

## 使用方法 / Usage

### 安装 / Installation
1. 将整个 PopTools 文件夹复制到 Blender 插件目录
2. 在 Blender 偏好设置中启用 PopTools 插件
3. 在 3D 视图侧边栏找到 PopTools 面板

### 配置 / Configuration
1. 打开 Blender 偏好设置 > 插件 > PopTools
2. 根据需要启用/禁用各个工具模块
3. 配置全局设置如默认导出路径等

### 面板访问 / Panel Access
- 在 3D 视图中按 `N` 键打开侧边栏
- 找到 "PopTools" 标签页
- 各工具面板按功能分组显示

## 迁移说明 / Migration Notes

### 从旧版本升级 / Upgrading from Old Version
1. **备份设置**: 旧版本的设置可能不兼容，建议重新配置
2. **功能对应**: 所有原有功能都已保留，只是组织方式改变
3. **面板位置**: 面板仍在 3D 视图侧边栏的 PopTools 标签页中

### 属性访问变化 / Property Access Changes
- 旧版本: `context.scene.mesh_exporter_settings`
- 新版本: `context.scene.poptools.mesh_exporter_settings`

## 开发说明 / Development Notes

### 添加新功能 / Adding New Features
1. 在相应的模块文件中添加操作符和面板
2. 在 `props.py` 中添加必要的属性定义
3. 在 `preferences.py` 中添加启用/禁用选项（如需要）
4. 更新 `__init__.py` 中的模块列表

### 调试 / Debugging
- 启用 Blender 控制台查看详细的注册/注销信息
- 每个模块都有独立的错误处理
- 使用 `utils.show_message_box()` 显示用户友好的错误信息

## 优势 / Advantages

1. **简化维护**: 扁平化结构更易于理解和维护
2. **模块化设计**: 各功能模块独立，可单独启用/禁用
3. **统一管理**: 属性和偏好设置集中管理
4. **代码复用**: 共享工具函数避免重复代码
5. **易于扩展**: 新功能可轻松集成到现有架构中
6. **用户友好**: 清晰的面板组织和错误提示

## 技术细节 / Technical Details

### 注册机制 / Registration Mechanism
- 使用动态模块加载和注册
- 支持模块热重载（开发时）
- 错误隔离，单个模块失败不影响整体

### 属性系统 / Property System
- 基于 Blender 的 PropertyGroup 系统
- 支持类型检查和验证
- 自动UI生成和布局

### 错误处理 / Error Handling
- 统一的错误消息显示
- 详细的日志记录
- 优雅的降级处理

---

**注意**: 这是 PopTools 的重构版本，如果遇到问题，可以通过重命名 `__init___old.py` 为 `__init__.py` 来恢复到旧版本。

**Note**: This is a refactored version of PopTools. If you encounter issues, you can revert to the old version by renaming `__init___old.py` back to `__init__.py`.