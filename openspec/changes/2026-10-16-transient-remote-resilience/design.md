# 安全恢复与补丁协议设计

作者：elvis。

## Facts and non-goals

基线为 350ec30。`scripts/session_binding.py` 的 Registry 用 FD/no-follow/private mode/flock 原子保存，send 在远端调用前保存 sending，但异常不分类；_verify 混合身份与活性，ensure/send/finish 的网络查询均在锁内。`task_packet.py` 已有原始 UTF-8 字节、LF 分帧、路径/基线/真实 Git 检查，不能回退这些保护。

只使用标准库和既有 helper/tests。无新调度/运行状态框架。共享真实 registry、真实 Orca/云端、配置/模型/认证、安装及 Git 发布不在范围。

## 1. Remote result and persistence

NativeOrca 的结构化异常区分 timeout、launch failure、nonzero、invalid JSON/envelope，并保留 returncode/stderr 供同一进程内判定；不把它们原文传至输出或 registry。固定错误 category/detail 模板及可验证错误码组成脱敏摘要；未知诊断不输出原文。可安全重试与错误类别是不同维度。

回执保存字段仅 requestId、stages、processIncarnation、handle、runtimeId、accepted，保留字段类型校验，不保存任意嵌套对象。旧记录读取时保守提取同样字段，身份不匹配不恢复状态。临时异常不得携带完整 prompt 至打印/持久化路径。

消息新增 marker：`grok-cc-msg:<task_id>/<message_id>/<sha8>`。sha256 仍针对用户原文；wire 文本追加一次 marker，重试同 ID/原文生成完全一致文本。拒绝用户原文中伪造保留 marker 前缀，以免多个冲突标识。

状态保持兼容：sending 为未确认 intent；accepted 为有有效输入受理证据；not_sent 为已证明未开始提交。进程中断时 sending 始终未知。出现 accepted/stages/requestId 痕迹、subprocess timeout、解析失败、无效身份回执或远端非零，均不能仅据错误字符串改 not_sent。

可证明 not_sent 的最小集合是 subprocess 启动前的本地失败，例如 executable 根本未启动；不能把已启动的 CLI 连接错误误当此类。相同 task/message/sha 重试前重做 verify/idle；不同内容、关闭任务、其他未确认消息继续阻止发送。

## 2. Reconcile and explicit request retry boundary

reconcile 只针对已保存 task/message 与绑定身份查询；读取保存 cursor 之后的输出。返回本地消息状态、证据可用性和未推进原因；可以写本地恢复证据，不提交任何远端输入，不新建终端。

缺页、limited/truncated/screen、cursor 未证实、handle/runtime/incarnation 漂移、未知 marker 或仅 marker 回显均不能推进 accepted/not_sent。已有白名单 receipt 同时证明 runtime/handle/incarnation/requestId/accepted/input_accepted 时，可完成中断的本地 accepted 状态更新；仅空 stream/idle 不构成 not_sent。

缺少官方原生retry参数和幂等契约，本轮不提交原生retry。识别`send --retry-request`即在任何Orca调用前返回unsupported_contract、retryable=false，不先verify/list/read/wait。交付列为未完成原始要求，后续另行批准真实契约，不用mock自证官方能力。

## 3. Registry locking and concurrency

不在 registry 锁内 sleep 或等待 list/read/wait。读操作前取得最小行快照，释放锁，进行限定只读调用与预算退避，重新加锁加载完整 registry，比较 owner/目标/active_task/消息及身份修订。

任何相关漂移立即重新报告 busy/identity_changed，不继续使用旧引用。发送前必须在重读成功后原子落盘 sending，再执行一次不可自动重试的 send；发送回执写回只可更新该 intent，不能覆盖并发任务。create 仍先保存创建 reservation，未知结果不重建；跨进程创建、发送最多一次的既有测试继续有效。

正预算由本次命令整条只读链路共享monotonic deadline，不在嵌套调用重置300秒；等待2/5/15/30秒后封顶30，每次timeout不超过剩余正预算。失败分类不明不重试。预算0关闭自动重试，各必要查询只执行一次并保留有限timeout，不适用剩余正预算限制。send timeout=wait-submit（15秒）+45秒，create不自动重试。task累计提交次数与read_attempts分离，最多两次由quota合同定义。

## 4. Explicit rebind

命令必须提供 confirm-handle、confirm-incarnation，文档要求主控先取得用户对目标的确认；本轮开发授权并非未来真实换绑授权。不得自动选终端、扫描空闲池或创建 replacement。

