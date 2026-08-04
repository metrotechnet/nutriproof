# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for NutriProof backend.
Bundles app.py + api/ + templates/ + static/ + dbase/ + config/ into a one-folder dist.
"""

import os
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

block_cipher = None
project_root = os.path.abspath('.')
cv2_binaries = collect_dynamic_libs('cv2')
cv2_hiddenimports = collect_submodules('cv2')

a = Analysis(
    ['app.py'],
    pathex=[project_root],
    binaries=cv2_binaries,
    datas=[
        ('templates', 'templates'),
        ('static', 'static'),
        ('dbase', 'dbase'),
        ('api', 'api'),
    ],
    hiddenimports=[
        'cv2',
        'waitress',
        'flask',
        'pyocr',
        'pyocr.builders',
        'pyocr.tesseract',
        'PIL',
        'pandas',
        'numpy',
        'xlwt',
        'fitz',
        'api',
        'api.extract_tables',
        'api.task_mngr',
        'api.clean_mngr',
        'api.firebase_auth',
        'api.routes',
        'api.routes.project_routes',
        'api.routes.document_routes',
        'api.routes.ocr_routes',
        'api.routes.data_routes',
        'api.routes.helpers',
        'firebase_admin',
        'firebase_admin.credentials',
        'firebase_admin.auth',
        'firebase_admin.firestore',
        'google.auth',
        'google.auth.transport',
        'google.auth.transport.requests',
        'google.oauth2',
        'cachetools',
        'google.cloud.firestore',
        'google.cloud.firestore_v1',
        'grpc',
    ] + cv2_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'vertexai',
        'uploads',
        'uploads - Copie',
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for Flask log output
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='backend',
)
