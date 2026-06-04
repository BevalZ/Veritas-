# 📄 学术论文审查报告 [耿同学标准]

**文件**: `Test_paper2/2026-040896_稿件全文C.docx`
**产物类型**: 完整审查 (complete)
**版本**: prompt=text_audit_prompt_v1；schema=strict_evidence_schema_v1；adapter=audit_adapters_v1；rules=risk_rules_v1
**文件大小**: 4.31 MB
**提取字符数**: 21718
**提取方式**: docx_text
**审查方式**: 分块审查 | 3块 | 单块上限4096字符 | 重叠512字符
**LLM覆盖率**: ✅ 3/3 个分块全部成功
**审查时间**: 2026-06-02T17:01:14+08:00
**运行时UTC年份**: 2026（用于未来发表年份等非LLM日期判断）

## 📊 本地统计检测结果
| 检测项 | 结果 | 状态 |
|--------|------|------|
| Benford分布偏差 | 0.456 | 高偏差⚠️ |
| p值数量/异常 | 23 / 3个>0.05 | ⚠️异常 |
| 标准差提及 | 0处 | N/A |
| 提取数字数 | 100 | - |

## 总评: [合并3段审查] 复核优先级中；红旗1项；证据型疑点3项；提取质量疑点0项。
**复核优先级**: 🔴 高
**证据风险分**: 63 / 100 (辅助排序指标，越高表示越需要优先复核)
**计分拆解**: 红旗 1；证据型疑点 3；提取质量疑点 0；统计调整 benford_high_deviation, p_value_abnormal

## 🎯 行动优先级摘要

| 优先级 | 来源 | 事项 | 复核建议 |
|--------|------|------|----------|
| 1 | LLM语义审查 | 方法论 / 多重比较校正缺失 | 这是一个明确的方法论缺陷（耿同学六式-统计异常，7类红旗-方法论缺陷）。频繁的DeLong检验比较未校正，会使报告的P值的可信度降低，影响对模型效能差异结论的可靠性判断。需在结论部分重新评估各比较结果的实际显著性 |
| 2 | 证据链与证据簇审查 | 1个强证据簇需优先复核 | 方法论 / 多重比较校正缺失: 方法论 / 多重比较校正缺失; 方法论严谨性 / 缺乏多重比较校正说明; Benford分布偏差较高; 参考文献 #1 在线证据不足。优先核对 Methods、Results、图表、补充材料和现有审查信号是否指向同一证据链。 |
| 3 | 本地统计 | Benford分布偏差较高 | 偏差=0.456，建议核对原始数值来源和批量生成痕迹。 |
| 4 | 参考文献在线检索 | 9条参考文献在线证据不足 | 优先核对编号: [1, 8, 9, 23, 26, 28, 29, 30, 34]；检查DOI、题名、年份是否与数据库命中一致。 |
| 5 | LLM语义审查 | 数据与结果自洽性 / 英文摘要模型数量表述矛盾 | 英文摘要中模型数量描述存在潜在矛盾，需人工复核以确认准确性，避免误导读者 |
| 6 | LLM语义审查 | 方法论严谨性 / 缺乏多重比较校正说明 | 方法论部分未明确多重比较校正，可能影响独立危险因素筛选的严谨性，需核对全文以澄清 |
| 7 | LLM语义审查 | 方法论 / 样本量不足与缺乏外部验证 | 作者已指出方法论缺陷，但需人工复核原PDF表格以确认样本量和验证细节，避免过度推广结论 |

## 🚩 可疑点证据汇总表

| # | 判定 | 来源类型 | 分类/检查项 | 原文证据摘录 | 可疑原因 |
|---|------|----------|-------------|--------------|----------|
| 1 | 🚩红旗 | 统计线索 | 方法论 / 多重比较校正缺失 | 通过De Long 检验结果显示...Clin-US模型的AUC显著高于TN-LN-US模型...Clin-US模型显著优于所有亚组合模型及单一指标（均P<0.001）...TN-LN-US模型显著优于LN-US模型...和TN-US模型...LN-US模型亦显著优于ALP...和年龄...TN-US模型与ALP...、年龄...差异无统计学意义，且ALP与年龄之间的差异亦无统计学意义 | 这是一个明确的方法论缺陷（耿同学六式-统计异常，7类红旗-方法论缺陷）。频繁的DeLong检验比较未校正，会使报告的P值的可信度降低，影响对模型效能差异结论的可靠性判断。需在结论部分重新评估各比较结果的实际显著性 |
| 2 | ⚠️疑点 | LLM语义 | 数据与结果自洽性 / 英文摘要模型数量表述矛盾 | Compared with the other four models | 英文摘要中模型数量描述存在潜在矛盾，需人工复核以确认准确性，避免误导读者 |
| 3 | ⚠️疑点 | LLM语义 | 方法论严谨性 / 缺乏多重比较校正说明 | 通过单因素、多因素Logistic回归分析筛选预测CLNM的独立影响因素，将P<0.05的特征用于模型构建 | 方法论部分未明确多重比较校正，可能影响独立危险因素筛选的严谨性，需核对全文以澄清 |
| 4 | ⚠️疑点 | LLM语义 | 方法论 / 样本量不足与缺乏外部验证 | 样本量相对较小，未设立外部验证集 | 作者已指出方法论缺陷，但需人工复核原PDF表格以确认样本量和验证细节，避免过度推广结论 |

