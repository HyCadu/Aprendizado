"""Componentes visuais reutilizáveis."""
from __future__ import annotations

import math

from PySide6.QtCore import (Property, QEasingCurve, QPoint, QPropertyAnimation, QRect, QRectF, QSize, Qt, QTimer,
                            Signal)
from PySide6.QtGui import QColor, QFont, QFontDatabase, QLinearGradient, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import (QBoxLayout, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QGridLayout,
                               QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout,
                               QWidget)

from . import theme as T

_icon_family = None


# ---------------------------------------------------------------- layouts responsivos
class FlowLayout(QLayout):
    """Itens lado a lado que quebram para a linha de baixo quando falta largura (barras de botões)."""

    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items = []
        self._sp = spacing
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

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, r):
        super().setGeometry(r)
        self._do(r, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test: bool) -> int:
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = r.x(), r.y(), 0
        for it in self._items:
            if it.widget() is not None and it.widget().isHidden():
                continue
            hint = it.sizeHint()
            if x > r.x() and x + hint.width() > r.right() + 1:
                x, y, line_h = r.x(), y + line_h + self._sp, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), QSize(min(hint.width(), r.width()), hint.height())))
            x += hint.width() + self._sp
            line_h = max(line_h, hint.height())
        return y + line_h - rect.y() + m.bottom()


