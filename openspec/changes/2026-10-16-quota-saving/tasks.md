# Tasks

作者：elvis。

## 1. Alignment and proposal

- [x] 完整阅读第二份任务；核对resilience未有产品实现，保留旧草案，从该分支创建新quota worktree。
- [x] 按用户委托采用推荐：模型派发最多2次，只读退避另计；不绕过uncertain，不把allow-binary当二进制传输，不从task-id虚构测试结果。
- [x] 编写本change的proposal/design/tasks/specs，与resilience形成显式依赖，统一产物模板及文件边界。
- [x] 严格验证两份OpenSpec，获得本会话明确“批准”；4项精度修订同步并重验通过，不将推荐委托或工具权限当批准。

## 2. Implementation after approval and dependency

- [x] dev2依赖片make check通过；统一执行计划和独立Preflight覆盖quota，无新调度框架。
- [x] RED/GREEN：真实render含10行/不复述/不贴日志且不诱导云端项目测试；实际CLI回归验证。
- [x] RED/GREEN：prepare/render同一UTF-8预算/阈值/max-bytes及粗估token，过限无输出并建议缩白名单。
- [x] RED/GREEN：summary显式证据/<=15行/默认未验证，拒绝任意日志和源码输入、secret，不覆盖/写项目或远端。
- [x] RED/GREEN：task累计2次含合法export，同message重试仅not_sent，同ID去重、unknown阻断、read次数分离；旧记录不重置次数。
- [x] RED/GREEN：媒体后缀及实际/已识别编码媒体，override不突破UTF-8；不声称识别任意编码。
- [x] 文档决策表、小白名单/用户handoff授权/Mac真值同步。
- [x] dev3/CHANGELOG/manifest已更新；先断言dev2以来仅packet helper与其测试hash变化，其余保留，8文件清单不改。
- [x] quota新增6项RED=4fail+2error，修复后packet34项GREEN；dev3 make check通过82项和8文件载荷，两个strict与diff检查通过。
- [x] 旧范围独立实现Review的4项发现已回归修复，复审PASS，独立54+35项及原探针通过；新增显式create不在该PASS范围。
- [x] 原批准quota本地范围单独Final Review PASS，独立89项/8payload/strict/diff和安全probe通过，不是Implementation结论改名。
- [x] 后追加create的范围批准以resilience change的proposal.md为准；用户批准本地最多一次提交后，新Full Preflight、独立Implementation attempt 2、学习签收后的新鲜最终验证及不同实例的单独Final Review均PASS；112项/8payload/两strict/diff与独立故障交错probe通过。control-plane已核对实际哈希并签收本地源码范围，具体证据见resilience tasks；不是沿用旧范围PASS，也不含Git/发布/安装/真实远端验收。

## 3. Delivery

- [x] 原批准范围当时为dev3、8文件manifest、89项（基线42，新增47）；2026-10-18新增create经23项回归达到112项，本地源码闭环并单独Final PASS。worktree/branch及既有成果保留；真实远端仍未验收，不扩大本地结论。
- [x] task状态与私有证据已更新，保留旧草案及已核实前像；2026-10-18源码验收后用户另行授权本地暂存/提交，范围为已验收的26项文件，实际结果以Git记录为准。两change保持active等待另行授权的source推送/发布，此后才可另行安装/真实远端验收，不归档/push/发布/安装或写云端handoff。详细本轮/既有清单与处理条件见resilience tasks第5节。

CodeIsland问答未完成的归因/交互处理独立于产品实现，本轮不改全局hook或settings。所有未执行验收保持未勾选。
