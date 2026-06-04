# ADR-0005: 显式输出路径相对当前工作目录

日期: 2026-06-04

## 状态

Accepted

## 背景

Paper Audit / Veritas 的默认输出路径会跟随输入文件或输入目录，这对不传 `--output/-o` 的简单命令是合理的。但当用户显式传入相对 `-o` 路径时，旧行为会把该路径再拼到自动输出目录下，例如输入目录为 `Test_paper2` 且 `-o Test_paper2/test_paper2_audit` 时会生成 `Test_paper2/Test_paper2/test_paper2_audit.audit.*`，这违背常见 CLI 直觉。

## 决策

显式 `--output/-o` 的相对路径按当前工作目录解释，不再相对自动输出目录解释。未传 `-o` 时保留现有默认行为：输出到输入文件旁边或输入目录内。

## 后果

用户显式指定输出位置时行为更符合 shell/CLI 直觉，也避免嵌套目录惊讶。实现时需要同步成功产物和失败诊断产物的路径解析，并用回归测试覆盖 `-o Test_paper2/name` 不再写成 `Test_paper2/Test_paper2/name.*`。