class ReflowGrid(QWidget):
    """Itens do mesmo tamanho numa grade cujo nº de colunas acompanha a largura.
    `cols` = opções de colunas, da maior para a menor (ex.: 4, 2, 1); usa a maior que couber
    com cada item tendo pelo menos `min_w` px."""

    def __init__(self, min_w: int, cols=(4, 2, 1), spacing: int = 14):
        super().__init__()
        self.min_w, self.opts = min_w, tuple(cols)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(spacing)
        self.items: list[QWidget] = []
        self._n = 0
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def add(self, w: QWidget):
        self.items.append(w)
        self._place(self._n or self.opts[-1], force=True)

    def _fit(self, width: int) -> int:
        sp = self.grid.spacing()
        for n in self.opts:
            if n * self.min_w + (n - 1) * sp <= width:
                return n
        return self.opts[-1]

    def _place(self, n: int, force: bool = False):
        if n == self._n and not force:
            return
        self._n = n
        for w in self.items:
            self.grid.removeWidget(w)
        for c in range(max(self.opts) + 1):
            self.grid.setColumnStretch(c, 1 if c < n else 0)
        for i, w in enumerate(self.items):
            self.grid.addWidget(w, i // n, i % n)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place(self._fit(e.size().width()))

    def minimumSizeHint(self):
        return QSize(self.min_w, super().minimumSizeHint().height())


class AdaptiveBox(QWidget):
    """Linha (lado a lado) que vira coluna (um embaixo do outro) quando a largura fica abaixo de `breakpoint`."""

    def __init__(self, breakpoint: int, spacing: int = 14):
        super().__init__()
        self.bp = breakpoint
        self.box = QBoxLayout(QBoxLayout.LeftToRight, self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(spacing)
        self.vertical = False
        self.on_change = None  # callback(vertical: bool)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        v = e.size().width() < self.bp
        if v != self.vertical:
            self.vertical = v
            self.box.setDirection(QBoxLayout.TopToBottom if v else QBoxLayout.LeftToRight)
            if self.on_change:
                self.on_change(v)

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())


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


class Icon(QLabel):
    def __init__(self, name: str, size: int = 16, color: str = T.TEXT, parent=None):
        super().__init__(glyph(name), parent)
        self.setFont(icon_font(size))
        self.setStyleSheet(f"color: {color}; background: transparent;")
        self.setFixedSize(size + 8, size + 8)
        self.setAlignment(Qt.AlignCenter)

    def set(self, name: str, color: str | None = None):
        self.setText(glyph(name))
        if color:
            self.setStyleSheet(f"color: {color}; background: transparent;")


def icon_button(text: str, icon: str, obj: str = "", tooltip: str = "") -> QPushButton:
    """Botão com glifo + texto (o glifo usa a fonte de ícones via rich text não funciona em QPushButton,
    então montamos um layout interno)."""
    b = QPushButton()
    if obj:
        b.setObjectName(obj)
    lay = QHBoxLayout(b)
    lay.setContentsMargins(12, 0, 14, 0)
    lay.setSpacing(8)
    ic = QLabel(glyph(icon))
    ic.setFont(icon_font(14))
    ic.setAttribute(Qt.WA_TransparentForMouseEvents)
    ic.setStyleSheet("background: transparent; color: inherit;")
    lb = QLabel(text)
    lb.setAttribute(Qt.WA_TransparentForMouseEvents)
    lb.setStyleSheet("background: transparent; font-weight: inherit;")
    lay.addStretch(1)
    lay.addWidget(ic)
    if text:
        lay.addWidget(lb)
    lay.addStretch(1)
    b._icon, b._label = ic, lb
    fm = lb.fontMetrics()
    b.setMinimumWidth(fm.horizontalAdvance(text) + (60 if text else 34))
    b.setMinimumHeight(38)
    if obj == "Primary":
        for w in (ic, lb):
            w.setStyleSheet(f"background: transparent; color: {T.ON_ACCENT}; font-weight: 800;")
    elif obj == "Danger":
        for w in (ic, lb):
            w.setStyleSheet(f"background: transparent; color: {T.RED};")
    if tooltip:
        b.setToolTip(tooltip)
    return b


def set_button_enabled(b: QPushButton, on: bool):
    b.setEnabled(on)
    col = None
    if b.objectName() == "Primary":
        col = T.ON_ACCENT if on else T.DIM
    elif b.objectName() == "Danger":
        col = T.RED if on else T.DIM
    else:
        col = T.TEXT if on else T.DIM
    for w in (getattr(b, "_icon", None), getattr(b, "_label", None)):
        if w is not None:
            w.setStyleSheet(f"background: transparent; color: {col}; font-weight: inherit;")


def card(obj: str = "Card") -> QFrame:
    f = QFrame()
    f.setObjectName(obj)
    return f


def glow(widget: QWidget, color: str = T.ACCENT, radius: int = 28, alpha: int = 90):
    eff = QGraphicsDropShadowEffect(widget)
    c = QColor(color)
    c.setAlpha(alpha)
    eff.setColor(c)
    eff.setBlurRadius(radius)
    eff.setOffset(0, 0)
    widget.setGraphicsEffect(eff)
    return eff


def label(text: str, obj: str = "", wrap: bool = False) -> QLabel:
    l = QLabel(text)
    if obj:
        l.setObjectName(obj)
    l.setWordWrap(wrap)
    return l


def badge(text: str, color: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("Badge")
    c = QColor(color)
    l.setStyleSheet(f"#Badge {{ color: {color}; background: rgba({c.red()},{c.green()},{c.blue()},0.13);"
                    f" border: 1px solid rgba({c.red()},{c.green()},{c.blue()},0.45); }}")
    return l


# ---------------------------------------------------------------- menu lateral
class NavButton(QPushButton):
    def __init__(self, icon: str, text: str):
        super().__init__()
        self.setObjectName("NavButton")
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 12, 0)
        lay.setSpacing(14)
        self.ic = QLabel(glyph(icon))
        self.ic.setFont(icon_font(17))
        self.lb = QLabel(text)
        self.text = text
        self.lay = lay
        for w in (self.ic, self.lb):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(self.ic)
        lay.addWidget(self.lb, 1)
        self.dot = QLabel("")
        self.dot.setFixedSize(8, 8)
        lay.addWidget(self.dot)
        self.toggled.connect(self._restyle)
        self._restyle(False)

    def _restyle(self, on: bool):
        self.ic.setStyleSheet(f"background: transparent; color: {T.ACCENT if on else T.MUTED};")
        self.lb.setStyleSheet(f"background: transparent; font-size: 13px; font-weight: 600;"
                              f" color: {T.TEXT if on else T.MUTED};")

    def set_compact(self, on: bool):
        """Só o ícone (menu estreito); o nome vira dica ao passar o mouse."""
        self.lb.setVisible(not on)
        self.lay.setContentsMargins(*((14, 0, 4, 0) if on else (16, 0, 12, 0)))
        self.setToolTip(self.text if on else "")

    def set_activity(self, on: bool):
        self.dot.setStyleSheet(f"background: {T.ACCENT}; border-radius: 4px;" if on else "background: transparent;")


class Sidebar(QFrame):
    changed = Signal(int)

    def __init__(self):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(232)
        self.compact = False
        self.v = v = QVBoxLayout(self)
        v.setContentsMargins(14, 22, 14, 18)
        v.setSpacing(4)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = Logo()
        brand.addWidget(logo)
        self.brand_txt = QWidget()
        txt = QVBoxLayout(self.brand_txt)
        txt.setContentsMargins(0, 0, 0, 0)
        txt.setSpacing(0)
        txt.addWidget(label("GTA CLIPPER", "Brand"))
        txt.addWidget(label("STUDIO", "BrandSub"))
        brand.addWidget(self.brand_txt)
        brand.addStretch(1)
        v.addLayout(brand)
        v.addSpacing(26)
        self.menu_lbl = label("MENU", "Dim")
        v.addWidget(self.menu_lbl)
        v.addSpacing(6)
        self.buttons: list[NavButton] = []
        self.nav = QWidget()
        self.nav_lay = QVBoxLayout(self.nav)
        self.nav_lay.setContentsMargins(0, 0, 0, 0)
        self.nav_lay.setSpacing(4)
        v.addWidget(self.nav)
        self.indicator = QFrame(self.nav)
        self.indicator.setFixedSize(4, 22)
        self.indicator.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 {T.PINK}, stop:1 {T.ORANGE});"
            " border-radius: 2px;")
        glow(self.indicator, T.PINK, 18, 190)
        self._anim = QPropertyAnimation(self.indicator, b"pos", self)
        self._anim.setDuration(320)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        v.addStretch(1)
        self.footer = label("", "Dim", wrap=True)
        v.addWidget(self.footer)

    def add(self, icon: str, text: str) -> NavButton:
        b = NavButton(icon, text)
        i = len(self.buttons)
        b.clicked.connect(lambda: self.select(i))
        self.buttons.append(b)
        self.nav_lay.addWidget(b)
        self.indicator.raise_()
        return b

    def set_compact(self, on: bool):
        """Janela estreita: menu só com ícones (72 px) para sobrar espaço para a página."""
        if on == self.compact:
            return
        self.compact = on
        self.setFixedWidth(72 if on else 232)
        self.v.setContentsMargins(*((10, 22, 10, 18) if on else (14, 22, 14, 18)))
        for w in (self.brand_txt, self.menu_lbl, self.footer):
            w.setVisible(not on)
        for b in self.buttons:
            b.set_compact(on)
        cur = next((i for i, b in enumerate(self.buttons) if b.isChecked()), None)
        if cur is not None:
            QTimer.singleShot(0, lambda: self._move(cur))

    def select(self, i: int, emit: bool = True):
        for j, b in enumerate(self.buttons):
            b.setChecked(i == j)
        QTimer.singleShot(0, lambda: self._move(i))
        if emit:
            self.changed.emit(i)

    def _move(self, i: int):
        b = self.buttons[i]
        target = QPoint(0, b.y() + (b.height() - self.indicator.height()) // 2)
        if self.indicator.pos() == QPoint(0, 0) and i != 0 and not self._anim.state():
            self.indicator.move(target)
        self._anim.stop()
        self._anim.setStartValue(self.indicator.pos())
        self._anim.setEndValue(target)
        self._anim.start()


class Logo(QWidget):
    """Marca desenhada: um 'play' cortado com gradiente verde → roxo."""

    def __init__(self, size: int = 38):
        super().__init__()
        self.setFixedSize(size, size)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, self.height() - 2)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, QColor(T.ORANGE))
        g.setColorAt(0.5, QColor(T.PINK))
        g.setColorAt(1, QColor(T.PURPLE))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(r, 10, 10)
        p.setBrush(QColor(T.BG))
        w, h = r.width(), r.height()
        path = QPainterPath()
        path.moveTo(r.left() + w * 0.36, r.top() + h * 0.26)
        path.lineTo(r.left() + w * 0.76, r.top() + h * 0.5)
        path.lineTo(r.left() + w * 0.36, r.top() + h * 0.74)
        path.closeSubpath()
        p.drawPath(path)
        p.setPen(QPen(QColor(T.BG), 2.4))
        p.drawLine(int(r.left() + w * 0.22), int(r.top() + h * 0.82), int(r.left() + w * 0.82), int(r.top() + h * 0.18))


