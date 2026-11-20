"""Componentes visuais reutilizáveis. Cores, tamanhos e tempos vêm de theme.py."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import (Property, QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, QSize, Qt,
                            QTimer, Signal)
from PySide6.QtGui import (QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPainterPath, QPen,
                           QPixmap)
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QLayout, QLineEdit, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from . import theme as T

# ================================================================ ícones
_icon_family = None


def icon_family() -> str:
    global _icon_family
    if _icon_family is None:
        fams = set(QFontDatabase.families())
        _icon_family = T.ICON_FONT if T.ICON_FONT in fams else T.ICON_FALLBACK
    return _icon_family


def icon_font(size: int = 14) -> QFont:
    f = QFont(icon_family())
    f.setPixelSize(size)
    return f


def glyph(name: str) -> str:
    return T.ICONS.get(name, "")


def _glyph_pixmap(name: str, color: str, size: int) -> QPixmap:
    ratio = 2.0
    pm = QPixmap(int(size * ratio), int(size * ratio))
    pm.setDevicePixelRatio(ratio)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setFont(icon_font(size))
    p.setPen(QColor(color))
    p.drawText(QRect(0, 0, size, size), Qt.AlignCenter, glyph(name))
    p.end()
    return pm


def glyph_icon(name: str, color: str = T.TEXT, size: int = 16, disabled: str = T.DIM) -> QIcon:
    ic = QIcon()
    ic.addPixmap(_glyph_pixmap(name, color, size), QIcon.Normal)
    ic.addPixmap(_glyph_pixmap(name, disabled, size), QIcon.Disabled)
    return ic


class Icon(QLabel):
    def __init__(self, name: str, size: int = 16, color: str = T.MUTED, parent=None):
        super().__init__(glyph(name), parent)
        self._size = size
        self.setFont(icon_font(size))
        self.setFixedSize(size + 6, size + 6)
        self.setAlignment(Qt.AlignCenter)
        self.set(name, color)

    def set(self, name: str, color: str | None = None):
        self.setText(glyph(name))
        if color:
            self._color = color
        # a folha de estilo global define font-family para todos os widgets: aqui precisa repetir a fonte de
        # ícones no próprio estilo, senão o glifo sai como um quadrado
        self.setStyleSheet(f"color: {getattr(self, '_color', T.MUTED)}; background: transparent;"
                           f" font-family: '{icon_family()}'; font-size: {self._size}px;")


# ================================================================ texto e superfícies
def label(text: str = "", obj: str = "", wrap: bool = False) -> QLabel:
    lb = QLabel(text)
    if obj:
        lb.setObjectName(obj)
    lb.setWordWrap(wrap)
    return lb


def elide(lb: QLabel, text: str, width: int, mode=Qt.ElideRight):
    lb.setText(lb.fontMetrics().elidedText(text, mode, width))
    lb.setToolTip(text if lb.text() != text else "")


def panel(obj: str = "Panel") -> QFrame:
    f = QFrame()
    f.setObjectName(obj)
    return f


def divider() -> QFrame:
    d = QFrame()
    d.setObjectName("Divider")
    return d


def clear_layout(lay):
    while lay.count():
        it = lay.takeAt(0)
        w = it.widget()
        if w is not None:
            w.deleteLater()
        elif it.layout() is not None:
            clear_layout(it.layout())


class Badge(QLabel):
    def __init__(self, text: str = "", color: str = T.MUTED):
        super().__init__(text)
        self.setObjectName("Badge")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setFixedHeight(20)
        self.setAlignment(Qt.AlignCenter)
        self.set(text, color)

    def set(self, text: str, color: str):
        self.setText(text)
        self.setStyleSheet(f"#Badge {{ color: {color}; background: {T.rgba(color, 0.12)};"
                           f" border: 1px solid {T.rgba(color, 0.30)}; }}")


def badge(text: str, color: str) -> Badge:
    return Badge(text, color)


# ================================================================ botões
def button(text: str = "", icon: str | None = None, variant: str = "", tooltip: str = "",
           large: bool = False) -> QPushButton:
    """variant: '' (padrão), 'Primary', 'Ghost', 'Danger'. Ícone desenhado na cor do texto de cada variante."""
    b = QPushButton(text)
    if variant:
        b.setObjectName(variant)
    b.setCursor(Qt.PointingHandCursor)
    if icon:
        col = {"Primary": T.ON_PRIMARY, "Ghost": T.MUTED, "Danger": T.ERROR}.get(variant, T.TEXT)
        b.setIcon(glyph_icon(icon, col, 14))
        b.setIconSize(QSize(14, 14))
    if not text:
        b.setFixedWidth(T.CONTROL_H)
    if large:
        b.setMinimumHeight(T.CONTROL_H_LG)
    if tooltip:
        b.setToolTip(tooltip)
    return b


icon_button = button  # nome antigo


def set_button_enabled(b: QPushButton, on: bool):
    b.setEnabled(on)


# ================================================================ seletores
class Select(QComboBox):
    """QComboBox com chevron desenhado e itens (chave, rótulo)."""

    def __init__(self, items: list[tuple] | None = None):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        for key, text in (items or []):
            self.addItem(text, key)

    def key(self):
        return self.currentData()

    def set_key(self, key):
        i = self.findData(key)
        if i >= 0:
            self.setCurrentIndex(i)

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setFont(icon_font(10))
        p.setPen(QColor(T.MUTED if self.isEnabled() else T.DIM))
        p.drawText(QRect(self.width() - 28, 0, 20, self.height()), Qt.AlignCenter, glyph("chevdown"))


class Segmented(QFrame):
    """Controle segmentado compacto (ex.: grade / lista)."""
    changed = Signal(object)

    def __init__(self, items: list[tuple], icons: bool = False):
        super().__init__()
        self.setObjectName("SegGroup")
        h = QHBoxLayout(self)
        h.setContentsMargins(3, 3, 3, 3)
        h.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (key, text) in enumerate(items):
            b = QPushButton("" if icons else text)
            b.setObjectName("Seg")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("key", key)
            if icons:
                b.setIcon(glyph_icon(text, T.TEXT, 14, T.MUTED))
                b.setFixedWidth(32)
            self.group.addButton(b, i)
            h.addWidget(b)
        self.group.buttons()[0].setChecked(True)
        self.group.idClicked.connect(lambda _i: self.changed.emit(self.value()))

    def value(self):
        b = self.group.checkedButton()
        return b.property("key") if b else None

    def set_value(self, key):
        for b in self.group.buttons():
            b.setChecked(b.property("key") == key)


# ================================================================ campo de link
class LinkField(QFrame):
    """Campo grande de link com ícone, selo de plataforma detectada e botão de colar."""
    submitted = Signal()

    def __init__(self, placeholder: str):
        super().__init__()
        self.setObjectName("LinkField")
        h = QHBoxLayout(self)
        h.setContentsMargins(T.SP3, 0, T.SP1 + 2, 0)
        h.setSpacing(T.SP2)
        self.ic = Icon("link", 14, T.DIM)
        h.addWidget(self.ic)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.returnPressed.connect(self.submitted.emit)
        self.edit.installEventFilter(self)
        h.addWidget(self.edit, 1)
        self.platform = Badge("", T.MUTED)
        self.platform.hide()
        h.addWidget(self.platform)
        self.paste = button("", "paste", "Ghost", "Colar da área de transferência (Ctrl+V)")
        h.addWidget(self.paste)

    def eventFilter(self, obj, ev):
        if obj is self.edit and ev.type() in (ev.Type.FocusIn, ev.Type.FocusOut):
            self.setProperty("focus", "true" if ev.type() == ev.Type.FocusIn else "false")
            self.style().unpolish(self)
            self.style().polish(self)
        return False

    def set_state(self, state: str):
        self.setProperty("state", state)
        self.style().unpolish(self)
        self.style().polish(self)


# ================================================================ marca do app
class AppMark(QWidget):
    """Marca do app: tesoura em rosa sobre um quadrado discreto."""

    def __init__(self, size: int = 28):
        super().__init__()
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QPen(QColor(255, 98, 157, 90), 1))
        p.setBrush(QColor(255, 98, 157, 34))
        p.drawRoundedRect(r, self.width() * 0.26, self.width() * 0.26)
        p.setFont(icon_font(int(self.width() * 0.5)))
        p.setPen(QColor(T.PRIMARY))
        p.drawText(r, Qt.AlignCenter, glyph("cut"))


# ================================================================ navegação superior
class TopNav(QWidget):
    """Abas horizontais com sublinhado animado."""
    changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.h = QHBoxLayout(self)
        self.h.setContentsMargins(0, 0, 0, 0)
        self.h.setSpacing(T.SP1)
        self.tabs: list[QPushButton] = []
        self.dots: list[QLabel] = []
        self.line = QFrame(self)
        self.line.setStyleSheet(f"background: {T.PRIMARY}; border-radius: 1px;")
        self.line.setFixedHeight(2)
        self._anim = QPropertyAnimation(self.line, b"geometry", self)
        self._anim.setDuration(T.ANIM)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.current = -1

    def add(self, text: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName("NavTab")
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(48)
        i = len(self.tabs)
        b.clicked.connect(lambda: self.select(i))
        self.tabs.append(b)
        self.h.addWidget(b)
        dot = QLabel(b)
        dot.setFixedSize(6, 6)
        dot.hide()
        self.dots.append(dot)
        return b

    def select(self, i: int, emit: bool = True):
        for j, b in enumerate(self.tabs):
            b.setChecked(i == j)
        first = self.current < 0
        self.current = i
        QTimer.singleShot(0, lambda: self._move(i, animate=not first))
        if emit:
            self.changed.emit(i)

    def _target(self, i: int) -> QRect:
        b = self.tabs[i]
        pad = T.SP3
        return QRect(b.x() + pad, self.height() - 2, max(8, b.width() - 2 * pad), 2)

    def _move(self, i: int, animate: bool = True):
        target = self._target(i)
        if not animate or not self.line.isVisible():
            self.line.setGeometry(target)
            return
        self._anim.stop()
        self._anim.setStartValue(self.line.geometry())
        self._anim.setEndValue(target)
        self._anim.start()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.current >= 0:
            self.line.setGeometry(self._target(self.current))
        for b, d in zip(self.tabs, self.dots):
            d.move(b.width() - 10, 12)

    def set_activity(self, i: int, on: bool):
        d = self.dots[i]
        d.setStyleSheet(f"background: {T.PRIMARY}; border-radius: 3px;")
        d.move(self.tabs[i].width() - 10, 12)
        d.setVisible(on)


# ================================================================ status
class StatusDot(QWidget):
    """Ponto de status. pulse=True: respiração lenta (processando)."""

    def __init__(self, color: str = T.DIM, size: int = 8):
        super().__init__()
        self.setFixedSize(size + 6, size + 6)
        self.color = QColor(color)
        self.size_ = size
        self._t = 0.0
        self.pulse = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set(self, color: str, pulse: bool = False):
        self.color = QColor(color)
        self.pulse = pulse
        if pulse:
            self._timer.start(50)
        else:
            self._timer.stop()
            self._t = 0.0
        self.update()

    def _tick(self):
        self._t = (self._t + 0.04) % 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QRectF(self.rect()).center()
        s = self.size_ / 2
        if self.pulse:
            ring = QColor(self.color)
            ring.setAlphaF(0.35 * (1 - self._t))
            rr = s + self._t * 3
            p.setPen(Qt.NoPen)
            p.setBrush(ring)
            p.drawEllipse(c, rr, rr)
        p.setPen(Qt.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(c, s, s)


class StatusBar(QFrame):
    """Barra discreta no rodapé: sistema, Claude Code e processamento."""
    clicked_issue = Signal()
    clicked_youtube = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("StatusBar")
        self.setFixedHeight(30)
        h = QHBoxLayout(self)
        h.setContentsMargins(T.SP4, 0, T.SP4, 0)
        h.setSpacing(T.SP2)
        self.sys_dot = StatusDot(T.DIM)
        self.sys_txt = label("Verificando o sistema…", "StatusText")
        self.sys_txt.setCursor(Qt.PointingHandCursor)
        self.sys_txt.mousePressEvent = lambda _e: self.clicked_issue.emit()
        h.addWidget(self.sys_dot)
        h.addWidget(self.sys_txt)
        h.addSpacing(T.SP4)
        self.job_dot = StatusDot(T.PRIMARY)
        self.job_txt = label("", "StatusText")
        h.addWidget(self.job_dot)
        h.addWidget(self.job_txt)
        self.job_dot.hide()
        h.addStretch(1)
        self.youtube_dot = StatusDot(T.DIM)
        h.addWidget(self.youtube_dot)
        self.youtube_txt = label("YouTube desconectado", "StatusText")
        self.youtube_txt.setCursor(Qt.PointingHandCursor)
        self.youtube_txt.mousePressEvent = lambda _e: self.clicked_youtube.emit()
        h.addWidget(self.youtube_txt)
        h.addSpacing(T.SP3)
        self.claude_dot = StatusDot(T.DIM)
        h.addWidget(self.claude_dot)
        self.claude_txt = label("", "StatusText")
        self.claude_txt.setCursor(Qt.PointingHandCursor)
        self.claude_txt.mousePressEvent = lambda _e: self.clicked_issue.emit()
        h.addWidget(self.claude_txt)

    def set_system(self, color: str, text: str):
        self.sys_dot.set(color)
        self.sys_txt.setText(text)

    def set_auth_status(self, status: str, text: str):
        colors = {
            "connected": T.SUCCESS,
            "disconnected": T.WARNING,
            "checking": T.PRIMARY,
            "unavailable": T.DIM,
            "auth_error": T.ERROR,
        }
        self.claude_dot.set(colors.get(status, T.DIM), status == "checking")
        self.claude_txt.setText(text)

    def set_youtube_status(self, status: str, text: str):
        colors = {"connected": T.SUCCESS, "disconnected": T.WARNING, "checking": T.PRIMARY,
                  "unavailable": T.DIM, "expired": T.WARNING, "error": T.ERROR}
        self.youtube_dot.set(colors.get(status, T.DIM), status == "checking")
        self.youtube_txt.setText(text)

    def set_job(self, text: str | None, color: str = T.PRIMARY, pulse: bool = True):
        self.job_dot.setVisible(bool(text))
        self.job_txt.setVisible(bool(text))
        if text:
            self.job_dot.set(color, pulse)
            self.job_txt.setText(text)


class Spinner(QWidget):
    def __init__(self, size: int = 16, color: str = T.PRIMARY):
        super().__init__()
        self.setFixedSize(size, size)
        self.color = QColor(color)
        self.angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self):
        if self.isVisible():
            self.angle = (self.angle + 6) % 360
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(T.BORDER), 2)
        p.setPen(pen)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.drawEllipse(r)
        pen.setColor(self.color)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(r, -self.angle * 16, 100 * 16)


# ================================================================ progresso por etapas
class StepProgress(QWidget):
    """Barra segmentada: um segmento por etapa. Só avança com eventos reais do pipeline; a etapa atual
    tem um brilho em movimento (não é porcentagem: não inventa quanto falta)."""

    def __init__(self, total: int = 1):
        super().__init__()
        self.setFixedHeight(6)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.total = total
        self.done: set[int] = set()
        self.skipped: set[int] = set()
        self.active = -1
        self.state = "run"   # run | ok | error | cancel
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def reset(self, total: int):
        self.total, self.done, self.skipped, self.active, self.state = total, set(), set(), -1, "run"
        self._timer.start(33)
        self.update()

    def set_active(self, i: int):
        self.active = i
        self.update()

    def finish(self, state: str):
        self.state = state
        self._timer.stop()
        self.update()

    def _tick(self):
        if self.isVisible():
            self._phase = (self._phase + 0.02) % 1.0
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        n = max(1, self.total)
        gap = 3
        w = (self.width() - gap * (n - 1)) / n
        h = self.height()
        end_col = {"ok": T.SUCCESS, "error": T.ERROR, "cancel": T.WARNING}.get(self.state, T.PRIMARY)
        for i in range(n):
            r = QRectF(i * (w + gap), 0, w, h)
            p.setPen(Qt.NoPen)
            if i in self.done:
                p.setBrush(QColor(T.SUCCESS if self.state == "ok" else T.PRIMARY))
            elif i in self.skipped:
                p.setBrush(QColor(T.BORDER_STRONG))
            elif i == self.active and self.state != "run":
                p.setBrush(QColor(end_col))
            else:
                p.setBrush(QColor(T.BORDER))
            p.drawRoundedRect(r, h / 2, h / 2)
            if i == self.active and self.state == "run":
                g = QLinearGradient(r.left(), 0, r.right(), 0)
                c = QColor(T.PRIMARY)
                for k in range(11):
                    x = k / 10
                    d = abs(x - self._phase)
                    d = min(d, 1 - d)
                    c.setAlphaF(max(0.25, 1 - d * 3))
                    g.setColorAt(x, QColor(c))
                p.setBrush(g)
                p.drawRoundedRect(r, h / 2, h / 2)


# ================================================================ mídia
SHEET_CELL = (0, 0, 270, 480)  # cl_render.contact_sheet: grade 6x2 de 270x480
_thumb_cache: dict = {}


def clip_thumb(sheet: Path, width: int, mtime: float = 0.0) -> QPixmap:
    """Primeiro quadro do sheet.jpg do clipe, em 9:16."""
    key = (str(sheet), mtime, width)
    if key in _thumb_cache:
        return _thumb_cache[key]
    h = int(width * 16 / 9)
    pm = QPixmap(str(sheet)) if Path(sheet).is_file() else QPixmap()
    if not pm.isNull():
        x, y, w, hh = SHEET_CELL
        pm = pm.copy(x, y, w, hh).scaled(width, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    else:
        pm = QPixmap(width, h)
        pm.fill(QColor(T.SURFACE))
        p = QPainter(pm)
        p.setFont(icon_font(22))
        p.setPen(QColor(T.DIM))
        p.drawText(pm.rect(), Qt.AlignCenter, glyph("video"))
        p.end()
    _thumb_cache[key] = pm
    return pm


def rounded(pm: QPixmap, radius: int = T.R_MD) -> QPixmap:
    out = QPixmap(pm.size())
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(pm)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(out.rect(), radius, radius)
    p.end()
    return out


class Thumb(QWidget):
    """Miniatura 9:16 com selos (duração, nota) e realce ao passar o mouse."""
    clicked = Signal()

    def __init__(self, sheet: Path, width: int, mtime: float = 0.0, duration: str = "", score: float | None = None):
        super().__init__()
        self.setFixedSize(width, int(width * 16 / 9))
        self.setCursor(Qt.PointingHandCursor)
        self.pm = rounded(clip_thumb(sheet, width, mtime), T.R_MD)
        self.duration, self.score = duration, score
        self._hover = 0.0
        self._anim = QPropertyAnimation(self, b"hover", self)
        self._anim.setDuration(T.ANIM_FAST)

    def get_hover(self):
        return self._hover

    def set_hover(self, v):
        self._hover = v
        self.update()

    hover = Property(float, get_hover, set_hover)

    def enterEvent(self, e):
        self._anim.stop()
        self._anim.setEndValue(1.0)
        self._anim.start()

    def leaveEvent(self, e):
        self._anim.stop()
        self._anim.setEndValue(0.0)
        self._anim.start()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.drawPixmap(0, 0, self.pm)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._hover > 0:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, int(70 * self._hover)))
            p.drawRoundedRect(r, T.R_MD, T.R_MD)
            c = r.center()
            p.setBrush(QColor(255, 255, 255, int(230 * self._hover)))
            p.drawEllipse(c, 18, 18)
            p.setFont(icon_font(14))
            p.setPen(QColor(16, 16, 19, int(255 * self._hover)))
            p.drawText(QRectF(c.x() - 18, c.y() - 18, 36, 36).translated(1.5, 0), Qt.AlignCenter, glyph("play"))
        pen = QPen(QColor(T.PRIMARY if self._hover > 0.5 else T.BORDER), 1)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, T.R_MD, T.R_MD)
        f = QFont(T.FONT_FAMILY)
        f.setPixelSize(T.FS_XS)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        if self.duration:
            self._chip(p, self.duration, right=True)
        if self.score is not None:
            self._chip(p, f"{self.score:.1f}", right=False, star=True)

    def _chip(self, p: QPainter, text: str, right: bool, star: bool = False):
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(text) + (22 if star else 10)
        h = 18
        x = self.width() - w - 6 if right else 6
        y = self.height() - h - 6 if right else 6
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 165))
        p.drawRoundedRect(QRectF(x, y, w, h), 4, 4)
        p.setPen(QColor(T.TEXT))
        tx = x + 5
        if star:
            p.save()
            p.setFont(icon_font(9))
            p.setPen(QColor(T.SECONDARY))
            p.drawText(QRectF(x + 4, y, 12, h), Qt.AlignCenter, glyph("star"))
            p.restore()
            tx = x + 17
        p.drawText(QRectF(tx, y, w, h), Qt.AlignVCenter | Qt.AlignLeft, text)


class VideoCard(QFrame):
    """Card de clipe: miniatura 9:16, título, origem e status de sincronia."""
    clicked = Signal(object)

    def __init__(self, clip, width: int = 180, platform_label: str = "", sync=None, date_text: str = "",
                 duration: str = ""):
        super().__init__()
        self.setObjectName("VideoCard")
        self.clip = clip
        self.setFixedWidth(width)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(T.SP2)
        th = Thumb(clip.sheet, width, clip.mtime, duration, clip.score)
        th.clicked.connect(lambda: self.clicked.emit(clip))
        v.addWidget(th)
        t = label("", "H3")
        t.setWordWrap(True)
        t.setFixedHeight(36)
        t.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        fm = t.fontMetrics()
        text = clip.title
        if fm.horizontalAdvance(text) > width * 2 - 20:
            text = fm.elidedText(text, Qt.ElideRight, width * 2 - 20)
        t.setText(text)
        t.setToolTip(clip.title)
        v.addWidget(t)
        meta = QHBoxLayout()
        meta.setSpacing(T.SP2)
        m = label(" · ".join(x for x in (platform_label, date_text) if x), "Dim")
        meta.addWidget(m, 1)
        if sync:
            text, color = sync
            d = StatusDot(color, 6)
            d.setToolTip(text)
            meta.addWidget(d)
        v.addLayout(meta)


# ================================================================ logos das plataformas
class BrandLogo(QWidget):
    """Logos das redes (desenho simples, só para identificar o serviço)."""

    def __init__(self, brand: str, size: int = 32):
        super().__init__()
        self.brand = brand
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self.width()
        r = QRectF(0, 0, s, s)
        b = self.brand
        if b == "youtube":
            body = QRectF(0, s * 0.18, s, s * 0.64)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FF0033"))
            p.drawRoundedRect(body, s * 0.18, s * 0.18)
            tri = QPainterPath()
            tri.moveTo(s * 0.40, s * 0.35)
            tri.lineTo(s * 0.68, s * 0.50)
            tri.lineTo(s * 0.40, s * 0.65)
            tri.closeSubpath()
            p.setBrush(QColor("white"))
            p.drawPath(tri)
        elif b == "tiktok":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#000000"))
            p.drawRoundedRect(r, s * 0.24, s * 0.24)
            for dx, col in ((-1.2, "#25F4EE"), (1.2, "#FE2C55"), (0, "#FFFFFF")):
                path = QPainterPath()
                x0 = s * 0.47 + dx
                path.addRect(QRectF(x0, s * 0.20, s * 0.09, s * 0.45))
                path.addEllipse(QRectF(x0 - s * 0.20, s * 0.50, s * 0.27, s * 0.27))
                hook = QPainterPath()
                hook.moveTo(x0 + s * 0.09, s * 0.20)
                hook.cubicTo(x0 + s * 0.12, s * 0.33, x0 + s * 0.22, s * 0.36, x0 + s * 0.30, s * 0.36)
                hook.lineTo(x0 + s * 0.30, s * 0.27)
                hook.cubicTo(x0 + s * 0.22, s * 0.27, x0 + s * 0.13, s * 0.22, x0 + s * 0.12, s * 0.20)
                hook.closeSubpath()
                path.addPath(hook)
                p.setBrush(QColor(col))
                p.drawPath(path.simplified())
        elif b == "instagram":
            g = QLinearGradient(r.bottomLeft(), r.topRight())
            g.setColorAt(0, QColor("#FEDA75"))
            g.setColorAt(0.35, QColor("#FA7E1E"))
            g.setColorAt(0.6, QColor("#D62976"))
            g.setColorAt(1, QColor("#4F5BD5"))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawRoundedRect(r, s * 0.28, s * 0.28)
            pen = QPen(QColor("white"), max(1.6, s * 0.075))
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(s * 0.22, s * 0.22, s * 0.56, s * 0.56), s * 0.16, s * 0.16)
            p.drawEllipse(QRectF(s * 0.36, s * 0.36, s * 0.28, s * 0.28))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("white"))
            p.drawEllipse(QRectF(s * 0.62, s * 0.29, s * 0.07, s * 0.07))
        elif b == "facebook":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#0866FF"))
            p.drawEllipse(r)
            f = QFont("Segoe UI")
            f.setPixelSize(int(s * 0.78))
            f.setWeight(QFont.Black)
            p.setFont(f)
            p.setPen(QColor("white"))
            p.drawText(r.adjusted(s * 0.08, s * 0.16, 0, 0), Qt.AlignCenter, "f")


# ================================================================ estados e blocos
class EmptyState(QWidget):
    def __init__(self, icon: str, title: str, text: str = "", action: QPushButton | None = None,
                 compact: bool = False):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(T.SP6, T.SP4 if compact else T.SP10, T.SP6, T.SP4 if compact else T.SP10)
        v.setSpacing(T.SP2)
        v.setAlignment(Qt.AlignCenter)
        self.ic = Icon(icon, 20 if compact else 26, T.DIM)
        v.addWidget(self.ic, 0, Qt.AlignHCenter)
        self.title = label(title, "H3")
        self.title.setAlignment(Qt.AlignCenter)
        v.addWidget(self.title, 0, Qt.AlignHCenter)
        self.text = label(text, "Dim", wrap=True)
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setMaximumWidth(420)
        self.text.setVisible(bool(text))
        v.addWidget(self.text, 0, Qt.AlignHCenter)
        if action:
            v.addSpacing(T.SP2)
            v.addWidget(action, 0, Qt.AlignHCenter)

    def set(self, icon: str, title: str, text: str = "", color: str = T.DIM):
        self.ic.set(icon, color)
        self.title.setText(title)
        self.text.setText(text)
        self.text.setVisible(bool(text))


class Collapsible(QWidget):
    """Seção recolhível (cabeçalho clicável + conteúdo)."""
    toggled = Signal(bool)

    def __init__(self, title: str, content: QWidget, expanded: bool = False, right: QWidget | None = None):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(T.SP2)
        head = QHBoxLayout()
        head.setSpacing(T.SP2)
        self.btn = QPushButton(title)
        self.btn.setObjectName("Ghost")
        self.btn.setCursor(Qt.PointingHandCursor)
        self.btn.setStyleSheet(f"QPushButton#Ghost {{ padding: 0 {T.SP2}px; text-align: left; }}")
        self.btn.clicked.connect(self.toggle)
        head.addWidget(self.btn)
        head.addStretch(1)
        if right is not None:
            head.addWidget(right)
        v.addLayout(head)
        self.content = content
        v.addWidget(content)
        self.expanded = not expanded
        self.toggle()

    def toggle(self):
        self.expanded = not self.expanded
        self.content.setVisible(self.expanded)
        self.btn.setIcon(glyph_icon("chevup" if self.expanded else "chevdown", T.MUTED, 10))
        self.toggled.emit(self.expanded)


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str = "", right: QWidget | None = None):
        super().__init__()
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        v = QVBoxLayout()
        v.setSpacing(2)
        v.addWidget(label(title, "H2"))
        if subtitle:
            v.addWidget(label(subtitle, "Dim", wrap=True))
        h.addLayout(v, 1)
        if right is not None:
            h.addWidget(right, 0, Qt.AlignBottom)


class Toast(QFrame):
    """Notificação discreta no canto inferior direito."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(T.SP3, T.SP2, T.SP4, T.SP2)
        lay.setSpacing(T.SP2)
        self.ic = Icon("check", 13, T.SUCCESS)
        self.lb = QLabel()
        self.lb.setStyleSheet("background: transparent;")
        lay.addWidget(self.ic)
        lay.addWidget(self.lb)
        self.eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.eff)
        self.anim = QPropertyAnimation(self.eff, b"opacity", self)
        self.anim.setDuration(T.ANIM)
        self.hide()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade_out)

    def show_msg(self, text: str, kind: str = "info"):
        col = {"info": T.SUCCESS, "warn": T.WARNING, "error": T.ERROR}.get(kind, T.SUCCESS)
        self.ic.set({"info": "check", "warn": "warn", "error": "error"}.get(kind, "info"), col)
        self.lb.setText(text)
        self.adjustSize()
        par = self.parentWidget()
        self.move(par.width() - self.width() - T.SP4, par.height() - self.height() - T.SP4 - 30)
        self.show()
        self.raise_()
        self.anim.stop()
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        self.timer.start(3200)

    def _fade_out(self):
        self.anim.stop()
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()
        QTimer.singleShot(T.ANIM + 20, self.hide)


