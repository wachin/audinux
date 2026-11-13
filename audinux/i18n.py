# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QLocale, QTranslator, QLibraryInfo

APP_NAME = "audinux"

def tr(context: str, text: str) -> str:
    return QCoreApplication.translate(context, text)

def _candidate_dirs() -> list[Path]:
    dirs: list[Path] = []
    here = Path(__file__).resolve().parent
    dirs.append(here.parent / "i18n")  # repo-level i18n
    dirs.append(here / "i18n")         # package-level i18n (optional)
    dirs.append(Path("/usr/share/audinux/i18n"))
    return dirs

def load_translators(app) -> list[QTranslator]:
    translators: list[QTranslator] = []
    locale = QLocale.system().name()  # es_EC, en_US, ...

    qt_translator = QTranslator()
    qt_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if qt_translator.load("qtbase_" + locale, qt_path):
        app.installTranslator(qt_translator)
        translators.append(qt_translator)

    candidates = [locale, locale.split("_")[0]]
    for cand in candidates:
        fname = f"{APP_NAME}_{cand}.qm"
        for d in _candidate_dirs():
            p = d / fname
            if p.exists():
                t = QTranslator()
                if t.load(str(p)):
                    app.installTranslator(t)
                    translators.append(t)
                    return translators
    return translators