# ---------------------------------------------------------------- páginas com fade
class FadeStack(QStackedWidget):
    def set_index(self, i: int):
        if i == self.currentIndex():
            return
        self.setCurrentIndex(i)
        w = self.currentWidget()
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", w)
        a.setDuration(260)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.finished.connect(lambda: w.setGraphicsEffect(None))
        a.start()
        # leve deslize para cima
        b = QPropertyAnimation(w, b"pos", w)
        b.setDuration(260)
        b.setStartValue(w.pos() + QPoint(0, 14))
        b.setEndValue(w.pos())
        b.setEasingCurve(QEasingCurve.OutCubic)
        b.start()
        w._anims = (a, b)


# ---------------------------------------------------------------- progresso neon
class NeonProgress(QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(14)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._value = 0.0
        self._phase = 0.0
        self.active = False
        self.state = "idle"  # idle | run | ok | error | cancel
        self._anim = QPropertyAnimation(self, b"value", self)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _tick(self):
        if self.active:
            self._phase = (self._phase + 0.012) % 1.0
            self.update()

    def get_value(self):
        return self._value

    def set_value(self, v):
        self._value = v
        self.update()

    value = Property(float, get_value, set_value)

    def animate_to(self, v: float):
        v = max(0.0, min(100.0, v))
        if abs(v - self._value) < 0.05:
            return
        self._anim.stop()
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(v)
        self._anim.start()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        rad = r.height() / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(T.SURFACE_3))
        p.drawRoundedRect(r, rad, rad)
        w = r.width() * self._value / 100.0
        if w <= 1:
            return
        fill = QRectF(0, 0, max(w, r.height()), r.height())
        g = QLinearGradient(0, 0, r.width(), 0)
        if self.state == "error":
            g.setColorAt(0, QColor(T.RED)); g.setColorAt(1, QColor("#ff8fa3"))
        elif self.state == "cancel":
            g.setColorAt(0, QColor(T.AMBER)); g.setColorAt(1, QColor("#ffd68a"))
        else:
            g.setColorAt(0, QColor(T.PURPLE)); g.setColorAt(0.55, QColor(T.PINK)); g.setColorAt(1, QColor(T.ORANGE))
        p.setBrush(g)
        p.drawRoundedRect(fill, rad, rad)
        if self.active:
            x = -0.3 * r.width() + self._phase * 1.6 * r.width()
            sh = QLinearGradient(x, 0, x + r.width() * 0.25, 0)
            sh.setColorAt(0, QColor(255, 255, 255, 0))
            sh.setColorAt(0.5, QColor(255, 255, 255, 80))
            sh.setColorAt(1, QColor(255, 255, 255, 0))
            path = QPainterPath()
            path.addRoundedRect(fill, rad, rad)
            p.setClipPath(path)
            p.setBrush(sh)
            p.drawRect(fill)


