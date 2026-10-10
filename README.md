# 📷 条码拍照PDF生成器 - Android APP

拍摄3张照片（其中1张为条码），自动识别条码作为PDF文件名，将3张图片合并到同一个PDF中，支持自定义保存路径。

## ✨ 功能特性

- ✅ **三步拍照**：引导式分步拍摄，第一张专门用于条码识别，其余两张为关联图片
- ✅ **智能条码识别**：集成ZBar引擎，支持 CODE128/EAN13/QR/PDF417 等10多种码制；自动旋转、缩放、灰度增强，识别率高
- ✅ **自动命名**：以条码内容作为PDF文件名，自动过滤非法字符、可手动修改
- ✅ **合并为PDF**：Pillow引擎生成标准PDF，EXIF方向自动校正，图片过大自动压缩
- ✅ **自定义路径**：预设 Documents/Download/根目录 三种常用位置，也可手动输入任意路径
- ✅ **界面简洁**：全中文UI，大按钮、清晰提示、步骤进度一目了然
- ✅ **防闪退**：全链路异常捕获、权限动态申请、摄像头多索引重试、文件不覆盖（自动编号）
- ✅ **单张重拍**：预览页支持只重拍某一张，不用全部重来

## 🚀 如何获得APK安装包（3分钟搞定）

### 方式一：GitHub云端编译（推荐，无需本地环境）

这是最快最可靠的方式，GitHub的服务器免费帮你编译：

**步骤：**

1. 注册/登录 [GitHub](https://github.com)（免费）
2. 点击右上角 `+` → `New repository`，命名为 `BarcodePDFApp`，选 Public，点 Create
3. 解压本压缩包，将里面所有文件拖到仓库页面上传（或用 git push）
4. 点击仓库顶部的 **Actions** 标签
5. 左侧选 **Build Android APK**，点击右侧 **Run workflow** → 绿色 **Run workflow** 按钮
6. 等待约 **10-15 分钟**（首次编译需要下载工具链，后续编译只需3-5分钟）
7. 编译完成后，点进该任务页面，底部 Artifacts 区域下载 **BarcodePDF-APK.zip**
8. 解压得到 `.apk` 文件，传到手机安装即可

> 💡 如果 Actions 显示需要启用，点绿色的 "I understand my workflows..." 按钮启用即可。

### 方式二：本地编译（需要Linux环境）

```bash
# Ubuntu/Debian/WSL2
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-dev \
    build-essential libffi-dev zlib1g-dev cmake autoconf libtool pkg-config
pip3 install --user buildozer cython==0.29.37
export PATH="$HOME/.local/bin:$PATH"

# 进入项目目录
cd BarcodePDFApp
buildozer android debug
# 成功后 APK 在 bin/ 目录下
```

## 📱 安装与使用

1. 将APK传到安卓手机（Android 7.0+）
2. 手机上点击APK安装，按提示授予「相机」和「存储」权限
3. 打开APP → 点「开始拍照」
4. **第一步**：对准条码/二维码拍摄，识别成功后自动进入下一步
5. **第二步、第三步**：拍摄关联图片
6. 预览页检查图片、确认文件名和保存路径（可点"浏览"切换位置）
7. 点「生成PDF」即可，生成的PDF在你选定的目录下

## 📂 项目结构

```
BarcodePDFApp/
├── main.py                    # 主程序（Kivy应用，含所有界面和逻辑）
├── buildozer.spec             # Android打包配置
├── build.sh                   # 本地编译脚本
├── requirements.txt           # PC测试依赖
├── README.md                  # 本说明文件
└── .github/
    └── workflows/
        └── build.yml          # GitHub Actions自动编译配置
```

## 🔧 技术栈

- **UI框架**：Kivy 2.3.0（跨平台Python UI）
- **条码识别**：pyzbar（ZBar的Python绑定）
- **图像处理**：Pillow（PIL）
- **PDF生成**：Pillow原生PDF输出（稳定兼容）
- **打包工具**：Buildozer + python-for-android
- **目标平台**：Android 7.0 (API 24) 及以上，arm64-v8a
