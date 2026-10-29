---
name: grok-cc
description: "Use when the user asks Codex, Claudex, or Grok CLI to delegate a concrete local Mac development task to Claude Code on the Grok Bot cloud computer."
---

# Mac 项目 → Grok Bot Claude Code

Mac源码是真值，云端`hello`不会看到Mac文件。Codex/现有Claudex负责必要上下文、固定绑定、补丁核对和Mac验证；云端CC只根据所给快照提出建议。作者：elvis。

遵循项目AGENTS、变更批准和独立Review。本Skill不授予提交、发布、配置、安装或实际换绑权限；不用重新安装/登录或修改Tailscale、Orca、模型、代理、认证。

## 1. 最小任务与安全prompt

先读适用规则、源码和用户改动，确定一个task_id、最少白名单及Mac验收条件；首轮先小，跑通check/apply/本地测试后再扩大。缺真实任务只查状态，不发送占位符。

packet/reply/checked.patch/prompt始终放项目外私有目录，不覆盖既有文件。允许/tmp等父目录别名，解析后仍须在项目外。packet含Mac来源和基线，只留本地，不能用云端内容替代；外发只用render结果并人工审查，发送保留其UTF-8原字节及CR/CRLF。

```text
python3 <skill-dir>/scripts/task_packet.py prepare --root <Mac根目录> --file src/labels.py --task '具体需求与Mac验收条件' --out <项目外>/packet.json
python3 <skill-dir>/scripts/task_packet.py render --packet <原packet.json> --out <项目外>/prompt.txt
```

prepare/render共用最终prompt默认120KiB预算，报告字节及粗略token估算；超限先缩小白名单，不打包整仓。明确审查后可用`--max-bytes`调阈值，但450KiB传输上限及文件/总量/安全限制仍有效。prepare/render和send均拒绝NUL及保留串`grok-cc-msg:`，包括源码中的同名字面量；遇到此限制在本地处理该文件，不编码绕过。助手扫描常见secret并仅报安全位置，不保证识别所有秘密：**不发送凭据、native配置、会话、历史、日志、hooks、密钥或完整依赖目录**，不同步Mac/云端登录。

截图、视频、扫描件不进入CC对话，先用已有合法本地/云端CLI得到必要文字摘要，再作为任务说明。prepare默认拒绝媒体扩展名；`--allow-binary`只放宽扩展名，绝不允许真实二进制、NUL、非UTF-8或已识别编码媒体，不自动转码/编码。

生产prompt要求：补丁块外最多10行结论，不复述任务、不贴完整日志；已有日志只报路径/计数并标非Mac验收，不诱导云端项目测试。补丁采用`---/+++/@@`最小unified diff，新文件旧路径为`/dev/null`；不输出`diff --git`、index或mode元数据。统一模板、临时diff工具计算及hash协议见[最终补丁请求](references/final-patch-prompt.md)：开头/结束分别由BEGIN_PATCH或END_PATCH、空格、单独给定的task_id拼接，不在prompt中展开带真实ID的完整标记行。diff后、结束前必须有PATCH_SHA256及PATCH_LINES，计算对象仅原始diff字节及LF数，不含元数据。

## 2. 固定会话后一次提交

先加载当前可执行文件提供的官方orca-cli guide，按对应--help发现环境/worktree；以下仅示意，参数放子命令后，不猜不支持的参数。

```text
orca status --environment 'Grok Bot' --json
orca terminal list --environment 'Grok Bot' --json
```

同一本地会话持续使用一个绑定CC，不扫描空闲池或直接agent launch/terminal create/send绕过helper。**不自动新建终端**；任务授权、时间压力和“自行推进”都不能代替用户对具体创建目标的明确选择。

- Codex使用当前CODEX_THREAD_ID，helper可读取；不能以外部UUID覆盖。
- Claudex本次原生渲染ID为`${CLAUDE_SESSION_ID}`，须作为`--session-id`传入。它不是shell环境变量；未取到真实ID或仍是占位符即停止，不用PID/目录/随机值替代。
- Grok CLI使用`--controller grok --session-id <真实Grok CLI会话UUID>`显式传入；不猜测Grok环境变量。环境有CODEX_THREAD_ID或CLAUDE_SESSION_ID时不能选择grok，换一个UUID也不行。
- claudex在存在CLAUDE_SESSION_ID时须一致，仅有Codex环境时拒绝。三个controller不跨映射会话ID，旧绑定键保持。省略controller仅在恰有一个已知原生环境变量时推断；零个或两个均须明确选择真实宿主，不能改身份解锁。

```text
python3 <skill-dir>/scripts/session_binding.py send --controller <codex|claudex|grok> --session-id <真实ID> --project-root <Mac根目录> --environment 'Grok Bot' --worktree <已发现完整云端worktreeID> --orca <本次选定可执行文件> --task-id <当前ID> --text-file <项目外已审查prompt.txt>
```

