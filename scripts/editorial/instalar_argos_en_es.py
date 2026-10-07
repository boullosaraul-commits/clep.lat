#!/usr/bin/env python3
"""Asegura localmente el paquete Argos Translate EN→ES."""
import argostranslate.package
import argostranslate.translate

installed = argostranslate.translate.get_installed_languages()
en = next((x for x in installed if x.code == "en"), None)
es = next((x for x in installed if x.code == "es"), None)
if en and es:
    try:
        en.get_translation(es)
        print("Argos EN→ES already installed")
        raise SystemExit(0)
    except Exception:
        pass

argostranslate.package.update_package_index()
packages = argostranslate.package.get_available_packages()
package = next((p for p in packages if p.from_code == "en" and p.to_code == "es"), None)
if package is None:
    raise SystemExit("ARGOS_EN_ES_PACKAGE_NOT_FOUND")
argostranslate.package.install_from_path(package.download())
print("Argos EN→ES installed")