## 🔍 全部检查项概览

| # | 分类 | 检查项 | 判定 | 证据摘要 |
|---|------|--------|------|----------|
| 1 | 方法论 | 多重比较校正缺失 | 🚩红旗 | 通过De Long 检验结果显示...Clin-US模型的AUC显著高于TN-LN-US模型...Clin-US模型显著优于所有亚组合模型及单一指标（均P<0.001）...TN-LN-US模型显著优于LN-US模型...和TN-US模型.… |
| 2 | 数据与结果自洽性 | 英文摘要模型数量表述矛盾 | ⚠️疑点 | Compared with the other four models |
| 3 | 方法论严谨性 | 缺乏多重比较校正说明 | ⚠️疑点 | 通过单因素、多因素Logistic回归分析筛选预测CLNM的独立影响因素，将P<0.05的特征用于模型构建 |
| 4 | 方法论 | 样本量不足与缺乏外部验证 | ⚠️疑点 | 样本量相对较小，未设立外部验证集 |
| 5 | 数据与结果 | 数据与结果自洽性 | ✅通过 | 本研究纳入PTC合并HT患者共261例，其中转移组141例（54.0%），无转移组120例（45.9%） |
| 6 | 数据与结果 | 模型性能数字自洽性 | ✅通过 | TN-US模型敏感度91.49%，特异度32.50%；Clin-US模型AUC 0.842，敏感度70.92%，特异度84.17% |

## 📋 逐条详细分析（含原文支撑）

### 1. 方法论 - 多重比较校正缺失 — 🚩红旗
> **原文/证据摘录**: 通过De Long 检验结果显示...Clin-US模型的AUC显著高于TN-LN-US模型...Clin-US模型显著优于所有亚组合模型及单一指标（均P<0.001）...TN-LN-US模型显著优于LN-US模型...和TN-US模型...LN-US模型亦显著优于ALP...和年龄...TN-US模型与ALP...、年龄...差异无统计学意义，且ALP与年龄之间的差异亦无统计学意义

**可疑原因/详细说明**：这是一个明确的方法论缺陷（耿同学六式-统计异常，7类红旗-方法论缺陷）。频繁的DeLong检验比较未校正，会使报告的P值的可信度降低，影响对模型效能差异结论的可靠性判断。需在结论部分重新评估各比较结果的实际显著性

### 2. 数据与结果自洽性 - 英文摘要模型数量表述矛盾 — ⚠️疑点
> **原文/证据摘录**: Compared with the other four models

**可疑原因/详细说明**：英文摘要中模型数量描述存在潜在矛盾，需人工复核以确认准确性，避免误导读者

### 3. 方法论严谨性 - 缺乏多重比较校正说明 — ⚠️疑点
> **原文/证据摘录**: 通过单因素、多因素Logistic回归分析筛选预测CLNM的独立影响因素，将P<0.05的特征用于模型构建

**可疑原因/详细说明**：方法论部分未明确多重比较校正，可能影响独立危险因素筛选的严谨性，需核对全文以澄清

### 4. 方法论 - 样本量不足与缺乏外部验证 — ⚠️疑点
> **原文/证据摘录**: 样本量相对较小，未设立外部验证集

**可疑原因/详细说明**：作者已指出方法论缺陷，但需人工复核原PDF表格以确认样本量和验证细节，避免过度推广结论

### 5. 数据与结果 - 数据与结果自洽性 — ✅通过
> **原文/证据摘录**: 本研究纳入PTC合并HT患者共261例，其中转移组141例（54.0%），无转移组120例（45.9%）

