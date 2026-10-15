# Mac 会话与云端 CC 的固定绑定
作者：elvis

每个真实本地会话固定绑定一个云端终端，后续任务持续复用。身份由本地产品名及原生会话 ID 组成；项目根目录、环境和云端 worktree 在绑定后保持一致。切项目或身份异常时停止协调，不自动生成另一份绑定。

## 调用

先按官方 orca-cli 发现环境/worktree。每条 helper 命令都传入相同的 `--controller`、`--session-id`、`--project-root`、`--environment`、`--worktree` 与 `--orca`。`--worktree` 使用包含 repoId::path 的完整 ID，允许 `id:` 前缀。Codex 可以省略 session-id，读取当前工具环境的 CODEX_THREAD_ID；Claudex 使用入口中原生渲染的真实 ID。不要把没有导出的 shell 变量当成已取得身份。[Claude 官方替换说明](https://code.claude.com/docs/en/skills#available-string-substitutions)。

```text
python3 <skill-dir>/scripts/session_binding.py identity --controller codex
python3 <skill-dir>/scripts/session_binding.py ensure <相同会话与目标参数>
python3 <skill-dir>/scripts/session_binding.py send <相同会话与目标参数> --task-id <packet的task_id> --text-file <项目外提示文件>
python3 <skill-dir>/scripts/session_binding.py send <相同会话与目标参数> --task-id <同一task_id> --message-id export-1 --text-file <仅最终补丁的格式修正提示文件>
python3 <skill-dir>/scripts/session_binding.py finish <相同会话与目标参数> --task-id <同一task_id>
```

正常使用共享的默认状态目录 `~/.local/state/grok-cc`；不要为每次调用、任务或安装副本另建 state-dir，否则失去跨调用约束。`--state-dir` 仅用于明确隔离的测试，不能当成绕开阻碍的办法。此目录是本 helper 的私有运行状态，不是 Claude/Codex 原生配置，不同步到任何远端或其他运行时。只保存绑定、任务/消息摘要、起始 cursor 和原生发送回执，不保存源码提示或其他会话内容。

`ensure` 仅确认/创建绑定，不证明模型已启动或任务完成。对它返回的终端使用官方 `terminal wait --for tui-idle`；启动中或忙碌时等待原终端。helper 的 send 会再次检查 runtime/incarnation、auto mode、空输入和空闲状态，在锁内先保存意图再提交一次。已知的空启动提示只在首条消息前识别；其他非空或无法辨认的输入保留并停止。

## 每个任务的状态

- 同一 task_id 的首次开发消息固定为 `main`。对相同 task_id/message-id/文本重复调用 send，返回 `action: resume` 及缓存回执或 sending 状态，不再发送。内容变了但 ID 未变会拒绝；不得换 ID 来重复已派发开发任务。
- `action: sent` 也不等于完成：检查回执的 input_accepted/turn_started，再按官方 wait/read（必要时原生 transcript）取回当前任务的完整补丁。所有读取都限定绑定的 handle/runtime/incarnation；补丁仍须原 task_packet.py 检查、Mac 测试和独立审核。
- 新开发任务在当前 active_task 结束前不能发送。最后补丁缺格式时可显式使用同一任务的 export-N 消息，每个消息单独去重。仍遵守原有最终产物限定和模型拦截处理，不重新开发或索要对话/内部推理。
- 核对结果后 finish 要求原 CC 已空闲且无未知发送结果，保留绑定与历史。返回 project_pass=false，表示派活占用结束，不代表代码任务通过。

## 不确定状态

创建/发送之前会持久化 intent。网络失败、进程中断、无效回执或身份变化时保留它：不另开窗，不盲目重发，也不删 registry“修复”。如果仅是锁忙，稍后以原身份重试；如果是绑定终端忙，仅等待它。

`state: creating` 或 message `state: sending` 表示外部操作结果尚未证实。后续只能按已知原生身份/回执做只读调查；不能 finish 或发新任务覆盖它。本次实现不提供 legacy adoption/reconcile/rebind/reset/delete：旧创建回执不含 Mac owner，不能用它认领旧窗。需要恢复未知归属时先交回主控核对事实和明确范围。

此锁只协调使用新版 helper、同一共享目录的本地调用。未重读新版的旧窗口、手工 Orca 操作或其他机器不受该锁控制；旧窗口需重新读取入口，不能继续按公共空闲池派活。不要因为终端暂时空闲就关闭它；本次修复不清理任何旧会话。
