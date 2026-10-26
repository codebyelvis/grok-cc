# Mac 会话与云端 CC 的固定绑定
作者：elvis

每个真实本地会话只有一个当前绑定CC，不扫描公共空闲池。owner由产品名及真实原生会话ID组成；项目、环境和云端worktree固定。切项目不生成替代绑定，身份变化不自动换窗。

## 调用与证据

先按版本匹配的官方orca-cli发现环境/worktree。每条helper命令使用相同`--controller`、`--session-id`、`--project-root`、`--environment`、`--worktree`、`--orca`。worktree必须是完整repoId::path，可带id:前缀。Codex读取真实CODEX_THREAD_ID；Claudex传入入口原生渲染的ID，不用未导出的shell变量或随机值替代。Grok CLI固定用`--controller grok --session-id <真实UUID>`，不读取或猜测环境变量；若存在Codex/Claudex原生环境则拒绝选择Grok。claudex须与存在的CLAUDE_SESSION_ID一致，仅有Codex环境时拒绝；ID等于其他controller原生环境变量时拒绝。省略controller只在恰有一个已知原生环境变量时推断，否则要求显式选择真实宿主。旧codex/claudex绑定键不变，不进行会话映射。[官方替换说明](https://code.claude.com/docs/en/skills#available-string-substitutions)。

```text
python3 <skill-dir>/scripts/session_binding.py identity --controller codex
python3 <skill-dir>/scripts/session_binding.py send <相同参数> --task-id <task_id> --text-file <项目外已审查prompt>
python3 <skill-dir>/scripts/session_binding.py reconcile <相同参数> --task-id <task_id> [--message-id main]
python3 <skill-dir>/scripts/session_binding.py finish <相同参数> --task-id <task_id>
```

正常运行持续复用默认共享状态目录`~/.local/state/grok-cc`，不能另建state-dir绕过约束；开发回归仅用临时`--state-dir`及Orca替身，不操作真实共享目录。状态是本helper的私有数据，不是Claude/Codex原生配置，不同步远端。只保留绑定/任务摘要、cursor、意图、尝试次数和白名单回执，不保存源码prompt、屏幕正文或原始诊断。

已知绑定和精确目标时直接send；不需要先ensure，正常路径少一次重复list。可选`ensure <相同参数>`仅诊断已有绑定，不创建；无绑定时不落盘，要求先展示目标并取得用户对换绑/新建的明确选择。它不证明CC就绪或模型完成。send自身验证runtime/incarnation/worktree/agent、auto mode、真实空composer和空闲。首任务前仅允许已核实的精确空启动提示，其他草稿/未知屏幕继续保留并阻止发送。

send按原字节解码已审查UTF-8 prompt，不转换CR/CRLF。prepare/render与send共用450KiB传输上限、NUL和保留串检查；预算override不能放宽传输边界。保留串出现在普通源码中同样拒绝，需本地处理相关内容，不能编码绕过。

## 显式创建与本地最多一次提交

不自动新建终端。先只读展示计划与同项目终端；没有真实任务或没有用户对具体目标的创建选择时，停在dry-run，不能因任务紧急、通用自主授权或ensure无绑定而追加confirm：

```text
python3 <skill-dir>/scripts/session_binding.py create <相同会话与目标参数> --project <完整云端worktreeID>
```

`--project`为已发现的完整`repoId::path`，可带`id:`前缀；Mac根目录仍由`--project-root`指定。可选`--worktree`须与project相同；其他命令不接受project/confirm/retry-launch。无confirm只读现有registry、完整native list和status，返回claude/所需auto/精确worktree位置计划、至多20项白名单inventory、同项目总数及限量标记；不创建状态目录、lock、intent或终端，不按空闲程度认领目标。

只有用户明确选择该目标的新建后，才可执行同一命令加`--confirm`。确认时重新核对当前事实：无active任务、无未解决消息和creating；已有live绑定返回has_live_binding。替代创建须在相同runtime完整清单中证明原实例确已消失；列表缺页、缺失/重复handle、身份漂移、临时断连、busy或非auto都不能证明消失。不可达先等一至两分钟再核查原操作。

执行端status须报告相同runtime、ready/reachable、正式版本≥1.4.229，以及既有`agent.launch.v2`、`agent.launch.replay-required.v1`、`agent.launch.local-presentation.v1`三项能力。保留此保守预检；缺失、旧版本、预发行版或status/list身份不一致时不预约、不启动，不在两种协议间自动回退。

helper在锁内重读/比对后，以fsync/replace/目录fsync持久保存稳定creation_id、state=creating与creation_launch上下文。新预约记录`terminal.create.claude-auto.v1`，锁外只调用一次公开`terminal create --worktree id:<完整ID> --command "claude --permission-mode auto"`。绝不传裸`claude`，否则Orca可能用全局agentDefaultArgs改写；仅新实例获得auto，不改全局配置、模型、账号或现有终端。原生进程使用已保存的可执行文件实际路径和规范化Mac项目目录；terminal create沿用有限30秒外层预算，既有agent launch为180秒。保存失败零调用；没有自动变异重试。不保证跨客户端/registry或exactly-once，不得删除、切换state目录或换身份逃避pending。

新路径只从同runtime的`result.terminal.handle`保存最小terminal outcome，不保存operationId/retrySafe、prompt或原始响应；该原生路径没有replay账本，未启动、失败、超时、丢回执或身份不可核实时保留creating，不再创建。已有`agent.launch.v2`预约不迁移，继续按旧协议保存最小operationId和outcome.kind/handle；structured返回unsupported_contract并保持pending，不对它调用terminal send。两种路径均仅从同runtime完整清单中精确handle对应的Claude取得incarnation，再保存creation_candidate。已保存handle但尚无candidate时同样占用目标，其他owner不能认领。

候选仍须核对connected/writable/non-orphaned、idle、auto和空输入/精确首次提示，成功后重锁比对并绑定。非auto或真实草稿保留pending，不为通过检查修改权限/输入。精确首次提示仅为Claude Code 2.1.303原生空输入占位集合（含`create a util logging.py that...`等），且Orca screen读未报告draft；helper拒绝已报告的draft，其余依赖屏幕精确匹配启发式，不构成原生空输入证明。光标隐藏且真实输入与提示逐字相同时仍可能误判；该限制在原有5条提示中也存在。任何集合外Try文本仍拒绝。Orca 1.4.229 `agent launch`无每实例权限参数，Claude参数来自Orca全局设置agentDefaultArgs（缺省claude为`--dangerously-skip-permissions`，即bypass）；helper不改全局设置、不按键切换，bypass候选保持pending。旧绑定及任务归档，历史task身份与累计提交额度继续有效。回执不是绑定成功证据。

恢复前须核对creation_previous的任务及active状态与reservation保留内容一致；带旧任务却缺少快照、任务缩水或状态不一致均保留原文件并阻断。其他owner已经持久保存的精确candidate也占用该目标，在接收候选、恢复核验及最终绑定时都不能认领。

一旦reservation持久化，即使原生进程未启动、超时、回执损坏/丢失，也不能重新启动。后续同目标confirm只继续已保存精确回执/candidate的只读核验；未保存任何精确回执且没有下述原生重放证据时保持pending，不根据标题、时间或新终端猜归属。pending仍阻止ensure/send/rebind；finish也不能解锁它。

## 显式启动重放

仅适用于既有`agent.launch.v2`预约。只有helper从该协议原生stdout JSON错误取得`agent_session_operation_unknown`，且其data明确包含`launchOutcome=unknown`、布尔`retrySafe=true`及合法operationId时，才持久保存重放依据。新terminal-create协议不能取得此权限。ID必须来自这一固定结构，不从错误散文、stderr token、recoveryCommand或任意嵌套字段提取，不在本地生成。creation_id是本地预约ID，不能用作原生operationId。

用户明确选择对这一次未知启动重放后，使用同一组create参数：

```text
python3 <skill-dir>/scripts/session_binding.py create <相同会话与目标参数> --project <原完整云端worktreeID> --confirm --retry-launch <已保存原生operationId>
```

只允许一次显式重放，helper先检查保存的协议/ID、无已知成功结果或candidate、无active/unknown消息、原owner/project/worktree/environment/runtime/executable/cwd及完整清单/执行端能力，再持久消耗replay_attempts，才给同一`agent launch`附加`--retry-launch <同ID>`。同时调用也不能重复重放；fsync失败零重放调用。即使本地调用失败，次数也不能重置。native负责同ID的启动账本；helper不把重放变成新启动。

重放仍未知、过期、返回不同ID或身份漂移时保持pending，不删除ID、不重放第二次，也不去掉retry-launch重启。已知terminal回执只继续只读核验；已知structured结果禁止重放。**旧pending没有operationId时，升级后即使ready、清单为空，也不能套用此入口**，不补造creation_launch。此能力不是发送重试；`send --retry-request`继续阻断。

BLOCKED可返回diagnostic（本地枚举kind、started、有限returncode/timeout、已知code）及最小launch身份/replay_available提示，后续恢复保留安全原因。原始message/stderr、launchRequest、cause、恢复命令、配置及源码不输出、不落registry；提示可重放不等于用户已授权。

## 状态、次数与恢复

- main是同一task首次开发消息。重复相同task/message/原文，对accepted或sending只返回resume，不再提交；不同文复用同ID拒绝。消息附加稳定grok-cc-msg标识，仅用于关联，不是受理证明。
- task累计最多2次模型提交，main、显式重试和合法export共用。每message另留计数去重；accepted重复resume不增次数。不能换export-N/task_id绕过未知结果或总额。
- 仅有正面证据证明Orca子进程根本未启动，才标not_sent；同ID同文显式再调send也必须重新verify/idle，并有剩余额度。远端非零、timeout、已受理痕迹或无效回执保持sending/uncertain；remote_runtime_unavailable不等于“没送到”。
- main已accepted且没有未知结果、还有一次额度时，用户明确要求的格式修正可用`--message-id export-1`只重导出既有最终补丁；不重新开发、不索要内部推理，不用于绕过模型拦截或丢失内容。未知/截断/缺页先停止报告，不能连续发导出消息。
- 保存/返回的receipt仅含requestId、stages、processIncarnation、handle、runtimeId、accepted。旧schema-1 intent保持保守兼容，无计数的旧发送至少按1次处理，旧完整回执仅做白名单投影。
- input_accepted不是执行完成，tui-idle不是成功回复。补丁必须完整读回、hash/原packet检查、Mac测试与独立Review通过。

`reconcile`只向既有绑定查询保存cursor后的输出，可写本地证据状态，绝不send/create。marker回显、终端空闲或没有新输入不能证明accepted/not_sent；source=screen、limited/truncated或身份不符不能解锁。已有同身份有效白名单receipt证明输入受理时才可恢复accepted；证据不足保持原状态并说明原因。

发送回执返回时，允许并发reconcile更新既有消息的evidence，保留这些观察后保存回执；其他绑定/任务/消息字段必须仍与持久intent一致。观察本身不证明受理，也不允许覆盖新的attempt、内容、次数或身份。

本开发版本未取得官方原生request retry的精确契约；`send --retry-request`在任何Orca调用之前返回`unsupported_contract`，即使已有requestId也不猜命令。此能力尚未实现，不通过手工terminal send绕过。

`finish`要求当前task无未知发送且原CC空闲，保留绑定及任务历史，返回project_pass=false；它只是释放派活占用，不是项目验收或清理。creating/unknown不能finish、重建、reset或delete。

## 只读退避

status/list/read/wait仅对限定瞬时错误按2、5、15、30秒（之后封顶30）退避；默认`--retry-budget-s 300`。正预算由一次helper命令整条只读链共享，不在verify/idle内部刷新；每次调用timeout不超过剩余预算。0关闭自动重试，各必要查询仍仅调一次且有有限timeout。read_attempts与模型提交attempts分开，不把只读轮询混为模型工作量。

原生CLI在独立的本地进程session中运行；超时或读取失败只终止该次自有进程组，并使用有限的管道/子进程回收窗口。该本地清理不证明远端任务停止或未受理，仍保留unknown，不能据此重发。

只读查询和sleep不持registry锁；重新加锁后重载并核对相关owner/目标/task/intent，漂移停止，不能用旧整库覆盖其他owner更新。send/首次launch/显式重放分别先在锁内原子记录意图，再单次调用；send的子进程timeout为wait-submit +45秒（当前60秒）。预算到期仅报告，不切身份、开终端或重启网络。

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
| create_unverified | 保留reservation/回执/candidate；已知精确handle仅继续只读核验；仅符合显式启动重放全部门禁才可同ID重放一次，旧无ID继续pending |
| busy、锁占用、真实草稿 | 保留草稿，稍后只读核对原绑定；不清空输入、不换终端 |
| identity_changed | 停止发送，核对runtime/handle/incarnation；只有符合门禁且用户确认后才显式rebind |
| uncertain_send / creating | 保留intent/白名单receipt；消息可只读reconcile，创建按candidate规则核查；不重发、不finish、不换ID/目标 |
| not_sent且task还有次数 | 同ID同文显式send，重做verify/idle；第三次阻断 |
| integrity_failure、补丁缺页/截断 | 停止应用并报告；不拼接猜写或循环导出 |
| unsupported_contract | 缺能力/版本、structured聊天页或发送retry缺契约，停止对应能力；不改配置或直接原生命令绕过 |
| invalid_input / secret命中 | 缩小/修正白名单及文本；不回显secret，不放宽安全边界 |
| 模型safeguards拦截 | 按实际provider错误报告，停止；不换模型/身份/编码改写绕过 |

本锁只约束使用同一共享目录的新helper；旧窗口、手工操作或其他机器不受约束。旧窗口须重新读入口，不按空闲池继续派活。


## 缺页最终答复回收

作者：elvis。stream 缺页或 screen 裁剪时，可对当前 owner 已受理的任务只读回收 Claude 原生 JSONL 的最终助手文本：

```sh
python3 <skill-dir>/scripts/session_binding.py recover-final-reply \
  --controller codex --session-id "$CODEX_THREAD_ID" \
  --task-id <已有任务UUID> --message-id main \
  --ssh-host 100.84.23.115 --ssh-user box \
  --out /private/tmp/<唯一输出前缀> \
  --expected-host-fp <可信ED25519的SHA256指纹>
```

`--session-id` 是本地主控原生会话 UUID，不是云端 Claude sessionId。Codex 必须有当前原生 `CODEX_THREAD_ID`；Claudex/Grok 使用既有 `resolve_owner` 规则。当前 binding 必须为 bound，task 必须已存在，目标 message 必须 accepted 且 receipt 的 handle/runtime/incarnation 与 binding 匹配。不创建锁文件、不写 registry，不调用 create/send/finish/rebind；默认完全不调用 Orca，结果 `inventory_checked=false`、`handle_absent_in_inventory=null` 表示未查询，不推断实例存活。

SSH 默认 IP `100.84.23.115`、用户 `box`，使用 BatchMode、StrictHostKeyChecking=yes、UpdateHostKeys=no 和 ED25519，禁用 ControlMaster/ControlPath 连接复用。指定预期指纹时先核 ssh-keyscan 展示值，再核 SSH 握手指纹；keyscan 不写 known_hosts，也不能替代 known_hosts 信任。主机密钥验证失败（指纹不符、未知主机，或 SSH 退出码 255 且 stderr 表明 host key verification 失败）为 `identity_changed` / `host_key_mismatch`，不得自动删除或接受主机钥。连接或认证未完成是 `unreachable` / `handshake_failed`，子进程超时是 `unreachable` / `timeout`。SSH 已返回非 255，但搜索、权限或投影解析失败是 `integrity_failure` / `jsonl_read_failed`。这些结果只含固定 kind，不含远端 stderr、主机钥或命令输出。屏幕片段仍不能批准。主机更新后的可信指纹由用户另行提供，不把短期指纹写成永久信任。

远端在 `~/.claude/projects/` 用 `rg -l --fixed-strings` 搜索 task（覆盖 hello）。user/assistant 只投影定位字段和 text，丢弃 thinking/tool_use/tool_result 正文。其他记录只保留 `type`、`uuid`、`parentUuid`，不传 message、attachment 正文、文件快照或其他字段，供父链穿过这些中间节点。用已接受消息的 `grok-cc-msg:<task>/<message>/<digest前8位>` 定位最后相关 user 轮；旧无标记 prompt 只有原文 SHA 与已保存消息一致才接受。相同 promptId 的纯 tool_result 续轮不切断轮次，其他 user 轮切断；最终 assistant 必须 end_turn、有非空 text，且 parentUuid 父链必须回到选定 user；回到另一条 user、中间 uuid 缺失或成环仍拒绝。并列最终分支拒绝。按原序直接拼接 text，不插入换行，不拼 screen/stream，不因模型拦截重导出。

多个相关 JSONL 时仅在 binding 确有数字型 `handle_created_at`、且只有一个 session-env mtime（缺失时用 JSONL mtime）落在创建时间前后 300 秒内才选择；缺少该字段或仍歧义返回候选 sessionId，绝不把 incarnation 字符串猜成创建时间。当前旧 binding 通常没有该时间字段。读取中 JSONL 变化、JSON 损坏、无 end_turn 或无 text 均失败。

`--out` 是前缀，父目录必须已存在、逐级无 symlink，且位于 binding 保存的 Mac 项目外；macOS `/tmp` 别名拒绝，使用 `/private/tmp`。省略时生成 `/private/tmp/grok-cc-final-<task>-<随机值>`。独占创建 mode 0600 的 `<out>.txt` 和 `<out>.meta.json`，不覆盖已有文件。meta 包含 sessionId、助手 uuid、stop_reason、text 块数、正文 SHA256/UTF-8 字节数、binding 身份、task/message、远端 JSONL 路径及补丁标记计数。

成功 stdout 为 `action=recovered`，导出正文成为本次回收真值。补丁 SHA/LF 数校验仅是元数据：空补丁允许 SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`、PATCH_LINES 0；标记/摘要异常仍导出原文并记 `patch_sha_ok=false`，无标记为 null。此校验不证明 diff 可应用，仍须原 packet 白名单、基线、Mac 验证与适用 Review；回收不等于 finish，也不改变 finish 的活验门禁。

| 回收错误 | 处理 |
| --- | --- |
| invalid_input | 原生身份、binding/task、输出路径或参数不合法；不创建回收文件，不改绑定。 |
| uncertain_send | 目标消息未 accepted 或缺匹配 receipt；保留 intent，不重发。 |
| identity_changed | 指纹不符、主机密钥验证失败（kind=`host_key_mismatch`），或回收期间绑定变化；保留 known_hosts/registry，由用户核验。 |
| unreachable | 握手未完成（kind=`handshake_failed`）或子进程超时（kind=`timeout`）；报告实际阻碍，不自动修复。 |
| integrity_failure | SSH 已完成但搜索、权限或投影解析失败时 kind=`jsonl_read_failed`。候选歧义、缺失/损坏/变化、无最终 text/end_turn、父链回不到已受理 user 仍拒绝；不猜正文。 |
