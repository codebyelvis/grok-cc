# 故障定位边界

作者：elvis。

## 启动提示与草稿

当前 helper 已核实这些精确原生启动提示，仅在无任务历史时允许：

- `Try "edit <filepath> to..."`
- `Try "fix typecheck errors"`
- `Try "refactor <filepath>"`
- `Try "write a test for <filepath>"`
- `Try "how does <filepath> work?"`
- `Try "fix lint errors"`
- `Try "how do I log an error?"`
- `Try "create a util logging.py that..."`

仍须通过原绑定身份、auto mode、空闲、真实 screen 和无显式 draft 检查。相似文本、真实输入或历史任务后的提示继续阻止派发，不要清空输入或改成匹配任意 `Try`。

若出现新的原生占位提示，先只读保存必要的 composer/状态证据，确认没有实际草稿，再按适用变更规则添加准确兼容及失败回归；不要边试边发送。

## 网络与回执

远端不可达不表示 Claude 进程退出。保留 handle、incarnation 和原回执；不重启代理、Tailscale、Orca 或 CC 来代替定位，不另建终端。

`ensure`无绑定时也不创建；先用`create --project <完整云端worktreeID>`只读展示目标和计划，用户明确选择该目标的新建后才可加`--confirm`。已有live绑定阻止新建；不可达先等一至两分钟核查原操作，只有相同runtime完整清单证明原实例消失、无active/unknown且用户确认后才可替代创建。

新创建先持久保存reservation，再按Orca≥1.4.229公开`terminal create --command "claude --permission-mode auto"`启动Claude，只作用于该实例，不传裸claude或prompt、不改全局设置。新协议只保存精确handle，没有operationId/replay；失败或丢回执保持pending，不能再新建。已有agent.launch.v2预约保留原协议及原生ID重放门禁。两种路径均从完整清单取得incarnation；非auto或草稿不能通过，旧structured结果保持pending。版本、能力和status/list runtime不一致时不启动，不自动换协议。

宿主 status 的能力列表不等于 Mac CLI 提交的 client capability。列表里已有 `agent.launch.v2`，仍可能在 operationId 出现前被拒绝。没有 operationId 时保持 unknown，不重放，不改记为无副作用，不再新建。查看能力时用完整列表；只看前几项会像是缺失。不在本仓库里改 Orca 安装包。

不带已保存 `--environment` 的 status 或 read 可能命中另一个 runtime。已绑定 handle 出现 stale 时，先用同一 environment 再读，不新开终端。

屏幕上的完整回答、结束标记、`tui-idle` 和空 stream 都不能把 `sending` 收成 accepted。没有保存 receipt 时不要重发。提问回显里可能先出现标记；可见正文从回答起到最后一处标记，这只是可见证据。

未知回执保留create_unverified；重复confirm只继续已保存精确回执/candidate的只读核验，不猜终端归属。只有已保存原生unknown+retrySafe+合法operationId，且用户选择重放时，才按[显式启动重放](../references/session-binding.md#显式启动重放)在原host/cwd/executable附加同ID，限一次且先落盘计数。没有ID、legacy creating、过期/再次未知、runtime变化都不能重新启动或换ID。损坏intent/candidate或缺失/重复清单身份不能证明消失，不删除/切换state绕过。

BLOCKED的diagnostic仅含安全枚举与有限退出码/timeout，launch只含最小身份与replay_available；不回显原始错误。原生JSON错误位于stdout，不能只从stderr判断受理状态。进程timeout不等于远端未受理；调整为180秒只是新协议的外层预算，不证明历史故障来自超时。

accepted/未知的同 task/message/文本调用只恢复已有记录；仅证明子进程未启动才可 not_sent 同文显式重试，task 累计最多2次，含合法格式导出。`sending` 仍表示未知，不能删除 registry、改 task_id、换终端重试。新增 reconcile 只查既有绑定/cursor，marker回显、空闲/空流不证明未送达；显式 rebind 只在无active/unknown且用户确认精确目标后执行，归档旧绑定，不自动换绑或reset。

status/list/read/wait在命令共享默认300秒预算内退避，read_attempts与模型提交attempts分开。send/launch不自动重试。BLOCKED JSON区分unreachable、busy、identity_changed、uncertain_send等；retryable不是自动提交授权。原生发送request retry缺官方契约，任何Orca调用前unsupported；完整[错误→下一步决策表](../references/session-binding.md#错误--下一步)。

## 精确会话与完整产物

`session_not_reported`、`sourceExact` 和 `contentComplete` 表示不同事实。精确来源不保证正文完整；按当前 Orca 的实际 guide 和 clipping/warnings 决定是否可读回。

一次 Orca 1.4.224 排障中，`worker-read` 的 transcript 文本块在 1,200 字符后追加截断提示，增大消息条数限制不能补回同一块的剩余正文。这是已观察的版本边界，不保证其他版本同样实现。本仓库没有修改第三方二进制或添加完整导出接口。

缺少 `END_PATCH`、hash/行数不符、丢失历史或 TUI 空格无法确定时停止应用，不猜补丁、不连续发送导出消息。check默认要求PATCH_SHA256及按LF计数的PATCH_LINES，保留CR/CRLF原字节；`--allow-unhashed`只接受完全无完整性元数据的唯一旧产物，不能挽救损坏hashed块。用户经可靠渠道提供完整当前补丁文件时仍须原packet检查；传输不代替基线、测试与Review。transcript缺必要token时报告不可用；云端jsonl仅可由获授权的云端侧既有只读渠道回收，Mac helper不新建shell/终端，本版collect延后。

## 外发预算与秘密扫描

prepare/render默认限制最终UTF-8 prompt为120KiB，token数仅粗估；过限先缩小白名单。secret命中只报安全位置，不回显值；扫描不保证所有秘密都能识别。媒体先变必要文字摘要，`--allow-binary`仅放宽扩展名，不允许二进制或已识别编码媒体。summary只取显式证据，不执行测试，不能从task_id生成通过结论。

## 模型拦截

按实际 provider 错误报告。`reasoning_extraction` 标签不能单独证明请求违规或上下文过长；不换账号/模型、编码请求或连续改写绕过拦截。详见 [最终补丁说明](../references/final-patch-prompt.md)。

## 验证声称

本地 suite 检查 helper 与 packet 行为，不证明远端服务持续在线、真实模型回复、业务源码通过，或云主机能 7×24 不休眠。分别记录 source 准备、远端发布、active Skill 安装和实际业务任务结果。
