# -*- coding: utf-8 -*-
"""
条码拍照PDF生成器 v3.0
功能：
1. 拍3张图片 或 从本地相册选择3张图片（条码图也支持从相册导入）
2. 自动识别条码（CODE128/EAN13/QR/PDF417等）作为PDF文件名
3. 自定义保存路径
4. 三张图合并为一个PDF文件
5. 全中文界面，简洁稳定
"""

import os
import sys
import time
import uuid
import shutil
from datetime import datetime

try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
    from PIL import Image

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image as KivyImage
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.logger import Logger

# ========== Android 专属导入 ==========
try:
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    from jnius import autoclass, cast
    IS_ANDROID = True
except ImportError:
    IS_ANDROID = False

# ========== 尝试导入相机和条码识别 ==========
try:
    from kivy.uix.camera import Camera
    HAS_CAMERA = True
except ImportError:
    HAS_CAMERA = False

try:
    from pyzbar import pyzbar
    HAS_ZBAR = True
except ImportError:
    HAS_ZBAR = False


# ============================================================
# 全局状态
# ============================================================
class AppState:
    """全局状态管理"""
    def __init__(self):
        self.temp_dir = ""          # 临时目录
        self.images = [None, None, None]  # 三张图片路径（0=条码，1=图1，2=图2）
        self.barcode_text = ""      # 识别出的条码
        self.screen_type = []       # 每张图是 'camera' 还是 'gallery'
        self.saved_pdf_path = ""    # 最终PDF路径
        self._init_dirs()

    def _init_dirs(self):
        if IS_ANDROID:
            self.temp_dir = os.path.join(primary_external_storage_path(),
                                         "BarcodePDFApp", "temp")
        else:
            self.temp_dir = os.path.join(os.path.expanduser("~"), "BarcodePDFApp")
        os.makedirs(self.temp_dir, exist_ok=True)

    def reset(self):
        self.images = [None, None, None]
        self.barcode_text = ""
        self.screen_type = []
        self.saved_pdf_path = ""
        # 清理临时文件
        try:
            for f in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, f))
        except Exception:
            pass

    def get_save_dirs(self):
        """返回可选的保存路径列表 [(中文名, 路径)]"""
        dirs = []
        if IS_ANDROID:
            base = primary_external_storage_path()
            candidates = [
                ("Documents（文档）", os.path.join(base, "Documents")),
                ("Download（下载）", os.path.join(base, "Download")),
                ("Pictures（图片）", os.path.join(base, "Pictures")),
                ("手机根目录", base),
                ("应用私有目录", self.temp_dir),
            ]
        else:
            base = os.path.expanduser("~")
            candidates = [
                ("桌面", os.path.join(base, "Desktop")),
                ("下载", os.path.join(base, "Downloads")),
                ("文档", os.path.join(base, "Documents")),
                ("家目录", base),
            ]
        for name, path in candidates:
            if os.path.exists(path) or path == self.temp_dir:
                try:
                    os.makedirs(path, exist_ok=True)
                    dirs.append((name, path))
                except Exception:
                    pass
        return dirs


STATE = AppState()


# ============================================================
# 工具函数
# ============================================================
def show_alert(title, msg, callback=None):
    """弹出提示框"""
    content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
    content.add_widget(Label(text=msg, font_size=dp(16), halign='center',
                             size_hint_y=0.7, text_size=(Window.width * 0.8, None)))
    btn = Button(text='确定', size_hint_y=0.3, height=dp(50),
                 background_color=(0.2, 0.6, 1, 1), font_size=dp(16))
    popup = Popup(title=title, content=content, size_hint=(0.85, 0.45),
                  auto_dismiss=False)
    def _close(*args):
        popup.dismiss()
        if callback:
            Clock.schedule_once(lambda dt: callback(), 0.1)
    btn.bind(on_release=_close)
    content.add_widget(btn)
    popup.open()


def fix_image_rotation(img_path):
    """修复EXIF方向"""
    try:
        img = Image.open(img_path)
        if hasattr(img, '_getexif') and img._getexif():
            exif = img._getexif()
            orientation = exif.get(274, 1)
            rotate_map = {3: 180, 6: 270, 8: 90}
            if orientation in rotate_map:
                img = img.rotate(rotate_map[orientation], expand=True)
                img.save(img_path)
    except Exception:
        pass


