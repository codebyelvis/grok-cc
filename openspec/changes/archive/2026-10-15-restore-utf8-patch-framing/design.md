# UTF-8 补丁读取与行边界

作者：elvis。

## Existing contract

已发布基线 `daf80281169aaef821619e76d292ae3d0c888ffa` 的 `SKILL.md` 约定只支持 UTF-8 文本修改/新增并经真实 `git apply --check` 验证。此变更恢复该能力，不扩大修改类型或路径范围。

## Mechanism

unified diff 的结构行以 LF 分隔。文件内容中的 VT、FF、FS/GS/RS、NEL、U+2028、U+2029、裸 CR 不应生成新结构行。结构识别可处理已有 CRLF 形式，但传给 Git 及写出的原始 diff 不应被换行正规化。

CLI 的回复读取也属于同一条链路，须显式 UTF-8 解码并保留换行字节，不能只在函数单测中验证。保持 Python 3.11/3.13 与 macOS/Linux 支持，不引入第三方补丁解析器。

不采用屏蔽字符、裁剪载荷、无条件接受 hunk、删 guard 或先改文件再验证的方式。任务标记仍须完整、唯一且绑定当前 task；同类字符不能用于伪造额外文件或结束标记。

## Evidence

在临时项目中构造人工可核对的字节夹具，先证明 native Git 接受，再证明当前 helper/CLI 拒绝或改变字节。失败回归覆盖 context、删除和新增行，裸 CR 与 CRLF 经 CLI 完整走 prepare/check/apply。检查前后原文件及无关用户文件应保持原字节；仅在测试项目显式应用后检查预期字节。

负向回归覆盖伪造 hunk/路径越界、不完整或重复任务标记和基线漂移。独立 reviewer 阅读完整 diff、复跑关键测试并添加独立反例。

## Publication and rollback

先审核并推送 source，核对确切提交及 CI；再用既有官方 installer 下载该 revision 到隔离 staging，验证清单/哈希。更新 active 前保存载荷前像、权限及入口链接，并核对并发漂移。只同步清单内经审核的载荷，保留 registry、回执、链接和原生配置；更新后验证 Codex/Claudex 发现及字节一致。

不在未经批准时实现，不以原地清理 Git 或 registry 换取验收。若当前 active/source 已被其他窗口更新，则停止覆盖并报告。

## Learning candidate: byte preservation

```yaml
status: promoted
event_kind: review-finding
severity: medium
scope: project-local
promotion_trigger: threshold
symptom: Native Git accepts a UTF-8 patch while helper rejects or rewrites it.
prior_assumption: Generic text line splitting and universal-newline reading preserve patch semantics.
correction_or_evidence: Source review found non-LF framing; independent review identified CLI ingress conversion; both were reproduced with real files and Git.
generalized_invariant: Treat patch framing and payload separately; preserve UTF-8 payload bytes across the actual CLI boundary.
independent_reproductions: Parser rejection for nine separators; CLI CR conversion and existing CRLF compatibility.
independence_rationale: Cloud static finding and distinct local reviewer inspected different production layers.
duplicate_or_conflict_result: Existing UTF-8 contract is retained; no new workflow rule.
target_artifacts: scripts/tests/test_task_packet.py; scripts/task_packet.py; CHANGELOG.md
mechanical_enforcement: required
mechanical_enforcement_reason: Three regression methods exercise actual helper, CLI and native Git behavior in isolated projects.
verification: RED 13 expected failures; GREEN 20 packet tests and 41 complete bundle tests.
review_result: pass
decision_owner: codex
decision_provenance: Approved restore-utf8-patch-framing scope and independent implementation/final Review gates.
```