已知精确绑定及同一目标参数时直接send；已有持久 bound 绑定时，`send`、`reconcile`、`finish`、`wait` 可省略 `--worktree`、`--environment` 与 `--project-root`，自动继承已绑定的云端目标；`python3 <skill-dir>/scripts/session_binding.py wait --task-id <ID>` 可阻塞等待 bound CC 完成当前执行并恢复 `tui-idle`。send 自带身份、空闲、auto和草稿核验，无需先ensure。ensure保留为可选只读诊断，不创建。无绑定或旧实例确实消失时，先用以下无confirm命令展示同项目目标及claude/auto/位置计划，等待用户明确选择换绑或新建；有现成任务也不能跳过选择：

```text
python3 <skill-dir>/scripts/session_binding.py create <同一组会话与目标参数> --project <已发现完整云端worktreeID>
```

`--project`是云端完整worktree ID，`--project-root`仍是Mac根目录；若同时传worktree，两者必须相同。dry-run不创建终端、状态目录、lock或intent。用户已明确批准该目标的新建后，才可对同一命令增加`--confirm`；既有bound的换绑则按reference的rebind门禁执行，无绑定不认领legacy终端。暂时不可达先等一至两分钟核查原操作，不据此新建。

确认后先持久保存reservation，新预约只调用一次`terminal create --worktree id:<完整ID> --command "claude --permission-mode auto"`，权限参数仅作用于该新实例；不传裸`claude`、prompt或模型参数，不改全局agentDefaultArgs。执行端仍须报告Orca≥1.4.229及既有能力。先保存精确handle，再由完整清单取得incarnation，经Claude身份、auto且无bypass、空输入及空闲核验后才绑定。已有绑定不改动。

