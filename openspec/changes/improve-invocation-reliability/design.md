# Design

作者：elvis。

## Fixed boundaries

维持一真实本地会话一绑定、旧 owner key、两次提交上限、未知结果不重发、显式创建确认、auto/草稿/完整产物检查。采用现有 schema 和文件，不迁移历史状态。

## Decisions

1. send 回执落盘只放宽既有 tasks/messages 的 evidence 差异；比较时去掉这些观察字段后，其余绑定、任务、消息和 attempt 必须仍等于保存的 intent。reconcile(task_id) 可同时更新 main 与 export 的证据，不能只忽略目标消息。将新回执合入最新行，保留所有并发 evidence。普通 _unchanged 和 reconcile 的身份/并发检查保持严格；send 错误分支使用相同合并条件。
2. CLI 以 read_bytes().decode('utf-8') 读取 prompt。task_packet 提供 MAX_SEND_BYTES=450*1024 与 validate_prompt_transport(text)，绑定 helper 复用；空文本、保留 marker、超传输上限和 NUL 在派发前拒绝，render 在输出前同样检查。默认预算仍为 120 KiB。
3. NativeOrca 为每次本地子进程建立独立 session，超时/读取失败只终止该自有进程组。收尾 communicate 必须有限；逃离组且持有管道的子进程也不能无限延长 helper 返回。失败仍保留 unknown，不推断远端未执行。
4. 逐项移植安装版 controller/realpath 行为及现有测试。Grok 始终需要显式真实 UUID；CODEX_THREAD_ID 或 CLAUDE_SESSION_ID 表明其他宿主时，不能借不同 UUID 选择 grok。没有可发现原生 Grok ID 时，真实性仍由调用者负责，不伪造环境或 ID。
5. 输出先 realpath 解析父目录，再逐组件 O_NOFOLLOW 打开，并以 O_EXCL 创建 leaf；项目内路径、已存在文件、解析后的 symlink swap 仍拒绝。
6. diff parser 保持现有保守范围；生产 prompt 明确只输出 ---/+++/@@ 最小格式，新文件使用 /dev/null，不含 diff --git/index/mode 元数据。保留完整 hash 与原 packet/Git 检查。
7. 绑定已知时直接 send，使用其既有前后身份、idle 和草稿检查；ensure 是可选诊断，省去一次重复 list。收取产物及 finish 条件不变。

## Release And Rollback

在平台管理的隔离 worktree 以当前 master 为基线。先保留 active 的八文件原字节/权限及发现入口；将这些差异作为导入候选而非新源码真值。所有修改经回归与独立审核后提交，并在 main 工作区无已跟踪漂移时 fast-forward master，推送 origin/master。若远端前进，先协调/整合并重验，不覆盖他人提交。

发布后用官方 skill-installer 在新 staging 下载固定 SHA，验证清单及 make check。只同步八文件；复制前再次比较 active 前像和链接，漂移则停止覆盖。保留前像供受控回退；非载荷、registry、native 配置及其他项目不变。安装后核对八文件、入口、非载荷并执行安装版 suite/独立验收。回退只允许安装仍等于本次后像时恢复本次前像。

## Learning Candidate Card

```yaml
status: promoted
event_kind: integrity
severity: high
scope: project-local
promotion_trigger: high-severity
symptom: 只读观察使已受理回执丢失；发送前换行被转换；超时后继承管道继续阻塞。
prior_assumption: 整行相等即同意图；文本读取保留字节；kill直接子进程后EOF必然及时到达。
correction_or_evidence: 原实现失败回归与独立Implementation Review确认；新实现make check通过161项。
generalized_invariant: 观察与提交意图区分；字节完整性覆盖发送入口；进程清理必须自有且有界。
independent_reproductions: 主控复现与builder RED/GREEN；独立review对旧任务evidence/内容漂移做额外反例。
independence_rationale: reviewer未参与代码实现，独立构造反例并运行完整检查。
duplicate_or_conflict_result: 扩展既有并发与字节不变量，不新增状态框架或改变未知结果规则。
target_artifacts: docs/engineering/engineering-invariants.md；scripts/tests/test_session_binding.py；scripts/tests/test_task_packet.py
mechanical_enforcement: required
mechanical_enforcement_reason: 确定性临时Registry、真实本地CLI和自限进程fixture覆盖旧假设。
verification: 既有不变量表列出逐项回归；主控与独立review均161项通过。
review_result: pass
decision_owner: codex
decision_provenance: 主控采纳独立Learning Review PASS，提升至项目内不变量与回归；不提升为全局Skill规则。
```
