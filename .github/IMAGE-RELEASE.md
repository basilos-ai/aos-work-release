# Workbench 镜像发布

先将接收工作流合入本仓库的 main，再启用Workbench 后端、前端和 Runtime 三个仓库 master 上的调用步骤。在调用方配置 Actions secret `AOS_WORK_RELEASE_DISPATCH_TOKEN`，使用限定到 basilos-ai/aos-work-release 的细粒度令牌，授予 Actions 写权限。发布仓库内置的 GITHUB_TOKEN 需要能够创建标签和 Release。

源仓库的手动镜像构建仅在 master 镜像发布并验证 latest digest 后请求发布。构建页记录派发结果，部署包的发布状态见此仓库的 Publish deployment package for a Workbench image。派发成功后若发布失败，重跑本仓库失败的运行即可。

发布作业按单一队列处理，从上一个正式 Latest Release 的标签和附件生成新版本。日期采用上海时区。同一天的后续版本追加递增后缀。只有本次构建组件的版本会变化；安装器中的版本清单、下载链接和附件校验和随版本生成。发布提交位于新标签上，main 继续承载自动化和部署开发。四个附件上传到草稿并核对摘要后才发布。