class PulseDot(QWidget):
    def __init__(self, color: str = T.ACCENT, size: int = 12):
        super().__init__()
        self.color = QColor(color)
        self.setFixedSize(size * 2, size * 2)
        self.size_ = size
        self.t = 0.0
        self.pulsing = True
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def set_color(self, c: str, pulsing: bool = True):
        self.color = QColor(c)
        self.pulsing = pulsing
        self.update()

    def _tick(self):
        if self.pulsing:
            self.t = (self.t + 0.03) % 1.0
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self.rect().center()
        s = self.size_ / 2
        if self.pulsing:
            ring = QColor(self.color)
            ring.setAlphaF(max(0.0, 0.55 * (1 - self.t)))
            p.setPen(Qt.NoPen)
            p.setBrush(ring)
            rr = s + self.t * s * 1.2
            p.drawEllipse(QRectF(c.x() - rr, c.y() - rr, rr * 2, rr * 2))
        p.setBrush(self.color)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(c.x() - s * 0.75, c.y() - s * 0.75, s * 1.5, s * 1.5))


class Spinner(QWidget):
    def __init__(self, size: int = 18, color: str = T.ACCENT):
        super().__init__()
        self.setFixedSize(size, size)
        self.color = QColor(color)
        self.angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self):
        self.angle = (self.angle + 7) % 360
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.color, 2.4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        r = QRectF(2, 2, self.width() - 4, self.height() - 4)
        p.drawArc(r, -self.angle * 16, 260 * 16)