def detect_barcode(img_path):
    """识别条码，返回文本或空字符串"""
    if not HAS_ZBAR:
        return ""
    try:
        img = Image.open(img_path)
        # 多尺寸尝试识别
        for scale in [1.0, 0.5, 2.0, 1.5]:
            w, h = img.size
            if scale != 1.0:
                test = img.resize((int(w*scale), int(h*scale)))
            else:
                test = img
            for rot in [0, 90, 180, 270]:
                if rot:
                    test2 = test.rotate(rot, expand=True)
                else:
                    test2 = test
                codes = pyzbar.decode(test2)
                if codes:
                    result = codes[0].data.decode('utf-8', errors='ignore').strip()
                    if result:
                        return result
        return ""
    except Exception as e:
        Logger.error(f"Barcode: 识别失败 {e}")
        return ""


def sanitize_filename(name):
    """过滤文件名非法字符"""
    bad = '<>:"/\\|?*\n\r\t'
    for c in bad:
        name = name.replace(c, '_')
    name = name.strip().strip('.')
    return name[:80] if name else f"PDF_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def images_to_pdf(image_paths, output_pdf):
    """多张图片合并成一个PDF"""
    pil_images = []
    first_img = None
    for p in image_paths:
        try:
            img = Image.open(p).convert('RGB')
            # 自适应A4宽度 (2480px @300dpi)
            max_w = 2480
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)
            if first_img is None:
                first_img = img
            else:
                pil_images.append(img)
        except Exception as e:
            Logger.error(f"PDF: 加载图片失败 {p}: {e}")
    if first_img is None:
        raise Exception("没有有效的图片可以生成PDF")
    first_img.save(output_pdf, "PDF", resolution=300.0,
                   save_all=True, append_images=pil_images)
    return True


# ============================================================
# 基础颜色主题
# ============================================================
BG = (0.95, 0.96, 0.98, 1)
PRIMARY = (0.15, 0.55, 0.95, 1)
PRIMARY_DARK = (0.12, 0.45, 0.8, 1)
SUCCESS = (0.2, 0.7, 0.35, 1)
DANGER = (0.9, 0.25, 0.25, 1)
TEXT_DARK = (0.15, 0.18, 0.22, 1)
TEXT_GRAY = (0.45, 0.5, 0.55, 1)
CARD = (1, 1, 1, 1)


def make_button(text, color=PRIMARY, size_y=None, font_size=16):
    btn = Button(
        text=text,
        background_normal='',
        background_color=color,
        font_size=dp(font_size),
        bold=True,
        size_hint_y=size_y,
        height=dp(55) if size_y is None else None,
    )
    return btn


# ============================================================
# 页面1：欢迎页
# ============================================================
class WelcomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation='vertical', padding=dp(25), spacing=dp(20))
        with root.canvas.before:
            Color(*BG)
            self.bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._update_bg, size=self._update_bg)

        # 标题
        title_box = BoxLayout(size_hint_y=0.25, orientation='vertical')
        title_box.add_widget(Label(
            text='[b]📸 条码PDF生成器[/b]', markup=True,
            font_size=dp(30), color=TEXT_DARK, size_hint_y=0.6))
        title_box.add_widget(Label(
            text='拍照或选择图片 → 识别条码 → 生成PDF',
            font_size=dp(15), color=TEXT_GRAY, size_hint_y=0.4))
        root.add_widget(title_box)

        # 功能卡片
        card = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(12),
                         size_hint_y=0.55)
        with card.canvas.before:
            Color(*CARD)
            self.card_bg = Rectangle(pos=card.pos, size=card.size)
        card.bind(pos=self._update_card, size=self._update_card)

        tips = [
            "✅  支持 [b]拍照[/b] 和 [b]从相册选择[/b]",
            "🔍  自动识别条码作为文档名",
            "📄  3张图片合成一个PDF",
            "📁  自定义保存位置",
        ]
        for t in tips:
            card.add_widget(Label(
                text=t, markup=True, font_size=dp(16),
                color=TEXT_DARK, halign='left', size_hint_y=None, height=dp(38)))
        root.add_widget(card)

        # 按钮
        root.add_widget(Label(size_hint_y=0.05))  # 间距
        btn_start = make_button('开始', color=PRIMARY, font_size=18)
        btn_start.bind(on_release=self.go_capture)
        root.add_widget(btn_start)

        self.add_widget(root)

    def _update_bg(self, i, v):
        self.bg.pos = i.pos
        self.bg.size = i.size

    def _update_card(self, i, v):
        self.card_bg.pos = i.pos
        self.card_bg.size = i.size

    def go_capture(self, *args):
        STATE.reset()
        self.manager.current = 'capture'


