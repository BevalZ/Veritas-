# 📄 Paper Audit - 耿同学版学术论文自动审查工具

> 面向公开发表文献的第三方增强审查工具，融合 MinerU OCR、在线文献核验、图像检测与 LLM 语义分析，一键生成可复核的专业审查报告。

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
- 📁 **目录级综合审查**：传入论文目录，自动识别PDF/Word/Excel/补充材料/原始数据，跨文件交叉验证
- 📝 **MinerU PDF解析**：公开文献审查默认使用 MinerU 将原生PDF/扫描件/图片PDF转Markdown，保留表格、公式、图片标注
- 📚 **参考文献在线核验**：DOI优先，联合Crossref/OpenAlex/PubMed检索引用真实性与题名/年份一致性
- 🖼️ **图像多路审查**：收集MinerU提取图片，执行轻量合理性筛查、图像语义分析，并自动调用 imagedetector.com 子工具记录AI概率
- 📚 **长论文冗余审查**：智能分块（默认4096字符/块+512字符重叠）+ 多块结果合并，并标注LLM覆盖率
- ⚡ **第三方增强 + 轻量统计**：MinerU/LLM/在线核验/图像检测为正式审查主路径，本地统计检测作为轻量线索
- 📊 **结构化输出**：Claude风格HTML报告 + Markdown报告 + 原始JSON结果导出 + 图像AI复核清单
- 🌐 **HTML联动操作**：报告生成后默认自动打开HTML，并自动启动本机动作服务；可在报告中一键生成 PubPeer Comment 或期刊 Letter 草稿
- 🧠 **社区驱动知识库**：内置12+种从PubPeer典型案例汇总的造假检测模式，支持社区贡献自动更新

---

## 🚀 快速开始
### 1. 安装依赖
```bash
pip install -r requirements.txt
```

<details>
<summary>📋 依赖详情</summary>

| 依赖 | 用途 | 必需 |
|------|------|------|
| Python ≥ 3.10 | 运行环境 | ✅ 必需 |
| python-docx ≥ 0.8.11 | 读取Word文档(.docx) | 📁 目录审查时需要 |
| openpyxl ≥ 3.1.0 | 读取Excel表格(.xlsx/.xlsm) | 📁 目录审查时需要 |
| lxml ≥ 4.9.0 | python-docx的XML解析依赖 | 📁 目录审查时需要 |
| requests ≥ 2.28.0 | LLM/MinerU/文献数据库/图像语义分析请求 | ✅ 必需 |
| pymupdf ≥ 1.24.0 | PDF内嵌图片提取 | 🖼️ 图像检测需要 |
| pillow ≥ 10.0.0 | 图片尺寸、空白、噪声和图像语义分析前压缩预处理 | 🖼️ 图像检测需要 |

> 💡 建议直接使用 `pip install -r requirements.txt`，以启用文献在线检索、图像检测和多格式目录审查的完整流程。

</details>

### 2. 配置API Key
本工具支持所有**OpenAI兼容LLM**（OpenAI/DeepSeek/通义千问/豆包等第三方或托管模型），采用外部配置文件避免泄露密钥：
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

```
#### MinerU配置（正式审查必填）
正式审查默认依赖 MinerU。到[MinerU官网](https://mineru.net/apiManage/docs)获取Token填写：
```python
MINERU_TOKEN = "你的MinerU Token"
```
#### 图像语义分析配置
用于对MinerU/PDF提取出的图片做语义理解。可填写任意 OpenAI-compatible 多模态模型；下面只是一个模型示例。密钥只放在本地 `config.py` 或环境变量 `IMAGE_SEMANTIC_API_KEY`，不要写入报告或提交仓库。
```python
IMAGE_SEMANTIC_API_KEY = "你的图像语义分析 API Key"
IMAGE_SEMANTIC_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
IMAGE_SEMANTIC_MODEL = "your-multimodal-model"
```

### 3. 运行检测
```bash
# 🆕 新功能：审查整个论文项目目录（自动识别主论文/补充材料/原始数据/表格，跨文件交叉验证）
python paper_audit.py ./my_paper_project/

