# Design

作者：elvis。

## Decisions

1. `nonempty_draft`、`sticky_draft` 均为 `Blocked`，`retryable=false`。
   `diagnostic` 固定投影 `draft_present`、`draft_lines`、`draft_bytes`、`draft_sha256`；
   不返回/落盘 draft 全文或 screen。空 draft 报 0 行、0 字节和空字节 SHA256。
2. 按上游 `text.split(/\r\n|\r|\n/)` 计非空草稿逻辑行，保留末尾空行；视觉折行、Unicode 分隔符不另计。
   `N=min(40,max(1,lines+8))`，先 `2N-1` 个 U+0015，再同数 U+000B。
   参考 [Orca clear 实现](https://github.com/stablyai/orca/blob/bbb3e7e5ee4a7c861d2f0e3a17b9b72be77d409d/src/shared/agent-tui-input-clear.ts)
   和 [独立 write 的修复说明](https://github.com/stablyai/orca/commit/bbb3e7e5ee4a7c861d2f0e3a17b9b72be77d409d)。
3. 复用/提取现有 idle、screen 身份/完整性和 composer/auto 核验；原 send/finish 的
   首任务占位符限制不变。draft 类型异常、身份漂移、未知提示和非 auto 均安全阻断。
4. `clear_draft(confirm=False)` 读取已绑定 owner 的只读快照并核验精确目标，返回 `draft-inspected`；
   不创建 state/lock/intent，不调用 send。缺绑定则阻断，不创建/认领终端。
5. 确认路径仅用于 bound，未决消息继续阻断。先 verify + idle，再核对 screen/composer/auto。
   draft 已空且 composer 为空或精确占位符时返回 `draft-already-clear`，零 send。
   draft 非空时只发控制串，独立 `terminal send --text <burst>`，无 `--enter`、正文和 `--wait-submit`。
6. 每次清理后重新核验身份、idle、screen/auto。draft 空且 composer 为空或精确
   `CLAUDE_EMPTY_PLACEHOLDERS` 才返回 `draft-cleared`。读回仍非空才允许第二次 N=40；
   第二次后仍非空或 composer 残留则 `sticky_draft`。screen limited/truncated 必须明确布尔 false，不能把缺失或其他假值视为完整。
   未知/超时/拒绝的清理回执不重发；清理开始后的查询失败/忙碌也不可重试整个清理命令；
   不将清理计入模型提交次数，不改任务、active_task、绑定或历史。
7. send/finish 不调用清理入口。清完后由调用者另行 ensure/send/finish；finish 仍 `project_pass=false`。
   两次后仍粘住只停下报告；用户可选择关闭终端，再走其另行批准的 retire-dead-binding 流程，
   本源码未提供该命令，不实现自动退役/换绑。

## Safety And Limits

确认授权允许删除当前草稿，并不能证明它是 ghost。请先保留真实未发送文本；
手动键入、其他客户端和用户在核验后的并发操作不受本地锁完全约束。
只读远端查询不持 registry 锁，清理前后重验绑定快照；不新增持久化状态或调度框架。
真实远端被用户明确排除，只对 mock Orca 边界与真实本地状态验证。

## Rollback And Stop

本轮无提交/安装/发布，成果留在独立 worktree 供审核；不 reset/clean 或覆盖原工作区。
如清单外/未知载荷漂移、基线/身份/状态漂移、需要真实远端或扩大生命周期行为，停止受影响动作并报告。

## Project Learning Candidate

```yaml
status: promoted
event_kind: false-pass
severity: high
scope: project-local
promotion_trigger: high-severity
symptom: 裁剪标志缺失仍被宣称清理成功；已发清理后的未知读回仍提示可重试。
prior_assumption: 假值等价完整；只读操作的retryable可直接代表整个变更命令。
correction_or_evidence: 独立Implementation Review反例及主控新增回归复现20个失败子例，随后最小修正。
generalized_invariant: 验空需要明确完整性证据；变更之后的读回失败不能授权重新执行变更。
independent_reproductions: 独立reviewer隔离探针；主控在现有fixture补22项focused中的两个回归及busy断言。
independence_rationale: reviewer未参与实现；主控独立编写回归复现同一边界，外部仅mock Orca。
duplicate_or_conflict_result: 补强既有draft/完整性与未知结果保护，不改变创建、换绑、任务状态机或全局规则。
target_artifacts: references/session-binding.md；scripts/tests/test_session_binding.py
mechanical_enforcement: required
mechanical_enforcement_reason: 缺字段/异常假值与发出clear后的list/wait/read故障可确定性复现。
verification: 旧候选22项focused出现20个失败子例；主控与独立重审22项focused及215项make check通过，另15个独立边界探针通过。
review_result: pass
decision_owner: codex
decision_provenance: 主控核证并签收独立Implementation修正重审PASS，提升至现有reference与确定性回归；不修改个人或共享Skill治理规则，不代表Final或远端验收。
```