# ============================================================
# 页面2：拍摄/选择页（3个步骤）
# ============================================================
class CaptureScreen(Screen):
    """拍摄或选择第n张图"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_step = 0  # 0=条码, 1=图1, 2=图2
        self.camera = None
        self.preview_img = None
        self._build_ui()

    def _build_ui(self):
        self.root = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        with self.root.canvas.before:
            Color(*BG)
            self.bg = Rectangle(pos=self.root.pos, size=self.root.size)
        self.root.bind(pos=self._upd_bg, size=self._upd_bg)
        self.add_widget(self.root)

    def _upd_bg(self, i, v):
        self.bg.pos = i.pos; self.bg.size = i.size

    def on_pre_enter(self):
        self.current_step = 0
        self._show_step()

    def _step_label(self):
        names = ["条码图片（用于命名文档）", "第 1 张文档图片", "第 2 张文档图片"]
        return names[self.current_step], self.current_step + 1

    def _show_step(self):
        self.root.clear_widgets()
        name, idx = self._step_label()

        # 顶部进度条
        header = BoxLayout(orientation='vertical', size_hint_y=0.12, spacing=dp(5))
        header.add_widget(Label(
            text=f'第 {idx} / 3 步 — {name}',
            font_size=dp(18), bold=True, color=TEXT_DARK, size_hint_y=0.5))
        # 进度指示点
        prog = BoxLayout(orientation='horizontal', size_hint_y=0.3,
                         spacing=dp(8), padding=[dp(60), 0, dp(60), 0])
        for i in range(3):
            color = PRIMARY if i <= self.current_step else (0.8, 0.82, 0.85, 1)
            dot = Button(background_normal='', background_color=color,
                         size_hint_x=0.3, disabled=True)
            prog.add_widget(dot)
        header.add_widget(prog)
        header.add_widget(Label(size_hint_y=0.2))
        self.root.add_widget(header)

        # 中间操作区
        center = BoxLayout(orientation='vertical', spacing=dp(15), padding=[dp(10), 0])
        hint_text = '请将条码置于框内拍摄' if self.current_step == 0 else '请拍摄或选择图片'
        center.add_widget(Label(text=hint_text, font_size=dp(14),
                                color=TEXT_GRAY, size_hint_y=0.08))

        # 预览区
        self.preview_area = BoxLayout(size_hint_y=0.55,
                                      padding=[dp(20), 0])
        with self.preview_area.canvas.before:
            Color(0.2,0.22,0.25,1)
            self.pv_bg = Rectangle(pos=self.preview_area.pos, size=self.preview_area.size)
        self.preview_area.bind(pos=self._upd_pv, size=self._upd_pv)
        self.preview_placeholder = Label(
            text='[b]📷[/b]\n\n尚未选择图片\n点击下方按钮',
            markup=True, font_size=dp(18), color=(0.8,0.82,0.85,1))
        self.preview_area.add_widget(self.preview_placeholder)
        center.add_widget(self.preview_area)

        # 状态文字
        self.status_label = Label(text='', font_size=dp(13),
                                  color=PRIMARY, size_hint_y=0.07)
        center.add_widget(self.status_label)
        self.root.add_widget(center)

        # 底部按钮区
        btns = BoxLayout(orientation='vertical', size_hint_y=0.33,
                         spacing=dp(10), padding=[dp(10), 0])

        # 两个操作按钮并排（拍照 / 相册选择）
        action_row = BoxLayout(orientation='horizontal', spacing=dp(10),
                               size_hint_y=0.33)
        self.btn_camera = make_button('📷 拍照', color=PRIMARY, font_size=16)
        self.btn_camera.bind(on_release=self.take_photo)
        self.btn_gallery = make_button('🖼️ 相册选择', color=(0.3, 0.65, 0.4, 1), font_size=16)
        self.btn_gallery.bind(on_release=self.choose_from_gallery)
        action_row.add_widget(self.btn_camera)
        action_row.add_widget(self.btn_gallery)
        btns.add_widget(action_row)

        # 确认按钮
        self.btn_confirm = make_button('下一步', color=SUCCESS, font_size=17)
        self.btn_confirm.bind(on_release=self.confirm_step)
        self.btn_confirm.disabled = True
        self.btn_confirm.opacity = 0.5
        btns.add_widget(self.btn_confirm)

        # 重拍/重选按钮
        self.btn_retake = make_button('重新选择', color=(0.95,0.6,0.15,1), font_size=14)
        self.btn_retake.bind(on_release=self.retake)
        self.btn_retake.disabled = True
        self.btn_retake.opacity = 0.5
        btns.add_widget(self.btn_retake)

        self.root.add_widget(btns)

        # 非条码页如果是拍摄则立刻初始化相机
        self.camera = None
        self.temp_path = None

    def _upd_pv(self, i, v):
        self.pv_bg.pos = i.pos; self.pv_bg.size = i.size

    # -------- 方法：拍照 --------
    def take_photo(self, *args):
        """调用相机拍摄"""
        if IS_ANDROID and HAS_CAMERA:
            try:
                # 申请相机权限
                request_permissions([Permission.CAMERA,
                                     Permission.WRITE_EXTERNAL_STORAGE,
                                     Permission.READ_EXTERNAL_STORAGE])
                self._open_camera()
                return
            except Exception as e:
                Logger.error(f"Camera: {e}")
        # PC调试时用占位图
        if not IS_ANDROID:
            self._simulate_photo()
            return
        # 兜底：用Android Intent调系统相机
        self._open_system_camera_intent()

    def _open_camera(self):
        """用Kivy Camera Widget打开相机预览"""
        self.preview_area.clear_widgets()
        try:
            self.camera = Camera(play=True, resolution=(1280, 720))
            self.preview_area.add_widget(self.camera)
            # 显示一个"点击拍照"的浮层按钮
            shoot_bar = BoxLayout(size_hint_y=None, height=dp(50),
                                  padding=[dp(20), 0])
            shoot_btn = make_button('点击拍照', color=SUCCESS, font_size=15)
            shoot_btn.bind(on_release=self._capture_from_widget)
            shoot_bar.add_widget(shoot_btn)
            self.preview_area.add_widget(shoot_bar)
        except Exception as e:
            Logger.error(f"Camera widget失败 {e}，使用系统相机")
            self._open_system_camera_intent()

    def _capture_from_widget(self, *args):
        """从Camera Widget截图保存"""
        if not self.camera:
            return
        try:
            fn = f"img_{self.current_step}_{uuid.uuid4().hex[:8]}.jpg"
            self.temp_path = os.path.join(STATE.temp_dir, fn)
            self.camera.export_to_png(self.temp_path)
            # PNG转JPG
            img = Image.open(self.temp_path).convert('RGB')
            img.save(self.temp_path, 'JPEG', quality=90)
            self.camera.play = False
            fix_image_rotation(self.temp_path)
            self._show_result()
        except Exception as e:
            show_alert('错误', f'拍照失败: {e}')

    def _open_system_camera_intent(self):
        """用Android Intent调系统相机（最通用）"""
        if not IS_ANDROID:
            self._simulate_photo()
            return
        try:
            from android import activity
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            MediaStore = autoclass('android.provider.MediaStore')
            Uri = autoclass('android.net.Uri')
            File = autoclass('java.io.File')
            from android.storage import app_storage_path
            fn = f"shot_{self.current_step}_{uuid.uuid4().hex[:8]}.jpg"
            out = File(STATE.temp_dir, fn)
            self.temp_path = out.getAbsolutePath()
            intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            intent.putExtra(MediaStore.EXTRA_OUTPUT, Uri.fromFile(out))
            activity.bind(on_activity_result=self._on_camera_result)
            PythonActivity.mActivity.startActivityForResult(intent, 1001 + self.current_step)
            self.status_label.text = '相机已打开，请拍照'
        except Exception as e:
            Logger.error(f"Intent相机失败 {e}")
            show_alert('提示', '无法打开相机，请改用"相册选择"上传已拍好的图片。')

    def _on_camera_result(self, request_code, result_code, intent):
        from android import activity
        activity.unbind(on_activity_result=self._on_camera_result)
        if self.temp_path and os.path.exists(self.temp_path):
            fix_image_rotation(self.temp_path)
            self._show_result()
        else:
            self.status_label.text = '拍照已取消'

    def _simulate_photo(self):
        """PC调试用：生成测试图"""
        fn = f"sim_{self.current_step}_{uuid.uuid4().hex[:6]}.jpg"
        self.temp_path = os.path.join(STATE.temp_dir, fn)
        img = Image.new('RGB', (800, 600), (200, 220, 240))
        label = "BARCODE 1234567890" if self.current_step == 0 else f"DOC IMAGE {self.current_step}"
        try:
            from PIL import ImageDraw, ImageFont
            d = ImageDraw.Draw(img)
            d.rectangle([50, 250, 750, 350], outline='black', width=3)
            d.text((100, 280), label, fill='black')
        except Exception:
            pass
        img.save(self.temp_path, 'JPEG', quality=85)
        self._show_result()

    # -------- 方法：相册选择 --------
    def choose_from_gallery(self, *args):
        """从相册选择图片"""
        if IS_ANDROID:
            try:
                request_permissions([Permission.READ_EXTERNAL_STORAGE,
                                     Permission.WRITE_EXTERNAL_STORAGE])
                self._open_gallery_intent()
                return
            except Exception as e:
                Logger.error(f"Gallery: {e}")
        # PC 调试：打开文件选择器
        self._simulate_gallery()

    def _open_gallery_intent(self):
        """用Android Intent打开系统相册/文件选择"""
        try:
            from android import activity
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            intent = Intent(Intent.ACTION_PICK)
            intent.setType("image/*")
            # 兜底：ACTION_GET_CONTENT
            chooser = Intent.createChooser(intent, "选择图片")
            activity.bind(on_activity_result=self._on_gallery_result)
            PythonActivity.mActivity.startActivityForResult(chooser, 2001 + self.current_step)
            self.status_label.text = '已打开相册，请选择图片'
        except Exception as e:
            Logger.error(f"Gallery Intent失败 {e}")
            # 最后兜底：直接让用户手动输入文件路径
            self._show_file_picker_fallback()

    def _on_gallery_result(self, request_code, result_code, intent):
        from android import activity
        activity.unbind(on_activity_result=self._on_gallery_result)
        try:
            if intent and intent.getData():
                uri = intent.getData()
                src = self._uri_to_file(uri)
                if src and os.path.exists(src):
                    fn = f"gal_{self.current_step}_{uuid.uuid4().hex[:8]}.jpg"
                    self.temp_path = os.path.join(STATE.temp_dir, fn)
                    # 拷贝到我们的临时目录
                    img = Image.open(src).convert('RGB')
                    img.save(self.temp_path, 'JPEG', quality=90)
                    fix_image_rotation(self.temp_path)
                    self._show_result()
                    return
            self.status_label.text = '未选择图片'
        except Exception as e:
            Logger.error(f"处理相册结果失败 {e}")
            show_alert('提示', f'处理图片失败: {e}\n请尝试重新选择或改用拍照。')

    def _uri_to_file(self, uri):
        """把content:// URI 转成实际文件路径，或拷到临时文件"""
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            ctx = PythonActivity.mActivity
            ContentResolver = autoclass('android.content.ContentResolver')
            resolver = ctx.getContentResolver()
            Cursor = autoclass('android.database.Cursor')
            # 查DATA列
            proj = ["_data"]
            cursor = resolver.query(uri, proj, None, None, None)
            if cursor and cursor.moveToFirst():
                idx = cursor.getColumnIndexOrThrow("_data")
                path = cursor.getString(idx)
                cursor.close()
                if path and os.path.exists(path):
                    return path
            # 拿不到路径则用流复制
            if cursor:
                cursor.close()
            stream = resolver.openInputStream(uri)
            fn = f"gal_stream_{uuid.uuid4().hex[:8]}.jpg"
            outp = os.path.join(STATE.temp_dir, fn)
            FileOutputStream = autoclass('java.io.FileOutputStream')
            File = autoclass('java.io.File')
            fos = FileOutputStream(File(outp))
            buffer = [0]*4096
            while True:
                n = stream.read(buffer)
                if n <= 0: break
                fos.write(bytes(buffer[:n]))
            fos.close()
            stream.close()
            return outp
        except Exception as e:
            Logger.error(f"URI转文件失败 {e}")
            return None

    def _simulate_gallery(self):
        """PC调试：文件选择弹窗（简化版）"""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(15))
        ti = TextInput(text='/tmp/test.jpg', multiline=False, font_size=dp(14))
        content.add_widget(Label(text='PC调试模式：输入图片路径（或留空用模拟图）',
                                 font_size=dp(13), color=TEXT_GRAY))
        content.add_widget(ti)
        btns = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(8))
        popup = Popup(title='选择图片', content=content, size_hint=(0.9, 0.35),
                      auto_dismiss=False)
        def _ok(*a):
            p = ti.text.strip()
            if p and os.path.exists(p):
                fn = f"gal_{self.current_step}_{uuid.uuid4().hex[:8]}.jpg"
                self.temp_path = os.path.join(STATE.temp_dir, fn)
                img = Image.open(p).convert('RGB')
                img.save(self.temp_path, 'JPEG', quality=90)
            else:
                self._simulate_photo()
            popup.dismiss()
            self._show_result()
        def _cancel(*a):
            popup.dismiss()
        bok = make_button('确定', color=PRIMARY); bok.bind(on_release=_ok)
        bcl = make_button('取消', color=DANGER); bcl.bind(on_release=_cancel)
        btns.add_widget(bok); btns.add_widget(bcl)
        content.add_widget(btns)
        popup.open()

    def _show_file_picker_fallback(self):
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(15))
        content.add_widget(Label(text='请输入图片完整路径\n（例如 /sdcard/Pictures/xxx.jpg）',
                                 font_size=dp(13), color=TEXT_GRAY))
        ti = TextInput(multiline=False, font_size=dp(14))
        content.add_widget(ti)
        btns = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(50), spacing=dp(8))
        popup = Popup(title='输入图片路径', content=content, size_hint=(0.9, 0.35),
                      auto_dismiss=False)
        def _ok(*a):
            p = ti.text.strip()
            if p and os.path.exists(p):
                fn = f"man_{self.current_step}_{uuid.uuid4().hex[:8]}.jpg"
                self.temp_path = os.path.join(STATE.temp_dir, fn)
                img = Image.open(p).convert('RGB')
                img.save(self.temp_path, 'JPEG', quality=90)
                fix_image_rotation(self.temp_path)
                popup.dismiss()
                self._show_result()
            else:
                show_alert('错误', '文件不存在')
        def _cancel(*a):
            popup.dismiss()
        bok = make_button('确定', color=PRIMARY); bok.bind(on_release=_ok)
        bcl = make_button('取消', color=DANGER); bcl.bind(on_release=_cancel)
        btns.add_widget(bok); btns.add_widget(bcl)
        content.add_widget(btns)
        popup.open()

    # -------- 处理拍摄/选择结果 --------
    def _show_result(self):
        """显示结果预览"""
        self.preview_area.clear_widgets()
        try:
            img_wid = KivyImage(source=self.temp_path, allow_stretch=True,
                                keep_ratio=True)
            self.preview_area.add_widget(img_wid)
        except Exception as e:
            Logger.error(f"预览失败 {e}")
            self.preview_area.add_widget(Label(text='图片加载失败', color=(1,1,1,1)))

        # 条码页尝试识别
        if self.current_step == 0:
            self.status_label.text = '正在识别条码...'
            Clock.schedule_once(self._do_recognize, 0.2)
        else:
            self.status_label.text = '图片已准备好，点击"下一步"'
            self.btn_confirm.disabled = False
            self.btn_confirm.opacity = 1
        self.btn_retake.disabled = False
        self.btn_retake.opacity = 1
        self.btn_camera.disabled = True; self.btn_camera.opacity = 0.4
        self.btn_gallery.disabled = True; self.btn_gallery.opacity = 0.4

    def _do_recognize(self, dt):
        code = detect_barcode(self.temp_path)
        if code:
            STATE.barcode_text = code
            self.status_label.text = f'✅ 识别成功：{code}'
        else:
            if HAS_ZBAR:
                self.status_label.text = '⚠️ 未识别到条码，你可以继续下一步后手动填写文件名'
            else:
                self.status_label.text = '⚠️ 未安装zbar，请在下一步手动输入文件名'
        self.btn_confirm.disabled = False
        self.btn_confirm.opacity = 1

    def retake(self, *args):
        if self.camera:
            try: self.camera.play = False
            except: pass
            self.camera = None
        self.temp_path = None
        self._show_step()

    def confirm_step(self, *args):
        if not self.temp_path:
            show_alert('提示', '请先拍摄或选择图片')
            return
        STATE.images[self.current_step] = self.temp_path
        if self.camera:
            try: self.camera.play = False
            except: pass
            self.camera = None
        if self.current_step < 2:
            self.current_step += 1
            self._show_step()
        else:
            self.manager.current = 'preview'


