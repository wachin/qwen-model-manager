#!/usr/bin/env python3
"""
Qwen Model Manager - GUI para gestionar modelos de Qwen Code
Adaptado a la estructura real de settings.json de Qwen Code v4

Uso:
    python3 qwen_model_manager.py
"""

import sys
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QListWidget, QListWidgetItem, QPushButton, QLabel, QMessageBox,
        QGroupBox, QTextEdit, QSplitter, QStatusBar, QDialog,
        QLineEdit, QFormLayout, QComboBox, QDialogButtonBox,
        QFileDialog
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QColor, QPalette, QShortcut, QKeySequence
except ImportError:
    print("ERROR: PyQt6 no esta instalado.")
    print("Instalalo con: pip install PyQt6")
    sys.exit(1)


SETTINGS_PATH = Path.home() / ".qwen" / "settings.json"


def _mask_key(value):
    """Enmascara una API key para mostrar de forma segura."""
    if not value:
        return "(no encontrada)"
    if len(value) > 16:
        return value[:8] + "..." + value[-6:]
    if len(value) > 8:
        return value[:4] + "..." + value[-4:]
    return value[:2] + "..."


def _file_info(path):
    """Retorna (size_str, mtime_str) del archivo."""
    if not path.exists():
        return ("(no existe)", "(no existe)")
    st = path.stat()
    size = st.st_size
    if size < 1024:
        size_str = f"{size} B"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"
    mtime = datetime.fromtimestamp(st.st_mtime)
    mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
    return (size_str, mtime_str)