# ---------------------------------------------------------------- cartões de estatística
class StatCard(QFrame):
    def __init__(self, icon: str, label_text: str, accent: str = T.ACCENT):
        super().__init__()
        self.setObjectName("Card")
        self.setMinimumHeight(118)
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        top = QHBoxLayout()
        ic = Icon(icon, 16, accent)
        c = QColor(accent)
        ic.setStyleSheet(f"color: {accent}; background: rgba({c.red()},{c.green()},{c.blue()},0.12);"
                         " border-radius: 8px;")
        ic.setFixedSize(32, 32)
        top.addWidget(ic)
        top.addStretch(1)
        v.addLayout(top)
        v.addStretch(1)
        self.value = label("0", "StatValue")
        v.addWidget(self.value)
        v.addWidget(label(label_text.upper(), "StatLabel"))
        self._shown = 0.0
        self._target = 0.0
        self._fmt = "{:.0f}"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._step)

    def set_value(self, v, fmt: str | None = None, text: str | None = None):
        if text is not None:
            self._timer.stop()
            self.value.setText(text)
            return
        self._fmt = fmt or self._fmt
        self._target = float(v)
        self._timer.start(16)

    def _step(self):
        d = self._target - self._shown
        if abs(d) < 0.5:
            self._shown = self._target
            self._timer.stop()
        else:
            self._shown += d * 0.12 + math.copysign(0.2, d)
        self.value.setText(self._fmt.format(self._shown))


class Toast(QFrame):
    """Aviso rápido no canto inferior direito."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("Toast")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 16, 10)
        self.ic = Icon("info", 15, T.GREEN)
        self.lb = QLabel()
        self.lb.setWordWrap(True)
        self.lb.setStyleSheet("background: transparent; font-weight: 600;")
        lay.addWidget(self.ic)
        lay.addWidget(self.lb)
        self.eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.eff)
        self.anim = QPropertyAnimation(self.eff, b"opacity", self)
        self.hide()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade_out)

    def show_msg(self, text: str, kind: str = "info"):
        col = {"info": T.GREEN, "warn": T.AMBER, "error": T.RED}.get(kind, T.GREEN)
        self.ic.set({"info": "check", "warn": "warn", "error": "error"}.get(kind, "info"), col)
        self.lb.setText(text)
        par = self.parentWidget()
        m = 24 if par.width() > 700 else 12
        self.setMaximumWidth(max(220, min(520, par.width() - 2 * m)))
        self.adjustSize()
        self.move(par.width() - self.width() - m, par.height() - self.height() - m)
        self.show()
        self.raise_()
        self.anim.stop()
        self.anim.setDuration(200)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        self.timer.start(3200)

    def _fade_out(self):
        self.anim.stop()
        self.anim.setDuration(400)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.start()
        QTimer.singleShot(420, self.hide)


class SunsetBackground(QWidget):
    """Fundo noturno com um brilho de pôr do sol (rosa/laranja/roxo) nos cantos, no clima de Vice City."""

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(T.BG))
        for cx, cy, rad, stops in (
            (w * 0.92, -h * 0.10, max(w, h) * 0.55, ((0, (255, 45, 149, 46)), (0.45, (255, 154, 60, 18)), (1, (0, 0, 0, 0)))),
            (w * 0.30, h * 1.10, max(w, h) * 0.50, ((0, (157, 92, 255, 34)), (1, (0, 0, 0, 0)))),
        ):
            g = QRadialGradient(cx, cy, rad)
            for pos, rgba in stops:
                g.setColorAt(pos, QColor(*rgba))
            p.fillRect(self.rect(), g)
