# 缺页最终答复回收源码集成

作者：elvis。

## Why

Orca stream/screen 缺页时，已完成的答复不能作为完整补丁使用。用户已要求安装版新增只读原生 JSONL 回收，并在本会话明确要求将该成果提交、推送 Git。

## What Changes

仅将本会话已验证的 recover-final-reply helper、22 项回归与对应 Skill/reference 文档纳入源码，更新 VERSION、CHANGELOG、bundle-manifest。绑定和 receipt 验证、严格 SSH 信任、最终助手父链和 text-only 导出保持安装版已审核实现。

## Scope And Authorization

用户原始任务明确八项回收门禁；后续“推送git”批准同范围源码提交和 origin/master 普通推送。本文件记录该具体成果的发布授权，不新增能力或重开设计。不纳入安装版前序 archive-creation、retire-dead-binding、collect，也不改前序工作区文档。当前安装保留，无覆盖安装、云端派发、创建/换绑、registry、known_hosts 或账号修改。

## Evidence

安装版曾完成 RED/GREEN、三环境各250项测试及独立本地审查。源码须重新执行 make check、三环境 unittest、完整差异审查和独立反例。不同副本测试总数不同，不能互相冒充；真实 SSH/云端回收及原任务 Mac 业务验收仍未执行。
