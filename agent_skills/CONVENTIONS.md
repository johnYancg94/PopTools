# PopTools Skill 编写规范

本规范约束 `poptools/agent_skills/*.py` 下所有向 POPAgent 注册的 skill。
要把 PopTools operator 包装成 Agent 可调用的能力，先读本文。

**三件套关系**：本规范（讲为什么/怎么判断）→ `_TEMPLATES/`（照着填的代码骨架）→ wiring 测试（机器把关红线）。

**执行链路一句话**（权威来源 `POPAgent/agent_core/executor.py`）：
LLM 发起 call → executor 查 registry → `is_handler_valid` → `validate_arguments` → `ask_confirmation` → `run_on_main(handler, context=context, **args)` → **30s 超时** → 成功且 `undoable` 则 `bpy.ops.ed.undo_push`。

---

## 第1章 什么该做成 skill，什么不该

判定口诀：**去掉 UI 后还剩业务逻辑吗？剩下的逻辑 Agent 能用参数表达吗？** 两个都否 → 不做。

**黑名单（不要包）：**
- UI 开关：`toggle_*_box`、`*_popup`、`toggle_*_help`（只控制面板显隐）
- 写下拉 prop：`set_*_type`、`set_minigame_*`、`set_building_type`（只写 scene prop，对 Agent 无独立价值——应作为别的 skill 的参数）
- 纯 UI 反馈/overlay：`transform_axis_monitor`、`clear_polycount_overlay`、坐标轴 overlay
- 安装/偏好：`install_*_sdk`、`reset_hotkey`、`open_addon_preferences`、`restart_blender`

**可合并：** 一组 `set_x_type` + 一个 `do_x` 应合成单个带 `enum` 参数的 skill。例：十余个 `rt.*` 角色/动物/建筑/minigame 重命名 operator → 单个带 `category` enum 的 `poptools.rename_by_category`，而非 13 个 skill。合并同时缓解第4章的 token 膨胀。

---

## 第2章 范式判定决策树（核心）

```
这个 operator 要不要包？
├─ 在第1章黑名单 → 不包
└─ 不在 → 继续

副作用逻辑能否抽成"不 import bpy 的纯函数"？
（输入=对象的 duck-typing 视图 + 环境状态如 existing_names；输出=计划/结果 dataclass）
├─ 能，且逻辑值得测（命名规则/序号/碰撞/名称推导/尺寸计算）
│     → 范式1：core 纯函数 + handler 落地。【默认偏好】
└─ 不值得/无法抽（逻辑就是一串 bpy.data 赋值或 bpy.ops 调用）
      → 范式2，再分叉：原 operator 怎么实现的？
      ├─ 只用 bpy.data + 名称赋值，且内部弹 show_message_box
      │     → handler 复刻 bpy.data 逻辑，不调 bpy.ops.rt.*（避开弹窗）
      │        参照 organize_materials / mark_high_low
      ├─ 调 bpy.ops 且不需要 viewport 上下文（如直接写 obj.location）
      │     → handler 直接调 bpy.ops
      └─ 调 bpy.ops 且需要 viewport/选择集上下文（transform_apply、origin_set）
            → 用 temp_override，参照 blender_transform._override_with_objects
```

**范式1 是默认偏好**：可单测、可脱离 Blender 跑 CI。
- 范式1 产出：core 函数 + handler + 纯函数单测 + skill dict
- 范式2 产出：handler + skill dict +（尽量）逻辑级测试或手测步骤

---

## 第3章 命名

- name 格式 `poptools.<action>` 或 `poptools.<domain>_<action>`，全小写 snake，动宾。
- owner 一律 `"poptools"`（`unregister_namespace("poptools")` 的清理依据，不能改）。
- domain 建议词表：`export` / `naming` / `texture` / `bake` / `translate` / `rig`。
- **撞名红线**：`skill_registry.get_skill_by_name` 只按 name 匹配、**忽略 owner**，按注册顺序取首个命中。所以 poptools 的 action 名不能与 builtin 的 `blender.*`/`agent.*` 末段或彼此重复。**起名前全局搜一遍现有 name。**
- providers 把 name 里的 `.` 转成 `__` 作为传给 LLM 的 wire name（debug 时会看到，作者不用管）。

