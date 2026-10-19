# ADR 0001：以本地最多一次提交约束显式创建

作者：elvis。状态：已接受，依据 2026-10-18 用户明确批准；本文于 2026-10-19 蒸馏既有决定，没有新增权限。

## 背景与已排除路径

2026-10-18 静态核对的 Mac Orca 为 1.4.227。公开 terminal create 有 worktree/command 等参数，没有首次 caller-key 接口；原生内部 schema 存在幂等字段，不等于公共 CLI 已接线。worker-start 的 retry-request 仅恢复 Orca 已报告的原请求 UUID，不作为首次自铸 key 的入口。

原设计要求原生 caller-key，因缺公共契约而阻塞。用户随后明确批准将保证改为“本地最多一次提交”，解除的是该接口依赖，没有发现或补造原生去重能力。

## 决定

使用既有 Registry 的私有文件、FD/no-follow、flock、file fsync、replace 和 directory fsync。用户明确选择目的地后，先持久预约稳定本地 creation_id，再锁外最多调用一次已核实的公开 terminal create。回执先保存精确 candidate，完整核验及重锁检查后才绑定；失败保留意图和证据。

不增加协调器、不改第三方 Orca、不手写 RPC，也不通过其他 caller、换身份、换 registry、删记录或自动换窗绕过不确定结果。

## 取舍

- 继续等待公共原生 key：保证较强，但当前契约不可用；若以后取得新版本的正式接口，再走新的能力核验与批准，不重复同版本泛搜。
- 本地最多一次提交：当前可验证、可交付，且不需要新运行状态框架；代价是即使子进程未启动或根本没有创建效果，也可能长期 pending。
- 未知结果自动重试：存在重复创建和错误认领风险，不接受。

保证只覆盖同一保留受管 registry 内本 helper 的意图，不是原生跨客户端/registry 去重或 exactly-once。完全丢失回执时不能凭标题、时间或“新出现”的终端认领；只有已保存的精确 candidate 可以恢复只读核验。

## 约束与验收

ensure 只验证已有绑定；create 默认无落盘预览，confirm 仍须具体用户选择。替代创建需完整有效清单证明旧实例消失；临时不可达不构成证据。任务历史、两次累计发送额度及其他 owner 的 pending 占用持续有效。

已在功能提交 `4e794a211f6c6044170b54d2b7c80ad4b5f0af34` 实现。112 项本地回归、独立实现复审及不同实例 Final Review 通过；这些不证明真实云端 E2E。合同见[显式创建 spec](../../openspec/changes/2026-10-16-transient-remote-resilience/specs/explicit-terminal-create/spec.md)，机制与回归见[工程不变量](../engineering/engineering-invariants.md)。
