"""Design system do GTA Clipper Studio: cores, tipografia, espaçamentos, raios, animação e folha de estilo.

Direção: escuro e neutro (Cobalt / Raycast) com um toque de Vice City só na cor primária (rosa) e secundária
(pêssego). Nada de gradiente grande, brilho (glow) ou vidro. Tudo que é visual sai daqui.
"""

# ---------------------------------------------------------------- cores
BG = "#101013"          # fundo principal
SURFACE = "#1C1C21"     # superfícies (cards, campos)
ELEVATED = "#25252B"    # superfícies elevadas (hover, menus, popups)
BORDER = "#303037"      # bordas
BORDER_STRONG = "#45454E"
PRIMARY = "#FF629D"     # rosa Vice City
PRIMARY_HOVER = "#FF7DAF"
PRIMARY_PRESSED = "#E9558C"
ON_PRIMARY = "#1A0B12"  # texto sobre a cor primária
SECONDARY = "#FFAB76"   # pêssego (pôr do sol)
TEXT = "#F5F5F5"
MUTED = "#A1A1AA"       # texto secundário
DIM = "#71717A"         # texto terciário / desabilitado
SUCCESS = "#39CA93"
WARNING = "#FBBF24"
ERROR = "#EF4444"
INFO = "#7DD3FC"

# cores das plataformas de origem (só em selos pequenos)
YOUTUBE_RED = "#FF4E45"
TWITCH_PURPLE = "#A970FF"

# nomes antigos (usados por app_icon / build_exe e pelo que ainda importa de fora)
SURFACE_2, SURFACE_3 = ELEVATED, ELEVATED
PINK, ORANGE, PURPLE = PRIMARY, SECONDARY, TWITCH_PURPLE
GREEN, RED, AMBER, CYAN = SUCCESS, ERROR, WARNING, INFO
ACCENT, ON_ACCENT = PRIMARY, ON_PRIMARY


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------- tipografia
FONT_FAMILY = "Segoe UI Variable Text"
FONT_DISPLAY = "Segoe UI Variable Display"
FONT = f"'{FONT_FAMILY}', 'Segoe UI', 'Inter', sans-serif"
FONT_MONO = "'Cascadia Mono', 'Consolas', monospace"
FS_XS, FS_SM, FS_MD, FS_LG, FS_XL, FS_HERO = 11, 12, 13, 15, 18, 26
ICON_FONT = "Segoe Fluent Icons"
ICON_FALLBACK = "Segoe MDL2 Assets"

# ---------------------------------------------------------------- espaçamento (múltiplos de 4) e forma
SP1, SP2, SP3, SP4, SP5, SP6, SP8, SP10 = 4, 8, 12, 16, 20, 24, 32, 40
R_SM, R_MD, R_LG = 6, 8, 12
CONTROL_H = 36          # altura de botões e campos
CONTROL_H_LG = 44       # campo de link e botão principal
CONTENT_MAX_W = 1120    # largura máxima do conteúdo (centralizado)
FORM_MAX_W = 640        # largura do formulário de Criar cortes

# ---------------------------------------------------------------- animação
ANIM_FAST, ANIM, ANIM_SLOW = 150, 200, 250

# ---------------------------------------------------------------- ícones (Segoe Fluent Icons / MDL2)
ICONS = {
    "home": "", "add": "", "sync": "", "library": "", "settings": "",
    "folder": "", "play": "", "pause": "", "stop": "", "cancel": "",
    "refresh": "", "video": "", "check": "", "error": "", "warn": "",
    "info": "", "paste": "", "gpu": "", "clock": "", "rocket": "",
    "doc": "", "copy": "", "search": "", "link": "", "cut": "",
    "open": "", "volume": "", "mute": "", "chip": "", "shield": "",
    "terminal": "", "star": "", "dot": "", "chev": "", "dash": "",
    "chevdown": "", "chevup": "", "back": "", "grid": "", "list": "",
    "upload": "", "calendar": "", "history": "", "people": "", "plug": "",
    "filter": "", "sparkle": "", "subtitle": "", "globe": "",
}
ICONS["fullscreen"] = ""