class AddEditModelDialog(QDialog):
    """Dialogo para anadir o editar un modelo."""

    def __init__(self, parent=None, model=None, providers=None, env_vars=None):
        super().__init__(parent)
        self.setWindowTitle("Editar Modelo" if model else "Anadir Modelo Nuevo")
        self.setMinimumWidth(550)
        self.setMinimumHeight(320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.combo_provider = QComboBox()
        if providers:
            self.combo_provider.addItems(sorted(providers.keys()))
        else:
            self.combo_provider.addItems(["openai"])
        form.addRow("Provider:", self.combo_provider)

        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText("ej: z-ai/glm-5.3-free")
        form.addRow("ID:", self.input_id)

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("Nombre visible del modelo")
        form.addRow("Name:", self.input_name)

        self.input_baseurl = QLineEdit()
        self.input_baseurl.setPlaceholderText("https://api.ejemplo.com/v1")
        form.addRow("Base URL:", self.input_baseurl)

        self.combo_envkey = QComboBox()
        self.combo_envkey.setEditable(True)
        if env_vars:
            self.combo_envkey.addItems(sorted(env_vars.keys()))
        self.combo_envkey.setPlaceholderText("Seleccionar o escribir nueva envKey")
        form.addRow("envKey:", self.combo_envkey)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Rellenar si es edicion
        if model:
            prov_idx = self.combo_provider.findText(model.get("provider", "openai"))
            if prov_idx >= 0:
                self.combo_provider.setCurrentIndex(prov_idx)
            self.combo_provider.setEnabled(False)
            self.input_id.setText(model.get("id", ""))
            self.input_id.setReadOnly(True)
            self.input_name.setText(model.get("name", ""))
            self.input_baseurl.setText(model.get("baseUrl", ""))
            env_idx = self.combo_envkey.findText(model.get("envKey", ""))
            if env_idx >= 0:
                self.combo_envkey.setCurrentIndex(env_idx)
            else:
                self.combo_envkey.setEditText(model.get("envKey", ""))

    def _validate_and_accept(self):
        if not self.input_id.text().strip():
            QMessageBox.warning(self, "Validacion", "El campo ID es obligatorio.")
            return
        if not self.input_name.text().strip():
            QMessageBox.warning(self, "Validacion", "El campo Name es obligatorio.")
            return
        if not self.input_baseurl.text().strip():
            QMessageBox.warning(self, "Validacion", "El campo Base URL es obligatorio.")
            return
        self.accept()

    def get_data(self):
        return {
            "provider": self.combo_provider.currentText().strip(),
            "id": self.input_id.text().strip(),
            "name": self.input_name.text().strip(),
            "baseUrl": self.input_baseurl.text().strip(),
            "envKey": self.combo_envkey.currentText().strip(),
        }


class QwenModelManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qwen Code - Gestor de Modelos")
        self.setMinimumSize(1000, 700)

        self.settings_data = {}
        self.models_list = []

        self._build_ui()
        self._setup_shortcuts()
        self._load_settings()
        self._apply_style()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # === PANEL IZQUIERDO ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Modelos Configurados en Qwen Code")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        left_layout.addWidget(title)

        self.lbl_file_info = QLabel(f"Archivo: {SETTINGS_PATH}")
        self.lbl_file_info.setStyleSheet("color: #888; font-size: 11px;")
        left_layout.addWidget(self.lbl_file_info)
        left_layout.addSpacing(5)

        help_label = QLabel(
            "Selecciona un modelo de la lista para ver detalles.\n"
            "Cambia el modelo activo, edita o borra modelos.\n"
            "Si varios modelos comparten la misma API Key, se conserva al borrar."
        )
        help_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        help_label.setWordWrap(True)
        left_layout.addWidget(help_label)
        left_layout.addSpacing(5)

        # Lista de modelos
        self.list_models = QListWidget()
        self.list_models.setSpacing(5)
        self.list_models.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.list_models)

        # Botones de accion
        btn_layout = QHBoxLayout()

        self.btn_add = QPushButton("+ Anadir Modelo")
        self.btn_add.setMinimumHeight(42)
        self.btn_add.clicked.connect(self._add_model)
        self.btn_add.setStyleSheet("""
            QPushButton {
                background-color: #00b894;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #00a381; }
        """)
        btn_layout.addWidget(self.btn_add)

        self.btn_edit = QPushButton("Editar")
        self.btn_edit.setMinimumHeight(42)
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self._edit_model)
        btn_layout.addWidget(self.btn_edit)

        left_layout.addLayout(btn_layout)

        btn_layout2 = QHBoxLayout()

        self.btn_set_active = QPushButton("Activar Este Modelo")
        self.btn_set_active.setMinimumHeight(42)
        self.btn_set_active.setEnabled(False)
        self.btn_set_active.clicked.connect(self._set_active_model)
        self.btn_set_active.setStyleSheet("""
            QPushButton {
                background-color: #6c5ce7;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5a4bd1; }
            QPushButton:disabled { background-color: #b2bec3; color: #636e72; }
        """)
        btn_layout2.addWidget(self.btn_set_active)

        self.btn_delete = QPushButton("Borrar")
        self.btn_delete.setMinimumHeight(42)
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_layout2.addWidget(self.btn_delete)

        left_layout.addLayout(btn_layout2)

        btn_layout3 = QHBoxLayout()

        self.btn_reload = QPushButton("Recargar (Ctrl+R)")
        self.btn_reload.setMinimumHeight(42)
        self.btn_reload.clicked.connect(self._load_settings)
        btn_layout3.addWidget(self.btn_reload)

        self.btn_backup = QPushButton("Crear Backup")
        self.btn_backup.setMinimumHeight(42)
        self.btn_backup.clicked.connect(self._create_backup)
        btn_layout3.addWidget(self.btn_backup)

        left_layout.addLayout(btn_layout3)

        btn_layout4 = QHBoxLayout()

        self.btn_restore = QPushButton("Restaurar Backup")
        self.btn_restore.setMinimumHeight(42)
        self.btn_restore.clicked.connect(self._restore_backup)
        btn_layout4.addWidget(self.btn_restore)

        self.btn_open_folder = QPushButton("Abrir Carpeta .qwen")
        self.btn_open_folder.setMinimumHeight(42)
        self.btn_open_folder.clicked.connect(self._open_folder)
        btn_layout4.addWidget(self.btn_open_folder)

        left_layout.addLayout(btn_layout4)

        # === PANEL DERECHO ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Detalles del modelo seleccionado
        details_group = QGroupBox("Detalles del Modelo Seleccionado")
        details_layout = QVBoxLayout(details_group)

        self.lbl_model_id = QLabel("Selecciona un modelo de la lista")
        self.lbl_model_id.setWordWrap(True)
        self.lbl_model_id.setStyleSheet("font-size: 13px; color: #333;")
        details_layout.addWidget(self.lbl_model_id)

        self.lbl_model_name = QLabel("")
        self.lbl_model_name.setWordWrap(True)
        self.lbl_model_name.setStyleSheet("font-size: 12px; color: #555;")
        details_layout.addWidget(self.lbl_model_name)

        self.lbl_base_url = QLabel("")
        self.lbl_base_url.setWordWrap(True)
        self.lbl_base_url.setStyleSheet("font-size: 12px; color: #555;")
        details_layout.addWidget(self.lbl_base_url)

        self.lbl_env_key = QLabel("")
        self.lbl_env_key.setWordWrap(True)
        self.lbl_env_key.setStyleSheet(
            "font-size: 11px; color: #8e44ad; font-family: monospace;"
        )
        details_layout.addWidget(self.lbl_env_key)

        self.lbl_api_key = QLabel("")
        self.lbl_api_key.setWordWrap(True)
        self.lbl_api_key.setStyleSheet(
            "font-size: 11px; color: #c0392b; font-family: monospace;"
        )
        details_layout.addWidget(self.lbl_api_key)

        self.lbl_shared_info = QLabel("")
        self.lbl_shared_info.setWordWrap(True)
        self.lbl_shared_info.setStyleSheet("font-size: 11px; color: #2980b9;")
        details_layout.addWidget(self.lbl_shared_info)

        right_layout.addWidget(details_group)

        # Estado actual
        status_group = QGroupBox("Estado Actual de Qwen Code")
        status_layout = QVBoxLayout(status_group)

        self.lbl_current_model = QLabel("Modelo activo: -")
        self.lbl_current_model.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #27ae60;"
        )
        status_layout.addWidget(self.lbl_current_model)

        self.lbl_current_baseurl = QLabel("Base URL activa: -")
        self.lbl_current_baseurl.setStyleSheet("font-size: 11px; color: #555;")
        status_layout.addWidget(self.lbl_current_baseurl)

        self.lbl_auth_type = QLabel("Auth type: -")
        status_layout.addWidget(self.lbl_auth_type)

        right_layout.addWidget(status_group)

        # Vista previa del JSON
        preview_group = QGroupBox("Vista previa del JSON (solo lectura)")
        preview_layout = QVBoxLayout(preview_group)

        self.text_preview = QTextEdit()
        self.text_preview.setReadOnly(True)
        mono_font = QFont("Monospace", 10)
        mono_font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_preview.setFont(mono_font)
        preview_layout.addWidget(self.text_preview)

        right_layout.addWidget(preview_group)

        # === SPLITTER ===
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 560])
        splitter.setHandleWidth(8)
        main_layout.addWidget(splitter)

        # Barra de estado
        self.statusBar().showMessage("Listo. Selecciona un modelo para ver detalles.")

    def _setup_shortcuts(self):
        """Configura atajos de teclado."""
        shortcut_reload = QShortcut(QKeySequence("Ctrl+R"), self)
        shortcut_reload.activated.connect(self._load_settings)

        shortcut_delete = QShortcut(QKeySequence("Delete"), self)
        shortcut_delete.activated.connect(self._delete_selected)

    def _apply_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f6fa;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dcdde1;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2f3640;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #dcdde1;
                border-radius: 8px;
                padding: 8px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 6px;
                margin-bottom: 4px;
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background-color: #0984e3;
                color: white;
                border: 1px solid #0770c2;
            }
            QListWidget::item:hover {
                background-color: #dfe6e9;
            }
            QPushButton {
                background-color: #0984e3;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0770c2;
            }
            QPushButton:disabled {
                background-color: #b2bec3;
                color: #636e72;
            }
            QTextEdit {
                background-color: #2d3436;
                color: #dfe6e9;
                border-radius: 6px;
                border: 1px solid #636e72;
                padding: 10px;
            }
            QLineEdit {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #0984e3;
            }
            QComboBox {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 6px;
                font-size: 13px;
            }
        """)
        # Estilo especial para el boton de peligro
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #d63031;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #b71515; }
            QPushButton:disabled { background-color: #b2bec3; color: #636e72; }
        """)

    def _load_settings(self):
        """Carga el settings.json y actualiza la interfaz."""
        self.list_models.clear()
        self.models_list = []
        self.settings_data = {}

        # Actualizar info del archivo
        size_str, mtime_str = _file_info(SETTINGS_PATH)
        self.lbl_file_info.setText(
            f"Archivo: {SETTINGS_PATH}  |  Tamano: {size_str}  |  "
            f"Modificado: {mtime_str}"
        )

        if not SETTINGS_PATH.exists():
            QMessageBox.critical(
                self,
                "Error",
                "No se encontro el archivo de configuracion:\n"
                f"{SETTINGS_PATH}\n\n"
                "Asegurate de haber configurado Qwen Code al menos una vez.",
            )
            self.statusBar().showMessage("Archivo no encontrado.")
            return

        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                self.settings_data = json.load(f)
        except json.JSONDecodeError as e:
            QMessageBox.critical(
                self,
                "Error de JSON",
                "El archivo settings.json esta corrupto:\n"
                f"{e}\n\n"
                "Debes arreglarlo manualmente antes de usar esta herramienta.",
            )
            self.statusBar().showMessage("JSON corrupto.")
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo leer el archivo:\n{e}"
            )
            return

        # Extraer modelos de la estructura real
        providers = self.settings_data.get("modelProviders", {})
        for provider_name, models in providers.items():
            if isinstance(models, list):
                for model in models:
                    model_id = model.get("id", "sin-id")
                    model_name = model.get("name", model_id)
                    base_url = model.get("baseUrl", "N/A")
                    env_key = model.get("envKey", "")

                    self.models_list.append({
                        "provider": provider_name,
                        "id": model_id,
                        "name": model_name,
                        "baseUrl": base_url,
                        "envKey": env_key,
                        "raw": model,
                    })

        # Mostrar en lista con indicador de provider
        for idx, m in enumerate(self.models_list):
            env_info = ""
            if m["envKey"]:
                env_info = " | Key: " + m["envKey"][-12:]

            # Indicador de modelo activo
            current = self.settings_data.get("model", {})
            is_active = (
                current.get("name") == m["name"]
                and current.get("baseUrl") == m["baseUrl"]
            )
            prefix = "[ACTIVO] " if is_active else "         "

            item_text = (
                f"{prefix}{m['name']}\n"
                f"    Provider: {m['provider']}  |  URL: {m['baseUrl']}{env_info}"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.list_models.addItem(item)

        # Actualizar estado actual
        current = self.settings_data.get("model", {})
        current_name = current.get("name", "Ninguno")
        current_baseurl = current.get("baseUrl", "N/A")
        auth_type = (
            self.settings_data.get("security", {})
            .get("auth", {})
            .get("selectedType", "N/A")
        )

        self.lbl_current_model.setText(f"Modelo activo: {current_name}")
        self.lbl_current_baseurl.setText(f"Base URL activa: {current_baseurl}")
        self.lbl_auth_type.setText(f"Auth type: {auth_type}")

        # Preview JSON
        self.text_preview.setText(
            json.dumps(self.settings_data, indent=2, ensure_ascii=False)
        )

        count = len(self.models_list)
        provider_count = len(providers)
        self.statusBar().showMessage(
            f"Cargados {count} modelo(s) en {provider_count} provider(s). "
            f"Selecciona uno para ver detalles."
        )

    def _on_selection_changed(self):
        selected = self.list_models.selectedItems()
        if not selected:
            self.btn_delete.setEnabled(False)
            self.btn_edit.setEnabled(False)
            self.btn_set_active.setEnabled(False)
            self.lbl_model_id.setText("Selecciona un modelo de la lista")
            self.lbl_model_name.setText("")
            self.lbl_base_url.setText("")
            self.lbl_env_key.setText("")
            self.lbl_api_key.setText("")
            self.lbl_shared_info.setText("")
            return

        idx = selected[0].data(Qt.ItemDataRole.UserRole)
        model = self.models_list[idx]

        self.lbl_model_id.setText(f"<b>ID:</b> {model['id']}")
        self.lbl_model_name.setText(f"<b>Name:</b> {model['name']}")
        self.lbl_base_url.setText(f"<b>Base URL:</b> {model['baseUrl']}")
        self.lbl_env_key.setText(f"<b>envKey:</b> {model['envKey']}")

        # API Key enmascarada
        env_vars = self.settings_data.get("env", {})
        key_val = env_vars.get(model["envKey"], "")
        self.lbl_api_key.setText(f"<b>API Key:</b> {_mask_key(key_val)}")

        # Info de comparticion
        env_key = model["envKey"]
        shared_count = sum(
            1 for m in self.models_list if m["envKey"] == env_key
        )
        if shared_count > 1:
            self.lbl_shared_info.setText(
                f"[COMPARTIDA] Esta API Key la usan {shared_count} modelos. "
                "Se conservara al borrar."
            )
        elif env_key:
            self.lbl_shared_info.setText(
                "[UNICA] Solo este modelo usa esta API Key."
            )
        else:
            self.lbl_shared_info.setText("")

        self.btn_delete.setEnabled(True)
        self.btn_edit.setEnabled(True)
        self.btn_set_active.setEnabled(True)

    def _validate_json(self, data):
        """Valida que los datos sean un JSON serializable y re-leible."""
        try:
            serialized = json.dumps(data, indent=2, ensure_ascii=False)
            json.loads(serialized)
            return True, "JSON valido."
        except (TypeError, ValueError) as e:
            return False, f"Error de validacion: {e}"

    def _save_settings(self):
        """Guarda el JSON de forma segura con backup y validacion."""
        # Validar antes de guardar
        valid, msg = self._validate_json(self.settings_data)
        if not valid:
            QMessageBox.critical(
                self,
                "Error de validacion",
                f"No se puede guardar el JSON:\n{msg}",
            )
            return False

        # Backup
        backup_path = SETTINGS_PATH.with_suffix(".json.backup")
        try:
            if SETTINGS_PATH.exists():
                shutil.copy2(SETTINGS_PATH, backup_path)
        except Exception:
            pass

        # Guardar preservando formato
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings_data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            return True
        except Exception as e:
            QMessageBox.critical(
                self, "Error al guardar", f"No se pudo guardar el archivo:\n{e}"
            )
            return False

    def _delete_selected(self):
        selected = self.list_models.selectedItems()
        if not selected:
            return

        idx = selected[0].data(Qt.ItemDataRole.UserRole)
        model = self.models_list[idx]
        model_name = model["name"]
        model_id = model["id"]
        provider = model["provider"]
        env_key_to_check = model["envKey"]

        # Contar modelos que usan la misma envKey
        shared_count = sum(
            1 for m in self.models_list if m["envKey"] == env_key_to_check
        )
        will_delete_key = shared_count <= 1

        key_msg = ""
        if will_delete_key and env_key_to_check:
            key_msg = "\n\nTambien se eliminara su API Key del archivo."
        elif env_key_to_check:
            key_msg = (
                "\n\nLa API Key se CONSERVA porque otros modelos la usan."
            )

        reply = QMessageBox.question(
            self,
            "Confirmar borrado",
            f"Vas a borrar el modelo:\n\n"
            f"  {model_name}\n"
            f"  ID: {model_id}\n"
            f"  Provider: {provider}\n"
            f"  envKey: {env_key_to_check}"
            f"{key_msg}\n\n"
            f"Estas seguro?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Borrado seguro
        try:
            providers = self.settings_data.get("modelProviders", {})
            if provider in providers and isinstance(providers[provider], list):
                providers[provider] = [
                    m
                    for m in providers[provider]
                    if not (
                        m.get("id") == model_id
                        and m.get("baseUrl") == model["baseUrl"]
                    )
                ]
                if not providers[provider]:
                    del providers[provider]

            # Borrar API key solo si nadie mas la usa
            if will_delete_key and env_key_to_check:
                env_vars = self.settings_data.get("env", {})
                if env_key_to_check in env_vars:
                    del env_vars[env_key_to_check]

            # Si el modelo borrado era el activo, poner otro
            current_model = self.settings_data.get("model", {})
            if current_model.get("name") == model_name:
                self._auto_select_new_active()

            if not self._save_settings():
                return

            deleted_items = ["modelo"]
            if will_delete_key and env_key_to_check:
                deleted_items.append("API Key")

            QMessageBox.information(
                self,
                "Exito",
                "Se ha eliminado correctamente:\n\n"
                f"  - {model_name}\n"
                + (
                    f"  - {env_key_to_check}\n"
                    if will_delete_key and env_key_to_check
                    else ""
                )
                + "\nReinicia Qwen Code para aplicar los cambios.",
            )

            self._load_settings()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error al borrar",
                f"Ocurrio un error:\n{e}\n\n"
                f"El archivo puede estar danado. Revisa manualmente:\n"
                f"{SETTINGS_PATH}",
            )

    def _auto_select_new_active(self):
        """Selecciona automaticamente otro modelo como activo."""
        new_active = None
        providers = self.settings_data.get("modelProviders", {})
        for prov_name, models in providers.items():
            if models:
                first = models[0]
                new_active = {
                    "name": first.get("name", first.get("id", "")),
                    "baseUrl": first.get("baseUrl", ""),
                }
                self.settings_data["security"] = self.settings_data.get(
                    "security", {}
                )
                self.settings_data["security"]["auth"] = {
                    "selectedType": prov_name
                }
                break

        if new_active:
            self.settings_data["model"] = new_active
        else:
            self.settings_data["model"] = {"name": "", "baseUrl": ""}
            self.settings_data["security"] = {
                "auth": {"selectedType": ""}
            }

    def _set_active_model(self):
        """Cambia el modelo activo sin borrar ninguno."""
        selected = self.list_models.selectedItems()
        if not selected:
            return

        idx = selected[0].data(Qt.ItemDataRole.UserRole)
        model = self.models_list[idx]

        # Verificar si ya es activo
        current = self.settings_data.get("model", {})
        if (
            current.get("name") == model["name"]
            and current.get("baseUrl") == model["baseUrl"]
        ):
            QMessageBox.information(
                self, "Info", "Este modelo ya es el activo."
            )
            return

        reply = QMessageBox.question(
            self,
            "Activar modelo",
            f"Desea activar el modelo:\n\n"
            f"  {model['name']}\n"
            f"  Base URL: {model['baseUrl']}\n"
            f"  Provider: {model['provider']}\n\n"
            f"Esto cambiara el modelo activo en Qwen Code.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.settings_data["model"] = {
            "name": model["name"],
            "baseUrl": model["baseUrl"],
        }
        self.settings_data["security"] = self.settings_data.get("security", {})
        self.settings_data["security"]["auth"] = {
            "selectedType": model["provider"]
        }

        if self._save_settings():
            QMessageBox.information(
                self,
                "Exito",
                f"Modelo activo cambiado a:\n\n  {model['name']}\n\n"
                "Reinicia Qwen Code para aplicar los cambios.",
            )
            self._load_settings()

    def _add_model(self):
        """Anade un nuevo modelo al settings.json."""
        providers = self.settings_data.get("modelProviders", {})
        env_vars = self.settings_data.get("env", {})

        dlg = AddEditModelDialog(self, model=None, providers=providers, env_vars=env_vars)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()
        provider = data["provider"]

        new_model = {
            "id": data["id"],
            "name": data["name"],
            "baseUrl": data["baseUrl"],
            "envKey": data["envKey"],
        }

        # Anadir al provider
        if provider not in self.settings_data.get("modelProviders", {}):
            self.settings_data.setdefault("modelProviders", {})[provider] = []

        self.settings_data["modelProviders"][provider].append(new_model)

        # Anadir envKey si es nueva
        if data["envKey"] and data["envKey"] not in self.settings_data.get(
            "env", {}
        ):
            self.settings_data.setdefault("env", {})[data["envKey"]] = ""

        if self._save_settings():
            QMessageBox.information(
                self,
                "Exito",
                f"Modelo anadido:\n\n  {data['name']}\n\n"
                "Recuerda asignar la API Key en el archivo settings.json "
                "si usaste una envKey nueva.",
            )
            self._load_settings()

    def _edit_model(self):
        """Edita un modelo existente."""
        selected = self.list_models.selectedItems()
        if not selected:
            return

        idx = selected[0].data(Qt.ItemDataRole.UserRole)
        model = self.models_list[idx]

        providers = self.settings_data.get("modelProviders", {})
        env_vars = self.settings_data.get("env", {})

        dlg = AddEditModelDialog(
            self,
            model={
                "provider": model["provider"],
                "id": model["id"],
                "name": model["name"],
                "baseUrl": model["baseUrl"],
                "envKey": model["envKey"],
            },
            providers=providers,
            env_vars=env_vars,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        data = dlg.get_data()

        # Buscar y actualizar el modelo en la estructura
        prov_list = self.settings_data.get("modelProviders", {}).get(
            model["provider"], []
        )
        for m in prov_list:
            if m.get("id") == model["id"] and m.get("baseUrl") == model["baseUrl"]:
                m["name"] = data["name"]
                m["baseUrl"] = data["baseUrl"]
                m["envKey"] = data["envKey"]
                break

        # Si el modelo editado era el activo, actualizar tambien
        current = self.settings_data.get("model", {})
        if current.get("name") == model["name"]:
            self.settings_data["model"]["name"] = data["name"]
            self.settings_data["model"]["baseUrl"] = data["baseUrl"]

        if self._save_settings():
            QMessageBox.information(
                self,
                "Exito",
                f"Modelo actualizado:\n\n  {data['name']}",
            )
            self._load_settings()

    def _create_backup(self):
        """Crea un backup con timestamp en ~/.qwen/backups/."""
        backup_dir = Path.home() / ".qwen" / "backups"
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo crear la carpeta de backups:\n{e}"
            )
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"settings_backup_{timestamp}.json"

        try:
            if SETTINGS_PATH.exists():
                shutil.copy2(SETTINGS_PATH, backup_path)
                QMessageBox.information(
                    self,
                    "Backup creado",
                    f"Backup guardado en:\n\n{backup_path}",
                )
            else:
                QMessageBox.warning(
                    self, "Aviso", "No existe el archivo settings.json para respaldar."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo crear el backup:\n{e}"
            )

    def _restore_backup(self):
        """Restaura el settings.json desde un backup seleccionado."""
        backup_dir = Path.home() / ".qwen" / "backups"
        start_dir = str(backup_dir) if backup_dir.exists() else str(Path.home())

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar backup para restaurar",
            start_dir,
            "Archivos JSON (*.json);;Todos los archivos (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                restored_data = json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo leer el archivo de backup:\n{e}",
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirmar restauracion",
            f"Se reemplazara el settings.json actual con:\n\n"
            f"  {file_path}\n\n"
            f"Se creara un backup del actual antes de restaurar.\n\n"
            f"Estas seguro?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Backup del actual antes de restaurar
        if SETTINGS_PATH.exists():
            pre_restore = SETTINGS_PATH.with_suffix(".json.pre-restore")
            try:
                shutil.copy2(SETTINGS_PATH, pre_restore)
            except Exception:
                pass

        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(restored_data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            QMessageBox.information(
                self,
                "Restaurado",
                "Backup restaurado correctamente.\n\n"
                "Reinicia Qwen Code para aplicar los cambios.",
            )
            self._load_settings()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo restaurar el backup:\n{e}"
            )

    def _open_folder(self):
        """Abre la carpeta .qwen en el explorador de archivos."""
        qwen_dir = Path.home() / ".qwen"
        if not qwen_dir.exists():
            QMessageBox.warning(
                self,
                "Aviso",
                f"La carpeta no existe:\n{qwen_dir}",
            )
            return

        try:
            import subprocess
            subprocess.Popen(
                ["xdg-open", str(qwen_dir)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo abrir la carpeta:\n{e}"
            )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f5f6fa"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#2f3640"))
    app.setPalette(palette)

    window = QwenModelManager()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
