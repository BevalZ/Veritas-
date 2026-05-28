# ADR-0004: 规则定级、LLM 解释、版本化缓存与评估集

日期: 2026-05-28

## 状态

Accepted

## 背景

当前实现让分块 LLM 返回风险等级和分数，再由规则做部分合并和降级。随着 Adapter、缓存、报告模型和评估集引入，需要更可复现的风险定级机制。

项目还需要避免自动报告直接定性“造假/学术不端”。报告应输出可复核风险，而不是最终裁决。

## 决策

风险定级采用“规则定级，LLM 解释”:

- 分块 LLM 只抽取局部结构化发现，不直接决定最终风险等级。
- 全局合并阶段用规则引擎计算风险等级、证据风险分和加权明细。
- LLM 可以生成自然语言摘要、复核建议、PubPeer comment 和期刊 letter 草稿。
- LLM 不直接决定最终等级，避免模型漂移。

风险语言:

- 删除用户可见的“可疑黑产”等级。
- 用户可见等级为: 低风险、中风险、高风险、严重证据冲突。
- “打假得分”改为“证据风险分”。
- 保留 0-100 分数作为辅助排序指标，不表达造假概率。
- 报告不得直接确认造假、确认学术不端或断言作者动机。

LLM schema:

- 使用严格结构化 schema。
- 缺少必填字段时该分块失败并重试。
- 重试仍失败时不生成完整报告，生成失败诊断报告。
- raw response 必须保存，但 partial JSON 不能进入完整报告。

缓存与版本:

- run workspace 按每次运行隔离，保存所有原始响应和中间产物。
- shared cache 可跨运行复用高成本结果，但 key 必须包含输入指纹、Adapter 版本、模型、prompt 版本、schema 版本和风险规则版本。
- preflight 成功结果不跨 run 缓存。
- 每份报告记录 `PROMPT_VERSION`、`SCHEMA_VERSION`、`RISK_RULE_VERSION`、`ADAPTER_VERSION`。

评估集:

- 引入合成默认测试和真实公开论文可选 eval。
- 默认 eval 使用录制响应 replay。
- 手动 `record` 模式才真实联网调用第三方服务。
- 修改 prompt/schema/risk rules 后必须跑评估集或明确记录未跑原因。

## 后果

需要新增 `risk_rules.py` 或等价 Module，第一版规则固定在代码里并版本化，等有评估集后再考虑开放配置。

需要新增评估 fixture 与 replay/record 工作流。

## 2026-05-28 checkpoint update

Implementation review confirmed that report headers and HTML metadata now carry
prompt, schema, adapter, and risk-rule versions. The default evaluation path is
synthetic replay under `eval/cases/synthetic` and `eval/replay/synthetic`;
public-paper cases stay separate under `eval/cases/public` and require explicit
record mode.
