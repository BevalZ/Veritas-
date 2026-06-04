# Veritas Paper Audit

Veritas Paper Audit helps reviewers produce evidence-backed, manually reviewable audit artifacts for academic papers. The language in this context should emphasize review prioritization and evidence navigation, not final misconduct judgments.

## Language

**复核概览**:
The first-screen summary of an audit report that helps a reviewer decide what to inspect first. It combines existing report type, 复核优先级, 证据风险分, coverage state, and top action items without creating a new risk model or replacing detailed evidence sections.
_Avoid_: Dashboard, 仪表盘, 结论摘要, 总览报告

**复核优先级**:
The rule-derived urgency level for manual review of a report or finding group. It is a prioritization label, not a misconduct verdict.
_Avoid_: 造假等级, 不端等级, 定罪结论

**证据风险分**:
A 0-100 auxiliary score used to sort and prioritize evidence review. It is not a probability of fraud or a measure of author intent.
_Avoid_: 打假得分, 造假概率, 可信度分

**行动优先级摘要**:
A ranked list of concrete review actions derived from existing audit signals. It should point reviewers to evidence sections rather than introduce new findings.
_Avoid_: 结论清单, 最终裁决

**审查相关文件**:
A file selected by directory scanning as part of the audit scope, such as the main manuscript, supplement, data table, reference material, image source, or other file that feeds extraction, cross-file consistency, reference/resource checks, image audit, or evidence-chain review. If an 审查相关文件 cannot be extracted, a complete audit report must not be produced unless the file was explicitly excluded by the user.
_Avoid_: Any file, incidental file, random project file

**失败恢复面板**:
The first-screen section of a failed diagnostic artifact that tells the user how to recover the run. It replaces 复核概览 for failed artifacts and focuses on failed capability, error category, completed stages, cache/resume state, retry command, and fix hints.
_Avoid_: 复核概览, 风险摘要, 结论摘要

**报告内证据导航**:
Links and anchors that move a reviewer from 复核概览 or 行动优先级摘要 to evidence already rendered inside the same report, such as findings, evidence clusters, reference checks, resource checks, image sections, or cross-file consistency sections. It does not promise navigation back to source-document pages, Word paragraphs, table cells, or image coordinates.
_Avoid_: 原文定位, PDF页码定位, Word段落定位

## Example Dialogue

Reviewer: "The 复核概览 says this report is high priority. Does that mean the paper is fraudulent?"

Developer: "No. 复核优先级 and 证据风险分 only decide what to inspect first. The reviewer still follows the linked 行动优先级摘要 and detailed evidence sections before making any external claim."

Reviewer: "The directory contains a Word manuscript and some hidden system files. Which files matter for completeness?"

Developer: "The Word manuscript is an 审查相关文件 because it feeds the audit. Hidden system files are incidental and can be ignored. If the manuscript cannot be extracted, the run should produce failed diagnostics rather than a complete report."

Reviewer: "A failed report shows no 复核优先级. Is that a bug?"

Developer: "No. Failed artifacts use a 失败恢复面板 because there is no complete or limited review result to prioritize yet."

Reviewer: "Can the action item link take me to the original Word paragraph?"

Developer: "Not in this task. 报告内证据导航 only links to evidence already rendered in the report. Source-document location tracking needs a separate source-span model."
