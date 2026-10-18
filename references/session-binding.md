# Mac 会话与云端 CC 的固定绑定
作者：elvis

每个真实本地会话只有一个当前绑定CC，不扫描公共空闲池。owner由产品名及真实原生会话ID组成；项目、环境和云端worktree固定。切项目不生成替代绑定，身份变化不自动换窗。

## 调用与证据

先按版本匹配的官方orca-cli发现环境/worktree。每条helper命令使用相同`--controller`、`--session-id`、`--project-root`、`--environment`、`--worktree`、`--orca`。worktree必须是完整repoId::path，可带id:前缀。Codex读取真实CODEX_THREAD_ID；Claudex传入入口原生渲染的ID，不用未导出的shell变量或随机值替代。[官方替换说明](https://code.claude.com/docs/en/skills#available-string-substitutions)。

```text
python3 <skill-dir>/scripts/session_binding.py identity --controller codex
python3 <skill-dir>/scripts/session_binding.py ensure <相同会话与目标参数>
python3 <skill-dir>/scripts/session_binding.py send <相同参数> --task-id <task_id> --text-file <项目外已审查prompt>
python3 <skill-dir>/scripts/session_binding.py reconcile <相同参数> --task-id <task_id> [--message-id main]
python3 <skill-dir>/scripts/session_binding.py finish <相同参数> --task-id <task_id>
```

正常运行持续复用默认共享状态目录`~/.local/state/grok-cc`，不能另建state-dir绕过约束；开发回归仅用临时`--state-dir`及Orca替身，不操作真实共享目录。状态是本helper的私有数据，不是Claude/Codex原生配置，不同步远端。只保留绑定/任务摘要、cursor、意图、尝试次数和白名单回执，不保存源码prompt、屏幕正文或原始诊断。

`ensure`仅核验已有绑定，不创建；无绑定时不落盘，要求先展示目标并取得用户对换绑/新建的明确选择。它不证明CC就绪或模型完成。send再次验证runtime/incarnation/worktree/agent、auto mode、真实空composer和空闲。首任务前仅允许已核实的精确空启动提示，其他草稿/未知屏幕继续保留并阻止发送。

## 显式创建与本地最多一次提交

不自动新建终端。先只读展示计划与同项目终端；没有真实任务或没有用户对具体目标的创建选择时，停在dry-run，不能因任务紧急、通用自主授权或ensure无绑定而追加confirm：

```text
python3 <skill-dir>/scripts/session_binding.py create <相同会话与目标参数> --project <完整云端worktreeID>
```

`--project`为已发现的完整`repoId::path`，可带`id:`前缀；Mac根目录仍由`--project-root`指定。可选`--worktree`须与project相同；其他命令不接受project/confirm。无confirm只读现有registry和完整native list，返回claude/auto/精确worktree位置计划、至多20项白名单inventory、同项目总数及限量标记；不创建状态目录、lock、intent或终端，不按空闲程度认领目标。

只有用户明确选择该目标的新建后，才可执行同一命令加`--confirm`。确认时重新核对当前事实：无active任务、无未解决消息和creating；已有live绑定返回has_live_binding。替代创建须在相同runtime完整清单中证明原实例确已消失；列表缺页、缺失/重复handle、身份漂移、临时断连、busy或非auto都不能证明消失。不可达先等一至两分钟再核查原操作。

helper在锁内重读/比对后，先以fsync/replace/目录fsync持久保存稳定creation_id和state=creating，再锁外最多调用一次公开terminal create，启动claude auto。保存失败零native调用。保证仅覆盖使用同一保留受管registry的本helper；没有原生caller-key去重，也不保证跨客户端/registry或exactly-once。不得通过删除、切换state目录或换身份逃避pending。

回执的精确runtime/handle/incarnation/worktree先保存为creation_candidate，验证候选与本地intent有效后，才按完整list、claude、connected/writable/non-orphaned、idle、auto和空输入/精确首次提示核验；成功后重锁比对并绑定。旧绑定及任务归档，历史task身份与累计提交额度继续有效。回执不是绑定成功证据。

恢复前须核对creation_previous的任务及active状态与reservation保留内容一致；带旧任务却缺少快照、任务缩水或状态不一致均保留原文件并阻断。其他owner已经持久保存的精确candidate也占用该目标，在接收候选、恢复核验及最终绑定时都不能认领。

一旦reservation持久化，即使原生进程未启动、超时、回执损坏/丢失，也不能再次提交。保存候选后核验失败返回create_unverified，后续同目标confirm只能继续只读核验该精确candidate；完全无candidate保持pending，不根据标题、时间或新终端猜归属。旧creating保持未知，不重置。pending仍阻止ensure/send/rebind；finish也不能解锁它。

## 状态、次数与恢复

- main是同一task首次开发消息。重复相同task/message/原文，对accepted或sending只返回resume，不再提交；不同文复用同ID拒绝。消息附加稳定grok-cc-msg标识，仅用于关联，不是受理证明。
- task累计最多2次模型提交，main、显式重试和合法export共用。每message另留计数去重；accepted重复resume不增次数。不能换export-N/task_id绕过未知结果或总额。
- 仅有正面证据证明Orca子进程根本未启动，才标not_sent；同ID同文显式再调send也必须重新verify/idle，并有剩余额度。远端非零、timeout、已受理痕迹或无效回执保持sending/uncertain；remote_runtime_unavailable不等于“没送到”。
- main已accepted且没有未知结果、还有一次额度时，用户明确要求的格式修正可用`--message-id export-1`只重导出既有最终补丁；不重新开发、不索要内部推理，不用于绕过模型拦截或丢失内容。未知/截断/缺页先停止报告，不能连续发导出消息。
- 保存/返回的receipt仅含requestId、stages、processIncarnation、handle、runtimeId、accepted。旧schema-1 intent保持保守兼容，无计数的旧发送至少按1次处理，旧完整回执仅做白名单投影。
- input_accepted不是执行完成，tui-idle不是成功回复。补丁必须完整读回、hash/原packet检查、Mac测试与独立Review通过。

`reconcile`只向既有绑定查询保存cursor后的输出，可写本地证据状态，绝不send/create。marker回显、终端空闲或没有新输入不能证明accepted/not_sent；source=screen、limited/truncated或身份不符不能解锁。已有同身份有效白名单receipt证明输入受理时才可恢复accepted；证据不足保持原状态并说明原因。

本开发版本未取得官方原生request retry的精确契约；`send --retry-request`在任何Orca调用之前返回`unsupported_contract`，即使已有requestId也不猜命令。此能力尚未实现，不通过手工terminal send绕过。

`finish`要求当前task无未知发送且原CC空闲，保留绑定及任务历史，返回project_pass=false；它只是释放派活占用，不是项目验收或清理。creating/unknown不能finish、重建、reset或delete。

## 只读退避

list/read/wait仅对限定瞬时错误按2、5、15、30秒（之后封顶30）退避；默认`--retry-budget-s 300`。正预算由一次helper命令整条只读链共享，不在verify/idle内部刷新；每次调用timeout不超过剩余预算。0关闭自动重试，各必要查询仍仅调一次且有有限timeout。read_attempts与模型提交attempts分开，不把只读轮询混为模型工作量。

只读查询和sleep不持registry锁；重新加锁后重载并核对相关owner/目标/task/intent，漂移停止，不能用旧整库覆盖其他owner更新。send/create先在锁内原子记录意图，再仅调用一次；send的子进程timeout为wait-submit +45秒（当前60秒）。预算到期仅报告，不切身份、开终端或重启网络。

## 显式换绑

只有用户已确认具体目标后才能调用，助手不得自动调用：

```text
python3 <skill-dir>/scripts/session_binding.py rebind <相同参数> --confirm-handle <已确认handle> --confirm-incarnation <已确认incarnation>
```

要求已有bound记录、active_task为空且没有unknown intent；目标同一worktree、claude、connected/writable/non-orphaned、auto mode、空composer且未被其他owner占用。旧绑定及任务完整归档history，不删除旧终端或历史；history中已有task_id禁止在新绑定上重放，同一目标的rebind是保留task/次数的no-op，不能重置额度；不创建目标，不提供无现有绑定的legacy认领、reset/delete或清理捷径。开发此命令的批准不等于未来真实换绑的用户确认。

## 错误 → 下一步

BLOCKED在stderr输出JSON，包含category、retryable、task累计attempts和read_attempts；不输出原始stderr/源码。retryable只是后续动作提示，绝不是自动send授权；task达到2次时false。

| category/证据 | 下一步 |
| --- | --- |
| unreachable，只读调用 | 原绑定内预算退避；耗尽停止报告；创建前不可达等一至两分钟再查原操作，不推断实例消失或未送达 |
| has_live_binding | 保留已有绑定，使用ensure核验；不另建终端 |
| create_unverified | 保留reservation/candidate，绝不再次提交；有精确candidate时仅继续只读核验，否则停止调查未知结果 |
| busy、锁占用、真实草稿 | 保留草稿，稍后只读核对原绑定；不清空输入、不换终端 |
| identity_changed | 停止发送，核对runtime/handle/incarnation；只有符合门禁且用户确认后才显式rebind |
| uncertain_send / creating | 保留intent/白名单receipt；消息可只读reconcile，创建按candidate规则核查；不重发、不finish、不换ID/目标 |
| not_sent且task还有次数 | 同ID同文显式send，重做verify/idle；第三次阻断 |
| integrity_failure、补丁缺页/截断 | 停止应用并报告；不拼接猜写或循环导出 |
| unsupported_contract | 缺官方契约，停止对应能力；不猜参数、不直接原生send绕过 |
| invalid_input / secret命中 | 缩小/修正白名单及文本；不回显secret，不放宽安全边界 |
| 模型safeguards拦截 | 按实际provider错误报告，停止；不换模型/身份/编码改写绕过 |

本锁只约束使用同一共享目录的新helper；旧窗口、手工操作或其他机器不受约束。旧窗口须重新读入口，不按空闲池继续派活。
