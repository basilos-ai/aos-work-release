# Workbench 镜像发布

后端、前端和 Runtime 的 master 构建在核验镜像后，在同一运行中检出本仓库指定的脚本提交并执行发布。每个调用仓库配置 Actions Secret `AOS_WORK_RELEASE_DISPATCH_TOKEN`，使用仅对 basilos-ai/aos-work-release 授予 Contents 读写权限的令牌。脚本更新后在三个调用仓库更新固定提交。

脚本在发布仓库原子创建临时分支 `automation/image-release-lock`，取得锁后读取 Latest Release，更新对应镜像版本和部署包。附件摘要核对成功后才公开草稿。正常退出按锁持有者的提交安全释放分支。若 runner 被强制终止留下锁，先查看锁提交中的运行链接，确认该运行已结束，再按锁提交 SHA 使用 Git 的 force-with-lease 删除锁分支并重跑失败作业。不同构建共用同一把锁。