# 推荐：单个PDF文件MinerU解析 + 完整检测
python paper_audit.py your_paper.pdf

# 自定义输出
python paper_audit.py your_paper.pdf -o report.md --json

# 断点续跑：默认启用。失败后直接重跑同一命令，会复用文本提取、参考文献、LLM分块和图片检测缓存
python paper_audit.py ./my_paper_project/ -o full_risk_from_scratch --json

# 从头重跑：清空该输入的断点缓存后重新执行
python paper_audit.py ./my_paper_project/ -o full_risk_from_scratch --json --fresh

# CI/服务器/批处理：生成报告但不打开浏览器，也不自动启动HTML动作服务
python paper_audit.py ./my_paper_project/ -o full_risk_from_scratch --json --no-open

# 调试/范围受限：控制在线文献核验数量（产物不应视为完整审查）
python paper_audit.py ./my_paper_project/ --reference-online-limit 80

# 调试/范围受限：提高图片语义理解与AI概率自动检测数量上限
python paper_audit.py ./my_paper_project/ --image-semantic-limit 20 --image-detector-limit 20

# 更新欺诈模式知识库（从PubPeer评论/造假案例文本中提取新检测模式）
python paper_audit.py --update-patterns pubpeer_comments.txt
```

图像语义分析断点续跑：
- 默认启用断点续跑；不要加 `--no-resume`。
- 每完成一张图片的图像语义分析，都会立即写入断点缓存，避免中断后重跑已完成图片。
- 可见缓存文件会写到输出目录：`image_semantic_cache.json`；隐藏断点缓存仍保留在 `.输入名.paper_audit_resume/image_semantic_cache.json`。
- 如果要强制重跑全部图片语义分析，使用 `--fresh` 清空断点缓存。

### 4. HTML报告与后续草稿生成
正常审查完成后会写入正式产物目录：
- `*.audit.md` / `*.audit.html`：完整审查；加 `--json` 时同时写入 `*.audit.json`
- `*.limited.md` / `*.limited.html`：范围受限审查；加 `--json` 时同时写入 `*.limited.json`
- `*.failed.md` / `*.failed.html` / `*.failed.json`：失败诊断始终写入三类产物，便于定位失败能力和断点续跑命令

默认行为：
- 审查成功生成HTML后，会自动打开浏览器查看报告。
- 打开HTML前，程序会自动启动或复用本机动作服务：`http://127.0.0.1:8765`。
- HTML里的“生成 PubPeer Comment”和“生成期刊 Letter”按钮会直接调用该本机服务生成草稿，不需要再手动运行额外脚本。
- 动作服务只监听 `127.0.0.1`，用于本机浏览器和本机Python进程通信；草稿仍由你在 `config.py` 中配置的LLM生成，使用前必须人工核对证据和措辞。

旧HTML报告的边界：
- 如果审查脚本正常运行结束，后台动作服务通常会继续存在；之后单独打开同一份HTML，按钮仍可直接生成草稿。
- 如果电脑重启、动作服务被手动结束、端口被占用，或服务异常退出，浏览器里的静态HTML不能自行启动本地Python脚本；此时按钮会提示服务未响应。
- 兜底方式是重新启动动作服务：
```bash
python paper_audit.py --serve-report-actions
```
- 如果 `8765` 端口被占用，可以在生成报告时指定端口，HTML会记录该端口：
```bash
python paper_audit.py ./my_paper_project/ --report-actions-port 8876
```
- 使用 `--no-open` 时会跳过自动打开HTML，也不会自动启动HTML动作服务，适合CI、远程服务器和批处理。

### 5. Test_paper HTML 演示
如果你把 `Test_paper/` 当作样例目录，推荐按下面流程验证 HTML 联动：
1. 重新生成报告：
```bash
python paper_audit.py Test_paper -o full_risk_from_scratch --json
```
2. 打开生成后的 `Test_paper/full_risk_from_scratch.audit.html`。
3. 在草稿区先选 `中文` 或 `English`。
4. 点击 `生成 PubPeer Comment` 或 `生成期刊 Letter`。
5. 如果旧页面报服务未响应，先重启 `python paper_audit.py --serve-report-actions`，再刷新页面。

