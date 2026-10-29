# Sticky draft clear — Implementation Review

记录：elvis。审核证据：独立 Codex `/root/sticky_draft_implementation_review`。
目的为源码候选的实现门禁审核；角色 independent-reviewer，profile control-plane-high，
实例区别于作者/实现 `/root`，结果权限仅 governed-review-evidence，不决定整任务完成。

## Initial result: FAIL, findings retained

初审 source SHA256：`99cd742e5ace8279fb558c5313ce41d187c2bad0759ad78c5515022929975b54`。
初审 tracked diff SHA256：`3a41cf1dc023dbfd7e57ceed71e5b82cb23acf1efba41d8cc5363e6c55479cec`。
初审含未跟踪文件的指纹：`43d69928abb9e85a1d95e168cfa234db100779e4cc9071aa67e1a5035e03baa3`。

- `_input_screen` 对 limited/truncated 使用 truthy 判断；独立删除任一字段，仍一次 clear 并返回 draft-cleared，不能证明完整性。
- 首次 clear 后读取抛 transport_unavailable，预算为 0 时返回 unreachable/retryable=true；查询重试提示不能授权重跑整个清理。

独立初审 focused 20/20、make check 213/213、OpenSpec strict/diffcheck 通过；
额外 10 个边界符合预期，但上面两个反例阻断 PASS。主控按根因新增缺字段/异常假值、
clear 后 list/wait/read 故障回归及 busy 不可重试断言：旧候选 22 项 focused 出现 20 个失败子例，
修正后 22 项 focused 通过。完整性标志改为明确布尔 false；清理循环错误保持类别并关闭 retryable。
同范围修正未重开 Preflight，不新增生命周期或权限变化。

## Reference-consumption GREEN

独立 reviewer 仅按新版 SKILL/reference 选择恢复动作，未执行真实远端命令：

- 未授权时使用 clear-draft 无 confirm 只读摘要，保留真实 draft，不把空 ❯ 当授权。
- 明确授权后 clear-draft --confirm；使用同一绑定，不混正文或 Enter，成功后另行 ensure/send/finish。
- 两次后仍 sticky 时停止，不循环清理、不自动 close/retire/rebind/finish；退役只为另行人工选择的文档说明。

相对 Preflight 中的旧版 RED，三种消费场景通过；不推断真实终端效果。

## Correction review

修正重审 **PASS**，无剩余 actionable finding。源码 SHA256：
`22eea92076df62a6b0eeb7a50cb328d3147d1d2104ea293dcc54ae88f4bea5f2`；
重审完整差异指纹：`7ea788b6d66950ed9e9d12ec818054da29af290ceeccc66c9946b109ee55bcd6`。

独立复跑 focused 22/22、make check 215/215、OpenSpec strict 与 diffcheck 均通过。
15 个独立边界探针通过，覆盖原两反例、第二循环 verify 的 list 失败仍只清理一次且 retryable=false、
预算内安全只读退避恢复不会重放 clear、回执形状/handle/来源/裁剪/身份及 registry 漂移。
create/rebind/send/finish 等不变函数核对通过。新旧 Skill 三场景消费结果继续有效。

主控核对本轮源码/测试及 manifest 后签收此证据；两项已确认知识落实到 reference 和确定性回归，
批准项目内候选提升，不改全局规则。Implementation PASS 不代表 Final Review 或真实远端验收。
