"""Сборка standalone-версии через PyInstaller."""
import PyInstaller.__main__

PyInstaller.__main__.run([
    "main.py",
    "--noconfirm",
    "--onefile",
    "--windowed",
    "--add-data=ui;ui",
    "--name=Kinobaza",
])