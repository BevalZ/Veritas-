# ADR-0003: 按审查能力定义 Adapter，部分服务商绑定

日期: 2026-05-28

## 状态

Accepted

## 背景

项目需要接入多类外部服务。部分能力必须绑定特定服务商，部分能力应保持可替换。当前实现直接使用全局配置和函数调用，导入 `paper_audit` 时还会自动搜索 `config.py` / `mykey.py`，导致配置、测试和运行环境耦合。

## 决策

Adapter 按审查能力定义，但保留两个服务商绑定:

- MinerU: 绑定服务商，作为文本提取能力默认实现。
- imagedetector: 绑定服务商，作为图像 AI 概率检测能力默认实现。
- 文本语义审查: 按能力定义，可替换 LLM Adapter。
- 参考文献在线核验: 按能力定义，可替换 scholarly lookup Adapter。
- 图像语义分析: 按能力定义，可替换多模态 LLM Adapter，不绑定 GLM。

配置系统改为单一、显式、可校验:

- 移除 `mykey.py` 自动搜索和导入期配置副作用。
- 启动时显式加载配置并在 preflight 前做 schema 校验。
- 配置按能力分组: MinerU、Text LLM、Reference Lookup、Image Semantic LLM、imagedetector。
- 测试使用 fake config 和 fake Adapter，不依赖开发者机器私有文件。

preflight 策略:

- 做真实轻量服务调用，而不只是检查配置存在。
- preflight 成功不跨运行长期缓存，只在本次运行内复用。
- preflight 结果写入 run workspace、诊断报告和日志。

## 后果

后续重构应先建立 Adapter Interface 和 fake Adapter，以支撑端到端测试。

配置错误、认证失败、网络失败、限流和服务异常需要结构化错误类型，供失败诊断报告展示。