仅已有 bound 行且 active_task 为空、没有 creating/sending/未知消息时允许；原终端不可达不自动触发换绑。目标必须在同一显式 worktree、agentIdentity=claude、connected/writable/non-orphaned，且通过 _idle 的 auto mode/真实空 composer 检查；目标不能被其他当前 owner 或 reservation 占用。返回字段保留 handle/incarnation/runtime/worktree/environment。

在锁内重新校验候选与 registry 无漂移后，将完整旧绑定/任务快照加入 history，再替换当前身份和空 tasks；历史不删除、不作为认领旧终端的权限。closed/uncertain/旧发送记录均保留，不提供 reset/delete/adopt。

## 5. Hashed patch framing

真实块为 BEGIN_PATCH + task_id、原始 diff 字节、PATCH_SHA256 + 64位小写hex、PATCH_LINES + LF行数、END_PATCH + task_id。diff 必须以 LF 结束；计数等于 diff 中 LF 字节数，CRLF 算一行，其他 Unicode/control 分隔符仍是 payload。hash 计算对象仅 diff，不含元数据或包围标记，不规范化裸 CR/CRLF。

模板用分段文字解释拼接标记，不将真实 task_id 插到完整 BEGIN/END 行里；CC 必须先把建议 diff 写到仅用于产物的临时文件，再用工具算 hash/行数，不能安装/测试/修改云端项目。文件写入仅为生成建议产物，不证明 Mac 代码通过。

从 LF 分帧的候选块识别元数据，恰好一个完整且 hash/lines 有效候选才通过。提示回显的无元数据样板不算候选；重复真实块、带 hash 但校验失败/截断的候选与任何其他有效块并存时 fail closed，不选择性忽略损坏产物。显式 allow-unhashed 仅适用唯一完整且没有完整性元数据的旧回复，不允许把损坏 hashed 回复降级。

之后继续 diff_paths、全部选定文件基线检查、路径/no-follow、真实 git apply --check 与二次基线检查；check 不写项目。packet JSON 显式 read_text(encoding='utf-8')，reply 仍 read_bytes().decode('utf-8') 保留原字节。

现行主 spec 的“所有标记必须全局唯一”需修改为“有效产物候选唯一”，其他既有保护保持；不能只加新 spec 而遗留矛盾合同。

## 6. Packet rendering and secrets

render 只使用本地 packet 已快照内容，不重读改变后的 Mac 源码，也不接受绝对/越界白名单。验证 schema、task_id、文件内容类型、sha 与内容一致、大小/路径及 UTF-8 文本边界。project_root 只用于本地安全输出校验，不进入 prompt。

输出使用既有 write_external_output：项目外、私有0600、no overwrite/no symlink。默认最大 120×1024 字节，以最终 prompt.encode('utf-8') 为权威；token_estimate 采用 ceil(bytes/4) 且明确仅粗估。prepare 预算前置与短回复约束由依赖 quota change 复用同一纯渲染函数，避免不同算法及协议模板漂移。

prepare 在任何 packet 写入前扫描任务、相对路径和文件内容；render 重新扫描相同来源，防止手工 packet 绕过。匹配要求的 secret 前缀及合理字符/长度，私钥头直接命中；只报经过安全限制的文件标签/行号，不输出命中字符串，也不通过文件名泄漏 token。scanner 不是无泄漏保证，人工审查不可替代。

## Learning candidate: task identity survives binding lifecycle

旧范围P1发现的工程不变量已机械固化在回归及现有reference；本卡只记录项目内证据，不新增全局规则，不把待批准create或整体完成当作已通过。

```yaml
status: candidate
event_kind: integrity
severity: high
scope: project-local
promotion_trigger: high-severity
symptom: Rebinding moved a completed task out of the active deduplication map and allowed a third submission.
prior_assumption: Keeping history was sufficient even if only the current tasks map enforced identity and attempts.
correction_or_evidence: The independent reviewer replayed the task after both replacement and same-target rebind; regression tests first failed and now reject archive replay and preserve no-op state.
generalized_invariant: A binding lifecycle change never resets the task identity or cumulative submission boundary.
independent_reproductions: Independent fixture probe and distinct author regression cases; neither is a real cloud acceptance claim.
independence_rationale: The reviewer did not implement the code and inspected actual production wiring before the author's repair.
duplicate_or_conflict_result: Existing no-reset and two-submission requirements are enforced; no new global workflow rule.
target_artifacts: scripts/tests/test_session_binding.py; scripts/session_binding.py; references/session-binding.md
mechanical_enforcement: required
mechanical_enforcement_reason: Deterministic archive/no-op/task-limit regressions reject the old implementation.
verification: Focused 54+35 and make check 89 passed; independent implementation recheck and separate old-scope Final Review passed, including this candidate evidence/boundary.
review_result: pass
decision_owner: user-approved local controller (claudex), not a schema-6 product claim
decision_provenance: Approved original resilience/quota contract and independent implementation findings; candidate/final closeout remains separate from pending create amendment.
```

