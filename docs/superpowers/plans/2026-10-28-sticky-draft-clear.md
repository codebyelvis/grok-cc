# Sticky Draft Clear Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline; independent Codex subagents review only. No external dispatch. Canonical contract progress is in OpenSpec tasks.md.

作者：elvis。

**Goal:** 显式、有限地清理已获用户确认的 draft，保留 send/finish 默认草稿保护。
**Architecture:** 在现有 BindingManager/CLI 复用身份与 composer 门禁；只增加元数据投影和控制串清理入口，不改变 Registry schema 或生命周期。
**Tech Stack:** Python stdlib、unittest、mock Orca、OpenSpec。
**Spec:** openspec/changes/2026-10-28-sticky-draft-clear/{proposal,design}.md；specs/sticky-draft/spec.md。

## Constraints and Review

- 源基线 `3ae6336`；worktree `/Users/elvis/file/develop/opensource/grok-cc-sticky-draft`，分支 `feat/sticky-draft-clear`。
- 用户已授权实现及本地验证；禁止 add/commit/push/安装/发布/真实 Orca/云端/共享 state/全局配置。
- standard 源码候选；本地主控 Codex `/root` 为 control-plane/control-plane-high，拥有证据签收权。
- Preflight、Implementation Review 与最终完整 diff Review 分别保留：产品 codex，角色 independent-reviewer，profile control-plane-high，
  分别绑定新建的独立本地 reviewer 实例；审核者不实现，不得自行宣称整任务完成，结果仅为 governed-review-evidence。
- 只改 helper/测试、SKILL.md、reference、CHANGELOG、VERSION、manifest、本 change、计划与审核记录。
- 回退保留独立 worktree，不修改原工作区；未知载荷/基线漂移、需真实远端或新增生命周期即停。

## Review Focus

- 空 `❯` 与真实 draft 并存；摘要脱敏，CRLF/CR/末尾空行和非 ASCII 字节准确。
- 无 confirm 不创建 state/lock；已空不 send，busy/非 auto/身份漂移/未知消息不清。
- 两次清理各自独立 write；body 不混入控制字节，clear 回执未知不得重试。
- 读回 draft 空但 composer 残留、screen 裁剪、清理间身份/idle 漂移不能报成功。
- finish 清完后保持任务历史/次数，project_pass=false；最大 burst 不超过 158 字节。

## Task 1 — One bounded draft recovery slice

Files: scripts/session_binding.py、scripts/tests/test_session_binding.py 及上述文档/制品元数据。
Consumes: 现有 bound registry、_verify、_idle、_call 的 Orca envelope。
Produces: `BindingManager.clear_draft(confirm=False)` 及 CLI `clear-draft [--confirm]`；
`diagnostic` 四个 draft 元数据字段；action draft-inspected/draft-already-clear/draft-cleared。

- [ ] 独立 Preflight：核对合同覆盖、可执行命令、负面边界和 scope；旧版参考消费演练记录不能恢复的缺口。
- [ ] RED：在现有测试 fixture 仅替换 Orca 边界；新增 nonempty_draft、只读、算法/上限/Enter、两次残留、busy、空 draft、独立 body write、清后 finish 和异常安全回归。
  Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s scripts/tests -p test_session_binding.py -k sticky_draft -v`。
  Expected: 分类不符/缺 clear_draft/CLI 不接受命令，且旧实现仍不能自动清。
- [ ] GREEN：提取最少共用 idle/screen/composer 检查，增加脱敏摘要、clear_draft 和 confirm 参数路由；保持 create/rebind/send 的其余状态语义。
  Run the same focused command, then binding suite when necessary。
- [ ] 更新 SKILL/reference 决策表与三步排查；新版独立消费演练须找对确认门禁、命令及失败恢复边界；不执行真实命令。
- [ ] VERSION=0.1.0.dev13，更新 CHANGELOG；审查 bundle-files.txt 仍八文件。
  先核对未改载荷等于基线 manifest，只有 SKILL/reference/helper/测试四个 hash 可更新。
- [ ] Run `make check`、`openspec validate 2026-10-28-sticky-draft-clear --strict`、`git diff --check`。
  独立 Implementation Review 审核实文件、完整 diff、关键回归并增加至少一个反例；有发现回到 RED/fix/verify/Review。
- [ ] 主控最终核验后由另一独立实例做 Final Review（恢复/草稿完整性不合并审核门禁）；
  核对两工作区残留并交付测试名/版本/路径/验证范围；等用户授权 Git/发布/安装。

不添加提交步骤，不把真实远端未验收写成端到端通过。