**可疑原因/详细说明**：经核查，正文文本中表述的样本量及分组比例无矛盾。建议在后续审查中对照原版表格进行最终确认，以排除潜在的印刷或排版错误

### 6. 数据与结果 - 模型性能数字自洽性 — ✅通过
> **原文/证据摘录**: TN-US模型敏感度91.49%，特异度32.50%；Clin-US模型AUC 0.842，敏感度70.92%，特异度84.17%

**可疑原因/详细说明**：数字基于讨论部分摘录，未发现自洽性问题；需人工核对原PDF表格数据，排除OCR噪声影响

## 📝 综合结论

综合结论：合并3段审查后，当前复核优先级为中；最终结论以合并后检查项为准，而不是逐段LLM原始措辞。

保留红旗1项，优先核对：方法论/多重比较校正缺失。

证据型疑点3项，优先复核：数据与结果自洽性/英文摘要模型数量表述矛盾、方法论严谨性/缺乏多重比较校正说明、方法论/样本量不足与缺乏外部验证。

Benford分布偏差较高，仅作为批量数值复核线索；在缺少表格语义和原始数据上下文时，不单独构成造假结论。

p值异常计数提示需核对统计报告，但仍应回到原文方法、样本量和多重比较设置判断。

建议复核顺序：先展开可疑点详情核对原PDF表格/补充材料，再查看图像检测清单，最后检查参考文献真实性校检结果。

## 🔗 证据链与证据簇审查

**状态**: ok
**证据簇**: 4（强 1 / 中 3 / 弱 0）
**链条发现**: 0
> 单文件链条审查范围较窄；未发现可比较的跨文件材料。 该结果用于人工复核排序，不等同于科研不端判断。

### 证据簇

| # | 级别 | 主题 | 来源 | 证据数 | 摘要 |
|---|------|------|------|--------|------|
| 1 | 强证据冲突 | 方法论 / 多重比较校正缺失 | llm_check, local_stat, reference_audit | 6 | 方法论 / 多重比较校正缺失; 方法论严谨性 / 缺乏多重比较校正说明; Benford分布偏差较高; 参考文献 #1 在线证据不足 |
| 2 | 中等疑点 | p值分布需复核 | local_stat | 1 | p值分布需复核 |
| 3 | 中等疑点 | 数据与结果自洽性 / 英文摘要模型数量表述矛盾 | llm_check | 1 | 数据与结果自洽性 / 英文摘要模型数量表述矛盾 |
| 4 | 中等疑点 | 方法论 / 样本量不足与缺乏外部验证 | llm_check | 1 | 方法论 / 样本量不足与缺乏外部验证 |

## 🖼️ 图像AI/合理性检测

**检测网站**: https://imagedetector.com/
**语义模型**: mimo-v2.5-free（0张）
**imagedetector自动检测**: 0张
**图片数量**: 0 / 0
> 本地做尺寸、空白、噪声/对比度筛查；图像语义分析模型做图片语义理解；imagedetector.com子工具自动上传并记录AI概率。

> 未发现可检测图片。

## 🧩 跨文件一致性审查

**状态**: skipped
**检查文件数**: 1
**发现数**: 0（强 0 / 中 0 / 弱 0）
> 缺少可比较的跨文件材料；跨文件一致性审查已跳过。

> 未发现明确跨文件不一致；仍建议人工抽查关键表格、补充材料和正文结论。

## 🔗 代码仓库与在线资源可用性校检

**状态**: ok
**资源数量**: 0
**在线检测**: 启用（已检测 0 项）
> 校检论文声明的代码仓库、在线计算器、部署平台等资源是否可访问；URL格式错误会单独标记。

> 未识别到代码仓库或论文部署的在线资源链接。

## 📚 参考文献真实性/可核验性校检

**状态**: online_needs_review
**参考文献数量**: 34
**含 DOI 数量**: 0
**含年份数量**: 34
**在线检索**: 启用（已检索 34 条）
> 在线真实性校检：优先用DOI精确检索，再用题名/年份在Crossref、OpenAlex和PubMed进行多源核验；结果为尽力检索证据，不等同于绝对证明。

