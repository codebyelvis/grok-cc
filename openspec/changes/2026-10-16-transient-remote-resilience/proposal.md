# Change: 增加安全的瞬时不可达恢复与补丁完整性保护

作者：elvis。

## Why

当前 send 在 Orca 调用前持久化 sending，非零退出、超时或无效回执后缺少安全恢复路径；NativeOrca 丢失结构化退出信息并固定 30 秒超时。补丁没有字节摘要，packet 没有专用外发渲染和内嵌 secret 扫描。

来源：用户提供的 `docs/review:requirement/grok-cc-optimize-prompt.md`。基线 `350ec30d2890deff7ce591f15c497e4b019b1f7f`，本地 make check 为 42 tests PASS、8 文件 manifest PASS；不是新行为验收。

## What Changes

- 结构化异常保留 returncode、timeout 与临时诊断信息；持久化/打印仅白名单、脱敏、限长摘要，不保留原始 stderr 或提示。
- BLOCKED JSON 区分 unreachable、busy、identity_changed、uncertain_send、invalid_input、integrity_failure、unsupported_contract；不把断连分类等同于未送达证明。
- 稳定消息标识和只读 reconcile；保留 uncertain，只有正面证据支持时推进 accepted/not_sent。已知未启动提交的本地失败允许相同 task/message/原文显式重试，仍须 verify/idle。
- 显式用户确认的 rebind，要求无 active_task/unknown intent，目标同 worktree、claude、auto、空闲且无其他 owner；归档旧绑定及任务到 history，不自动换绑或创建目标。
- list/read/wait 对限定瞬时错误做 2/5/15/30 秒封顶退避，默认总预算 300 秒，`--retry-budget-s` 可调；锁外查询/退避，重新加锁并重读/比对后才允许任何本地或远端写入。send/create 不自动重试；send 超时为 wait-submit + 45 秒。
- check 默认要求 PATCH_SHA256/PATCH_LINES，按原始 UTF-8/LF 校验；无有效元数据的提示回显不算真实补丁，多个有效候选拒绝。旧回复仅显式 `--allow-unhashed`，不能救回损坏的 hashed 回复。
- render 输出项目外 prompt，仅含 task_id、相对路径、任务、文件内容及必需的协议约束；不泄露 project_root/基线 sha。默认 120 KiB，报告字节与非权威 token 估算。
- prepare/render 扫描 AKIA、GitHub、sk、Slack、Tailscale token 和 private key 族，覆盖任务、路径及文件内容，命中只报位置。手工修改 packet 后 render 仍重查，不能绕过扫描。
- 更新 SKILL 与既有 references 内决策表；不增加载荷文件。版本为 `0.1.0.dev2`，只更新本轮已审查载荷哈希。

## Scope alignment

后续 change `2026-10-16-quota-saving` 依赖本 change，增加 prepare 前置预算、短回复、摘要及模型派发最多两次，最终版本顺延为 `0.1.0.dev3`。用户于本会话委托按分析后的推荐方案解决普通抉择；据此采用“模型派发最多两次，只读调用另按预算退避”，不等同于具体 OpenSpec 实现批准。

两项安全收紧：空闲且 cursor 无新输入不能证明未送达；消息标识回显不能单独证明 accepted。不确定发送继续 pending，不通过 finish/rebind/新 task/新终端绕过。

## Explicit limitations

- 禁止运行真实 Orca，离线检索未找到可确认的官方完整错误码、cursor 输入受理或 request retry 契约。不能假设 `remote_runtime_unavailable`、connection refused、host did not answer 证明未受理。
- 本轮仅实现可证明的本地未启动失败 not_sent、既有有效白名单 receipt 的恢复，以及证据不足的只读 reconcile 报告。远端错误自动判 not_sent、无 receipt 时凭标识推进 accepted、真正原生 `--retry-request` 提交均保持关闭；如暴露请求入口，必须在调用 Orca 前返回 unsupported_contract，不能猜命令。此限制必须在交付中列为未完成原始需求，而非完整 P0 PASS。
- 可选 collect 延后：缺少可核实的分页/来源完整性契约，不伪造完整回收。文档说明已有绑定只读回收及云端 jsonl 降级，Mac 不建 shell/终端，不发送导出消息。
- mock/临时文件/真实 Git 验证仅证明 helper 本地行为；真实远端发送恢复和长期连通未验证，本轮不以此宣称业务端到端验收。

## Impact

允许产品文件：两个 scripts helper、现有两个 tests、SKILL.md、两个现有 references、VERSION、bundle-manifest.json、CHANGELOG.md；README.md/README.en.md/docs/troubleshooting.md 仅同步本次受影响声明。治理文件：本 change、quota change、精简 CONTEXT.md 术语表及批准后的执行计划。

