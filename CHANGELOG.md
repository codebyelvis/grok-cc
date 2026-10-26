# 变更记录

作者：elvis。

## 0.1.0.dev8 — 2026-10-26

- recover-final-reply 用 `diagnostic.kind` 区分 `timeout`、`handshake_failed`、`host_key_mismatch`、`jsonl_read_failed`。
- 主机密钥验证失败记为 `identity_changed`。SSH 已结束但搜索、权限或 JSONL 解析失败记为 `integrity_failure`，不再称为 SSH 不可达。
- 结果不回传远端 stderr、主机钥或命令输出，不改 known_hosts。屏幕片段仍不能批准。真实远端回收未验收，active Skill 未更新。

## 0.1.0.dev7 — 2026-10-24

- 新增 recover-final-reply：只读回收当前 bound、accepted 任务的 Claude 原生 JSONL 最终助手 text，保留正文原字节和来源元数据。
- 严格核验 SSH known_hosts 与可选指纹，禁用连接复用；候选歧义、父链不符、无 end_turn 或无 text 时拒绝，不拼 screen/stream，不重发或 finish。
- 项目外独占输出；空补丁合法，补丁摘要异常记为 false 并保留原文，仍须原 packet 与 Mac 验收。
- 仅集成本轮回收能力，不纳入安装侧前序 archive/retire/collect，不覆盖当前 active Skill 或运行状态。真实远端回收未验收。

## 0.1.0.dev6 — 2026-10-22

- 修复send与reconcile交错时只读evidence变化导致有效回执丢失；仅合并观察字段，真实intent/身份漂移仍阻断，不新增派发。
- CLI发送保留已审查prompt的CR/CRLF原字节；prepare/render/send共用450KiB传输上限、NUL及保留标记校验，默认预算仍为120KiB。
- 本地CLI使用自有进程组，超时和读取失败后的管道/子进程回收有界；不把本地退出视作远端未送达。
- 将安装版已有Grok controller、原生身份检查与父输出路径realpath兼容纳入源码和回归；Grok禁止在其他原生controller环境下换UUID使用。
- 已知绑定直接send，ensure保留为可选诊断；生产prompt明确最小文本diff，减少新增文件/脚本补丁的元数据格式失败。
- 发布与安装仍分别验证固定提交、八文件hash、入口和回归；不迁移registry、不更新native配置，真实云端业务验收单独取证。

## 0.1.0.dev5 — 2026-10-20

- 新预约用公开terminal create及完整命令`claude --permission-mode auto`，仅对新实例设置auto；不改Orca全局agentDefaultArgs或已有终端。
- 新terminal.create.claude-auto.v1无原生operationId/replay；reservation与精确handle先落盘，失败/丢失/不可核实结果保留pending，不重复创建。既有agent.launch.v2及legacy记录保留原有恢复边界，不迁移状态。
- 保留八个精确首次启动占位提示和显式draft拒绝，说明屏幕匹配的启发式限制；补充新路径、旧协议、可见标记不能代替受理及准确零落盘预览回归。
- 源码发布、本地安装和真实云端验收分别记录；本次不创建CC、不发送消息，也不处理既有pending。真实新实例验证须另行确认。

## 0.1.0.dev4 — 2026-10-19，源码候选

- 显式create改用Orca1.4.229公开agent launch，不带prompt或模型/设置变更；执行端版本、能力与runtime先核对。原生operationId及精确handle先落盘，再取得incarnation并执行原有Claude/auto/空闲/输入核验；structured聊天页保留pending。
- 只对已保存原生unknown/retrySafe/operationId，允许原目标、runtime、executable与cwd显式重放同ID一次；先持久计数、无自动重试。旧无ID pending跨升级保持原样，发送retry-request仍不支持。
- stdout JSON错误做白名单诊断与最小启动身份投影；原始message/stderr、launchRequest/cause/recoveryCommand不输出或入registry。新启动外层timeout为180秒，不将其视为历史故障根因。
- 在真实私有文件、锁、helper进程和外部Orca替身边界验证，保留原packet回归。本版本仅源码准备，未发布/安装，不代表真实云端通过。

