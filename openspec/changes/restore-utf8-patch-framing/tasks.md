# Tasks

作者：elvis。

## 1. Proposal

- [x] 通过原 CC 单次只读审查并完整读回唯一发现。
- [x] 使用真实文件和 Git 复现非 LF 字符误分帧，定位 CLI 换行转换。
- [x] 严格验证提案并获得用户对本 change 的明确批准。

## 2. Implementation after approval

- [x] 在隔离工作区制定可执行计划并完成 Preflight Review。
- [x] 先添加真实 helper/CLI/Git 回归并记录预期 RED，覆盖九类内嵌字符及既有 CRLF 兼容。
- [x] 最小恢复原字节读取和 LF 分帧；仅在失败回归证明必要时修复同源标记分帧。
- [x] 更新版本、双语 README 版本徽标、受影响载荷哈希和变更记录，保持其他载荷及所有保护。
- [x] 运行 focused GREEN、`make check` 和官方 Skill validator，独立审查完整 diff及反例。

## 3. Delivery

- [ ] 按用户授权精选提交/推送并核验远端 exact revision 和四组合 CI。
- [ ] 从已发布 revision 隔离 staging；核验安装前像/并发漂移后最后更新本地载荷，保留绑定与原生配置。
- [ ] 验证 active suite、Codex/Claudex 发现和 parity，完成独立 Final Review。
- [ ] 核对 proposal/tasks 和 Git 残留，按可用生命周期规则归档/严格验证并如实汇报。