## Approved amendment: explicit creation with local at-most-once submission

2026-10-18用户明确批准将原生caller-key去重改为本地最多一次提交保证。批准事实和现行spec哈希见proposal.md；此前Pending scope decision已获选择，原native-key合同仅为历史，不再阻塞本增量。旧范围89项/旧Implementation及Final Review不覆盖本增量。

### Official route and evidence boundary

本机Info.plist于2026-10-18复核为1.4.227。此前只读官方包的公开源码，未执行Orca/Node或读取配置/state：

- `/Applications/Orca.app/Contents/Resources/app.asar.unpacked/out/cli/specs/core.js:201-218`公开terminal create的worktree/command/shell/title/focus；`cli/args.js:204-223`拒绝未知flag。
- 同前缀`cli/handlers/terminal.js:100-136`要求remote create显式worktree，转发worktree及command等字段。既有helper使用该路径启动`claude --permission-mode auto`；environment/json沿现有_call传入。
- CLI没有native caller-key转发；内部clientMutationId/operationId等schema及worker-start仅恢复原请求的retry-request均不作为本helper调用入口。不手写RPC、不修改Orca、不另建协调者。

同一受管registry下本helper每个intent最多一次native调用；不保证原生跨客户端、跨registry或exactly-once创建。未知结果可能保持pending，即使实际没有创建；丢弃/切换registry、清理intent或换身份绕过未知仍禁止。

### Interface, inventory and eligibility

`create --project <完整Orca worktree ID> [--confirm]`复用controller/session-id/project-root/environment/orca；create的project是云端worktree，Mac project-root不可替代。若提供worktree，去除官方id:选择器前缀后须与project完全一致；active/current、缺失或不完整目标拒绝。非create命令拒绝create专属参数。

无confirm仅用FD/no-follow只读打开现有registry；不存在时视为空，不创建目录/lock/intent。通过完整terminal list核对目标；输出精确计划和至多20项同worktree白名单清单及总数/输出裁剪标记，不包含屏幕、prompt或原始native响应。输出限量不改变内部完整inventory核验。confirm重新取得当前事实，不能把旧dry-run当授权token。

先拒绝active_task、任一未解决消息或pending create。旧绑定存在时要求同runtime完整清单：精确原实例仍在则has_live_binding，临时断连为unreachable；相同handle但身份改变、runtime漂移、列表不完整均不证明原实例消失。仅完整清单中原handle确实不存在才可替代。其他owner终端只用于占用核验，不认领或挑选空闲窗。

### Durable reservation, candidate and binding

复用既有Registry原子保存/锁，不建运行状态框架，registry保持schema 1。只读快照与锁内重读必须比对同owner整行；远端调用/等待均不持锁。

1. 确认资格后重锁、重载并比对初始快照；保存state=creating、稳定creation_id和必要旧绑定快照，保留tasks与扁平history。既有creating记录无可信候选时直接create_unverified，不能升级为新intent。save完成文件fsync、replace、目录fsync后才允许一次native create；保存失败零native调用。
2. 已保留intent之后的任何native失败（含Popen未启动）、中断、超时、非零或损坏/丢失回执都不能再提交。失败仅返回安全create_unverified摘要，原intent保留；attempts仍沿原任务语义，不能把读取次数或create计入模型发送次数。
3. 回执只接受同runtime/精确worktree及非空安全handle/incarnation，先在锁内比对原intent和其他owner的bound/candidate占用并保存最小creation_candidate。此时不写bound。未知字段/屏幕/错误原文不落盘；candidate要求有效稳定creation_id，creation_previous/candidate读取时同样验证结构及owner/目标；previous任务/active必须与reservation一致，保留旧任务却缺快照同样阻断。畸形记录在native调用前fail closed。
4. 用保存的精确candidate做完整list和原_verify/_idle检查，包含claude、live/writable/non-orphaned、idle、auto、空输入/原精确启动提示。后续confirm只能对这份candidate重做只读核验；完全无receipt时保持pending，不按标题/时间/新终端猜归属。
5. 成功后重锁重载、比较同intent和目标占用，归档旧绑定的非递归快照并保留既有扁平history，再写bound。当前tasks重置仅在旧tasks已归档后发生，旧task身份及累计额度沿既有history保护。其他owner并发更新合并保留；旧回执/漂移不能覆盖新owner状态。