---

## 🤝 社区贡献知识库
本工具内置的欺诈模式知识库基于PubPeer公开案例和社区贡献构建，欢迎所有人参与共建：
1. 收集PubPeer上的公开造假案例评论/描述，保存为纯文本文件
2. 运行`--update-patterns`命令自动提取新的检测模式
3. 提交PR到本仓库，审核通过后会合并到公共知识库，所有人都能受益

---

## 📖 完整用法
```
usage: paper_audit.py [-h] [--mineru]
                      [--mineru-model {pipeline,vlm,MinerU-HTML}]
                      [--mineru-lang MINERU_LANG] [--no-mineru]
                      [--max-chars MAX_CHARS] [--output OUTPUT] [--json]
                      [--serve-report-actions]
                      [--report-actions-port REPORT_ACTIONS_PORT]
                      pdf_path

positional arguments:
  pdf_path              待审查的文件路径或论文目录路径（支持PDF/Word/Excel/Supplement等）

options:
  -h, --help            show this help message and exit
  --serve-report-actions
                        启动本机HTML报告动作服务：一键生成PubPeer comment和期刊letter
  --report-actions-port
                        HTML报告动作服务端口（默认8765，仅监听127.0.0.1）
  --mineru              使用MinerU API将PDF转为Markdown再审查（PDF默认启用）
  --mineru-model        MinerU模型版本（默认vlm，仅Precision API生效）
  --mineru-lang         MinerU OCR语言（默认ch=中英，en=英文，japan=日文）
  --no-mineru           调试/范围受限：禁用MinerU；不能作为完整正式审查
  --max-chars           单块最大字符数（默认4096，超过4096会自动压到4096）
  --output, -o          输出报告文件路径（默认输出到同目录）
  --json                同时保存原始JSON结果
  --no-resume           禁用断点续作缓存，强制重新提取文本和重新LLM审查
  --fresh               运行前清空本输入的断点续作缓存，然后重新开始；默认不清空缓存并自动续跑
  --no-open             生成报告后不自动打开HTML报告，适合CI、服务器和批处理环境
  --reference-online-limit
                        参考文献在线检索条数上限，默认全部；设置后为范围受限审查
  --no-reference-online
                        调试/范围受限：关闭参考文献在线检索；识别到参考文献时不能作为完整正式审查
  --no-resource-online  调试/范围受限：关闭代码仓库与在线资源可用性校检；识别到资源时不能作为完整正式审查
  --image-audit-limit   报告中纳入图片检测的数量上限，默认30
  --image-semantic-limit
                        图像语义分析数量上限，默认全部；设置后为范围受限审查
  --no-image-semantic   调试/范围受限：关闭图像语义分析；存在可检测图片时不能作为完整正式审查
  --image-detector-limit
                        自动调用imagedetector.com检测的图片数量上限，默认全部；设置后为范围受限审查
  --image-detector-timeout
                        单张图片imagedetector自动检测超时时间秒数，默认60
  --no-image-detector   调试/范围受限：关闭imagedetector.com自动图片AI概率检测；存在可检测图片时不能作为完整正式审查
  --image-detect        兼容旧流程：打开图像复核清单
```

---

## 📊 报告示例
```
# 📄 学术论文审查报告 [耿同学标准]
**文件**: `test_paper.pdf`
**文件大小**: 3.2 MB
**提取字符数**: 23456
**提取方式**: MinerU VLM
**审查方式**: 分块审查 | 6块 | 单块上限4096字符 | 重叠512字符
**审查时间**: 2026-05-22 15:30:00

## 📊 本地统计检测结果
| 检测项 | 结果 | 状态 |
|--------|------|------|
| Benford分布偏差 | 0.123 | ✅正常 |
| p值数量/异常 | 12 / 2个>0.05 | ⚠️异常 |
| 标准差提及 | 4处 | N/A |
| 提取数字数 | 234 | - |

## 总评: 存在多处统计异常，复核优先级为中
**复核优先级**: 🟡 中
**证据风险分**: 72 / 100 (辅助排序指标，越高表示越需要优先复核)

## 🔍 逐项检查
| # | 分类 | 检查项 | 判定 |
|---|------|--------|------|
| 1 | 数据与结果 | p值未做多重比较校正 | 🚩红旗 |
| 2 | 图片与图表 | Figure 2与Figure 3背景高度相似 | ⚠️疑点 |
| 3 | 方法论 | 样本量n=12不足以支撑统计结论 | 🚩红旗 |
```