# ============================================================
# 页面3：预览 + 文件名 + 保存路径选择
# ============================================================
class PreviewScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build()

    def build(self):
        self.root = ScrollView(do_scroll_x=False)
        wrapper = BoxLayout(orientation='vertical', padding=dp(15),
                            spacing=dp(12), size_hint_y=None)
        wrapper.bind(minimum_height=wrapper.setter('height'))
        with wrapper.canvas.before:
            Color(*BG)
            self.bg = Rectangle(pos=wrapper.pos, size=(Window.width, Window.height))

        # 标题
        wrapper.add_widget(Label(
            text='[b]确认并生成PDF[/b]', markup=True,
            font_size=dp(22), color=TEXT_DARK,
            size_hint_y=None, height=dp(40)))

        # 三图缩略预览
        thumbs = GridLayout(cols=3, size_hint_y=None, height=dp(130), spacing=dp(6))
        self.thumb_imgs = []
        labels = ['条码', '图1', '图2']
        for i in range(3):
            box = BoxLayout(orientation='vertical', spacing=dp(4))
            img = KivyImage(size_hint_y=0.8, allow_stretch=True, keep_ratio=True)
            lb = Label(text=labels[i], font_size=dp(12),
                       color=TEXT_GRAY, size_hint_y=0.2)
            box.add_widget(img); box.add_widget(lb)
            self.thumb_imgs.append(img)
            thumbs.add_widget(box)
        wrapper.add_widget(thumbs)

        # 条码结果
        wrapper.add_widget(Label(
            text='[b]📄 PDF文件名称[/b]', markup=True,
            font_size=dp(16), color=TEXT_DARK,
            size_hint_y=None, height=dp(30), halign='left'))
        self.filename_input = TextInput(
            text='', multiline=False, font_size=dp(16),
            size_hint_y=None, height=dp(48),
            background_color=(1,1,1,1), foreground_color=TEXT_DARK,
            padding=[dp(10), dp(12)])
        wrapper.add_widget(self.filename_input)

        # 保存路径
        wrapper.add_widget(Label(
            text='[b]📁 保存位置[/b]', markup=True,
            font_size=dp(16), color=TEXT_DARK,
            size_hint_y=None, height=dp(30), halign='left'))

        self.dir_btns_box = GridLayout(cols=1, size_hint_y=None,
                                       spacing=dp(8))
        wrapper.add_widget(self.dir_btns_box)

        wrapper.add_widget(Label(text='或手动输入路径（可选）：',
                                 font_size=dp(13), color=TEXT_GRAY,
                                 size_hint_y=None, height=dp(22)))
        self.custom_path_input = TextInput(
            text='', multiline=False, font_size=dp(13),
            size_hint_y=None, height=dp(42),
            background_color=(1,1,1,1),
            padding=[dp(10), dp(10)])
        wrapper.add_widget(self.custom_path_input)

        # 按钮
        wrapper.add_widget(Label(size_hint_y=None, height=dp(10)))
        self.selected_dir = None
        btn_gen = make_button('✅ 生成PDF文件', color=SUCCESS, font_size=18)
        btn_gen.bind(on_release=self.generate_pdf)
        wrapper.add_widget(btn_gen)
        btn_back = make_button('返回重拍', color=(0.6,0.6,0.65,1), font_size=14)
        btn_back.bind(on_release=lambda a: setattr(self.manager, 'current', 'capture'))
        wrapper.add_widget(btn_back)

        self.root.add_widget(wrapper)
        self.add_widget(self.root)

    def on_pre_enter(self):
        # 加载缩略图
        for i in range(3):
            if STATE.images[i]:
                self.thumb_imgs[i].source = STATE.images[i]
                self.thumb_imgs[i].reload()
        # 文件名
        self.filename_input.text = sanitize_filename(
            STATE.barcode_text if STATE.barcode_text
            else f"PDF_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        # 保存路径按钮
        self.dir_btns_box.clear_widgets()
        self.selected_dir = None
        self.dir_btn_widgets = []
        for name, path in STATE.get_save_dirs():
            btn = Button(
                text=f'  {name}\n  {path}',
                background_normal='',
                background_color=(1,1,1,1),
                color=TEXT_DARK,
                font_size=dp(12),
                halign='left',
                valign='middle',
                size_hint_y=None,
                height=dp(50),
                text_size=(Window.width*0.9, dp(50)))
            btn.bind(on_release=lambda b, p=path, w=btn: self._select_dir(p, w))
            self.dir_btns_box.add_widget(btn)
            self.dir_btn_widgets.append((btn, path))

    def _select_dir(self, path, widget):
        self.selected_dir = path
        for btn, _ in self.dir_btn_widgets:
            if btn is widget:
                btn.background_color = (0.5, 0.8, 1, 1)
                btn.color = (1,1,1,1)
            else:
                btn.background_color = (1,1,1,1)
                btn.color = TEXT_DARK

    def generate_pdf(self, *args):
        name = sanitize_filename(self.filename_input.text.strip())
        save_dir = self.custom_path_input.text.strip() if self.custom_path_input.text.strip() else self.selected_dir
        if not save_dir:
            # 默认取第一个
            dirs = STATE.get_save_dirs()
            save_dir = dirs[0][1] if dirs else STATE.temp_dir
        try:
            os.makedirs(save_dir, exist_ok=True)
            # 测试是否可写
            testf = os.path.join(save_dir, f'.test_{uuid.uuid4().hex}.tmp')
            with open(testf,'w') as f: f.write('ok')
            os.remove(testf)
        except Exception as e:
            show_alert('错误', f'无法写入该目录: {e}\n已改用应用私有目录')
            save_dir = STATE.temp_dir
            os.makedirs(save_dir, exist_ok=True)

        pdf_path = os.path.join(save_dir, f"{name}.pdf")
        # 防重名
        if os.path.exists(pdf_path):
            i = 1
            while os.path.exists(os.path.join(save_dir, f"{name}({i}).pdf")):
                i += 1
            pdf_path = os.path.join(save_dir, f"{name}({i}).pdf")

        try:
            images_to_pdf(STATE.images, pdf_path)
            STATE.saved_pdf_path = pdf_path
            self.manager.current = 'result'
        except Exception as e:
            Logger.error(f"PDF生成失败: {e}")
            show_alert('错误', f'PDF生成失败: {e}')


# ============================================================
# 页面4：生成结果页
# ============================================================
class ResultScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.build()

    def build(self):
        root = BoxLayout(orientation='vertical', padding=dp(25), spacing=dp(20))
        with root.canvas.before:
            Color(*BG)
            self.bg = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._upd, size=self._upd)

        root.add_widget(Label(size_hint_y=0.1))
        icon = Label(text='[size=80]✅[/size]', markup=True,
                     size_hint_y=0.25, color=SUCCESS)
        root.add_widget(icon)
        root.add_widget(Label(
            text='[b]PDF 生成成功！[/b]', markup=True,
            font_size=dp(26), color=TEXT_DARK,
            size_hint_y=0.1))
        self.path_label = Label(text='', font_size=dp(12), color=TEXT_GRAY,
                                size_hint_y=0.15, halign='center',
                                text_size=(Window.width*0.85, None))
        root.add_widget(self.path_label)
        self.size_label = Label(text='', font_size=dp(14), color=PRIMARY,
                                size_hint_y=0.08)
        root.add_widget(self.size_label)

        root.add_widget(Label(size_hint_y=0.05))
        btn_new = make_button('📸 继续新建PDF', color=PRIMARY, font_size=17)
        btn_new.bind(on_release=self.new_one)
        root.add_widget(btn_new)
        btn_open = make_button('📂 打开所在文件夹', color=SUCCESS, font_size=14)
        btn_open.bind(on_release=self.open_folder)
        root.add_widget(btn_open)
        btn_home = make_button('返回首页', color=(0.6,0.6,0.65,1), font_size=14)
        btn_home.bind(on_release=lambda a: setattr(self.manager, 'current', 'welcome'))
        root.add_widget(btn_home)

        self.add_widget(root)

    def _upd(self,i,v): self.bg.pos=i.pos; self.bg.size=i.size

    def on_pre_enter(self):
        p = STATE.saved_pdf_path
        self.path_label.text = f'文件路径：\n{p}'
        try:
            sz = os.path.getsize(p) / 1024
            self.size_label.text = f'文件大小：{sz:.1f} KB'
        except Exception:
            self.size_label.text = ''

    def new_one(self, *args):
        STATE.reset()
        self.manager.current = 'capture'

    def open_folder(self, *args):
        p = STATE.saved_pdf_path
        if not IS_ANDROID:
            show_alert('提示', f'请手动打开文件夹：\n{os.path.dirname(p)}')
            return
        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            File = autoclass('java.io.File')
            intent = Intent(Intent.ACTION_VIEW)
            intent.setDataAndType(Uri.fromFile(File(p)), "application/pdf")
            intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            PythonActivity.mActivity.startActivity(intent)
        except Exception as e:
            show_alert('提示', f'未找到PDF阅读器，请手动打开：\n{p}')


# ============================================================
# 主应用
# ============================================================
class BarcodePDFApp(App):
    title = '条码PDF生成器'
    icon = ''

    def build(self):
        # Android动态申请权限
        if IS_ANDROID:
            Clock.schedule_once(self._req_perms, 0.5)
        sm = ScreenManager()
        sm.add_widget(WelcomeScreen(name='welcome'))
        sm.add_widget(CaptureScreen(name='capture'))
        sm.add_widget(PreviewScreen(name='preview'))
        sm.add_widget(ResultScreen(name='result'))
        return sm

    def _req_perms(self, dt):
        try:
            request_permissions([
                Permission.CAMERA,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
            ])
        except Exception:
            pass

    def on_pause(self):
        return True

    def on_resume(self):
        pass


if __name__ == '__main__':
    Window.clearcolor = BG
    BarcodePDFApp().run()
