# Third-Party-First Refactor Plan

日期: 2026-05-28

## 目标

把 Paper Audit / Veritas 从单脚本、混合本地兜底的审查工具，重构为第三方服务优先、关键能力 preflight、完整/范围受限/失败产物清晰区分的审查系统。

本计划受以下 ADR 约束:

- [ADR-0001: 第三方服务优先与关键服务阻断策略](adr/ADR-0001-third-party-first-critical-service-gating.md)
- [ADR-0002: 删除本地 LLM/OCR 正式审查路径](adr/ADR-0002-remove-local-llm-and-ocr-formal-paths.md)
- [ADR-0003: 按审查能力定义 Adapter，部分服务商绑定](adr/ADR-0003-adapter-capabilities-and-configuration.md)
- [ADR-0004: 规则定级、LLM 解释、版本化缓存与评估集](adr/ADR-0004-risk-rules-versioned-cache-and-evaluation.md)

## 非目标

- 不在第一阶段重新设计所有审查规则。
- 不把 MinerU 或 imagedetector 改成可替换服务商。
- 不保留本地 LLM/OCR 作为正式审查路径。
- 不把 LLM 输出 partial parse 纳入完整报告。
- 不直接定性“确认造假”或“确认学术不端”。

## 阶段 0: 用户可见语义对齐

目的: 先消除 README、CLI、报告术语和 ADR 的冲突。

改动:

- README 改为第三方服务优先。
- 删除 Ollama/本地 LLM 和本地 OCR 正式审查宣传。
- CLI help 说明关闭关键能力会生成 limited 或 failed 产物，不能生成完整报告。
- 报告展示名从“打假得分”改为“证据风险分”。
- 删除用户可见的“可疑黑产”风险等级，改为“严重证据冲突”。

验收:

- `python paper_audit.py --help` 中不再宣传本地正式审查路径。
- README 与 ADR-0001/0002/0004 不冲突。
- 报告模板中用户可见术语使用“证据风险分”。

## 阶段 1: 配置与 preflight

目的: 在运行前发现关键服务不可用，避免跑到中途才失败。

改动:

- 引入显式 `RuntimeConfig`。
- 移除导入期 `mykey.py` 自动兼容。
- 按能力分组配置: MinerU、Text LLM、Reference Lookup、Image Semantic LLM、imagedetector。
- 实现真实轻量 preflight。
- preflight 结果写入 run workspace。
- preflight 失败生成 `audit_report.failed.md/json`，必要时生成 HTML。

验收:

- 缺少 MinerU 配置时，不生成完整报告，只生成 failed 产物。
- 文本 LLM preflight 失败时，不进入分块审查。
- preflight 成功结果不跨 run 缓存。
- 测试使用 fake config，不依赖开发者本机私有文件。

## 阶段 2: 产物类型与 run workspace

目的: 区分完整报告、范围受限报告、失败诊断报告，并让每次运行可追溯。

改动:

- 每次运行创建独立 workspace，例如 `.paper_audit_runs/<run-id>/`。
- workspace 保存 preflight、input manifest、MinerU 产物、LLM raw response、参考文献结果、图片结果、报告和诊断。
- 根目录保留最新快捷副本:
  - `audit_report.audit.*`
  - `audit_report.limited.*`
  - `audit_report.failed.*`
- shared cache 只缓存高成本结果，cache key 包含输入指纹、Adapter 版本、模型、prompt 版本、schema 版本、risk rule 版本。

验收:

- 同一输入连续运行两次，产生两个不同 workspace。
- 根目录快捷报告指向最新结果。
- shared cache 命中时，本次 workspace 仍能追溯使用了哪些缓存。

## 阶段 3: Adapter Interface 和 fake Adapter 测试

目的: 先稳定测试 seam，再大规模移动代码。

改动:

- 定义 Adapter Interface:
  - MinerU Adapter
  - Text LLM Adapter
  - Reference Lookup Adapter
  - Image Semantic Adapter
  - imagedetector Adapter
- 真实 Adapter 包装现有函数。
- fake Adapter 支持成功、失败、限流、返回 schema 错误、部分内容不可检测等场景。

验收:

- 一个端到端测试用 fake Adapter 生成完整报告。
- LLM 分块失败测试生成 failed 产物。
- 输入含图片且 imagedetector fake 失败测试生成 failed 产物。
- 参考文献外部源整体失败测试生成 failed 产物。

## 阶段 4: Audit Run Module

目的: 把 `main()` 从业务流程中解耦。

改动:

- 新增 `RunRequest` 和 `RunResult`。
- 抽出 `Audit Run Module` 编排阶段:
  - preflight
  - input manifest
  - extraction
  - reference audit
  - image audit
  - LLM chunk audit
  - risk rules
  - rendering
- `paper_audit.py` 只保留薄 CLI 入口。

验收:

- CLI 调用和测试都通过 `RunRequest -> RunResult`。
- `main()` 不直接调用 MinerU/LLM/Reference/Image 具体实现。
- 每个失败路径返回结构化失败结果。

## 阶段 5: Evidence Model、严格 schema 和规则定级

目的: 让报告语义可复现，避免 dict 自由漂移。

改动:

- 定义 `AuditFinding`、`AuditReport`、`ReferenceAudit`、`ImageAudit`、`RunMeta`、`Coverage`。
- LLM 输出使用严格 schema。
- partial parse 不进入完整报告。
- 风险等级由规则引擎决定，LLM 只负责解释。
- 引入 `PROMPT_VERSION`、`SCHEMA_VERSION`、`RISK_RULE_VERSION`、`ADAPTER_VERSION`。

验收:

- schema 缺字段时，分块重试；重试失败生成 failed 产物。
- 风险等级输出只包含低风险/中风险/高风险/严重证据冲突。
- 报告记录版本信息。
- 测试覆盖 imagedetector 高分但无其他证据时不能单独升到最高风险。

## 阶段 6: 拆包和渲染分层

目的: 降低单文件复杂度，并隔离报告内容和视觉皮肤。

建议结构:

- `paper_audit.py`: 薄 CLI 入口。
- `paper_audit_app/config.py`
- `paper_audit_app/preflight.py`
- `paper_audit_app/run.py`
- `paper_audit_app/workspace.py`
- `paper_audit_app/input_project.py`
- `paper_audit_app/models.py`
- `paper_audit_app/risk_rules.py`
- `paper_audit_app/adapters/`
- `paper_audit_app/renderers/`

验收:

- `paper_audit.py --help` 仍可用。
- 旧命令入口不破坏。
- 渲染器只消费稳定模型，不直接修补上游 dict。

## 阶段 7: 评估集和 record/replay

目的: 让 prompt、schema 和规则变化可校准。

改动:

- 建立默认合成 evaluation cases。
- 建立真实公开论文可选 eval。
- 默认 eval 使用 replay。
- 手动 record 模式才真实联网调用第三方服务。

验收:

- 默认测试不联网。
- record 产物记录 Adapter、模型、prompt、schema、输入 hash。
- 修改 prompt/schema/risk rules 后，必须跑 eval 或记录未跑原因。

## 推荐实施顺序

1. 阶段 0: 用户可见语义对齐。
2. 阶段 1: 配置与 preflight。
3. 阶段 2: 产物类型与 run workspace。
4. 阶段 3: Adapter Interface 和 fake Adapter 测试。
5. 阶段 4: Audit Run Module。
6. 阶段 5: Evidence Model、严格 schema 和规则定级。
7. 阶段 6: 拆包和渲染分层。
8. 阶段 7: 评估集和 record/replay。

## 风险与回滚

- 风险: 一次性拆包过大导致 CLI 失效。
  - 缓解: 每阶段保持 `paper_audit.py --help` 和 fake Adapter e2e 测试通过。
- 风险: 第三方服务 preflight 增加运行耗时。
  - 缓解: 只做轻量真实调用，同 run 内复用结果。
- 风险: 完整报告阻断变严格后用户感觉失败率升高。
  - 缓解: failed 报告必须清楚给出修复和重试命令。
- 风险: 删除本地路径影响旧用户。
  - 缓解: 先在 CLI help 和 README 明确迁移；必要时保留诊断模式，不生成完整报告。