---

## 第4章 参数 schema 约束

校验器 `POPAgent/agent_core/schema_validation.py` **故意只支持子集**：

**支持：** 顶层 `type:object`、`required`、property 的 `type`（含类型数组如 `["string","null"]`）、`enum`。number/integer 校验**排除 bool**。

**不支持（写了静默忽略，必须 handler 自己兜）：** `minimum`/`maximum`/`minLength`/`maxLength`/`pattern`、array 的 `items` 子类型、`default`。
> 反面教材：现有 `preview_generic_names` 写了 `"minimum": 1`，但完全不生效。

**规避建议：**
| 需求 | 做法 |
|---|---|
| 范围约束（count≥1） | handler 内 clamp + description 写明 |
| 枚举 | 用 `enum`（被支持，优先用） |
| array 元素类型 | handler 手工校验，参照 `blender_transform._as_vec3` 的 `[float(v) for v in value]` |
| 不在 schema 内的参数 | 要么进 schema，要么 handler 给默认值兜 |

**铁律：所有 handler 形参都要有默认值**（executor 用 `**call.arguments` 展开，缺参靠默认值兜）。`required` 只用于"缺了就没法干活"的参数。

---

## 第5章 metadata 标注矩阵

按操作类型对号入座（5 字段）：

| 操作类型 | modifies_scene | writes_files | launches_external | undoable | requires_confirmation |
|---|---|---|---|---|---|
| 只读/诊断（check_uvs、polycount、find_missing） | False | False | False | False | **never** |
| 纯计算/预览（preview_names、build_texture_name） | False | False | False | False | never |
| 改场景可撤销（rename、organize_materials、mark、transform、annotations） | True | False | False | **True** | first |
| 破坏但可撤销（清材质槽等，能 Ctrl+Z 恢复） | True | False | False | True | **first** |
| 不可逆（写盘/删文件/启外部进程） | 视情况 | 视情况 | 视情况 | **False** | **always** |
| 写文件（export_*、unpack_textures、secure_textures） | 视情况 | **True** | False | False | **always** |
| 启外部进程（marmoset one_click_bake） | 视情况 | True | **True** | False | always |
| undo/redo 本身 | True | False | False | **False（红线）** | never/first |

**确认级判据（按可逆性，不按"是否破坏"）：** 能 Ctrl+Z 完全恢复(undoable=True) → `first`；不可逆(写盘/删文件/外部进程) → `always`。据此 `organize_materials` 清材质槽虽破坏但可撤销，维持 `first`。

**逐条为什么：**
- `undoable=True` 时 executor 成功后自动 `undo_push`，所以 **handler 内绝不能再自己 push undo**（否则双推）。
- **undo/redo 类必须 undoable=False**：否则 executor 在撤销后立刻推一个新 undo step，腐坏栈。
- 写文件必须 `writes_files=True` + `requires_confirmation="always"`（wiring 红线）。
- 删除/不可逆类必须 `requires_confirmation="always"`（wiring 红线）。
- 只读类必须 `modifies_scene=False` + `writes_files=False` + `requires_confirmation="never"`（wiring 红线）。

**注：** metadata 的 `requires_confirmation` 只是默认值，可被用户 prefs/runtime override 覆盖（`get_permission_level`）。但你仍须按矩阵标对默认值。

**写文件路径参数命名：** 确认框 `confirm_dialog._build_risk_lines` 只认 `path`/`output_path`/`filepath` 三个键来显示目标路径。写文件类 skill 的路径参数**优先命名 `output_path` 或 `filepath`**。沿用历史名（如 `export_path`）会导致确认框显示"(参数中)"而非真实路径——需在 PR 注明并记入遗留。

---

## 第6章 错误返回约定

- **成功：** 返回 dict，executor `_make_ok` 补 `ok=True`；建议总是显式带 `ok` 和人类可读 `message`。
- **失败：** 返回 `{"ok": False, "error_kind": <稳定标识>, "error": <人类可读说明>}`。**返回 `ok=False` 必须同时带 `error_kind`**（executor 不会替你补）。
- **抛异常：** 被 executor 兜成 `{"error_kind":"handler_exception"}`，**信息丢失**。可预期的错误要自己 try/except 转结构化 error_kind。

