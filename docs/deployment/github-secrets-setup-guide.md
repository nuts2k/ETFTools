# GitHub Secrets 配置步骤

## 第一步：创建 DockerHub Access Token

### 1.1 登录 DockerHub

访问 [DockerHub](https://hub.docker.com/) 并登录你的账户。

### 1.2 进入安全设置

1. 点击右上角的用户头像
2. 选择 **"Account Settings"**
3. 在左侧菜单中选择 **"Security"**
4. 或直接访问：https://hub.docker.com/settings/security

### 1.3 创建新的 Access Token

1. 在 "Access Tokens" 部分，点击 **"New Access Token"** 按钮

2. 填写 Token 信息：
   - **Access Token Description**: `GitHub Actions - ETFTools`
   - **Access permissions**: 选择 **"Read, Write, Delete"**

3. 点击 **"Generate"** 按钮

4. **重要**：立即复制生成的 Token
   - Token 格式类似：`dckr_pat_xxxxxxxxxxxxxxxxxxxxx`
   - Token 只显示一次，关闭后无法再次查看
   - 建议先保存到安全的地方（如密码管理器）

### 1.4 记录你的 DockerHub 用户名

- 你的 DockerHub 用户名（不是邮箱）
- 例如：如果你的 DockerHub 主页是 `https://hub.docker.com/u/yourname`
- 那么你的用户名就是 `yourname`

---

## 第二步：在 GitHub 仓库中添加 Secrets

### 2.1 进入仓库设置

1. 打开你的 GitHub 仓库页面
2. 点击仓库顶部的 **"Settings"** 标签
3. 在左侧菜单中找到 **"Secrets and variables"**
4. 点击展开，选择 **"Actions"**

### 2.2 添加 DOCKERHUB_USERNAME

1. 点击 **"New repository secret"** 按钮

2. 填写 Secret 信息：
   - **Name**: `DOCKERHUB_USERNAME`
   - **Secret**: 输入你的 DockerHub 用户名（例如：`yourname`）

3. 点击 **"Add secret"** 按钮

### 2.3 添加 DOCKERHUB_TOKEN

1. 再次点击 **"New repository secret"** 按钮

2. 填写 Secret 信息：
   - **Name**: `DOCKERHUB_TOKEN`
   - **Secret**: 粘贴第一步中复制的 Access Token

3. 点击 **"Add secret"** 按钮

### 2.4 验证配置

配置完成后，你应该在 "Repository secrets" 列表中看到两个 Secrets：
- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

**注意**：Secret 的值在添加后无法查看，只能更新或删除。

---

## 第三步：测试工作流

### 3.1 手动触发测试（推荐）

1. 进入仓库的 **"Actions"** 页面
2. 在左侧选择 **"Docker Multi-Platform Build"** 工作流
3. 点击右侧的 **"Run workflow"** 下拉按钮
4. 配置参数：
   - **Use workflow from**: `Branch: main`
   - **Custom tag for the image**: 留空或输入 `test`
   - **Push to DockerHub**: 选择 `false`（首次测试建议不推送）
5. 点击绿色的 **"Run workflow"** 按钮

### 3.2 查看构建日志

1. 工作流开始运行后，会出现在列表中
2. 点击工作流运行记录
3. 点击 **"build"** 作业查看详细日志
4. 等待构建完成（首次构建约 20-30 分钟）

### 3.3 验证构建成功

构建成功的标志：
- ✅ 所有步骤显示绿色对勾
- ✅ "Build and push Docker image" 步骤成功
- ✅ "Generate build summary" 显示构建信息
- ✅ 如果选择了推送，"Verify multi-arch manifest" 步骤成功

---

## 常见问题

### Q1: 找不到 Settings 标签

**原因**：你可能没有仓库的管理员权限。

**解决方案**：
- 确认你是仓库的 Owner 或 Admin
- 如果是 Fork 的仓库，需要在你自己的 Fork 中配置

### Q2: 认证失败

**错误信息**：`Error: Cannot perform an interactive login from a non TTY device`

**解决方案**：
1. 检查 Secret 名称是否完全正确（区分大小写）
   - 必须是 `DOCKERHUB_USERNAME`（不是 `DOCKER_USERNAME`）
   - 必须是 `DOCKERHUB_TOKEN`（不是 `DOCKER_TOKEN`）
2. 确认 Token 是 Access Token（不是密码）
3. 检查 Token 权限是否包含 Read, Write, Delete
4. 确认 Token 未过期

### Q3: 构建超时

**错误信息**：`Error: The operation was canceled.`

**解决方案**：
1. 首次构建时间较长（20-30 分钟），这是正常的
2. 检查网络连接是否稳定
3. 如果持续超时，可以在工作流文件中增加 `timeout-minutes`

### Q4: 推送失败

**错误信息**：`denied: requested access to the resource is denied`

**解决方案**：
1. 确认 DockerHub 用户名正确
2. 确认 Token 权限包含 Write
3. 确认 DockerHub 账户未被限制

---

## 安全提示

1. **不要泄露 Token**
   - 不要在代码、日志、截图中暴露 Token
   - 不要将 Token 提交到 Git 仓库

2. **定期轮换 Token**
   - 建议每 3-6 个月更新一次 Token
   - 如果 Token 泄露，立即在 DockerHub 中删除

3. **最小权限原则**
   - 只授予必要的权限
   - 如果只需要推送镜像，Read, Write 权限即可

4. **监控使用情况**
   - 定期检查 DockerHub 的访问日志
   - 关注异常的拉取或推送活动

---

## 下一步

配置完成后，你可以：

1. **测试 PR 构建**
   ```bash
   git checkout -b test-ci
   git push origin test-ci
   # 在 GitHub 上创建 PR
   ```

2. **测试 main 分支推送**
   ```bash
   git push origin main
   # 会自动构建并推送到 DockerHub
   ```

3. **测试版本标签**
   ```bash
   git tag v0.0.1-test
   git push origin v0.0.1-test
   # 会自动构建、推送并创建 Release
   ```

4. **验证 DockerHub 镜像**
   - 访问 https://hub.docker.com/r/yourname/etftool
   - 检查镜像是否存在
   - 验证多架构支持

---

**配置完成！** 🎉

如果遇到问题，请查看：
- [GitHub Actions 配置指南](github-actions-setup.md)
- [故障排查章节](github-actions-setup.md#故障排除)
