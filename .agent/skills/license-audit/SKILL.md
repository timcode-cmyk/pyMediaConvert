---
name: license-audit
description: 依赖协议合规检查 — 当依赖文件变更时自动检查协议合规性
triggers:
  - file_changed: "package.json"
  - file_changed: "go.mod"
  - file_changed: "requirements.txt"
  - file_changed: "pyproject.toml"
  - file_changed: "Cargo.toml"
  - file_changed: "*.csproj"
---

# 依赖协议审计 Skill

## 何时使用

当用户修改了依赖文件（package.json、go.mod、requirements.txt、pyproject.toml、Cargo.toml、*.csproj）时自动触发。

## 不要使用

当用户只是阅读或查看依赖文件而没有修改时，不要触发本 Skill。

## 执行步骤

### 1. 检测变更的依赖

对比当前依赖文件与项目根目录的 `LICENSE.LIST` 中已记录的依赖，找出：
- **新增的依赖**：在依赖文件中存在但 LICENSE.LIST 中没有的
- **版本变更的依赖**：版本号发生变化的
- **移除的依赖**：在 LICENSE.LIST 中存在但依赖文件中已删除的

### 2. 查询新增/变更依赖的协议

对新增或版本变更的依赖，使用 WebSearch 查询其协议：
- npm 包：搜索 `<包名> npm package license`
- Go 模块：搜索 `<模块路径> go module license`
- Python 包：搜索 `<包名> pypi license`
- Rust 包：搜索 `<包名> crates.io license`
- .NET 包：搜索 `<包名> nuget license`

如果搜索结果不明确，二次搜索：`<包名> github LICENSE file`
无法确定的标记为 UNKNOWN。

### 3. 检查协议兼容性

对新增或版本变更的依赖，检查其协议与项目协议的兼容性：
- 读取项目根目录的 LICENSE 文件，识别项目协议的 SPDX 标识符
- 对照协议兼容性矩阵（参见 https://tpscsm-docs.pages.dev/license-audit/），判定兼容性
- 不兼容时警告用户并给出修复建议

### 4. 更新 LICENSE.LIST

- 添加新增依赖的协议信息
- 更新版本变更的依赖信息
- 移除已删除的依赖条目
- 更新统计摘要

### 5. 更新 LICENSE

- 重新分析协议兼容性
- 更新继承限制部分
- 更新第三方协议声明

### 6. 通知用户

完成后通知用户变更结果：

> 依赖协议检查完成：
> - 新增 X 个依赖，协议均为 [协议列表]
> - 更新 X 个依赖版本
> - 移除 X 个依赖
> - 兼容性检查：✅ 所有新增依赖与项目协议兼容 / ❌ 以下依赖与项目协议不兼容：[列表]
> - 风险提示：[如有新增风险协议则列出]

## 风险分类

- ✅ 低风险：MIT、BSD、ISC、Apache-2.0、Unlicense、CC0-1.0
- ⚠️ 需关注：GPL、AGPL、LGPL、MPL、BSL、SSPL
- ❌ 需确认：UNKNOWN、CC-BY-NC、自定义协议

## 重要说明

- 只检查直接依赖，不检查传递依赖
- UNKNOWN 协议需要用户手动确认
- 完整参考表：https://tpscsm-docs.pages.dev/license-audit/