**error_kind 命名规约：** 小写 snake、稳定（上层可能据此分支）、英文。词表：
- 输入类：`no_selection`、`no_active`、`invalid_arguments`、`missing_<param>`（如 `missing_item_land`）
- 资源类：`not_found`、`file_exists`、`path_not_writable`、`missing_textures`
- 执行类：`<domain>_failed`（如 `export_failed`、`organize_failed`、`bake_failed`）
- 环境类：`marmoset_not_found`、`dependency_missing`（`timeout`/`handler_exception` 由 executor 占用，handler 别用）

`error`/`message` 文案面向人，**可中文**；`error_kind` 永远英文 snake。

---

## 第7章 handler 编写铁律

逐条（正例见 `retex_skills.py`、模板见 `_TEMPLATES/`）：

1. **context 兜底**：必须 `def _handler_x(context=None, ...)`，函数体首行 `if context is None: context = bpy.context`（executor 总传 context，但纯函数单测会传 fake）。
2. **禁止 run_on_main**（wiring 红线）：handler 已在主线程，直接 `bpy.ops`/`bpy.data`。
3. **no_selection 提前返回**：读 `context.selected_objects`/`active_object` 后立刻判空返回结构化错误，别让后面 bpy 调用炸成 `handler_exception`。
4. **异常转 error_kind**：可预期失败 try/except 包住转 `<domain>_failed`。
5. **所有形参带默认值**（见第4章）。
6. **prop 仅作 fallback**：优先用参数；scene prop 只在参数缺省时兜底（参照 `smart_rename` 先用 `item_land` 参数、空了才读 `retex_settings.item_land`）。
7. **返回可 JSON 序列化数据**：返回对象名字符串列表，别返回 bpy 对象（会进 confirm_dialog 的 `json.dumps` 和上层消息）。

---

## 第8章 description 写法

- **语言：英文。** description 直接进 LLM 的 tool schema/system prompt，英文 token 更省、工具调用更稳。**中文只出现在面向用户的 `message`/`error` 文案里。** 现有 12 个 skill 全英文，不要破坏一致性。
- **三段式：** ①一句话功能 ②前置条件（"Requires objects to be selected first."）③返回内容/关键参数语义。
- **写清会改什么/不改什么：** "Read-only inspection; does not modify anything." / "Destructive — existing material assignments are removed."
- **写清近义 skill 取舍**（参照 `preview_generic_names` 点名"想真改用 apply_generic_naming"），降低 LLM 选错。
- **长度克制：** 2-4 句（进 token 预算，见第4章风险）。

---

## 第9章 core 纯函数层约定

- 文件位置 `poptools/core/<域>_core.py`，**绝不 import bpy**，绝不读 `context.scene.*`。
- 环境状态作参数传入（`existing_names`、`objects` 列表、`item_land`）。
- 返回 `@dataclass XxxResult`：固定带 `ok: bool`、`message: str`，按需加业务字段、`error: str`、`error_kind: str`（参照 `SmartRenameResult`/`UVCheckResult`）。
- 用 `getattr(obj, "attr", None)` 支持 duck-typing（让单测能塞 fake 对象）。
- **规划与落地分离：** 纯函数只"算计划"（如 `build_smart_rename` 返回 renamed 列表但不改名），handler 才执行 `obj.name = ...`。

---

## 第10章 注册接线步骤

1. 在对应 `<域>_skills.py` 定义 handler + skill dict 常量（字段固定顺序：name / description / parameters / owner / handler / metadata）。
2. 改 `agent_skills/__init__.py` **两处**：① import 行加入新常量 ② `_ALL_SKILLS` 列表加入。
3. `register()` 遍历 `_ALL_SKILLS`、`unregister()` 按 `_OWNER_PREFIX="poptools"` 清，**无需改**。
4. **改完重新启用插件**：`is_handler_valid` 按 handler 所在模块是否仍在 sys.modules 判，热重载后旧模块对象被替换会判 stale（返回 `handler_stale`）。

---

## 第11章 测试要求

