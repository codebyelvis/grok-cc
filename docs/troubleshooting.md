# 故障定位边界

作者：elvis。

## 启动提示与草稿

当前 helper 已核实三种精确原生启动提示，仅在无任务历史时允许：

- `Try "edit <filepath> to..."`
- `Try "fix typecheck errors"`
- `Try "refactor <filepath>"`

仍须通过原绑定身份、auto mode、空闲、真实 screen 和无显式 draft 检查。相似文本、真实输入或历史任务后的提示继续阻止派发，不要清空输入或改成匹配任意 `Try`。

若出现新的原生占位提示，先只读保存必要的 composer/状态证据，确认没有实际草稿，再按适用变更规则添加准确兼容及失败回归；不要边试边发送。

## 网络与回执

远端不可达不表示 Claude 进程退出。保留 handle、incarnation 和原回执；不重启代理、Tailscale、Orca 或 CC 来代替定位，不另建终端。

同一 task/message/文本再次调用 helper 只恢复已有记录。`sending` 表示未知结果，不能删除 registry 或改 task_id 重试。当前不提供自动 reconcile/rebind/reset。

## 精确会话与完整产物

`session_not_reported`、`sourceExact` 和 `contentComplete` 表示不同事实。精确来源不保证正文完整；按当前 Orca 的实际 guide 和 clipping/warnings 决定是否可读回。

一次 Orca 1.4.224 排障中，`worker-read` 的 transcript 文本块在 1,200 字符后追加截断提示，增大消息条数限制不能补回同一块的剩余正文。这是已观察的版本边界，不保证其他版本同样实现。本仓库没有修改第三方二进制或添加完整导出接口。

缺少 `END_PATCH`、丢失历史或 TUI 空格无法确定时停止应用，不猜补丁、不连续发送导出消息。用户经可靠渠道提供完整当前补丁文件时，核对任务范围、字节数与 SHA256，再走原 packet check；文件传输不代替基线、测试与 Review。

## 模型拦截

按实际 provider 错误报告。`reasoning_extraction` 标签不能单独证明请求违规或上下文过长；不换账号/模型、编码请求或连续改写绕过拦截。详见 [最终补丁说明](../references/final-patch-prompt.md)。

## 验证声称

本地 suite 检查 helper 与 packet 行为，不证明远端服务持续在线、真实模型回复、业务源码通过，或云主机能 7×24 不休眠。分别记录 source 准备、远端发布、active Skill 安装和实际业务任务结果。
