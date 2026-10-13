[app]
title = 条码PDF生成器
package.name = barcodepdf
package.domain = org.example
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 3.0
requirements = python3,kivy==2.3.0,pillow,pyzbar,libzbar
orientation = portrait
fullscreen = 0
android.api = 33
android.apptheme = @android:style/Theme.NoTitleBar.Fullscreen
android.ndk = 25b
android.ndk_api = 21
android.minapi = 21
android.skip_update = False
android.accept_sdk_license = True
android.archs = arm64-v8a, armeabi-v7a
android.permissions = CAMERA, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, READ_MEDIA_IMAGES
android.features = android.hardware.camera
android.presplash_color = #2688EB
p4a.branch = master
p4a.bootstrap = sdl2
log_level = 2
warn_on_root = 1
