# Skill 模板 _TEMPLATES/

复制对应模板到目标位置，重命名后填写。完整规范见上级目录的 `CONVENTIONS.md`。
**下划线前缀目录**：`register()` 不会把这里当真实 skill 加载。

## 选哪个模板（详见 CONVENTIONS.md 第2章决策树）

| 你的情况 | 用这个模板 | 复制到 |
|---|---|---|
| 逻辑可抽成纯函数、值得单测（命名/序号/碰撞/尺寸计算） | `template_core.py` + `template_pattern1_skill.py` | `core/<域>_core.py` + `agent_skills/<域>_skills.py` |
| 原 operator 只用 bpy.data + 名称赋值且弹 show_message_box | `template_pattern2_bpydata_skill.py` | `agent_skills/<域>_skills.py` |
| 必须调 bpy.ops 且依赖 viewport/选择集上下文 | `template_pattern2_ops_override_skill.py` | `agent_skills/<域>_skills.py` |

**范式1 是默认偏好**（可脱离 Blender 单测）。只有逻辑无法/不值得抽成纯函数时才用范式2。

## 测试模板

| 模板 | 用途 | 复制到 |
|---|---|---|
| `template_test_core.py` | 范式1 纯函数单测（importlib 按路径加载规避 import bpy） | `tests/test_<域>_core.py` |
| `template_test_wiring.py` | 新 skill 接线+metadata 文本静态检查 | `tests/test_<域>_skills_wiring.py` 或扩现有 |

两个测试模板开箱即跑（分别指向 `template_core.py` 和真实 `retex_skills.py`），证明拿来即用。改成真实目标时替换路径与 `NEW_SKILLS` 表。

## 接线（每次新增 skill 必做，CONVENTIONS.md 第10章）

改 `agent_skills/__init__.py` 两处：① import 行加新常量 ② `_ALL_SKILLS` 列表加新常量。`register()`/`unregister()` 自动生效。**改完重新启用插件**（热重载否则 handler 判 stale）。