保持 registry schema 1，通过可选新增字段兼容旧记录；旧 sending 默认为 uncertain，旧完整回执在实际读取本行时做保守白名单投影，不遍历共享真实 registry。原 resilience/quota 范围不修改 AGENTS、bundle-files、Makefile、CI、安装器或其他工程；AGENTS 的 explicit-create 增量例外以以下批准范围为准。

## Approved scope amendment: explicitly confirmed terminal creation

用户于2026-10-18先批准explicit-create范围，随后明确回复“批准将‘原生 caller-key 去重’改为上述‘本地最多一次提交’保证”。本节及`specs/explicit-terminal-create/spec.md`是现行增量合同；原native-key版本的SHA256 `e1b3a1972f230667c8f48860a1bcc7c9a4d604142711c03cbbae4cd635a270c6`仅保留为批准历史，已由本次明确修订替代。现行spec SHA256为`52b3a9098c56c02596f5457f05ba69f67834aa9fa203d3f75ff3620e1a854c1d`。复用当前worktree/change，版本保持0.1.0.dev3。

- 新增helper `create --project <完整Orca worktree ID> [--confirm]`，复用真实owner、Mac project-root、environment及已选Orca；可选worktree必须与project一致。无confirm仅返回计划和同目标的有界脱敏清单，不创建state目录、lock或intent。ensure只验证已有绑定，不再首次隐式创建。
- 确认前必须无active task、uncertain消息或未核实create。仍有存活绑定拒绝创建；完整可达清单须正面证明原实例不存在。断连、列表不完整、runtime/身份漂移、busy或非auto不授权替代创建。不认领公共空闲窗。
- 在锁内保存稳定本地creation intent ID，完成文件fsync、原子替换和目录fsync后，再锁外调用一次已核实的官方terminal create。无论未启动、超时、非零或回执丢失，已保留intent均不得再次调用native create；重复确认/进程恢复只读原证据，不换ID或registry绕过未知。保存失败零native调用。
- 保证仅覆盖同一受管registry、真实owner和精确目标下本helper最多一次提交；不声称Orca原生跨客户端/跨registry去重或exactly-once创建。它不要求或猜测native caller-key参数。
- 有效回执只最小化保存精确候选身份，再用完整list及claude/live/writable/non-orphaned/idle/auto/空输入检查核验；核验后重锁、重读及比对原intent，再绑定并归档旧绑定/历史task。旧task身份及累计额度保留，其他owner更新不得丢失。
- 未核验或未知结果报告create_unverified，保留intent；有已保存精确候选时后续confirm仅恢复只读核验。回执完全丢失不按标题/时间/任意新终端猜归属。pending create继续阻止ensure/send/rebind及另一create；旧creating记录不因升级重置。
- 不可达提示等1–2分钟后只读调查原操作；不自动retry。AGENTS仅新增“不自动新建终端”，SKILL及原reference说明由用户选择rebind或create，不自动代选confirm。

官方本机1.4.227静态证据仍适用：terminal create公开worktree/command/shell/title/focus；handler将精确worktree和command交给terminal.create，回执可与list中的runtime/handle/incarnation/worktree核对。证据来源详见design.md；不执行真实Orca/Node、网络或远端探测。公共CLI缺少首次caller-key的事实保留，但按本次批准它不再是实施前置条件，不借内部schema、RPC或额外协调者绕过。

**现行状态：增量及本地最多一次提交修订已批准，待新Full Preflight；尚未实施/验收。** 新Preflight覆盖追加计划、当前spec及实际源码，旧计划hash/旧Review不覆盖新增边界。仅本地源码维护、隔离测试和独立Review获批；真实创建/发送、共享state、配置、安装、Git写入及发布仍未授权。实质范围或保护边界变化须重新审批，同范围工作持续推进。

## Approval and Delivery

原 resilience/quota 范围的历史批准：用户在原会话明确回复“批准”，ExitPlanMode确认通过；范围含统一计划列明的4项精度修订。旧 resilience worktree 只有一份未批准草案，没有产品实现；从其分支创建 `worktree-quota-saving-a8e9002d`，worktree `.claude/worktrees/quota-saving-a8e9002d`，原草案保留，当前合同以本 worktree 的两份提案为准，不自动覆盖旧草案。2026-10-18的explicit-create增量及本地最多一次提交修订以以上amendment为准。

严格验证两份 change 后提交一次具体合同批准；随后执行计划/独立 Preflight、分片 TDD、make check、独立实现评审及最终复核。未授权 add/commit/push/publish/install；不访问共享 state、不运行真实 Orca、不改配置/认证/模型/网络。遇未知文件漂移、关键测试失败或越界立即停写并报告。