| # | 问题 | 在线证据 | 引用摘录 |
|---|------|----------|----------|
| 1 | 缺少DOI, 缺少期刊/来源, 在线检索异常, 无在线命中, 部分外部源异常 | error / 0.0 / 无命中 | Xu S, Huang H, Qian J, et al. Prevalence of Hashimoto Thyroiditis in Adults With Papillary Thyroid Cancer and Its Association With Cancer Recurrence and Outcomes [J]. 2021, 4(7): e2118526. |
| 2 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Antonaci A, Consorti F, Mardente S, et al. Clinical and biological relationship between chronic lymphocytic thyroiditis and papillary thyroid carcinoma [J]. 2009, 17(10): 495–503. |
| 3 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Marotta V, Sciammarella C, Chiofalo M G, et al. Hashimoto's thyroiditis predicts outcome in intrathyroidal papillary thyroid cancer [J]. Endocr Relat Cancer, 2017, 24(9): 485–493. |
| 4 | 缺少DOI, 部分外部源异常 | verified / 1.0 / Crossref | Hu X, Wang X, Liang Y, et al. Cancer Risk in Hashimoto's Thyroiditis: a Systematic Review and Meta-Analysis [J]. Frontiers in endocrinology, 2022, 13: 937871. |
| 5 | 缺少DOI, 部分外部源异常 | verified / 1.0 / Crossref | Xu S J, Jin B, Zhao W J, et al. The Specifically Androgen-Regulated Gene (SARG) Promotes Papillary Thyroid Carcinoma (PTC) Lymphatic Metastasis Through Vascular Endothelial Growth Factor C (VEGF-C) and VEGF Receptor 3 (V… |
| 6 | 缺少DOI, 部分外部源异常 | verified / 1.0 / Crossref | Kobawala T P, Trivedi T I, Gajjar K K, et al. Significance of TNF-α and the Adhesion Molecules: L-Selectin and VCAM-1 in Papillary Thyroid Carcinoma [J]. Journal of thyroid research, 2016, 2016: 8143695. |
| 7 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | likely / 0.739 / Crossref | Wang Y, Zong H, Zhou H. Circular RNA circ_0062389 modulates papillary thyroid carcinoma progression via the miR-1179/high mobility group box 1 axis [J]. Bioengineered, 2021, 12(1): 1484–1494. |
| 8 | 缺少DOI, 缺少期刊/来源, 在线未检索到, 部分外部源异常, 题名相似度低 | not_found / 0.16 / Crossref | 余小情, 傅晓红, 沈燕, 等. 超声特征预测甲状腺微小乳头状癌颈部淋巴转移的相关因素分析 [J]. 2023, 39(11): 1212–1215. |
| 9 | 缺少DOI, 缺少期刊/来源, 在线未检索到, 部分外部源异常, 题名相似度低, 年份不一致 | not_found / 0.0 / Crossref | 葛均波, 徐永健, 王辰. 内科学 [M]. 北京: 人民卫生出版社, 2018:693-694. |
| 10 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Ragusa F, Fallahi P, Elia G, et al. Hashimoto's thyroiditis: Epidemiology, pathogenesis, clinic and therapy [J]. Best Pract Res Clin Endocrinol Metab, 2019, 33(6): 101367. |
| 11 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Ito Y, Fukushima M, Tomoda C, et al. Prognosis of patients with papillary thyroid carcinoma having clinically apparent metastasis to the lateral compartment [J]. Endocr J, 2009, 56(6): 759–766. |
| 12 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Yang Z, Heng Y, Lin J, et al. Nomogram for Predicting Central Lymph Node Metastasis in Papillary Thyroid Cancer: A Retrospective Cohort Study of Two Clinical Centers [J]. 2020, (4). |
| 13 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Zhao L, Sun X, Luo Y, et al. Clinical and pathologic predictors of lymph node metastasis in papillary thyroid microcarcinomas [J]. 2020, 49: 151647. |
| 14 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Sugitani I, Kiyota N, Ito Y, et al. The 2024 revised clinical guidelines on the management of thyroid tumors by the Japan Association of Endocrine Surgery [J]. Endocr J, 2025, 72(5): 545–635. |
| 15 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | likely / 0.729 / Crossref/PubMed | Zheng K, Mao J. Comparison and Analysis of Clinical Features of Papillary Thyroid Cancer Complicated With Hashimoto's Thyroiditis [J]. Clinical Medicine Insights Oncology, 2024, 18: 11795549241287085. |
| 16 | 缺少DOI, 部分外部源异常 | verified / 1.0 / Crossref | Liu W C, Li M P, Hong W Y, et al. A practical dynamic nomogram model for predicting bone metastasis in patients with thyroid cancer [J]. Frontiers in endocrinology, 2023, 14: 1142796. |
| 17 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Zhao W, He L, Zhu J, et al. A nomogram model based on the preoperative clinical characteristics of papillary thyroid carcinoma with Hashimoto's thyroiditis to predict central lymph node metastasis [J]. 2021, 94(2): 310–3… |
| 18 | 缺少DOI, 缺少期刊/来源 | verified / 0.93 / Crossref | Zhong M, Zhang Z, Xiao Y, et al. The Predictive Value of ACR TI-RADS Classification for Central Lymph Node Metastasis of Papillary Thyroid Carcinoma: A Retrospective Study [J]. 2022, 2022: 4412725. |
| 19 | 缺少DOI, 缺少期刊/来源 | verified / 0.93 / Crossref | Liu C, Xiao C, Chen J, et al. Risk factor analysis for predicting cervical lymph node metastasis in papillary thyroid carcinoma: a study of 966 patients [J]. 2019, 19(1): 622. |
| 20 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Sisdelli L, Cordioli M, Vaisman F, et al. AGK-BRAF is associated with distant metastasis and younger age in pediatric papillary thyroid carcinoma [J]. Pediatric blood & cancer, 2019, 66(7): e27707. |
| 21 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Wang L, Chen J, Yuan X, et al. Lymph node metastasis of papillary thyroid carcinoma in the context of Hashimoto's thyroiditis [J]. 2022, 22(1). |
| 22 | 缺少DOI, 缺少期刊/来源 | verified / 0.93 / Crossref | Mao J, Zhang Q, Zhang H, et al. Risk Factors for Lymph Node Metastasis in Papillary Thyroid Carcinoma: A Systematic Review and Meta-Analysis [J]. 2020, 11. |
| 23 | 缺少DOI, 缺少期刊/来源, 在线未检索到, 部分外部源异常, 年份不一致 | not_found / 0.21 / Crossref | Dioufa N, Baloch Z W. Encapsulated neoplasms of the thyroid gland [J]. Virchows Arch, 2026, 488(1): 95–111. |
| 24 | 缺少DOI | verified / 1.0 / Crossref | Fang M, Lei M, Chen X, et al. Radiomics-based ultrasound models for thyroid nodule differentiation in Hashimoto's thyroiditis [J]. Frontiers in endocrinology, 2023, 14: 1267886. |
| 25 | 缺少DOI, 缺少期刊/来源 | verified / 0.93 / Crossref | Wang J Z, Zhu W, Han J, et al. The role of the HIF-1α/ALYREF/PKM2 axis in glycolysis and tumorigenesis of bladder cancer [J]. 2021, 41(7): 16. |
| 26 | 缺少DOI, 缺少期刊/来源, 在线未检索到, 部分外部源异常, 题名相似度低, 年份接近但不一致 | not_found / 0.204 / Crossref | 闵楠, 艾空, 杨新宇, 等. 甲状腺乳头状癌合并桥本甲状腺炎患者发生淋巴结转移的风险预测模型构建 [J]. 巴楚医学, 2025, 8(1): 75–81. |
| 27 | 缺少DOI, 缺少期刊/来源, 部分外部源异常 | verified / 0.93 / Crossref | Chahardoli R, Saboor-Yaraghi A A, Amouzegar A, et al. Can Supplementation with Vitamin D Modify Thyroid Autoantibodies (Anti-TPO Ab, Anti-Tg Ab) and Thyroid Profile (T3, T4, TSH) in Hashimoto's Thyroiditis? A Double Blin… |
| 28 | 缺少DOI, 缺少期刊/来源, 在线弱匹配, 部分外部源异常 | weak / 0.592 / Crossref | Rosario P W, Côrtes M C S, Franco Mourão G. Follow-up of patients with thyroid cancer and antithyroglobulin antibodies: a review for clinicians [J]. Endocr Relat Cancer, 2021, 28(4): R111–r119. |
| 29 | 缺少DOI, 缺少期刊/来源, 在线未检索到, 部分外部源异常, 题名相似度低 | not_found / 0.16 / Crossref | 柯晓丽, 沈浩霖, 吕国荣,等l. 颈部淋巴结超声良恶性风险预测模型的构建及价值 [J]. 中国超声医学杂志, 2020, 36(4): 314–317. |
| 30 | 缺少DOI, 缺少期刊/来源, 在线弱匹配 | weak / 0.586 / Crossref | Ahuja A, Ying M. Sonography of neck lymph nodes. Part II: abnormal lymph nodes [J]. Clinical radiology, 2003, 58(5): 359–366. |