未知结果保留creating；重复confirm只核验已保存的精确结果，不自动启动或重放。新`terminal.create.claude-auto.v1`没有原生operationId/replay，丢失结果继续pending。既有`agent.launch.v2`预约保留原协议；只有它已保存有效原生operationId及明确retrySafe证据时，才可按[显式启动重放](references/session-binding.md#显式启动重放)在原目标、runtime、可执行文件和目录，显式重放同ID一次。无ID的旧pending保持未知；不能借升级、空清单、随机ID或新state-dir恢复创建机会。启动重放与发送`--retry-request`是两个不同协议。

所有wait/read只针对返回的handle/runtime/incarnation；发送前保存cursor和intent，receipt仅保留白名单字段。保留真实草稿、未知屏幕、非auto、身份漂移、creating/sending未知结果；send/finish不清空输入，清理仅走下述用户确认入口。不自动换绑、开窗、重启网络或删registry。

同task主消息main；accepted/sending重复调用只resume。task累计最多2次提交（含合法export），unknown不因还有次数就重发；同message仅明确not_sent且同文才可显式再提交，并重做verify/idle。list/read/wait另按默认300秒预算退避，不触发新模型任务。`input_accepted`和`tui-idle`都不代表产物完成。

故障只读用`reconcile <同参数> --task-id <id>`；marker/空闲/无新输入不能解锁。当前原生`--retry-request`缺官方契约，在任何Orca调用前unsupported，不能手工send绕过。只有已有bound、无active/unknown且用户确认精确目标后，才允许显式rebind，旧绑定归档不删除。完整[状态、退避、换绑门禁和错误决策表](references/session-binding.md)。

### 粘住 draft：三步排查

1. 读取原绑定的 screen JSON：`draft` 字段优先于视觉 `❯`。可用 `python3 <skill-dir>/scripts/session_binding.py clear-draft <相同会话与目标参数>` 只读取得 JSON 摘要；不带 `--confirm` 零 send。`nonempty_draft` 的 `diagnostic` 只含 `draft_present`、`draft_lines`、`draft_bytes`、`draft_sha256`，不含正文。
2. 先保留需要的真实未发送文本，取得用户对当前草稿清理的明确授权，再执行 `python3 <skill-dir>/scripts/session_binding.py clear-draft <相同会话与目标参数> --confirm`。它先验身份/idle/auto，最多两次独立且不带 Enter 的清理 write；不提交正文、不改权限或绑定。
3. 只在 `draft-cleared` / `draft-already-clear` 后另行 ensure，再按原任务 send/finish。`sticky_draft` 或未知清理结果立即停止；不连续重跑 clear、不自动 close/retire/rebind。用户可选择关闭终端后另行安排 `retire-dead-binding`；本源码未实现此命令，本轮只说明人工恢复边界。

| 现象 | 动作 |
| --- | --- |
| draft 空且 composer 合法 | 正常 send/finish，沿用原有身份、auto、任务历史及精确占位符门禁 |
| draft 非空 | BLOCKED nonempty_draft；真实草稿默认保留；用户确认后 clear-draft，再 ensure/send/finish |
| clear-draft 两次仍粘 | BLOCKED sticky_draft，停止报告；用户可选择关终端及另行批准退役流程，不自动执行 |

## 3. 完整回收、Mac检查与验收

按官方能力从保存cursor读完整stream；screen回退、裁剪、历史缺页、权限/模型提示未解决时停止，不猜补丁。transcript/token不足及云端jsonl只读降级见[长回复与降级](references/final-patch-prompt.md#长回复与降级)。回收不新增shell/终端，也没有collect自动完整回收功能。

已存在 bound 任务且目标 message 为 accepted、有匹配 receipt 时，可用 `recover-final-reply --controller <c> --session-id <本地主控UUID> --task-id <已有任务UUID> [--message-id main] [--out /private/tmp/<唯一前缀>] [--expected-host-fp <可信SHA256指纹>]` 从云端原生 JSONL 只读导出最终助手 text。SSH 默认直连 `box@100.84.23.115`，严格核 known_hosts，绝不自动修钥。失败结果只带固定 `diagnostic.kind`：`handshake_failed` 与 `timeout` 属于 `unreachable`；`host_key_mismatch` 属于 `identity_changed`，包括主机密钥验证失败的 SSH 退出码 255。SSH 已结束但搜索、权限或 JSONL 解析失败时 kind 为 `jsonl_read_failed`，类别是 `integrity_failure`。`timeout` 与进程尚未启动的 `handshake_failed` 最多尝试 3 次，间隔 2 秒和 5 秒；单次 SSH 240 秒，`ConnectTimeout` 20 秒。主机钥失败和 JSONL 读取失败不重试。user 文本只留 `grok-cc-msg:` 或 task_id 附近窗口，不传整段 user；assistant 只保留 end_turn 全文。不要把 timeout 当成 attachment 父链的 integrity_failure。结果不含远端 stderr、主机钥或命令输出。成功后以导出 `.txt` 为真值；屏幕结束标记和残缺 screen/stream 仍不能批准或猜补丁。空补丁合法，回收不代表 finish 或 Mac 验收。身份、歧义、输出与错误边界见[缺页最终答复回收](references/session-binding.md#缺页最终答复回收)。

main已accepted、无unknown且有剩余次数时，仅经用户明确要求，才可同task用export-1重导出既有最终补丁修正格式。不能连续导出、重新执行开发任务、索要内部推理/其他会话，或绕过模型拦截；不完整产物先停止报告。

```text
python3 <skill-dir>/scripts/task_packet.py check --packet <原packet.json> --reply <完整原字节reply.txt> --out <项目外>/checked.patch
```

check不改项目；默认核对唯一有效hashed产物、原字节SHA/LF数、白名单、所有选定文件基线/新增缺席、路径/symlink、hunk及真实git apply --check（空补丁合法，0 行且为空 SHA 时核验基线通过并输出 0 字节补丁）。旧无hash回复只能显式`--allow-unhashed`，不能挽救损坏hashed块。只支持UTF-8文本修改/新增，不支持删除/重命名/二进制/权限变更/空白文件名。

审读补丁与源码，应用前用新输出名重新check；基线漂移先协调，不reset/force或覆盖本地用户文件。再用标准git apply应用checked.patch，运行Mac项目所需测试及独立Review；云端PASS和hash都不是Mac业务验收。未经授权不暂存/提交/推送。

核对结果或如实记录阻碍后，原CC空闲且无unknown时用finish结束task，保留绑定/历史，project_pass=false不等于项目完成。下一任务仍复用当前绑定。

## 4. 可选调度员摘要

Grok Bot只调度，重活交CC；grok-cc是Mac直连入口，不需要bot对话中转源码。若任务来自云端`/workspace/handoff/`，只取目标、白名单和完成标准，Mac仍是真值。

`task_packet.py handoff-summary --task-id <id> --packet <原packet> --out <项目外summary.md>`生成最多15行摘要；可显式提供受限`--mac-test <label:pass或fail或not_run:通过数:失败数>`、`--unverified <短标签>`、`--category <类别>`。helper不执行测试，缺证据就未验证，不含源码/diff/secret，不读共享registry。无packet时需可靠project-root边界。

只有用户另行同意目标和内容后，才由用户/本地主控将摘要追加到云端`/workspace/handoff/tasks/<文件>.md`的结果/待确认章节；helper不做任何远端写入。

维护本Skill时运行`make check`（独立安装副本可运行随包unittest）。分别报告本地通过、真实远端未验证、模型拦截、网络故障、产物裁剪和剩余风险，不自动换账号/模型或把Mac登录改成云端身份。
