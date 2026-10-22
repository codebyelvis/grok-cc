# 调用可靠性与安装一致性

作者：elvis。

## Why

本次只读审查复现：并发 reconcile 写证据会使正常 send 回执被丢弃；CLI 读取 prompt 转换 CR/CRLF；超时回收可能等待继承管道的子孙进程；生产 prompt 未说明受支持的窄 diff 格式。另有安装版独有的 Grok 身份支持与 macOS 临时路径兼容，尚未进入源码。

## What Changes

- 保留同一发送意图的并发只读证据，可靠保存正常或异常回执；真实身份、内容、次数、attempt 或任务变化继续阻断。
- 发送保持审查过的 UTF-8 原字节；prepare/render 与 send 共用传输限制并提前报告不可发送输入。
- 本地原生命令超时后有限回收自有进程及管道；不重试 create/send。
- 导入已安装且审查过的 controller 与输出路径兼容，并补 Grok 在其他原生宿主环境中的身份保护。
- 明确最小 unified diff 格式；已有绑定正常调用直接 send，ensure 保留为可选诊断。
- 更新源码、回归、Skill、版本与 manifest，审核后推送当前 origin/master，再以固定发布提交更新共享安装。

## Scope And Authorization

用户在本次五项审查后明确要求闭环优化、推送 Git 并更新本地 Skill。本 change 记录该已授权范围，不另授云端派发、真实终端创建/换绑、共享 registry 修改或 native 配置权限。提交/推送与安装包含在本次授权内；不 force-push。

只修改既有两个 helper、两个测试、SKILL/references、受影响工程文档、VERSION、CHANGELOG、manifest 与本 change/计划。不新增调度、安装器、状态框架或 collect，不扩大补丁权限语法，不变更未知结果的保留规则。安装版六处差异先逐项审查并保留前像，不通过重算 hash 掩盖漂移。

## Evidence

采用 strict 的持久化/字节完整性验证：真实临时项目、Git、文件锁、CLI/子进程，只有外部 Orca 边界使用替身；分别执行 Preflight、Implementation Review、Final Review。真实云端业务调用不属于本次源码与安装验收，也不能由本地回归推断。