- **范式1 必须有纯函数单测**：用 `importlib.util.spec_from_file_location` 按路径加载 core 文件，**先 `sys.modules[spec.name]=mod` 再 `exec_module`**（否则 `from __future__ import annotations` 下 dataclass 注解解析失败）。覆盖：正常、边界、碰撞、空输入、未知输入。模板 `_TEMPLATES/template_test_core.py`。
- **每个新 skill 必须进 wiring 测试**：在 `test_<域>_skills_wiring.py` 的 `NEW_SKILLS` 表登记 `skill_name` + `readonly`，自动校验：在 __init__ 出现、name/owner 正确、metadata 与操作类型自洽、name 互不重复。模板 `_TEMPLATES/template_test_wiring.py`。
- wiring 测试是**纯文本正则检查**（skill 模块 import bpy，无 Blender 环境跑不了 import），能在 CI 跑。
- **范式2 覆盖策略（自动测接线、手测测效果）：** ①能抽的算法尽量下沉 core 走范式1；②真范式2 的，wiring 测"接线+metadata 自洽"；③副作用正确性靠 PR 内手测步骤 + 可选的 Blender 内 MCP 冒烟测试（不进常规 CI）。

---

## 第12章 PR 前 Checklist

- [ ] 不在第1章黑名单；同类 set/toggle 已合并而非拆分
- [ ] name 全局唯一（搜过 builtin + poptools），owner="poptools"
- [ ] 所有 handler 形参带默认值；handler 有 `context=None` 兜底
- [ ] handler 无 run_on_main；可预期错误已转 error_kind
- [ ] metadata 五字段对照矩阵无误；undo/redo→undoable=False；写文件→writes_files+always；不可逆→always；只读→三连 never
- [ ] 写文件路径参数命名为 output_path/filepath（或已记遗留）
- [ ] description 英文、三段式、标注是否改场景
- [ ] schema 只用支持子集；范围/长度约束已在 handler 兜
- [ ] 返回 ok=False 时带 error_kind
- [ ] 范式1 有 core 纯函数单测；新 skill 已登记 wiring 测试
- [ ] __init__.py 两处都改了
- [ ] 本地跑过 `test_<域>_core.py` 与 `test_<域>_skills_wiring.py`

---

## 附：落地路线图

剩余 ~40 个有效 operator（原 70+ 扣黑名单 ~20、已完成 12）分 4 批。原则：**先高频刚需且复用现有 core，后破坏性/外部依赖，遗留硬约束垫底。**

**P1 命名与纹理收尾**（高频、低风险、复用现有 core）
- `poptools.rename_by_category`（范式1，合并十余个 `rt.*` 角色/动物/建筑/minigame 重命名为单个 `category` enum skill——**最大合并收益**）
- `set_texname_of_object`（范式1，复用 retex_naming）、`sync_texture_names`（范式2 bpy.data）
- `adjust_serial_number`（范式1，纯计算序号±）、动作序号±

**P2 翻译与导出补全**（中风险）
- `translate_text`（范式1，本地翻译）、`export_obj_batch`（范式2，写文件→always）、`open_export_dir`（范式2，launches_external）
- AI 翻译标注网络延迟可能逼近 30s。`batch_translate_objects` **暂缓**（props 遗留）。

**P3 Marmoset 非阻塞部分**（中高风险）
- `auto_mark_high_low`（范式2）、`show_polycount`（范式1，只读 never）、`find_missing_textures`（只读 never）
- `generate_lowpoly`（范式2，破坏性，可能慢）、`secure_texture_resources`（范式2，写文件→always）、`auto_detect_toolbag`（只读探测）
- `one_click_bake` **不做**（30s 超时遗留）。

**P4 顶点烘焙/绑定**（低频、需上下文，最后做）
- `VTBB_OT_*` 系列（create_empties/bind/bake_weights/clear），多需 temp_override，最难单测。

**遗留事项（本期只标不解）：**
1. **30s 超时 → 异步化**：影响 `one_click_bake`、AI 翻译、lowpoly。需改 executor `future.result(timeout=30)`，属 POPAgent 核心改动。
2. **翻译 props 未挂载**：`batch_translate_objects` 依赖未注册的 scene prop，需先修 props 注册。
3. **确认框路径键**：`export_*` 用 `export_path` 不在 `_build_risk_lines` 白名单。新 skill 改用 `output_path`，或扩 POPAgent 侧键表。