class FadeStack(QStackedWidget):
    """Troca de página com fade curto."""

    def set_index(self, i: int):
        if i == self.currentIndex():
            return
        self.setCurrentIndex(i)
        w = self.currentWidget()
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", w)
        a.setDuration(T.ANIM)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.finished.connect(lambda: w.setGraphicsEffect(None))
        a.start()
        w._fade = a


class AdaptiveStack(QStackedWidget):
    """QStackedWidget que tem a altura da página visível (o padrão usa a maior de todas)."""

    def __init__(self):
        super().__init__()
        self.currentChanged.connect(self._fit)

    def _fit(self, *_):
        for i in range(self.count()):
            w = self.widget(i)
            w.setSizePolicy(QSizePolicy.Preferred,
                            QSizePolicy.Preferred if w is self.currentWidget() else QSizePolicy.Ignored)
        self.updateGeometry()

    def addWidget(self, w):
        i = super().addWidget(w)
        self._fit()
        return i

    def sizeHint(self):
        w = self.currentWidget()
        return w.sizeHint() if w else super().sizeHint()

    def minimumSizeHint(self):
        w = self.currentWidget()
        return w.minimumSizeHint() if w else super().minimumSizeHint()


class FlowLayout(QLayout):
    """Layout que quebra linha quando falta largura (selos e botões na visualização do clipe)."""

    def __init__(self, parent=None, spacing: int = T.SP2):
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientations(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do(QRect(0, 0, width, 0), test=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, test=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        return s

    def _do(self, rect, test):
        x, y, line_h = rect.x(), rect.y(), 0
        sp = self.spacing()
        for it in self._items:
            if it.widget() is not None and not it.widget().isVisible() and not test:
                continue
            hint = it.sizeHint()
            nx = x + hint.width() + sp
            if nx - sp > rect.right() + 1 and line_h > 0:
                x, y = rect.x(), y + line_h + sp
                nx = x + hint.width() + sp
                line_h = 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), hint))
            x = nx
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y()


def fmt_ago(ts: float) -> str:
    """'hoje', 'ontem', 'há 3 dias' ou a data."""
    d = int((time.time() - ts) // 86400)
    if d <= 0:
        return "hoje"
    if d == 1:
        return "ontem"
    if d < 7:
        return f"há {d} dias"
    return time.strftime("%d/%m/%Y", time.localtime(ts))


def centered(widget: QWidget, max_width: int) -> QWidget:
    """Embrulha `widget` numa linha que o centraliza com largura máxima."""
    holder = QWidget()
    holder.setObjectName("Transparent")
    h = QHBoxLayout(holder)
    h.setContentsMargins(0, 0, 0, 0)
    h.addStretch(1)
    widget.setMaximumWidth(max_width)
    widget.setSizePolicy(QSizePolicy.Expanding, widget.sizePolicy().verticalPolicy())
    h.addWidget(widget, 100)
    h.addStretch(1)
    return holder
