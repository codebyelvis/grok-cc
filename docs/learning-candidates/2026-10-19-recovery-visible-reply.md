# 可见回复与客户端能力

作者：elvis。

本卡只蒸馏 grok-cc 在 2026-10-19 恢复里反复拖长时间的项目内教训。不收录聊天、咨询正文、凭据、owner 材料或私有证据目录。原始候选由恢复执行会话记录。2026-10-20 由本轮 Codex 主控核验回归及独立实现 Review 后提升为项目内规则；历史云端故障的发生细节不因此成为本轮实测。

```yaml
status: promoted
event_kind: false-pass
severity: high
scope: project-local
promotion_trigger: explicit-archive-distill
symptom: 宿主能力列表已含 agent.launch.v2 时，Mac CLI 仍可能在写出 operationId 前拒绝 launch。随后 bypass、未登记的空启动提示、无 receipt 的 sending，以及屏幕上已有完整回答和标记，先后被当成可以重开、重发或 finish 的信号。
prior_assumption: status 能力列表等于客户端已提交的能力；没有 operationId 可以再新建；屏幕正文、结束标记或 tui-idle 可以代替 receipt；本地 claudex 配置应复制云端 CC 一份。
correction_or_evidence: 现有 helper 已拒绝无 operationId 的重放和未知 sending 的重发。test_reconcile_echo_empty_incomplete_never_proves_acceptance 已拒绝空流、回显、裁剪和 screen 把丢失发送收成 accepted。本次补上 test_visible_screen_marker_without_receipt_stays_unaccepted：非零退出、无 receipt、屏幕含标记时保持 sending，finish 拒绝，再次 send 只 resume，原生调用带已保存 environment，标记不写入 registry。启动提示闭集已含 Try "how does <filepath> work?"，仅无任务历史时放行。
generalized_invariant: 宿主能力、客户端能力、operationId、receipt、stream 和屏幕可见文本分层取证。没有 operationId 保持 unknown。没有 receipt 的可见回复不能受理、不能 finish、不能重发。命名 environment 属于调用身份。本地 claudex 与云端 CC 的 native 配置不对拷。
independent_reproductions: 2026-10-20 独立 Codex 实现审核完整检查本卡、源码差异和回归，独立运行139项通过；另以实际helper进程和隔离原生CLI替身核验未知结果、显式draft和协议权限拒绝。历史宿主/客户端能力不一致仍只作为既有观察，不宣称本轮云端复现。
independence_rationale: 原候选作者与本轮独立审核实例不同；Codex mode-auto-implementation 只提供独立证据，提升由主控接受，不以候选自评代替审核。
duplicate_or_conflict_result: 与 references/session-binding.md、SKILL.md 的受理边界和安装说明一致。新回归补的是 finish、resume 和 environment，不替代已有的空流/回显/screen 回归，也不新增第二套创建或发送规则，不把 Orca 客户端补丁纳入 grok-cc 默认安装。
target_artifacts: docs/engineering/engineering-invariants.md; docs/troubleshooting.md; scripts/tests/test_session_binding.py
mechanical_enforcement: required
mechanical_enforcement_reason: test_visible_screen_marker_without_receipt_stays_unaccepted 拒绝把可见标记当成受理。启动提示回归拒绝把 how does 提示当成草稿，也拒绝有任务历史后继续放行。宿主能力列表与 Mac CLI client capability 不一致这一点无法在本仓库内对 Orca 安装包做确定性测试。
nonmechanical_boundary: 对抗审查必须拒绝这句推断：status 已列出 agent.launch.v2，所以客户端一定提交了它，或者原生退出 1 且没有 operationId 就是无副作用。也必须拒绝用屏幕全文或 tui-idle 宣布 helper 已受理。
verification: 2026-10-20 主控make check139 PASS，独立实现审核make check139 PASS，dev5载荷、严格OpenSpec及diff核验通过。固定源码2152650已推送并通过CI4/4，staging及实际安装各139项通过；独立安装139项及两入口隔离探针通过。来源、发布和安装详情见现有change的status/tasks，真实云端受理未验证。
review_result: independent implementation PASS; distinct final source PASS; independent publication/installation acceptance PASS
decision_owner: codex
decision_provenance: 用户明确要求把本次长时间修复蒸馏进 grok-cc，防止再犯。提升与最终完成仍归 Codex 主控。
```

## 每实例启动与既有协议

新创建须使用完整命令`claude --permission-mode auto`，而非让裸claude接受
Orca全局agentDefaultArgs。只改变新实例，不能为通过auto检查去改配置、
切权限、清空草稿或另开实例。已有预约按保存的protocol处理，不因升级
把旧operationId迁入terminal-create，也不把新路径的未知结果升级为重放权。
原生结果、完整清单和屏幕auto/输入核验各自提供不同事实。

机制在`scripts/session_binding.py`的协议校验、launch分派、先保存outcome
再查incarnation以及既有占用/任务历史保护。机械回归包括AutoLaunchTests、
实际helper CLI确认与并发、既有同ID重放及显式draft/首次提示测试。
主控已观察旧实现在新路径/预览上的RED，然后最小修复GREEN；独立审核
另探测了终端协议伪造agent重放证据、已保存handle占用和结果持久顺序。

源码的正确性、Git发布、active文件一致、其他窗口加载规则和真实云端
行为分别验收。本轮源码已发布且本地安装已验收，不授权真实CC操作。
