# 执行上下文与隔离替身

作者：elvis。

```yaml
status: promoted
event_kind: integrity
severity: high
scope: project-local
promotion_trigger: threshold
symptom: 首次预检与提交可能执行不同相对路径文件；异常outcome=null或巨型timeout整数可产生非JSON错误。
prior_assumption: 设置Popen cwd后，父进程shutil.which得到的文件仍等于子进程选择的文件。
correction_or_evidence: 父线程离线代码核对与独立闭合PATH探测分别指出该问题；双cwd真实helper回归RED复现。另有null状态真实CLI RED。
generalized_invariant: 首次查询前按child cwd解析并pin同一绝对executable；保存字段的显式null不得按缺省合法化，数值边界检查先于float有限性转换；测试不能回退安装的CLI。
independent_reproductions: 父线程双cwd回归与独立reviewer同名fixture探测。
independence_rationale: reviewer未编写实现或仓库回归，独立创建临时进程探测；主线程依据代码另写确定性回归。
duplicate_or_conflict_result: 扩展既有工程不变量和现有unittest，不建立第二运行框架或全局Skill规则。
target_artifacts: docs/engineering/engineering-invariants.md; scripts/session_binding.py; scripts/tests/test_session_binding.py
mechanical_enforcement: required
mechanical_enforcement_reason: 双cwd/相对PATH、无默认CLI、畸形state均可在真实私有文件及进程边界确定性验证。
verification: 首轮Review修正前94项绑定回归1 FAIL+1 ERROR；修正后94 PASS，全量129 PASS，独立双cwd/null/符号链接换向与同ID重放probe通过。Final Review另发现巨型timeout整数，新增真实CLI子用例RED为94项中1 ERROR；修正后主控129 PASS，distinct final reviewer129 PASS及巨型/无限/null/正常/边界数值独立进程对照通过，坏值安全JSON且零native查询。strict与diff check均通过。
review_result: pass
decision_owner: codex
decision_provenance: docs/agent-collab/adapt-orca-229-agent-launch/status.md
```

独立探测曾因`./orca`归一化成`orca`且PATH未闭合，可能调用真实CLI。该次带confirm，输出与临时state未保存，是否进入native mutation未知；不能声称全轮零真实调用或无effects。后续闭合PATH验证不能抹去此事，也不作为云端验收。真实绑定目录及安装版不在该临时state路径内；不得为调查该例外盲目重建或更换原绑定。
