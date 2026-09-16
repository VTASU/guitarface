# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

mediapipe_datas, mediapipe_binaries, mediapipe_hiddenimports = collect_all("mediapipe")
mediapipe_hiddenimports = [
    module
    for module in mediapipe_hiddenimports
    if ".test" not in module
    and not module.endswith("_test")
    and ".genai.converter" not in module
]

a = Analysis(
    ["src/guitar_face/__main__.py"],
    pathex=["src"],
    binaries=mediapipe_binaries,
    datas=mediapipe_datas + [("assets/face_landmarker.task", "assets")],
    hiddenimports=mediapipe_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["jax", "jaxlib", "scipy", "pytest", "torch"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Guitar Face",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Guitar Face",
)
app = BUNDLE(
    coll,
    name="Guitar Face.app",
    bundle_identifier="com.guitarface.app",
    version="0.1.0",
    info_plist={
        "CFBundleDisplayName": "Guitar Face",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "2",
        "LSMinimumSystemVersion": "13.0",
        "NSCameraUsageDescription": (
            "Guitar Face uses the selected camera to turn your facial expression into MIDI wah control."
        ),
        "NSCameraUseContinuityCameraDeviceType": True,
        "NSHighResolutionCapable": True,
    },
)
