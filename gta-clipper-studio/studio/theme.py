"""Paleta e folha de estilo: pôr do sol de Vice City / Leonida (rosa, laranja, roxo) sobre fundo noturno."""

BG = "#0c0812"
SIDEBAR = "#100a19"
SURFACE = "#171021"
SURFACE_2 = "#1f162e"
SURFACE_3 = "#2a1f3e"
BORDER = "#2e2342"
TEXT = "#f6f0fb"
MUTED = "#a99ac0"
DIM = "#6d5f86"
GREEN = "#2ef0c2"  # sucesso / OK (verde-água de Vice City)
GREEN_DIM = "#1a8c72"
PURPLE = "#9d5cff"
PURPLE_DIM = "#5a2fa8"
PINK = "#ff2d95"
ORANGE = "#ff9a3c"
ACCENT = PINK          # cor de destaque da marca
ON_ACCENT = "#1c0613"  # texto sobre o gradiente
RED = "#ff4d5e"
AMBER = "#ffc247"
CYAN = "#38d6ff"

FONT = "Segoe UI Variable Text, Segoe UI, sans-serif"
ICON_FONT = "Segoe Fluent Icons"
ICON_FALLBACK = "Segoe MDL2 Assets"

# Glifos Segoe Fluent / MDL2
ICONS = {
    "home": "", "add": "", "sync": "", "library": "", "settings": "",
    "folder": "", "play": "", "pause": "", "stop": "", "cancel": "",
    "refresh": "", "video": "", "check": "", "error": "", "warn": "",
    "info": "", "paste": "", "gpu": "", "clock": "", "rocket": "",
    "doc": "", "copy": "", "search": "", "link": "", "cut": "",
    "open": "", "volume": "", "mute": "", "chip": "", "shield": "",
    "terminal": "", "star": "", "dot": "", "chev": "", "dash": "",
}

QSS = f"""
* {{ font-family: {FONT}; color: {TEXT}; }}
QMainWindow {{ background: {BG}; }}
QWidget#Page {{ background: transparent; }}
QToolTip {{ background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px 8px; border-radius: 6px; }}

#Sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
#Brand {{ font-size: 15px; font-weight: 800; letter-spacing: 2px; color: {TEXT}; }}
#BrandSub {{ font-size: 10px; font-weight: 700; letter-spacing: 4px; color: {ORANGE}; }}
#NavButton {{ background: transparent; border: none; border-radius: 10px; text-align: left;
              padding: 0 14px; font-size: 13px; font-weight: 600; color: {MUTED}; }}
#NavButton:hover {{ background: {SURFACE}; color: {TEXT}; }}
#NavButton:checked {{ background: {SURFACE_2}; color: {TEXT}; }}

#PageTitle {{ font-size: 26px; font-weight: 800; }}
#PageSub {{ font-size: 13px; color: {MUTED}; }}
#SectionTitle {{ font-size: 14px; font-weight: 700; color: {TEXT}; }}
#Muted {{ color: {MUTED}; }}
#Dim {{ color: {DIM}; font-size: 12px; }}

#Card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
#Card:hover {{ border-color: #4a3566; }}
#CardFlat {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
#StatValue {{ font-size: 30px; font-weight: 800; }}
#StatLabel {{ font-size: 12px; color: {MUTED}; font-weight: 600; letter-spacing: 0.5px; }}

QPushButton {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 9px;
               padding: 8px 14px; font-weight: 600; font-size: 13px; }}
QPushButton:hover {{ background: {SURFACE_3}; border-color: #4a3a66; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:disabled {{ color: {DIM}; background: {SURFACE}; border-color: {BORDER}; }}
QPushButton#Primary {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {PINK}, stop:1 {ORANGE});
                       color: {ON_ACCENT}; border: none; font-weight: 800; letter-spacing: 1px; }}
QPushButton#Primary:hover {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff5aac, stop:1 #ffb366); }}
QPushButton#Primary:disabled {{ background: {SURFACE_2}; color: {DIM}; }}
QPushButton#Danger {{ background: rgba(255,77,109,0.12); border: 1px solid rgba(255,77,109,0.55); color: {RED}; }}
QPushButton#Danger:hover {{ background: rgba(255,77,109,0.22); }}
QPushButton#Danger:disabled {{ background: {SURFACE}; border-color: {BORDER}; color: {DIM}; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid {BORDER}; }}
QPushButton#Ghost:hover {{ border-color: {PINK}; background: rgba(255,45,149,0.08); }}
QPushButton#Seg {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px;
                   padding: 10px 16px; font-size: 14px; }}
QPushButton#Seg:checked {{ background: rgba(255,45,149,0.12); border: 1px solid {PINK}; color: #ff7dbd; }}
QPushButton#SegPurple {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px;
                   padding: 10px 0; font-size: 16px; font-weight: 800; }}
QPushButton#SegPurple:checked {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(157,92,255,0.22), stop:1 rgba(255,45,149,0.22)); border: 1px solid {PINK}; color: #ffd0ea; }}
QPushButton#SegPurple:disabled {{ color: #44375c; background: {SURFACE}; }}

QLineEdit {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 10px; padding: 10px 12px;
             font-size: 14px; selection-background-color: {PURPLE_DIM}; }}
QLineEdit:focus {{ border: 1px solid {PINK}; }}
QLineEdit#Big {{ font-size: 15px; padding: 14px 14px; }}

QPlainTextEdit, QTextBrowser {{ background: #09060e; border: 1px solid {BORDER}; border-radius: 12px; padding: 8px;
                  font-family: Cascadia Mono, Consolas, monospace; font-size: 12px;
                  selection-background-color: {PURPLE_DIM}; }}
QTextBrowser#Post {{ font-family: {FONT}; font-size: 13px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {PURPLE_DIM}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {SURFACE_3}; border-radius: 4px; min-width: 30px; }}

QComboBox {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 9px; padding: 7px 12px; }}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; border: 1px solid {BORDER}; selection-background-color: {PURPLE_DIM}; }}
QCheckBox {{ color: {MUTED}; spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {BORDER}; background: {SURFACE_2}; }}
QCheckBox::indicator:checked {{ background: {PINK}; border-color: {PINK}; }}

QSlider::groove:horizontal {{ height: 4px; background: {SURFACE_3}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {PINK}, stop:1 {ORANGE}); border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}

QMessageBox {{ background: {SURFACE}; }}
QMessageBox QLabel {{ color: {TEXT}; }}
QDialog {{ background: {BG}; }}

#Badge {{ border-radius: 8px; padding: 2px 8px; font-size: 11px; font-weight: 700; }}
#Toast {{ background: {SURFACE_3}; border: 1px solid {BORDER}; border-radius: 12px; }}
"""
