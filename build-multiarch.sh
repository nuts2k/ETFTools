#!/bin/bash

# ============================================
# ETFTool 多架构 Docker 镜像构建脚本
# ============================================
# 支持平台: linux/amd64, linux/arm64
# 使用方法: ./build-multiarch.sh [选项]
# ============================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
BUILDER_NAME="etftool-multiarch"
IMAGE_NAME="etftool"
IMAGE_TAG="latest"
PLATFORMS="linux/amd64,linux/arm64"
PUSH=false
REGISTRY=""
LOAD=false

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示使用说明
show_usage() {
    cat << EOF
ETFTool 多架构 Docker 镜像构建脚本

使用方法:
    ./build-multiarch.sh [选项]

选项:
    -p, --platform PLATFORMS    目标平台 (默认: linux/amd64,linux/arm64)
                                单平台示例: linux/amd64
                                多平台示例: linux/amd64,linux/arm64

    -t, --tag TAG               镜像标签 (默认: latest)

    -n, --name NAME             镜像名称 (默认: etftool)

    -r, --registry REGISTRY     镜像仓库地址 (例如: docker.io/username)

    --push                      构建后推送到镜像仓库

    --load                      加载到本地 Docker (仅支持单平台)

    -h, --help                  显示此帮助信息

示例:
    # 本地单平台构建 (AMD64)
    ./build-multiarch.sh --platform linux/amd64 --load

    # 本地单平台构建 (ARM64)
    ./build-multiarch.sh --platform linux/arm64 --load

    # 多平台构建并推送到 Docker Hub
    ./build-multiarch.sh --registry docker.io/username --push

    # 多平台构建并推送到私有仓库
    ./build-multiarch.sh --registry registry.example.com/etftool --push

    # 自定义标签
    ./build-multiarch.sh --tag v1.0.0 --push

EOF
}

# 解析命令行参数
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -p|--platform)
                PLATFORMS="$2"
                shift 2
                ;;
            -t|--tag)
                IMAGE_TAG="$2"
                shift 2
                ;;
            -n|--name)
                IMAGE_NAME="$2"
                shift 2
                ;;
            -r|--registry)
                REGISTRY="$2"
                shift 2
                ;;
            --push)
                PUSH=true
                shift
                ;;
            --load)
                LOAD=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                print_error "未知选项: $1"
                show_usage
                exit 1
                ;;
        esac
    done
}

# 检查 Docker 环境
check_docker() {
    print_info "检查 Docker 环境..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker 守护进程未运行，请启动 Docker"
        exit 1
    fi

    print_success "Docker 环境检查通过"
}

# 检查 buildx
check_buildx() {
    print_info "检查 Docker Buildx..."

    if ! docker buildx version &> /dev/null; then
        print_error "Docker Buildx 未安装"
        print_info "请升级到 Docker 19.03 或更高版本"
        exit 1
    fi

    print_success "Docker Buildx 可用"
}

# 创建或使用 builder
setup_builder() {
    print_info "配置 Buildx Builder..."

    # 检查 builder 是否已存在
    if docker buildx inspect "$BUILDER_NAME" &> /dev/null; then
        print_info "使用现有 builder: $BUILDER_NAME"
        docker buildx use "$BUILDER_NAME"
    else
        print_info "创建新的 builder: $BUILDER_NAME"
        docker buildx create \
            --name "$BUILDER_NAME" \
            --driver docker-container \
            --use
    fi

    # 启动 builder
    print_info "启动 builder..."
    docker buildx inspect --bootstrap

    print_success "Builder 配置完成"
}

# 验证参数
validate_args() {
    # 检查 --load 和 --push 不能同时使用
    if [ "$LOAD" = true ] && [ "$PUSH" = true ]; then
        print_error "--load 和 --push 不能同时使用"
        exit 1
    fi

    # 检查多平台构建时不能使用 --load
    if [ "$LOAD" = true ] && [[ "$PLATFORMS" == *","* ]]; then
        print_error "--load 只支持单平台构建"
        print_info "请使用单个平台，例如: --platform linux/amd64"
        exit 1
    fi

    # 检查 --push 时必须指定 registry
    if [ "$PUSH" = true ] && [ -z "$REGISTRY" ]; then
        print_error "--push 需要指定 --registry"
        exit 1
    fi
}

# 构建镜像
build_image() {
    print_info "开始构建镜像..."
    print_info "平台: $PLATFORMS"

    # 构建完整的镜像名称
    if [ -n "$REGISTRY" ]; then
        FULL_IMAGE_NAME="$REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
    else
        FULL_IMAGE_NAME="$IMAGE_NAME:$IMAGE_TAG"
    fi

    print_info "镜像名称: $FULL_IMAGE_NAME"

    # 构建参数
    BUILD_ARGS=(
        "buildx" "build"
        "--platform" "$PLATFORMS"
        "-t" "$FULL_IMAGE_NAME"
        "-f" "Dockerfile"
    )

    # 添加 --push 或 --load
    if [ "$PUSH" = true ]; then
        BUILD_ARGS+=("--push")
        print_info "构建完成后将推送到镜像仓库"
    elif [ "$LOAD" = true ]; then
        BUILD_ARGS+=("--load")
        print_info "构建完成后将加载到本地 Docker"
    else
        print_warning "未指定 --push 或 --load，镜像将只存在于构建缓存中"
    fi

    BUILD_ARGS+=(".")

    # 执行构建
    print_info "执行构建命令..."
    echo "docker ${BUILD_ARGS[*]}"

    if docker "${BUILD_ARGS[@]}"; then
        print_success "镜像构建成功！"

        if [ "$PUSH" = true ]; then
            print_success "镜像已推送到: $FULL_IMAGE_NAME"
        elif [ "$LOAD" = true ]; then
            print_success "镜像已加载到本地 Docker"
            print_info "运行镜像: docker run -p 3000:3000 $FULL_IMAGE_NAME"
        fi
    else
        print_error "镜像构建失败"
        exit 1
    fi
}

# 显示构建信息
show_build_info() {
    echo ""
    echo "=========================================="
    echo "  ETFTool 多架构镜像构建"
    echo "=========================================="
    echo "镜像名称: $IMAGE_NAME"
    echo "镜像标签: $IMAGE_TAG"
    echo "目标平台: $PLATFORMS"
    if [ -n "$REGISTRY" ]; then
        echo "镜像仓库: $REGISTRY"
    fi
    if [ "$PUSH" = true ]; then
        echo "推送模式: 是"
    elif [ "$LOAD" = true ]; then
        echo "加载模式: 是"
    fi
    echo "=========================================="
    echo ""
}

# 主函数
main() {
    # 解析参数
    parse_args "$@"

    # 显示构建信息
    show_build_info

    # 验证参数
    validate_args

    # 检查环境
    check_docker
    check_buildx

    # 配置 builder
    setup_builder

    # 构建镜像
    build_image

    echo ""
    print_success "所有操作完成！"
    echo ""
}

# 脚本入口
main "$@"