失败诊断也会写入正式产物目录，包含：
- `*.failed.md`
- `*.failed.html`
- `*.failed.json`

---

## 🧠 工作原理
```mermaid
graph TD
    A["输入路径"] --> B{"文件/目录?"}
    B -->|目录| C["递归扫描目录 → 自动分类所有文件"]
    C --> D["多格式文本提取(PDF/Word/Excel/CSV)"]
    D --> E["合并所有文件文本(带文件来源标注)"]
    B -->|单文件| F{"文件类型?"}
    F -->|PDF| G{"MinerU解析?"}
    G -->|是| H["MinerU API转Markdown"]
    G -->|否| I["范围受限/诊断提取"]
    F -->|Word/Excel/CSV| J["对应格式文本提取"]
    H --> K["全文文本"]
    I --> K
    J --> K
    E --> K
    K --> L["本地统计检测"]
    L --> M["智能分块: 默认4096字符/块, 512重叠"]
    M --> N["逐块LLM语义审查"]
    N --> O["多块结果合并: 去重+风险升级"]
    O --> P["输出Markdown + HTML + 可选JSON正式产物"]
    P --> Q["自动打开HTML报告"]
    Q --> R["本机动作服务生成PubPeer Comment/期刊Letter草稿"]
```

---

## 🙏 鸣谢
本项目检测体系融合参考以下优秀开源项目：
- [wooly99/geng-academic-fraud-detector](https://github.com/wooly99/geng-academic-fraud-detector) - 耿同学六式检测框架
- [Neospecies/AcademicIntegrityHunter](https://github.com/Neospecies/AcademicIntegrityHunter) - 本地统计检测算法
- [jingshouyan/academic-integrity-geng](https://github.com/jingshouyan/academic-integrity-geng) - 五维审查体系

感谢 [LINUX DO 社区](https://linux.do/) 提供的技术交流与支持。

感谢 https://linux.do/t/topic/2177102 该吃细糠了！！这才是我们需要的回复样式！！(提示词4.0) @Eeevan

感谢 linux.do 几位佬提供 token：@Member @picpi @Rawchat

---

## ⚠️ 免责声明
本工具仅供学术研究使用，所有检测结果仅为参考，不构成任何学术不端的判定依据。请严格遵守相关法律法规和学术规范，禁止将本工具用于任何非法用途。

## 无利益冲突声明
本项目作者与维护者声明：本工具及其检测规则、示例报告和文档说明不代表任何期刊、出版机构、审稿平台、商业检测服务或第三方模型服务商的立场；除用户自行配置和承担的第三方服务调用成本外，项目本身不因特定论文、期刊、机构或服务商的检测结果获得利益。

---

## 🤝 贡献
欢迎提交Issue和PR！参考方向：
- 增加新的第三方/托管LLM Adapter
- 更多统计检测维度
- 批量检测功能
- 图形界面开发

---

## 📄 许可证
MIT License

## 🧑‍💻 二次开发仓库说明

本目录是从 Agent 临时工作区整理出的独立 Git 仓库，适合用 Cursor、VS Code、PyCharm 等工具继续开发。

- 主程序：`paper_audit.py`
- 配置模板：复制 `config.example.py` 为 `config.py`，填入自己的 OpenAI-compatible LLM / MinerU 配置。
- 请勿提交 `config.py`、`.env`、日志、审查报告和断点缓存；这些已在 `.gitignore` 中排除。
- 安装开发依赖：`python -m pip install -r requirements.txt`
- CLI 检查：`python paper_audit.py --help` 或安装后运行 `paper-audit --help`
- 语法检查：`python -m py_compile paper_audit.py`
