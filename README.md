# 📄 Paper Audit - 耿同学版学术论文自动审查工具

> 开箱即用的学术造假检测工具，融合3大开源项目思路 + MinerU OCR + LLM语义分析，一键生成专业审查报告。

<div align="center">
<img src="https://img.shields.io/badge/python-3.10+-blue.svg">
<img src="https://img.shields.io/badge/license-MIT-green.svg">
<img src="https://img.shields.io/badge/API-MinerU/Mimo-orange.svg">
</div>

---

## ✨ 核心特性
### 🎯 检测体系（耿同学标准）
融合3大开源项目的核心检测逻辑：
- ✅ [wooly99/geng-academic-fraud-detector](https://github.com/wooly99/geng-academic-fraud-detector) 耿同学六式检测
- ✅ [NeoSpecies/AcademicIntegrityHunter](https://github.com/NeoSpecies/AcademicIntegrityHunter) 本地统计算法（Benford分布校验、p值异常检测、数字自洽性分析）
- ✅ [jingshouyan/academic-integrity-geng](https://github.com/jingshouyan/academic-integrity-geng) 五维审查体系

### 🔧 技术特性
- 📝 **MinerU PDF解析**：支持原生PDF/扫描件/图片PDF转Markdown，保留表格、公式、图片标注
- 📚 **长论文冗余审查**：智能分块（8000字符/块+1000字符重叠）+ 多块结果合并，无信息丢失
- ⚡ **双引擎检测**：本地统计检测（无API调用）+ LLM语义分析（Mimo模型）
- 📊 **结构化输出**：美观的Markdown报告 + 原始JSON结果导出
- 🔒 **隐私友好**：本地文件可选免Token的MinerU Agent API，无需上传到第三方训练集

---

## 🚀 快速开始
### 1. 安装依赖
```bash
# 仅标准库，无额外依赖！
python >= 3.10
```

### 2. 配置API Key
本工具支持所有**OpenAI兼容LLM**（OpenAI/DeepSeek/通义千问/豆包/Ollama本地部署等），采用外部配置文件避免泄露密钥：
```bash
# 复制配置模板
cp config.example.py config.py
```
编辑`config.py`填写你的配置：
#### LLM配置（必填，支持所有OpenAI兼容API）
```python
# 示例1: OpenAI官方
LLM_API_KEY = "sk-xxxxxx"
LLM_API_URL = "https://api.openai.com/v1/chat/completions"
LLM_MODEL = "gpt-3.5-turbo"

# 示例2: DeepSeek
# LLM_API_KEY = "sk-xxxxxx"
# LLM_API_URL = "https://api.deepseek.com/v1/chat/completions"
# LLM_MODEL = "deepseek-chat"

# 示例3: 本地Ollama（完全离线）
# LLM_API_KEY = "ollama"
# LLM_API_URL = "http://localhost:11434/v1/chat/completions"
# LLM_MODEL = "qwen2:7b"
```
#### MinerU配置（可选）
- 小文件（≤10MB/≤20页）：无需配置，自动使用内置免Token的Agent API
- 大文件（>10MB/>20页）：到[MinerU官网](https://mineru.net/apiManage/docs)获取Token填写即可
```python
MINERU_TOKEN = "你的MinerU Token（可选）"
```

### 3. 运行检测
```bash
# 推荐：MinerU解析 + 完整检测
python paper_audit.py your_paper.pdf --mineru

# 仅原始PDF文本提取 + 检测
python paper_audit.py your_paper.pdf

# 自定义输出
python paper_audit.py your_paper.pdf --mineru -o report.md --json
```

---

## 📖 完整用法
```
usage: paper_audit.py [-h] [--mineru]
                      [--mineru-model {pipeline,vlm,MinerU-HTML}]
                      [--mineru-lang MINERU_LANG] [--no-mineru]
                      [--max-chars MAX_CHARS] [--output OUTPUT] [--json]
                      pdf_path

positional arguments:
  pdf_path              待审查的PDF文件路径

options:
  -h, --help            show this help message and exit
  --mineru              使用MinerU API将PDF转为Markdown再审查（推荐，质量更高）
  --mineru-model        MinerU模型版本（默认vlm，仅Precision API生效）
  --mineru-lang         MinerU OCR语言（默认ch=中英，en=英文，japan=日文）
  --no-mineru           强制使用原始PDF文本提取，禁用MinerU
  --max-chars           单块最大字符数（默认8000）
  --output, -o          输出报告文件路径（默认输出到同目录）
  --json                同时保存原始JSON结果
```

---

## 📊 报告示例
```
# 📄 学术论文审查报告 [耿同学标准]
**文件**: `test_paper.pdf`
**文件大小**: 3.2 MB
**提取字符数**: 23456
**提取方式**: MinerU VLM
**审查方式**: 分块审查 | 3块 | 单块上限8000字符 | 重叠1000字符
**审查时间**: 2026-05-22 15:30:00

## 📊 本地统计检测结果
| 检测项 | 结果 | 状态 |
|--------|------|------|
| Benford分布偏差 | 0.123 | ✅正常 |
| p值数量/异常 | 12 / 2个>0.05 | ⚠️异常 |
| 标准差提及 | 4处 | N/A |
| 提取数字数 | 234 | - |

## 总评: 存在多处统计异常，判定为中风险
**风险等级**: 🟡 中
**打假得分**: 72 (越高越可疑)

## 🔍 逐项检查
| # | 分类 | 检查项 | 判定 |
|---|------|--------|------|
| 1 | 数据与结果 | p值未做多重比较校正 | 🚩红旗 |
| 2 | 图片与图表 | Figure 2与Figure 3背景高度相似 | ⚠️疑点 |
| 3 | 方法论 | 样本量n=12不足以支撑统计结论 | 🚩红旗 |
```

---

## 🧠 工作原理
```mermaid
graph TD
A[输入PDF] --> B{MinerU解析?}
B -->|是| C[MinerU API转Markdown]
B -->|否| D[本地PDF文本提取]
C --> E[全文文本]
D --> E
E --> F[本地统计检测]
F --> G[智能分块(8000字符/块 + 1000重叠)]
G --> H[逐块LLM语义审查]
H --> I[多块结果合并(去重+风险升级)]
I --> J[输出Markdown报告 + JSON结果]
```

---

## 🙏 鸣谢
本项目检测体系融合参考以下优秀开源项目：
- [wooly99/geng-academic-fraud-detector](https://github.com/wooly99/geng-academic-fraud-detector) - 耿同学六式检测框架
- [Neospecies/AcademicIntegrityHunter](https://github.com/Neospecies/AcademicIntegrityHunter) - 本地统计检测算法
- [jingshouyan/academic-integrity-geng](https://github.com/jingshouyan/academic-integrity-geng) - 五维审查体系

---

## ⚠️ 免责声明
本工具仅供学术研究使用，所有检测结果仅为参考，不构成任何学术不端的判定依据。请严格遵守相关法律法规和学术规范，禁止将本工具用于任何非法用途。

---

## 🤝 贡献
欢迎提交Issue和PR！参考方向：
- 增加本地LLM支持
- 更多统计检测维度
- 批量检测功能
- 图形界面开发

---

## 📄 许可证
MIT License
