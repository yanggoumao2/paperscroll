# 参与贡献

[English](CONTRIBUTING.md)

欢迎任何人改进 PaperScroll：修 Bug、提出更好的方案、接入新的论文来源、完善文档都可以。
标准只有一条：让读论文的体验变好，同时不让项目变得更难部署。**每一个被合并的 Pull Request，都会让你成为本仓库的贡献者。**

## 怎么提交

1. **有想法或更好的方案？** 除了小修小补，建议先开一个 [Issue](https://github.com/yanggoumao2/paperscroll/issues/new/choose)，
   写清楚问题和你的方案，先对齐方向，免得白费功夫。
2. 在 GitHub 页面右上角 **Fork** 本仓库，并克隆你自己的 fork。
3. 新建分支：`git checkout -b fix-figure-crop`。
4. 修改并自测（见下方「开发环境」）。
5. 提交、推送到你的 fork，然后向本仓库的 `main` 发起 **Pull Request**，按模板写明改了什么、怎么测的。
6. 维护者审阅，必要时来回讨论后合并。

不需要申请仓库的写权限，Fork + Pull Request 就是标准的贡献方式。

## 怎样算作贡献者

合并后提交的作者仍然是你，所以你会出现在仓库右侧的 **Contributors** 列表和 README 的贡献者头像墙里。前提是 GitHub 能认出你的提交邮箱：

- 用你 GitHub 账号里已验证的邮箱，或者账号的隐私邮箱 `ID+用户名@users.noreply.github.com`（GitHub → Settings → Emails 可查）；
- 提交前用 `git config user.email` 确认一下。

多人合作完成的改动，在提交信息末尾加一行 `Co-authored-by: 名字 <邮箱>`，所有人都会被记为贡献者。较大的贡献也会写进 `CHANGELOG.md`。
GitHub 的 Contributors 列表在合并后会延迟几个小时刷新。

## 可以从这些地方入手

- [路线图](README.zh-CN.md#路线图)里的条目：更多论文来源（OpenReview、期刊）、没有 arXiv HTML 版时从 PDF 取主图、英文界面、iOS 外壳。
- 改进「问题 / 方法 / 结果」抽取（`server/paperscroll/glance.py`），附上 `server/dev/glance_check.py` 改动前后的对比。
- 会议级别缺失或错误（`server/tools/build_tiers.py`、`server/paperscroll/tiers.py`）。
- 文档和翻译。

## 报告 Bug

开 Issue 时请写明：做了什么、期望什么、实际发生了什么；平台（Windows/Linux/macOS、手机型号和 Android 版本、浏览器）；
排版问题附截图，服务端问题附 `data/paperscroll.log` 最后几行（先删掉 API key 和隐私内容）。
抽错了「问题 / 方法 / 结果」句子也很有用：写上 arXiv 编号和应该选哪一句。

## 开发环境

```bash
cd server
uv sync
uv run python run.py            # http://127.0.0.1:8765
```

`web/` 界面没有构建步骤，改完刷新页面即可。

- `server/dev/sandbox_server.py` 在 8799 端口用数据库**副本**起第二个服务，不会动到你真实的论文库和画像。
- `server/dev/glance_check.py 20` 随机打印 20 篇论文抽出的问题 / 方法 / 结果。
- `server/dev/shots_multi.ps1 -path "__frame"`（Windows）对沙盒截手机尺寸的图。

请不要在真实画像上测试：修改课题或把论文标为已读的脚本会改变你的推荐结果。

## Pull Request 要求

- 一个 PR 只做一件事，简要说明用户能看到的变化（界面改动请附截图）。
- Python：尽量只用标准库和已有依赖，写类型注解，引入较重的新依赖前先讨论。JavaScript：原生浏览器 JS，不用框架，不加构建步骤。
- 服务端要能在 Windows、Linux、macOS 上运行。
- 行为有变化时，在 `CHANGELOG.md` 的 *Unreleased* 下记一笔，并更新文档。
- 不要提交 `data/`、API key、你自己的服务器地址或任何隐私内容。

## 联系

杨昆谕（Kunyu Yang）— kyyang26@m.fudan.edu.cn