ensure无绑定时直接说明需用户选择rebind/create，不访问native create或创建state。creating/pending继续阻止ensure/send/rebind和另一create。已bound时create再次请求不得重复创建；已确认不存在且无pending/active后，另一次明确confirm才可建立新的不同intent。

### Implementation, tests and completion

沿用当前worktree、dev3、8文件载荷清单及原允许文件；AGENTS仅新增“不自动新建终端”一条。追加执行步骤位于原`docs/superpowers/plans/2026-10-16-resilience-quota.md`，原计划/旧Preflight不代替新增Full Preflight。任务进度继续记录本change tasks，不另建任务账本；Reviewer必须是实际独立Codex实例，Implementation与Final分阶段签收。

本轮已重放三个既有可行性回归：重复ensure、丢失create回执、真实多进程最多一次，3 PASS/0 skip；helper SHA256 `bab91e6f6f612fc5a360f8e3edf7f7bc40b44a0a12347d2ea785e0f000bcf35c`，tests SHA256 `d618bb75b4105538dfeaa05acbd8dc4f7f2d32879f6dd90b99e3d47ce30780ad`。它们不是新create实现验收。新增回归须先RED再GREEN，覆盖只读dry-run/ensure零落盘、实际CLI参数、确认核验成功、保存失败零调用、回执丢失/损坏/未启动不再提交、已保存candidate重入核验、并发/晚回执/其他owner、live/active/uncertain/旧creating、runtime/身份漂移、归档task去重及额度不重置。所有远端边界仅fixture，本地文件/锁/CLI是真实隔离调用。

完成增量须两组focused unittest、make check、两change strict和diff检查新鲜通过；独立Implementation Review后再做最终验证及单独Final Review。真实远端/安装/发布未验收，用户提供截图仅报告连接就绪，不能扩为新创建或端到端PASS。

## Learning candidate: validate creation evidence before state transitions

```yaml
status: promoted
event_kind: integrity
severity: high
scope: project-local
promotion_trigger: high-severity
symptom: A damaged saved intent could become bound; a reduced prior-task snapshot could permit a third submission, and another owner pending candidate could be claimed.
prior_assumption: Validating the returned create receipt was enough; saved intent and pre-create inventory needed no equivalent identity validation.
correction_or_evidence: Author RED/GREEN first reproduced four validation gaps; independent Implementation Review then reproduced prior-task loss, incomplete selector mutation and pending-candidate ownership conflict. Three further regression methods first failed and now enforce rejection and valid recovery.
generalized_invariant: Creation evidence includes a valid intent, complete inventory identities, preserved prior tasks and exclusive saved candidate ownership; invalid evidence never authorizes reservation or a binding transition.
independent_reproductions: Author regressions and distinct reviewer filesystem/CLI fault probes independently exercised prior-task loss and ownership conflict.
independence_rationale: The independent reviewer did not implement the code, inspected the complete diff and reproduced the safety failures using real isolated Registry and CLI paths.
duplicate_or_conflict_result: Implements the existing fail-closed creation contract; no new global rule or runtime publication.
target_artifacts: scripts/tests/test_session_binding.py; scripts/session_binding.py; references/session-binding.md
mechanical_enforcement: required
mechanical_enforcement_reason: Deterministic candidate, inventory, selector, prior-task preservation and other-owner reservation regressions reject the prior implementation and retain pending evidence without another native submission.
verification: Three Review findings first reproduced under RED; binding 77 plus packet 35 and make check 112 passed. Independent Implementation attempt 2 reran all original fault probes and make check 112, 8 payload, both strict and diff checks with no open findings; report SHA256 d5777701b6b14c63341e8b2101c1d420714e902393a71dc390f193c60ba7f248.
review_result: pass
decision_owner: codex
decision_provenance: Bound Codex control-plane accepted the actual source and evidence hashes after independent Implementation PASS. Project Learning Closeout promotes only the already-reviewed project reference and deterministic regressions; no global Skill or installed runtime changes. Separate final verification and Final Review remain required.
```

## Verification and delivery boundaries

每片先在既有 tests 添加失败回归，确认失败原因后最小修复。真实临时 state/project、flock/并发 CLI 和 Git；仅远端边界 mock，退避使用假时钟不真实等待300秒。独立评审必须检查生产调用链和负向场景，不能仅看绿色单测。

验证：两组 focused unittest、make check、两个 change 的 openspec validate --strict、git diff --check。载荷先 verify 基线8文件，无未知漂移再对本轮白名单改动更新 manifest；后续 quota 顺延版本。rollback 仅针对本 worktree 的已知改动人工反向补丁，不 reset/clean、不触碰用户原有文件。缺官方契约的能力不列PASS；真实远端验收明确未执行。