## 0.1.0.dev3 — 2026-10-17

- prepare/render共用最终UTF-8 prompt默认120KiB预算与max-bytes，prepare写packet之前阻断过限；分别报告prompt/packet字节和明确粗估token。
- 生产prompt要求补丁外最多10行、不复述任务或贴完整日志；仍禁止云端项目测试冒充Mac验收。
- 可选handoff-summary仅汇总显式身份/白名单/测试状态计数，不执行测试、推断通过或写云端；最多15行、私有项目外输出，不包含源码/diff/secret。
- 媒体后缀默认拦截，allow-binary只放宽扩展名；实际二进制、明确媒体data URL及有限解码后命中magic的块仍拒绝，不承诺任意编码检测。
- main/合法格式export共享task累计两次提交上限，unknown继续pending，不能换ID绕过；只读次数另计。
- 独立实现Review发现后补回归修复：rebind归档task禁止重放、同目标不重置次数；finish/reconcile恢复累计计数；嵌套native/registry形状与创建身份安全阻断；ftyp需有效容器长度，避免误伤普通源码。
- 保留全部路径、基线、原字节与未知结果保护，未发布/安装，真实远端恢复和原生request retry/collect边界不变。
- 2026-10-18批准将显式create的原生caller-key要求改为本地最多一次提交：ensure取消隐式创建；create默认零落盘dry-run，仅用户选择目标后confirm。先持久reservation再一次native调用，回执candidate完整核验后才bound；未启动/丢失/损坏/核验失败不重提，保留旧creating与历史task保护。静态契约来自本机Orca 1.4.227公开terminal create；没有原生去重，不扩大为真实远端验收，VERSION仍为dev3。

## 0.1.0.dev2 — 2026-10-17

- 将Orca启动失败、非零、超时和无效响应分开；仅证明未启动才not_sent，远端未知仍保留intent；回执白名单与脱敏摘要取代完整响应。
- 只读查询/退避移出registry锁，重载后校验本owner快照，避免旧回执和整库覆盖；新增保守reconcile及用户确认的显式rebind，保留扁平history。
- 默认校验原字节PATCH_SHA256/PATCH_LINES，忽略无元数据的提示样板，但损坏/截断/重复hashed产物阻断；旧回复仅显式allow-unhashed。
- 增加安全render及prepare/render秘密扫描；保留UTF-8/CR/CRLF、白名单、基线、路径和真实Git检查。
- 已集成绑定消息/任务计数基础保护及生产prompt短回复约束；prepare前置预算、媒体门禁和handoff摘要由后续dev3完成。
- 官方远端未送达/request retry契约缺失，相关推断/原生重试保持关闭，collect延后；未执行真实云端验收、发布或安装。

## 0.1.0.dev1 — 2026-10-15

- 修复 UTF-8 补丁中的非 LF 字符被误当结构换行：换页符、分隔符、裸 CR 等在 hunk 内容中保持原字节。
- 修复 CLI 读取回复时的通用换行转换，保留裸 CR、CRLF 及既有 CRLF 结构头兼容。
- 任务标记按 LF 行识别，文件内容中类似标记的文本不再造成误拒；原有唯一/完整标记、白名单、基线、路径及 Git 校验仍生效。
- 新增真实文件、CLI prepare/check 与 Git 检查/应用回归；保持会话绑定及其他载荷不变。

## 0.1.0.dev0 — 2026-10-15，源码基线

- 将既有 grok-cc 的 8 个当前载荷文件按原字节整理为独立源码工程。
- 保留会话绑定、发送去重、未知结果保护、三种精确首次启动提示及 packet 校验回归，不重做已完成业务任务。
- 补齐中文工程说明、来源和许可说明、固定载荷清单/哈希、本地验证入口及 GitHub CI。
- 补齐中英文 README 和深色终端蓝图，提供单文件 HTML 与 README SVG。
- 保持既有 8 个载荷原字节，不新增派发/恢复/安装运行行为。

版本号描述源码工程准备状态；不能据此推断远端发布、本地安装或云端任务验收已经完成。
