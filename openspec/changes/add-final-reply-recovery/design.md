# 源码集成设计

作者：elvis。

既有实现不重新设计。仅迁入最终回收代码块、导入、CLI参数与分支，复用源码已存在的 Registry.inspect、BindingManager._accepted 与 open_directory。保留原有 SafeParser 及创建/发送/finish 路径。

定位使用已接受消息摘要和 marker；候选先定位、再按可用创建时间消歧、最后抽取。当前旧 binding 无创建时间时多候选拒绝。助手 parentUuid 必须回到目标 user，禁用 SSH multiplex，expected fingerprint 同时核 keyscan 与实际握手。项目外独占输出正文与元数据；补丁哈希失败仍保留原文。

本机运行副本还有独立未发布能力，不能整目录复制到源码，也不能用此次源码反向覆盖安装副本。更新窗口应重新读取实际安装 Skill；git pull 只更新源码。

回退使用反向提交恢复此次源码变更；不重写远端历史。安装未变，无运行状态迁移。
