# 学术论文审查失败诊断

> 未生成完整审查报告。关键审查能力失败，本次运行只生成失败诊断产物。

**文件**: `Test_paper2/2026-040896_稿件全文C.docx`
**产物类型**: failed
**完整审查报告已生成**: 否
**失败时间**: 2026-06-02 16:43:46

## 失败能力

- 能力: `input_extraction`
- 错误类别: `missing_optional_dependency`
- 错误信息: 读取 .docx 文件需要安装可选依赖 python-docx。

## 已完成阶段

- init
- runtime_config_loaded

## 修复建议

- 安装 python-docx 后重试。
- 或转换为 PDF 后重新运行审查。

## 重试命令

```bash
python paper_audit.py 'Test_paper2/2026-040896_稿件全文C.docx' --output Test_paper2/test_paper2_docx_direct --mineru-model vlm --mineru-lang ch --max-chars 4096 --reference-timeout 10 --resource-timeout 10 --image-semantic-timeout 45 --image-detector-timeout 60 --llm-timeout 45 --llm-retries 1 --json --no-open
```