# ---------------------------------------------------------------- folha de estilo
QSS = f"""
* {{ font-family: {FONT}; color: {TEXT}; font-size: {FS_MD}px; outline: none; }}
QMainWindow, #Root {{ background: {BG}; }}
QWidget#Page, QWidget#Transparent {{ background: transparent; }}
QToolTip {{ background: {ELEVATED}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px 8px;
            border-radius: {R_SM}px; font-size: {FS_SM}px; }}

/* barra superior */
#TopBar {{ background: {BG}; border-bottom: 1px solid {BORDER}; }}
#BrandName {{ font-size: {FS_MD}px; font-weight: 600; color: {TEXT}; }}
#NavTab {{ background: transparent; border: none; padding: 0 {SP3}px; color: {MUTED};
           font-size: {FS_MD}px; font-weight: 500; }}
#NavTab:hover {{ color: {TEXT}; }}
#NavTab:checked {{ color: {TEXT}; }}

/* barra de status */
#StatusBar {{ background: {BG}; border-top: 1px solid {BORDER}; }}
#StatusText {{ color: {MUTED}; font-size: {FS_SM}px; }}

/* texto */
#Hero {{ font-family: '{FONT_DISPLAY}', 'Segoe UI'; font-size: {FS_HERO}px; font-weight: 700; }}
#HeroSub {{ font-size: {FS_LG}px; color: {MUTED}; }}
#H1 {{ font-family: '{FONT_DISPLAY}', 'Segoe UI'; font-size: {FS_XL}px; font-weight: 700; }}
#H2 {{ font-size: {FS_LG}px; font-weight: 600; }}
#H3 {{ font-size: {FS_MD}px; font-weight: 600; }}
#Label {{ font-size: {FS_SM}px; color: {MUTED}; font-weight: 500; }}
#Muted {{ color: {MUTED}; }}
#Dim {{ color: {DIM}; font-size: {FS_SM}px; }}
#Mono {{ font-family: {FONT_MONO}; font-size: {FS_SM}px; color: {MUTED}; }}

/* superfícies */
#Panel {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {R_LG}px; }}
#PanelFlat {{ background: transparent; border: 1px solid {BORDER}; border-radius: {R_LG}px; }}
#Divider {{ background: {BORDER}; max-height: 1px; min-height: 1px; border: none; }}
#VideoCard {{ background: transparent; border: none; border-radius: {R_MD}px; }}
#ListRow {{ background: transparent; border: 1px solid transparent; border-radius: {R_MD}px; }}
#ListRow:hover {{ background: {SURFACE}; border-color: {BORDER}; }}

/* botões */
QPushButton {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {R_MD}px;
               padding: 0 {SP3}px; min-height: {CONTROL_H}px; font-weight: 500; }}
QPushButton:hover {{ background: {ELEVATED}; border-color: {BORDER_STRONG}; }}
QPushButton:pressed {{ background: {SURFACE}; }}
QPushButton:focus {{ border-color: {PRIMARY}; }}
QPushButton:disabled {{ color: {DIM}; background: {SURFACE}; border-color: {BORDER}; }}
QPushButton#Primary {{ background: {PRIMARY}; color: {ON_PRIMARY}; border: 1px solid {PRIMARY}; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {PRIMARY_HOVER}; border-color: {PRIMARY_HOVER}; }}
QPushButton#Primary:pressed {{ background: {PRIMARY_PRESSED}; }}
QPushButton#Primary:focus {{ border: 1px solid {TEXT}; }}
QPushButton#Primary:disabled {{ background: {ELEVATED}; border-color: {ELEVATED}; color: {DIM}; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid transparent; color: {MUTED}; }}
QPushButton#Ghost:hover {{ background: {SURFACE}; color: {TEXT}; }}
QPushButton#Ghost:disabled {{ color: {DIM}; background: transparent; }}
QPushButton#Danger {{ background: transparent; border: 1px solid {rgba(ERROR, 0.45)}; color: {ERROR}; }}
QPushButton#Danger:hover {{ background: {rgba(ERROR, 0.10)}; }}
QPushButton#Danger:disabled {{ border-color: {BORDER}; color: {DIM}; }}
QPushButton#Seg {{ background: transparent; border: none; border-radius: {R_SM}px; min-height: 28px;
                   padding: 0 {SP3}px; color: {MUTED}; }}
QPushButton#Seg:hover {{ color: {TEXT}; }}
QPushButton#Seg:checked {{ background: {ELEVATED}; color: {TEXT}; }}
#SegGroup {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {R_MD}px; }}

/* campos */
QLineEdit {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {R_MD}px; padding: 0 {SP3}px;
             min-height: {CONTROL_H}px; selection-background-color: {rgba(PRIMARY, 0.35)}; }}
QLineEdit:hover {{ border-color: {BORDER_STRONG}; }}
QLineEdit:focus {{ border-color: {PRIMARY}; }}
QLineEdit:read-only {{ color: {MUTED}; }}
#LinkField {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {R_LG}px; }}
#LinkField[focus="true"] {{ border-color: {PRIMARY}; }}
#LinkField[state="error"] {{ border-color: {ERROR}; }}
#LinkField QLineEdit {{ background: transparent; border: none; min-height: {CONTROL_H_LG}px; font-size: {FS_LG}px;
                        padding: 0 {SP1}px; }}

QComboBox {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {R_MD}px; padding: 0 {SP3}px;
             min-height: {CONTROL_H}px; }}
QComboBox:hover {{ border-color: {BORDER_STRONG}; }}
QComboBox:focus {{ border-color: {PRIMARY}; }}
QComboBox:disabled {{ color: {DIM}; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{ background: {ELEVATED}; border: 1px solid {BORDER}; border-radius: {R_MD}px;
                               padding: {SP1}px; selection-background-color: {rgba(PRIMARY, 0.18)};
                               selection-color: {TEXT}; outline: none; }}

QCheckBox {{ color: {MUTED}; spacing: {SP2}px; }}
QCheckBox::indicator {{ width: 12px; height: 12px; border-radius: 3px; border: 1px solid {BORDER_STRONG};
                        background: {SURFACE}; }}
QCheckBox::indicator:checked {{ background: {rgba(PRIMARY, 0.85)}; border-color: {PRIMARY}; }}

QPlainTextEdit, QTextBrowser {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: {R_MD}px;
                                padding: {SP2}px; font-family: {FONT_MONO}; font-size: {FS_SM}px;
                                selection-background-color: {rgba(PRIMARY, 0.35)}; }}
QTextBrowser#Prose {{ font-family: {FONT}; font-size: {FS_MD}px; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 3px; min-height: 32px; }}
QScrollBar::handle:vertical:hover {{ background: {BORDER_STRONG}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 3px; min-width: 32px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {PRIMARY}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}

QMessageBox, QDialog {{ background: {BG}; }}
QMessageBox QLabel {{ color: {TEXT}; }}
QMenu {{ background: {ELEVATED}; border: 1px solid {BORDER}; border-radius: {R_MD}px; padding: {SP1}px; }}
QMenu::item {{ padding: 6px {SP3}px; border-radius: {R_SM}px; }}
QMenu::item:selected {{ background: {rgba(PRIMARY, 0.18)}; }}

#Badge {{ border-radius: {R_SM}px; padding: 1px 6px; font-size: {FS_XS}px; font-weight: 600; }}
#Toast {{ background: {ELEVATED}; border: 1px solid {BORDER}; border-radius: {R_MD}px; }}
#Kbd {{ color: {DIM}; font-size: {FS_XS}px; border: 1px solid {BORDER}; border-radius: 4px; padding: 0 4px; }}
"""
