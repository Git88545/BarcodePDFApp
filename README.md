# 📸 条码PDF生成器 v3.0（Android）

## 功能
- ✅ 拍 3 张图片 **或** 从本地相册选择 3 张图片（支持拍照+相册混合）
- 🔍 自动识别条码（CODE128/EAN13/QR/PDF417 等）作为 PDF 文件名，未识别到可手动输入
- 📄 3 张图片自动校正方向、压缩后合并为一个 PDF
- 📁 自定义保存路径（Documents/Download/Pictures/根目录/应用私有目录/手动输入路径）
- 🇨🇳 全中文简洁 UI，防闪退设计（异常捕获、相机权限、同名自动编号、路径不可写自动回退）

## 一键云端编译出 APK（推荐）
1. 登录 https://github.com 并新建仓库（Public/Private 均可）
2. **重要**：Windows 请先在文件管理器中开启「显示隐藏的项目」，macOS 按 Cmd+Shift+. 显示隐藏文件；把本压缩包**所有内容**（含隐藏的 `.github` 文件夹）上传到仓库根目录
   - 若 `.github` 拖不进去：在 GitHub 点 Add file → Create new file → 文件名填 `.github/workflows/build.yml`，把本文件内对应内容复制粘贴保存
3. 上传完成后，点仓库顶部 **Actions** → 左侧选 **Build Android APK** → 点 **Run workflow** → 绿色按钮确认
4. 等待约 10~20 分钟，看到绿色 ✅ 后点进运行记录，底部 Artifacts 下载 `BarcodePDFApp-apk`（zip），解压得到 APK
5. 传到安卓手机安装，允许「相机」「存储」权限即可使用

## 本地编译（可选）
已装 WSL2/Ubuntu 可执行：
```bash
pip3 install --user buildozer cython==0.29.37
export PATH="$HOME/.local/bin:$PATH"
buildozer android debug
# 产物在 bin/ 目录
```
