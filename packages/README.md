# PopTools 扩展仓库

这是PopTools插件的Blender扩展仓库，用于支持Blender 4.2+的扩展系统。

## 如何在Blender中添加此仓库

1. 打开 Blender → 偏好设置 → 获取扩展 → 仓库
2. 点击 "+" → 添加远程仓库
3. 设置URL为: `https://你的用户名.github.io/你的仓库名/index.json`
4. 启用"启动时检查更新"

## 包含的扩展

### PopTools - 游戏资产制作工具集 v3.1.1

专业的Blender游戏资产制作和导出工具集，支持多引擎导出和纹理管理。

- **类型**: 插件
- **最低Blender版本**: 4.2.0
- **许可证**: GPL-3.0-or-later

#### 功能特点

- 支持多种游戏引擎的资产导出（Unity、Unreal、Godot等）
- 优化的OBJ导出工具，修复轴向问题
- 批量纹理处理工具
- 顶点烘焙工具
- 更多...

## 仓库结构

```
./
├── index.json         # 扩展列表文件
├── index.html         # 网页界面
├── PopTools.zip       # PopTools扩展包
└── README.md          # 本文件
```

## 更新日志

### v3.1.1
- 修复OBJ导出轴向问题（"Y" "-Z"）
- 设置Unity专用为默认导出选项
- 优化Unity工作流导出体验

### v3.1.0
- 添加批量纹理处理功能
- 优化UI布局
- 修复多个bug

## 许可证

GPL-3.0-or-later