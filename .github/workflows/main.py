#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
条码拍照PDF生成器 - Android App
功能：拍摄3张照片（第1张为条码），自动识别条码作为PDF文件名，
      将3张图片合并为同一个PDF文档，支持自定义保存路径。
"""

import os
import sys
import time
import uuid
from datetime import datetime

# ============ 平台检测 ============
IS_ANDROID = False
try:
    from jnius import autoclass, cast, java_method, PythonJavaClass
    from android import mActivity
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path, app_storage_path
    IS_ANDROID = True
except ImportError:
    pass

# ============ Kivy导入 ============
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image as KivyImage
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.graphics.texture import Texture
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.camera import Camera as CameraWidget
from kivy.properties import StringProperty, ListProperty, ObjectProperty, NumericProperty

# ============ 图像处理 & 条码识别 ============
try:
    from PIL import Image as PILImage, ImageOps, ImageEnhance
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    from pyzbar.pyzbar import decode as zbar_decode
    from pyzbar.pyzbar import ZBarSymbol
    HAS_ZBAR = True
except ImportError:
    HAS_ZBAR = False

# ============ KV语言定义UI ============
KV = '''
<WelcomeScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(30)
        spacing: dp(20)
        canvas.before:
            Color:
                rgba: 0.95, 0.97, 0.99, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Widget:
            size_hint_y: 0.1

        Label:
            text: "📷"
            font_size: sp(72)
            size_hint_y: 0.18

        Label:
            text: "条码拍照PDF"
            font_size: sp(30)
            bold: True
            color: 0.15, 0.25, 0.45, 1
            size_hint_y: 0.08

        Label:
            text: "拍摄条码 + 两张图片\\n自动识别条码命名，合并为PDF"
            font_size: sp(16)
            color: 0.4, 0.45, 0.55, 1
            halign: 'center'
            size_hint_y: 0.15

        Widget:
            size_hint_y: 0.08

        Button:
            text: "开 始 拍 照"
            font_size: sp(22)
            bold: True
            size_hint_y: 0.13
            background_normal: ''
            background_color: 0.2, 0.55, 0.9, 1
            on_press: root.start_capture()

        Widget:
            size_hint_y: 0.28

<CameraScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(8)
        spacing: dp(6)
        canvas.before:
            Color:
                rgba: 0.08, 0.08, 0.1, 1
            Rectangle:
                pos: self.pos
                size: self.size

        # 顶部标题栏
        BoxLayout:
            size_hint_y: 0.07
            orientation: 'horizontal'
            spacing: dp(8)
            Button:
                text: "← 返回"
                size_hint_x: 0.2
                font_size: sp(14)
                background_normal: ''
                background_color: 0.4, 0.4, 0.45, 1
                on_press: root.go_back()
            Label:
                text: root.step_title
                font_size: sp(16)
                bold: True
                color: 1, 1, 1, 1
            Label:
                text: root.step_hint
                size_hint_x: 0.2
                font_size: sp(13)
                color: 0.7, 0.9, 1, 1
                bold: True

        # 相机预览区域
        BoxLayout:
            id: cam_container
            size_hint_y: 0.65
            canvas.before:
                Color:
                    rgba: 0, 0, 0, 1
                Rectangle:
                    pos: self.pos
                    size: self.size

        # 识别结果显示区
        Label:
            id: result_label
            text: ""
            size_hint_y: 0.06
            font_size: sp(13)
            color: 0.4, 1, 0.5, 1
            halign: 'center'

        # 拍照按钮
        Button:
            id: capture_btn
            text: "📷 拍 照"
            size_hint_y: 0.13
            font_size: sp(24)
            bold: True
            background_normal: ''
            background_color: 0.85, 0.25, 0.2, 1
            on_press: root.capture()

        # 操作提示
        Label:
            text: root.tip_text
            size_hint_y: 0.05
            font_size: sp(11)
            color: 0.65, 0.7, 0.78, 1
            halign: 'center'

<PreviewScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(12)
        spacing: dp(10)
        canvas.before:
            Color:
                rgba: 0.93, 0.95, 0.98, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Label:
            text: "拍摄预览"
            font_size: sp(22)
            bold: True
            color: 0.15, 0.25, 0.4, 1
            size_hint_y: 0.06

        # 三图预览
        GridLayout:
            cols: 3
            spacing: dp(6)
            size_hint_y: 0.45

            BoxLayout:
                orientation: 'vertical'
                spacing: dp(3)
                Label:
                    text: "① 条码"
                    font_size: sp(12)
                    bold: True
                    color: 0.15, 0.55, 0.15, 1
                    size_hint_y: 0.1
                Image:
                    id: img_barcode
                    source: ''
                    allow_stretch: True
                    keep_ratio: True
                Button:
                    text: "重拍"
                    font_size: sp(11)
                    size_hint_y: 0.11
                    background_normal: ''
                    background_color: 0.9, 0.6, 0.2, 1
                    on_press: root.retake(0)

            BoxLayout:
                orientation: 'vertical'
                spacing: dp(3)
                Label:
                    text: "② 图片2"
                    font_size: sp(12)
                    bold: True
                    color: 0.3, 0.35, 0.5, 1
                    size_hint_y: 0.1
                Image:
                    id: img_pic2
                    source: ''
                    allow_stretch: True
                    keep_ratio: True
                Button:
                    text: "重拍"
                    font_size: sp(11)
                    size_hint_y: 0.11
                    background_normal: ''
                    background_color: 0.9, 0.6, 0.2, 1
                    on_press: root.retake(1)

            BoxLayout:
                orientation: 'vertical'
                spacing: dp(3)
                Label:
                    text: "③ 图片3"
                    font_size: sp(12)
                    bold: True
                    color: 0.3, 0.35, 0.5, 1
                    size_hint_y: 0.1
                Image:
                    id: img_pic3
                    source: ''
                    allow_stretch: True
                    keep_ratio: True
                Button:
                    text: "重拍"
                    font_size: sp(11)
                    size_hint_y: 0.11
                    background_normal: ''
                    background_color: 0.9, 0.6, 0.2, 1
                    on_press: root.retake(2)

        # 条码信息和文件名
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: 0.2
            spacing: dp(5)
            padding: dp(8)
            canvas.before:
                Color:
                    rgba: 1, 1, 1, 0.95
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(8)]

            Label:
                id: barcode_info
                text: "识别条码: "
                font_size: sp(13)
                color: 0.15, 0.45, 0.15, 1
                halign: 'center'

            BoxLayout:
                orientation: 'horizontal'
                spacing: dp(6)
                Label:
                    text: "文件名:"
                    size_hint_x: 0.18
                    font_size: sp(13)
                    color: 0.3, 0.3, 0.4, 1
                TextInput:
                    id: filename_input
                    text: ""
                    font_size: sp(14)
                    multiline: False
                    background_normal: ''
                    background_color: 0.95, 0.97, 1, 1
                    foreground_color: 0.1, 0.1, 0.2, 1

        # 保存路径
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.09
            spacing: dp(6)
            Label:
                text: "保存至:"
                size_hint_x: 0.18
                font_size: sp(12)
                color: 0.3, 0.3, 0.4, 1
            TextInput:
                id: path_input
                text: ""
                font_size: sp(11)
                multiline: False
                readonly: True
                background_normal: ''
                background_color: 0.95, 0.97, 1, 1
                foreground_color: 0.2, 0.2, 0.3, 1
            Button:
                text: "浏览"
                size_hint_x: 0.18
                font_size: sp(12)
                background_normal: ''
                background_color: 0.3, 0.55, 0.85, 1
                on_press: root.choose_path()

        # 底部按钮
        BoxLayout:
            orientation: 'horizontal'
            size_hint_y: 0.11
            spacing: dp(10)
            Button:
                text: "重新开始"
                font_size: sp(15)
                background_normal: ''
                background_color: 0.6, 0.6, 0.65, 1
                on_press: root.restart()
            Button:
                text: "✔ 生成PDF"
                font_size: sp(20)
                bold: True
                background_normal: ''
                background_color: 0.15, 0.7, 0.25, 1
                on_press: root.generate_pdf()

<ResultScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(30)
        spacing: dp(18)
        canvas.before:
            Color:
                rgba: 0.93, 0.98, 0.93, 1
            Rectangle:
                pos: self.pos
                size: self.size

        Widget:
            size_hint_y: 0.08

        Label:
            text: "✅"
            font_size: sp(72)
            size_hint_y: 0.2

        Label:
            text: "PDF生成成功！"
            font_size: sp(26)
            bold: True
            color: 0.15, 0.5, 0.2, 1
            size_hint_y: 0.08

        Label:
            id: file_info
            text: ""
            font_size: sp(13)
            color: 0.3, 0.4, 0.3, 1
            halign: 'center'
            size_hint_y: 0.22
            text_size: self.width, None

        Widget:
            size_hint_y: 0.08

        Button:
            text: "继续拍摄新文档"
            font_size: sp(18)
            bold: True
            size_hint_y: 0.1
            background_normal: ''
            background_color: 0.2, 0.6, 0.85, 1
            on_press: root.continue_new()

        Button:
            text: "返回首页"
            font_size: sp(15)
            size_hint_y: 0.08
            background_normal: ''
            background_color: 0.5, 0.55, 0.65, 1
            on_press: root.go_home()

        Widget:
            size_hint_y: 0.16
'''

Builder.load_string(KV)


# ============ 工具函数 ============

def get_default_save_dir():
    """获取默认保存目录"""
    if IS_ANDROID:
        try:
            documents_dir = os.path.join(
                primary_external_storage_path(), 'Documents', 'BarcodePDF')
            os.makedirs(documents_dir, exist_ok=True)
            return documents_dir
        except Exception:
            pass
        try:
            save_dir = os.path.join(primary_external_storage_path(), 'BarcodePDF')
            os.makedirs(save_dir, exist_ok=True)
            return save_dir
        except Exception:
            return app_storage_path()
    else:
        save_dir = os.path.join(os.path.expanduser('~'), 'BarcodePDF')
        os.makedirs(save_dir, exist_ok=True)
        return save_dir


def _correct_exif(img):
    """根据EXIF旋转图片"""
    try:
        exif = img.getexif()
        if exif:
            orientation = exif.get(274, 1)
            if orientation == 3:
                img = img.rotate(180, expand=True)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 8:
                img = img.rotate(90, expand=True)
    except Exception:
        pass
    return img


def decode_barcode(image_path):
    """从图片中识别条码/二维码，返回条码文本"""
    if not HAS_ZBAR or not HAS_PIL:
        return None
    try:
        pil_img = PILImage.open(image_path)
        pil_img = _correct_exif(pil_img)
        pil_img = pil_img.convert('L')  # 灰度化提高识别率

        # 对比度增强
        try:
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(2.0)
        except Exception:
            pass

        # 多方向尝试
        for angle in [0, 90, 180, 270]:
            try:
                if angle != 0:
                    test_img = pil_img.rotate(angle, expand=True)
                else:
                    test_img = pil_img
                results = zbar_decode(test_img)
                if results:
                    for r in results:
                        for enc in ('utf-8', 'gbk', 'latin-1'):
                            try:
                                text = r.data.decode(enc).strip()
                                if text and len(text) > 1:
                                    return text
                            except Exception:
                                continue
            except Exception:
                continue

        # 缩放再试
        for scale in (0.5, 0.75, 1.5, 2.0):
            try:
                w, h = pil_img.size
                nw, nh = int(w * scale), int(h * scale)
                if nw < 100 or nh < 100:
                    continue
                small = pil_img.resize((nw, nh))
                results = zbar_decode(small)
                if results:
                    for r in results:
                        for enc in ('utf-8', 'gbk', 'latin-1'):
                            try:
                                text = r.data.decode(enc).strip()
                                if text and len(text) > 1:
                                    return text
                            except Exception:
                                continue
            except Exception:
                continue
        return None
    except Exception as e:
        print(f"条码识别出错: {e}")
        return None


def images_to_pdf(image_paths, pdf_path):
    """将多张图片合并为一个PDF文件"""
    if not HAS_PIL:
        return False
    try:
        imgs = []
        first_img = None
        for p in image_paths:
            try:
                img = PILImage.open(p).convert('RGB')
                img = _correct_exif(img)
                # 适当压缩避免PDF过大
                w, h = img.size
                if max(w, h) > 2000:
                    ratio = 2000 / max(w, h)
                    img = img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
                if first_img is None:
                    first_img = img
                else:
                    imgs.append(img)
            except Exception as e:
                print(f"打开图片失败 {p}: {e}")
                return False
        if first_img:
            first_img.save(pdf_path, "PDF", resolution=150.0,
                          save_all=True, append_images=imgs)
            return True
        return False
    except Exception as e:
        print(f"PDF生成出错: {e}")
        return False


# ============ 屏幕类 ============

class WelcomeScreen(Screen):
    def start_capture(self):
        app = App.get_running_app()
        app.reset_session()
        app.root.current = 'camera'
        Clock.schedule_once(lambda dt: app.root.get_screen('camera').prepare_step(0), 0.1)


class CameraScreen(Screen):
    step_title = StringProperty("第一步：拍摄条码")
    step_hint = StringProperty("1/3")
    tip_text = StringProperty("请将条码/二维码对准镜头，保持清晰")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.camera = None
        self.current_step = 0
        self.temp_dir = None
        self._init_attempts = 0

    def on_pre_enter(self):
        self._init_attempts = 0
        Clock.schedule_once(self.init_camera, 0.4)

    def on_leave(self):
        self.release_camera()

    def init_camera(self, dt=0):
        self.release_camera()
        container = self.ids.cam_container
        container.clear_widgets()
        self._init_attempts += 1
        # Android上尝试多个索引（0=后置通常成立，但有些机型不同）
        cam_indices = [0, 1] if self._init_attempts == 1 else [1, 0]
        for idx in cam_indices:
            try:
                self.camera = CameraWidget(play=True, index=idx, resolution=(1280, 720))
                container.add_widget(self.camera)
                return
            except Exception as e:
                print(f"摄像头 idx={idx} 初始化失败: {e}")
                self.camera = None
        # 全部失败
        err_label = Label(
            text="无法打开摄像头\n请检查相机权限后重启APP",
            font_size=sp(16), color=(1, 0.5, 0.5, 1), halign='center')
        container.add_widget(err_label)

    def release_camera(self):
        if self.camera:
            try:
                self.camera.play = False
            except Exception:
                pass
            try:
                self.ids.cam_container.clear_widgets()
            except Exception:
                pass
            self.camera = None

    def prepare_step(self, step):
        self.current_step = step
        titles = [
            ("第一步：拍摄条码", "1/3", "将条码/二维码对准镜头，保持光线充足、图像清晰"),
            ("第二步：拍摄图片2", "2/3", "请拍摄与条码相关的第二张图片"),
            ("第三步：拍摄图片3", "3/3", "请拍摄与条码相关的第三张图片"),
        ]
        self.step_title, self.step_hint, self.tip_text = titles[step]
        self.ids.result_label.text = ""

    def capture(self):
        if not self.camera:
            self.show_popup("提示", "摄像头未就绪，请返回重试")
            return
        self.ids.capture_btn.disabled = True
        self.ids.capture_btn.text = "处理中..."
        Clock.schedule_once(self._do_capture, 0.2)

    def _do_capture(self, dt):
        btn_reset = True
        try:
            texture = self.camera.texture
            if not texture:
                self.ids.result_label.text = "⚠️ 获取图像失败，请重试"
                self.ids.capture_btn.disabled = False
                self.ids.capture_btn.text = "📷 重新拍摄"
                return

            app = App.get_running_app()
            self.temp_dir = app.temp_dir
            img_name = f"capture_{self.current_step}_{int(time.time()*1000)}.jpg"
            img_path = os.path.join(self.temp_dir, img_name)

            if HAS_PIL:
                size = texture.size
                pixels = texture.pixels
                mode = 'RGBA' if len(pixels) == size[0]*size[1]*4 else 'RGB'
                pil_img = PILImage.frombytes(mode, size, pixels)
                pil_img = pil_img.convert('RGB')
                # 纹理是上下翻转的，翻转回来
                pil_img = pil_img.transpose(PILImage.FLIP_TOP_BOTTOM)
                pil_img.save(img_path, 'JPEG', quality=92)
            else:
                texture.save(img_path, flipped=False)

            # 第一步：识别条码
            if self.current_step == 0:
                self.ids.result_label.text = "正在识别条码..."
                barcode_text = decode_barcode(img_path)
                if not barcode_text:
                    self.ids.result_label.text = "⚠️ 未识别到条码，请重新对准拍摄"
                    self.ids.capture_btn.disabled = False
                    self.ids.capture_btn.text = "📷 重新拍摄"
                    try:
                        os.remove(img_path)
                    except Exception:
                        pass
                    return
                self.ids.result_label.text = f"✓ 识别成功: {barcode_text[:30]}"
                app.barcode_text = barcode_text

            app.captured_images[self.current_step] = img_path
            btn_reset = False

            if self.current_step < 2:
                Clock.schedule_once(lambda dt: self._goto_next(), 0.7)
            else:
                Clock.schedule_once(lambda dt: self._goto_preview(), 0.7)

        except Exception as e:
            print(f"拍照处理出错: {e}")
            import traceback; traceback.print_exc()
            self.ids.result_label.text = f"拍照失败: {str(e)[:40]}"
            self.ids.capture_btn.disabled = False
            self.ids.capture_btn.text = "📷 拍 照"
        finally:
            if btn_reset:
                pass

    def _goto_next(self):
        self.current_step += 1
        self.prepare_step(self.current_step)
        self.ids.capture_btn.disabled = False
        self.ids.capture_btn.text = "📷 拍 照"

    def _goto_preview(self):
        self.release_camera()
        app = App.get_running_app()
        app.root.current = 'preview'
        app.root.get_screen('preview').load_images()
        self.ids.capture_btn.disabled = False
        self.ids.capture_btn.text = "📷 拍 照"

    def go_back(self):
        app = App.get_running_app()
        self.release_camera()
        if self.current_step > 0:
            self.current_step -= 1
            self.prepare_step(self.current_step)
            Clock.schedule_once(self.init_camera, 0.2)
        else:
            app.root.current = 'welcome'

    def show_popup(self, title, content):
        box = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(12))
        lbl = Label(text=content, font_size=sp(15), color=(0.2, 0.2, 0.2, 1))
        btn = Button(text="确定", size_hint_y=0.3, font_size=sp(16),
                     background_normal='', background_color=(0.3, 0.55, 0.85, 1))
        box.add_widget(lbl)
        box.add_widget(btn)
        popup = Popup(title=title, content=box, size_hint=(0.78, 0.38),
                      auto_dismiss=False)
        btn.bind(on_press=popup.dismiss)
        popup.open()


class PreviewScreen(Screen):

    def on_pre_enter(self):
        pass

    def load_images(self):
        app = App.get_running_app()
        imgs = app.captured_images
        for key, default in [('img_barcode', 0), ('img_pic2', 1), ('img_pic3', 2)]:
            src = imgs[default] if imgs[default] else ''
            self.ids[key].source = src
            self.ids[key].reload()

        barcode = app.barcode_text or "未识别"
        self.ids.barcode_info.text = f"识别条码: {barcode}"
        safe_name = self._safe_filename(barcode) if barcode and barcode != "未识别" else "document"
        self.ids.filename_input.text = safe_name
        self.ids.path_input.text = get_default_save_dir()

    def _safe_filename(self, name):
        invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|', '\n', '\r', '\t']
        result = str(name)
        for ch in invalid_chars:
            result = result.replace(ch, '_')
        result = result.strip().strip('.')
        if len(result) > 80:
            result = result[:80]
        return result or "document"

    def retake(self, step_index):
        app = App.get_running_app()
        app.root.current = 'camera'
        cam_screen = app.root.get_screen('camera')
        cam_screen.prepare_step(step_index)
        Clock.schedule_once(cam_screen.init_camera, 0.2)

    def choose_path(self):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8))

        default_dirs = []
        if IS_ANDROID:
            try:
                base = primary_external_storage_path()
                default_dirs.append(os.path.join(base, 'Documents', 'BarcodePDF'))
                default_dirs.append(os.path.join(base, 'Download', 'BarcodePDF'))
                default_dirs.append(os.path.join(base, 'BarcodePDF'))
            except Exception:
                pass
        default_dirs.append(get_default_save_dir())
        seen = set()
        unique_dirs = []
        for d in default_dirs:
            if d and d not in seen:
                seen.add(d); unique_dirs.append(d)

        btn_layout = GridLayout(cols=1, spacing=dp(6), size_hint_y=None)
        btn_layout.bind(minimum_height=btn_layout.setter('height'))
        for d in unique_dirs:
            btn = Button(text=d, font_size=sp(12), size_hint_y=None, height=dp(44),
                         background_normal='', background_color=(0.92, 0.94, 0.98, 1),
                         color=(0.2, 0.25, 0.4, 1), halign='left',
                         text_size=(None, None))
            btn.bind(on_press=lambda b, path=d, pop=None: self._set_path(path, popup))
            btn_layout.add_widget(btn)

        scroll = ScrollView(size_hint_y=0.5)
        scroll.add_widget(btn_layout)

        title_lbl = Label(text="选择保存目录（常用位置）：",
                          size_hint_y=0.08, font_size=sp(14),
                          color=(0.2, 0.2, 0.3, 1))
        content.add_widget(title_lbl)
        content.add_widget(scroll)

        custom_box = BoxLayout(orientation='horizontal', spacing=dp(6), size_hint_y=0.15)
        custom_input = TextInput(text=self.ids.path_input.text, font_size=sp(12),
                                 multiline=False, hint_text="或手动输入完整路径")
        custom_ok = Button(text="确定", size_hint_x=0.22, font_size=sp(14),
                           background_normal='', background_color=(0.2, 0.7, 0.3, 1))
        custom_box.add_widget(custom_input)
        custom_box.add_widget(custom_ok)
        content.add_widget(custom_box)

        tip = Label(text="提示：输入格式如 /storage/emulated/0/Documents/BarcodePDF",
                    size_hint_y=0.08, font_size=sp(10), color=(0.5, 0.5, 0.6, 1))
        content.add_widget(tip)

        cancel_btn = Button(text="取消", size_hint_y=0.1, font_size=sp(15),
                            background_normal='', background_color=(0.6, 0.6, 0.65, 1))
        content.add_widget(cancel_btn)

        popup = Popup(title="选择保存路径", content=content, size_hint=(0.92, 0.75))
        cancel_btn.bind(on_press=popup.dismiss)
        custom_ok.bind(on_press=lambda b: self._set_path(custom_input.text.strip(), popup))
        popup.open()

    def _set_path(self, path, popup):
        if path:
            self.ids.path_input.text = path
        popup.dismiss()

    def restart(self):
        app = App.get_running_app()
        app.reset_session()
        app.root.current = 'welcome'

    def generate_pdf(self):
        app = App.get_running_app()
        imgs = app.captured_images
        for i, img in enumerate(imgs):
            if not img or not os.path.exists(img):
                self._show_msg("提示", f"第{i+1}张图片缺失，请重新拍摄")
                return

        filename = self.ids.filename_input.text.strip() or "document"
        filename = self._safe_filename(filename)
        if not filename.lower().endswith('.pdf'):
            filename += '.pdf'

        save_dir = self.ids.path_input.text.strip() or get_default_save_dir()
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception as e:
            self._show_msg("错误", f"无法创建目录，请检查路径:\n{str(e)[:80]}")
            return

        pdf_path = os.path.join(save_dir, filename)
        # 同名文件自动加序号
        if os.path.exists(pdf_path):
            base, ext = os.path.splitext(pdf_path)
            counter = 1
            while os.path.exists(f"{base}_{counter}{ext}"):
                counter += 1
            pdf_path = f"{base}_{counter}{ext}"

        loading = self._show_loading("正在生成PDF，请稍候...")
        Clock.schedule_once(lambda dt: self._do_generate_pdf(imgs, pdf_path, loading), 0.3)

    def _do_generate_pdf(self, imgs, pdf_path, loading):
        try:
            success = images_to_pdf(list(imgs), pdf_path)
        except Exception as e:
            print(f"PDF生成异常: {e}")
            import traceback; traceback.print_exc()
            success = False
        loading.dismiss()

        if success and os.path.exists(pdf_path):
            app = App.get_running_app()
            app.last_pdf_path = pdf_path
            app.root.current = 'result'
            app.root.get_screen('result').show_result(pdf_path)
        else:
            self._show_msg("错误", "PDF生成失败，请检查存储空间和权限后重试")

    def _show_msg(self, title, msg):
        box = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(12))
        lbl = Label(text=msg, font_size=sp(14), color=(0.2, 0.2, 0.2, 1),
                    halign='center', valign='middle')
        lbl.bind(size=lambda s, v: setattr(s, 'text_size', v))
        btn = Button(text="确定", size_hint_y=0.3, font_size=sp(16),
                     background_normal='', background_color=(0.3, 0.55, 0.85, 1))
        box.add_widget(lbl)
        box.add_widget(btn)
        popup = Popup(title=title, content=box, size_hint=(0.8, 0.4), auto_dismiss=False)
        btn.bind(on_press=popup.dismiss)
        popup.open()

    def _show_loading(self, msg):
        box = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        lbl = Label(text=msg, font_size=sp(15), color=(0.3, 0.3, 0.4, 1))
        box.add_widget(lbl)
        popup = Popup(title="请稍候", content=box, size_hint=(0.65, 0.28),
                      auto_dismiss=False, separator_color=[0.3, 0.55, 0.85, 1])
        popup.open()
        return popup


class ResultScreen(Screen):
    def show_result(self, pdf_path):
        try:
            file_size = os.path.getsize(pdf_path)
            size_str = self._format_size(file_size)
        except Exception:
            size_str = "未知"
        self.ids.file_info.text = (
            f"文件：{os.path.basename(pdf_path)}\n"
            f"位置：{pdf_path}\n"
            f"大小：{size_str}\n\n"
            f"可在手机「文件管理」中查看"
        )

    def _format_size(self, size):
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f} KB"
        else:
            return f"{size/(1024*1024):.1f} MB"

    def continue_new(self):
        app = App.get_running_app()
        app.reset_session()
        app.root.current = 'camera'
        cam_screen = app.root.get_screen('camera')
        cam_screen.prepare_step(0)

    def go_home(self):
        app = App.get_running_app()
        app.reset_session()
        app.root.current = 'welcome'


# ============ 主应用 ============

class BarcodePDFApp(App):
    title = "条码拍照PDF"

    def build(self):
        # 申请Android权限（Android 13+ 需要细分媒体权限）
        if IS_ANDROID:
            Clock.schedule_once(self._request_permissions, 0.3)

        if IS_ANDROID:
            self.temp_dir = app_storage_path()
        else:
            self.temp_dir = os.path.join(os.path.expanduser('~'), '.barcodepdf_temp')
        os.makedirs(self.temp_dir, exist_ok=True)

        sm = ScreenManager()
        sm.add_widget(WelcomeScreen(name='welcome'))
        sm.add_widget(CameraScreen(name='camera'))
        sm.add_widget(PreviewScreen(name='preview'))
        sm.add_widget(ResultScreen(name='result'))

        self.captured_images = ['', '', '']
        self.barcode_text = ''
        self.last_pdf_path = ''
        return sm

    def _request_permissions(self, dt=0):
        if not IS_ANDROID:
            return
        perms = [Permission.CAMERA]
        # Android 13 (API 33) 用 READ_MEDIA_IMAGES；低版本用 WRITE_EXTERNAL_STORAGE / READ_EXTERNAL_STORAGE
        try:
            perms.append(Permission.WRITE_EXTERNAL_STORAGE)
            perms.append(Permission.READ_EXTERNAL_STORAGE)
        except Exception:
            pass
        try:
            # Android 13+ 新权限
            perms.append(Permission.READ_MEDIA_IMAGES)
        except Exception:
            pass
        try:
            request_permissions(perms)
        except Exception as e:
            print(f"权限请求失败: {e}")

    def reset_session(self):
        for f in self.captured_images:
            if f and os.path.exists(f) and self.temp_dir in f:
                try:
                    os.remove(f)
                except Exception:
                    pass
        self.captured_images = ['', '', '']
        self.barcode_text = ''
        self.last_pdf_path = ''

    def on_pause(self):
        return True

    def on_resume(self):
        pass


if __name__ == '__main__':
    Window.clearcolor = (0.95, 0.97, 0.99, 1)
    BarcodePDFApp().run()
