#!/bin/bash
# ==============================================
# 条码拍照PDF生成器 - Android APK 一键编译脚本
# 使用方法: chmod +x build.sh && ./build.sh
# ==============================================

set -e

echo "=========================================="
echo "  条码拍照PDF生成器 - Android 编译脚本"
echo "=========================================="
echo ""

# 检查是否在Linux环境
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "⚠️  警告: Buildozer推荐在Linux环境下编译（Ubuntu 20.04/22.04）"
    echo "   在macOS/Windows下可能需要使用虚拟机或WSL2"
    echo ""
fi

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到python3，请先安装Python 3.8+"
    exit 1
fi

echo "[1/5] 安装/更新 Buildozer 和依赖..."
pip3 install --user buildozer cython virtualenv 2>/dev/null || pip install buildozer cython virtualenv

echo ""
echo "[2/5] 检查系统依赖（Ubuntu/Debian）..."
if command -v apt &> /dev/null; then
    echo "   检测到apt包管理器，安装编译依赖..."
    sudo apt update -qq
    sudo apt install -y -qq git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
        zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev \
        libltdl-dev libusb-dev libzbar0 libzbar-dev patchelf 2>/dev/null
    echo "   ✓ 系统依赖安装完成"
else
    echo "   ⚠️  非Debian系系统，请手动安装以下依赖："
    echo "      git, zip, unzip, openjdk-17-jdk, autoconf, libtool, cmake, libffi-dev, libssl-dev, libzbar-dev"
fi

echo ""
echo "[3/5] 检查并准备p4a recipes..."
if [ ! -d "p4a-recipes" ]; then
    mkdir -p p4a-recipes
fi

echo ""
echo "[4/5] 开始编译APK（首次编译需要下载SDK/NDK，约需15-30分钟）..."
echo "   请确保网络连接稳定..."
echo ""

buildozer android clean 2>/dev/null || true
buildozer -v android debug

echo ""
echo "[5/5] 编译完成！"
echo ""

if [ -f "bin/barcodepdf-1.0-arm64-v8a-debug.apk" ] || [ -f "bin/barcodepdf-1.0-armeabi-v7a-debug.apk" ]; then
    echo "=========================================="
    echo "  ✅ APK编译成功！"
    echo "=========================================="
    echo ""
    echo "生成的APK文件位于 bin/ 目录下："
    ls -lh bin/*.apk 2>/dev/null
    echo ""
    echo "安装方法："
    echo "  1. 通过USB连接手机，开启USB调试"
    echo "  2. 执行: adb install -r bin/barcodepdf-1.0-*.apk"
    echo "  3. 或将APK文件传到手机后直接安装"
    echo ""
else
    echo "❌ 未找到生成的APK，请检查编译错误日志"
fi
