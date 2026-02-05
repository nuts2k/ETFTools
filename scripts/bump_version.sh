#!/bin/bash
# ETFTool 版本升级脚本
# 支持语义化版本自动升级（major/minor/patch）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 获取当前版本
CURRENT_VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
CURRENT_VERSION=${CURRENT_VERSION#v}

echo -e "${BLUE}当前版本: ${CURRENT_VERSION}${NC}"

# 解析版本号（去除预发布后缀）
BASE_VERSION="${CURRENT_VERSION%%-*}"
IFS='.' read -r MAJOR MINOR PATCH <<< "$BASE_VERSION"

# 验证版本号格式
if ! [[ "$MAJOR" =~ ^[0-9]+$ ]] || ! [[ "$MINOR" =~ ^[0-9]+$ ]] || ! [[ "$PATCH" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}错误: 无法解析版本号 '$CURRENT_VERSION'${NC}"
    exit 1
fi

# 确定升级类型
BUMP_TYPE=${1:-patch}

case $BUMP_TYPE in
  major)
    MAJOR=$((MAJOR + 1))
    MINOR=0
    PATCH=0
    ;;
  minor)
    MINOR=$((MINOR + 1))
    PATCH=0
    ;;
  patch)
    PATCH=$((PATCH + 1))
    ;;
  *)
    echo -e "${RED}错误: 无效的升级类型 '$BUMP_TYPE'${NC}"
    echo "用法: $0 [major|minor|patch]"
    echo ""
    echo "示例:"
    echo "  $0 patch  # 0.1.0 -> 0.1.1"
    echo "  $0 minor  # 0.1.1 -> 0.2.0"
    echo "  $0 major  # 0.2.0 -> 1.0.0"
    exit 1
    ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"
NEW_TAG="v$NEW_VERSION"

echo -e "${GREEN}新版本: ${NEW_VERSION}${NC}"
echo ""

# 确认操作
read -p "创建标签 $NEW_TAG? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "已取消。"
    exit 1
fi

# 更新 CHANGELOG.md
echo -e "${BLUE}更新 CHANGELOG.md...${NC}"
DATE=$(date +%Y-%m-%d)

# 检查 CHANGELOG.md 是否存在
if [ ! -f "$PROJECT_ROOT/CHANGELOG.md" ]; then
    echo "# Changelog" > "$PROJECT_ROOT/CHANGELOG.md"
    echo "" >> "$PROJECT_ROOT/CHANGELOG.md"
fi

# 创建临时文件
TEMP_FILE=$(mktemp)

# 写入新版本信息
cat > "$TEMP_FILE" << EOF
# Changelog

## [$NEW_VERSION] - $DATE

### 变更内容

- TODO: 请在此添加本次发布的详细变更说明

EOF

# 追加原有内容（跳过第一行的 "# Changelog"）
tail -n +2 "$PROJECT_ROOT/CHANGELOG.md" >> "$TEMP_FILE"

# 替换原文件
mv "$TEMP_FILE" "$PROJECT_ROOT/CHANGELOG.md"

echo -e "${GREEN}✓ CHANGELOG.md 已更新${NC}"

# 创建 Git 标签
echo -e "${BLUE}创建 Git 标签...${NC}"
git tag -a "$NEW_TAG" -m "Release $NEW_VERSION"

echo ""
echo -e "${GREEN}✓ 版本已升级到 $NEW_VERSION${NC}"
echo ""
echo -e "${YELLOW}后续步骤:${NC}"
echo "  1. 编辑 CHANGELOG.md 添加详细的发布说明"
echo "  2. 提交 CHANGELOG.md 变更:"
echo "     ${BLUE}git add CHANGELOG.md${NC}"
echo "     ${BLUE}git commit -m \"docs: update CHANGELOG for $NEW_VERSION\"${NC}"
echo "  3. 推送代码和标签:"
echo "     ${BLUE}git push origin main${NC}"
echo "     ${BLUE}git push origin $NEW_TAG${NC}"
echo "  4. GitHub Actions 将自动构建并发布"
echo ""
