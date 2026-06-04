# 学术论文审查失败诊断

> 未生成完整审查报告。关键审查能力失败，本次运行只生成失败诊断产物。

**文件**: `Test_paper2`
**产物类型**: failed
**完整审查报告已生成**: 否
**失败时间**: 2026-06-02 16:27:43

## 失败能力

- 能力: `text_llm`
- 错误类别: `provider_unavailable`
- 错误信息: 文本LLM预检请求失败: HTTPSConnectionPool(host='hub.oaifree.com', port=443): Max retries exceeded with url: /v1/chat/completions (Caused by NameResolutionError("HTTPSConnection(host='hub.oaifree.com', port=443): Failed to resolve 'hub.oaifree.com' ([Errno -2] Name or service not known)"))

## 已完成阶段

- init
- runtime_config_loaded
- stage1_text_extraction
- stage1_reference_audit
- stage1_resource_audit
- stage2_stat_check

## 修复建议

- 检查config.py或环境变量中的LLM_API_KEY、LLM_API_URL和LLM_MODEL。
- 确认文本语义审查LLM服务可访问，账号额度、模型名和网关状态正常。
- 修复配置或网络后使用下方命令重试。

## 重试命令

```bash
python paper_audit.py Test_paper2 --output Test_paper2/test_paper2_audit --mineru-model vlm --mineru-lang ch --max-chars 4096 --reference-timeout 10 --resource-timeout 10 --image-semantic-timeout 45 --image-detector-timeout 60 --llm-timeout 45 --llm-retries 1 --json --no-open
```

## 技术细节

```json
{
  "capability": "text_llm",
  "ok": false,
  "error_class": "provider_unavailable",
  "message": "文本LLM预检请求失败: HTTPSConnectionPool(host='hub.oaifree.com', port=443): Max retries exceeded with url: /v1/chat/completions (Caused by NameResolutionError(\"HTTPSConnection(host='hub.oaifree.com', port=443): Failed to resolve 'hub.oaifree.com' ([Errno -2] Name or service not known)\"))",
  "details": {
    "endpoint": "https://hub.oaifree.com/v1/chat/completions",
    "model": "mimo-v2.5-free"
  },
  "created_at": "2026-06-02 16:27:43"
}
```

## 已完成校检摘要

> 以下为失败前已经完成并写入 JSON 的正式校检结果；失败能力修复后应重新运行以生成完整报告。

## 🔗 代码仓库与在线资源可用性校检

**状态**: ok
**资源数量**: 0
**在线检测**: 启用（已检测 0 项）
> 校检论文声明的代码仓库、在线计算器、部署平台等资源是否可访问；URL格式错误会单独标记。

> 未识别到代码仓库或论文部署的在线资源链接。

## 📚 参考文献真实性/可核验性校检

**状态**: ok
**参考文献数量**: 0
**含 DOI 数量**: 0
**含年份数量**: 0
**在线检索**: 未启用
> 离线格式/可核验性校检：检查DOI、年份、来源字段等基本信息；不代表已联网验证引用真实存在。

> 未发现明显格式缺失；仍建议对关键引用进行数据库/DOI人工核验。
