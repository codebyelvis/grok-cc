# Change: 前置任务预算并减少模型对话工作量

作者：elvis。

## Why

Grok Bot 调度消息不应反复承载源码和长日志，grok-cc 的 Mac 直连任务也应先以最小白名单跑通完整本地验证链路。用户提供 `docs/review:requirement/grok-cc-local-optimize.md`，要求短回复、prepare 前置预算、可选 handoff 留档、失败上限及多模态边界。

## Dependencies and agreed interpretation

依赖 `2026-10-16-transient-remote-resilience` 的 render、secret扫描、结构化结果与不确定发送保护；两份 change 在同一新 worktree `.claude/worktrees/quota-saving-a8e9002d` 对齐，不假定上一轮已有实现或已合并。

用户已委托采用分析后的推荐抉择。本合同采用：模型派发最多两次，只读调用另按300秒预算退避；未知发送从不因“还有次数”变可重试。该委托不是未形成的具体 OpenSpec 合同批准。

## What Changes

- 将“补丁块外最多10行结论、不复述任务、不贴长日志”纳入真实 render 提示及 Skill/模板，回归验证生产渲染。仅已有日志报路径和计数，不诱导云端跑 Mac 项目测试，建议产物生成所需工具计算除外。
- prepare 使用与 render 相同的最终 prompt 字节预算，默认120KiB；两者复用 `--max-bytes`。在写packet前报告过限并建议缩小白名单，不输出部分packet/提示。成功输出包含字节与粗略token估算，原始本地packet JSON大小另行区分。
- 增加可选 `handoff-summary --task-id --out`，可补充 `--packet` 及重复 `--mac-test`、`--unverified` 和 `--category` 作为主控显式提供的证据标签；不执行测试、不读registry、不推断通过。task-id必须与packet一致；无packet/测试证据时明确未提供/未验证。限制15行，不含源码、diff、敏感值，输出新私有项目外文件。
- BLOCKED JSON复用类别，并提供 attempts；消息提交次数durable保存且最多2次。仅明确not_sent、同ID同文并重新verify/idle后可第二次；accepted重调只resume、未知结果停。达到上限retryable=false。只读调用次数使用独立read_attempts，不把预算退避谎报成模型派发次数。
- Skill说明只有获得用户对目标和内容的授权后，才可由用户/本地主控另行将摘要追加云端 `/workspace/handoff/tasks/` 的结果/待确认章节；helper本身无远端写入。来自调度员的handoff只取目标、白名单和完成标准，Mac源码仍是真值，不把bot消息路径当作Mac可读文件。
- prepare默认拒绝常见图片/视频/扫描件扩展名，提示先做必要文字摘要；`--allow-binary`仅放宽扩展名门禁，不接受实际二进制、非UTF-8、NUL、媒体magic或编码媒体载荷，不改变文本补丁能力。
- 在原references决策表补充失败上限及停止条件，Skill强调先小后大。版本从依赖片的0.1.0.dev2顺延为0.1.0.dev3，更新CHANGELOG与本轮明确变更文件的manifest哈希，不扩容8文件清单。

## Impact

产品修改限于两个helpers、现有tests、SKILL、两个references、VERSION/manifest/CHANGELOG，以及双语README和troubleshooting本次受影响声明。与依赖片共用执行计划及独立评审入口；不重复建立调度框架，不新增第三方依赖，不改配置/安装器/CI/AGENTS或其他工程。

可选摘要纳入范围，可选collect延后；原生request retry及远端not_sent推断受依赖片的官方契约前置条件限制，不能假称完整实现。

## Approval and Delivery

用户在本会话明确“批准”，ExitPlanMode已确认；批准包括task累计2次（含合法export）、retry零Orca调用、共享deadline及有限媒体识别4项修订。先同步合同并独立Preflight，再按TDD串行完成resilience及quota业务片；开发和独立评审不并行争用同一路径，一次最多一个模型子任务。最后运行make check、OpenSpec严格校验及完整diff审查，交付真实结果/未验证项并等待授权。

不访问真实state、不运行真实Orca、不连云端、不安装、不登录登出、不改网络/配置/模型，不add/commit/push/publish。静态契约和mock不能代替真实云端/业务验收。CodeIsland问答hook诊断是本机会话协作问题，不混入本产品范围或顺手更改全局权限。
