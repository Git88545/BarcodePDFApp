[app]

title = 条码拍照PDF
package.name = barcodepdf
package.domain = org.barcodepdf.app

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf

version = 1.0

# 核心依赖：去掉opencv，只用pillow+pyzbar+reportlab（编译更稳定快速）
requirements = python3,kivy==2.3.0,pillow,pyzbar,reportlab,numpy

orientation = portrait
fullscreen = 0

# Android 配置 - 使用较宽的API范围保证兼容性
android.api = 33
android.ndk = 25b
android.sdk = 24
android.minapi = 24
android.archs = arm64-v8a

# Android 权限
android.permissions = CAMERA, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, READ_MEDIA_IMAGES

# Android 特性
android.features = android.hardware.camera, android.hardware.camera.autofocus

bin = ./bin

log_level = 2

android.androidx = 1
android.buildmode = debug
android.release_artifact = apk

# p4a配置
p4a.branch = master
p4a.bootstrap = sdl2

android.allow_backup = True
android.windowSoftInputMode = adjustResize

# 避免在非termux环境出问题
android.skip_update = False
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 0
