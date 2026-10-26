# 实现自检

文档类型：实现自检
日志及版本：2026-10-26，`retry-final-reply-ssh-timeout`，源码 `0.1.0.dev10`
结论：有风险
验证范围：`scripts/session_binding.py`、`scripts/tests/test_session_binding.py`、`SKILL.md`、`references/session-binding.md`、`CHANGELOG.md`、`VERSION`、`bundle-manifest.json`；`make check`

本文件是实施者自检，不是独立 Review，不批准安装、提交或任务完成。

## 问题与风险

未发现源码阻塞缺陷。剩余风险：

- 未再跑真实 SSH。活动 skill 仍是 60 秒单次超时，没有这轮短重试。
- `ssh` 自己因 `ConnectTimeout` 返回退出码 255 时，类别仍是 `handshake_failed`，且文案不是「进程尚未启动」，因此不重试。进程没创建的 `OSError` 和子进程 `TimeoutExpired` 才会重试。
- 先前只读测量里，完整投影约 20 秒传出 196,608 字节仍未结束。单次 90 秒能盖住那次量级附近的慢传输；路径若持续更慢，三次尝试仍会以 `timeout` 结束。
- 云机 keepalive 不在这次改动里。

## 事实偏差 / 遗漏

无。主机钥失败、`jsonl_read_failed` 和父链校验没有放宽。

## 摘要

`read_final_candidates` 对 recover SSH 使用 `ConnectTimeout=20` 和 90 秒子进程期限。`timeout` 与 `SSH unavailable` 的 `handshake_failed` 最多 3 次，间隔 2 秒和 5 秒。最终失败带整数 `attempts`，不回传 stderr。

`make check`：`Payload verified: 8 files, 0.1.0.dev10`，`Ran 187 tests`，`OK`。

## 后续

独立 Review、提交、推送和活动 skill 更新都还没有做。
