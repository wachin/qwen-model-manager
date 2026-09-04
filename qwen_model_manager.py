#!/usr/bin/env python3
"""
Qwen Model Manager - GUI for managing Qwen Code models
Adapted to the real settings.json structure of Qwen Code v4

Usage:
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
    from PyQt6.QtCore import Qt, QTimer, QTranslator, QLocale
    from PyQt6.QtGui import QFont, QColor, QPalette, QShortcut, QKeySequence
except ImportError:
    print("ERROR: PyQt6 is not installed.")
    print("Install it with: pip install PyQt6")
    sys.exit(1)


SETTINGS_PATH = Path.home() / ".qwen" / "settings.json"
TRANSLATIONS_DIR = Path(__file__).parent / "translations"


def _mask_key(value):
    """Masks an API key for safe display."""
    if not value:
        return QApplication.translate("App", "(not found)")
    if len(value) > 16:
        return value[:8] + "..." + value[-6:]
    if len(value) > 8:
        return value[:4] + "..." + value[-4:]
    return value[:2] + "..."


def _file_info(path):
    """Returns (size_str, mtime_str) for a file."""
    if not path.exists():
        return (QApplication.translate("App", "(does not exist)"),
                QApplication.translate("App", "(does not exist)"))
    st = path.stat()
    size = st.st_size
    if size < 1024:
        size_str = f"{size} B"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):1f} MB"
    mtime = datetime.fromtimestamp(st.st_mtime)
    mtime_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
    return (size_str, mtime_str)


class AddEditModelDialog(QDialog):
    """Dialog for adding or editing a model."""

    def __init__(self, parent=None, model=None, providers=None, env_vars=None,
                 preset=None):
        super().__init__(parent)
        self.setWindowTitle(
            self.tr("Edit Model") if model else self.tr("Add New Model")
        )
        self.setMinimumWidth(550)
        self.setMinimumHeight(360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.combo_provider = QComboBox()
        if providers:
            self.combo_provider.addItems(sorted(providers.keys()))
        else:
            self.combo_provider.addItems(["openai"])
        form.addRow(self.tr("Provider:"), self.combo_provider)

        self.input_id = QLineEdit()
        self.input_id.setPlaceholderText(self.tr("e.g. z-ai/glm-5.3-free"))
        form.addRow("ID:", self.input_id)

        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText(self.tr("Visible model name"))
        form.addRow(self.tr("Name:"), self.input_name)

        self.input_baseurl = QLineEdit()
        self.input_baseurl.setPlaceholderText("https://api.example.com/v1")
        form.addRow(self.tr("Base URL:"), self.input_baseurl)

        self.combo_envkey = QComboBox()
        self.combo_envkey.setEditable(True)
        if env_vars:
            self.combo_envkey.addItems(sorted(env_vars.keys()))
        self.combo_envkey.setPlaceholderText(
            self.tr("Select or type a new envKey")
        )
        form.addRow("envKey:", self.combo_envkey)

        self.input_apikey = QLineEdit()
        self.input_apikey.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_apikey.setPlaceholderText(
            self.tr("Paste the real API key value (optional)")
        )
        form.addRow(self.tr("API Key Value:"), self.input_apikey)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Pre-fill if editing
        if model:
            prov_idx = self.combo_provider.findText(model.get("provider", "openai"))
            if prov_idx >= 0:
                self.combo_provider.setCurrentIndex(prov_idx)
            self.input_id.setText(model.get("id", ""))
            self.input_id.setReadOnly(True)
            self.input_name.setText(model.get("name", ""))
            self.input_baseurl.setText(model.get("baseUrl", ""))
            env_idx = self.combo_envkey.findText(model.get("envKey", ""))
            if env_idx >= 0:
                self.combo_envkey.setCurrentIndex(env_idx)
            else:
                self.combo_envkey.setEditText(model.get("envKey", ""))
            if env_vars:
                existing = env_vars.get(model.get("envKey", ""), "")
                if existing:
                    self.input_apikey.setPlaceholderText(
                        self.tr(
                            "Key already set ({}); leave empty to keep it"
                        ).format(_mask_key(existing))
                    )

        # Apply preset for quick-add of well-known providers
        if preset == "openrouter":
            prov_idx = self.combo_provider.findText("openai")
            if prov_idx < 0:
                self.combo_provider.addItem("openai")
                prov_idx = self.combo_provider.count() - 1
            self.combo_provider.setCurrentIndex(prov_idx)
            self.input_baseurl.setText("https://openrouter.ai/api/v1")
            self.combo_envkey.setEditText("OPENROUTER_API_KEY")

    def _validate_and_accept(self):
        if not self.input_id.text().strip():
            QMessageBox.warning(
                self, self.tr("Validation"), self.tr("The ID field is required.")
            )
            return
        if not self.input_name.text().strip():
            QMessageBox.warning(
                self, self.tr("Validation"), self.tr("The Name field is required.")
            )
            return
        if not self.input_baseurl.text().strip():
            QMessageBox.warning(
                self, self.tr("Validation"),
                self.tr("The Base URL field is required.")
            )
            return
        self.accept()

    def get_data(self):
        return {
            "provider": self.combo_provider.currentText().strip(),
            "id": self.input_id.text().strip(),
            "name": self.input_name.text().strip(),
            "baseUrl": self.input_baseurl.text().strip(),
            "envKey": self.combo_envkey.currentText().strip(),
            "apiKey": self.input_apikey.text().strip(),
        }


class QwenModelManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr("Qwen Code - Model Manager"))
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

        # === LEFT PANEL ===
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel(self.tr("Models Configured in Qwen Code"))
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        left_layout.addWidget(title)

        self.lbl_file_info = QLabel(f"File: {SETTINGS_PATH}")
        self.lbl_file_info.setStyleSheet("color: #888; font-size: 11px;")
        left_layout.addWidget(self.lbl_file_info)
        left_layout.addSpacing(5)

        help_label = QLabel(
            self.tr(
                "Select a model from the list to view details.\n"
                "Change the active model, edit or delete models.\n"
                "If multiple models share the same API Key, it is preserved on deletion."
            )
        )
        help_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        help_label.setWordWrap(True)
        left_layout.addWidget(help_label)
        left_layout.addSpacing(5)

        # Model list
        self.list_models = QListWidget()
        self.list_models.setSpacing(5)
        self.list_models.itemSelectionChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.list_models)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.btn_add = QPushButton(self.tr("+ Add Model"))
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

        self.btn_add_openrouter = QPushButton(self.tr("+ OpenRouter"))
        self.btn_add_openrouter.setMinimumHeight(42)
        self.btn_add_openrouter.setToolTip(
            self.tr(
                "Quick-add an OpenRouter model\n"
                "(baseUrl: https://openrouter.ai/api/v1, "
                "envKey: OPENROUTER_API_KEY)"
            )
        )
        self.btn_add_openrouter.clicked.connect(
            lambda: self._add_model(preset="openrouter")
        )
        self.btn_add_openrouter.setStyleSheet("""
            QPushButton {
                background-color: #2d3436;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1e272e; }
        """)
        btn_layout.addWidget(self.btn_add_openrouter)

        self.btn_edit = QPushButton(self.tr("Edit"))
        self.btn_edit.setMinimumHeight(42)
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self._edit_model)
        btn_layout.addWidget(self.btn_edit)

        left_layout.addLayout(btn_layout)

        btn_layout2 = QHBoxLayout()

        self.btn_set_active = QPushButton(self.tr("Set Active"))
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

        self.btn_delete = QPushButton(self.tr("Delete"))
        self.btn_delete.setMinimumHeight(42)
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self._delete_selected)
        btn_layout2.addWidget(self.btn_delete)

        left_layout.addLayout(btn_layout2)

        btn_layout3 = QHBoxLayout()

        self.btn_reload = QPushButton(self.tr("Reload (Ctrl+R)"))
        self.btn_reload.setMinimumHeight(42)
        self.btn_reload.clicked.connect(self._load_settings)
        btn_layout3.addWidget(self.btn_reload)

        self.btn_backup = QPushButton(self.tr("Create Backup"))
        self.btn_backup.setMinimumHeight(42)
        self.btn_backup.clicked.connect(self._create_backup)
        btn_layout3.addWidget(self.btn_backup)

        left_layout.addLayout(btn_layout3)

        btn_layout4 = QHBoxLayout()

        self.btn_restore = QPushButton(self.tr("Restore Backup"))
        self.btn_restore.setMinimumHeight(42)
        self.btn_restore.clicked.connect(self._restore_backup)
        btn_layout4.addWidget(self.btn_restore)

        self.btn_open_folder = QPushButton(self.tr("Open .qwen Folder"))
        self.btn_open_folder.setMinimumHeight(42)
        self.btn_open_folder.clicked.connect(self._open_folder)
        btn_layout4.addWidget(self.btn_open_folder)

        left_layout.addLayout(btn_layout4)

        # === RIGHT PANEL ===
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Selected model details
        details_group = QGroupBox(self.tr("Selected Model Details"))
        details_layout = QVBoxLayout(details_group)

        self.lbl_model_id = QLabel(self.tr("Select a model from the list"))
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

        # Current status
        status_group = QGroupBox(self.tr("Qwen Code Current Status"))
        status_layout = QVBoxLayout(status_group)

        self.lbl_current_model = QLabel(self.tr("Active model: -"))
        self.lbl_current_model.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #27ae60;"
        )
        status_layout.addWidget(self.lbl_current_model)

        self.lbl_current_baseurl = QLabel(self.tr("Active base URL: -"))
        self.lbl_current_baseurl.setStyleSheet("font-size: 11px; color: #555;")
        status_layout.addWidget(self.lbl_current_baseurl)

        self.lbl_auth_type = QLabel(self.tr("Auth type: -"))
        status_layout.addWidget(self.lbl_auth_type)

        right_layout.addWidget(status_group)

        # JSON preview
        preview_group = QGroupBox(self.tr("JSON Preview (read-only)"))
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

        # Status bar
        self.statusBar().showMessage(
            self.tr("Ready. Select a model to view details.")
        )

    def _setup_shortcuts(self):
        """Configure keyboard shortcuts."""
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
                color: #2f3640;
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
        # Special style for danger button
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
        """Load settings.json and update the interface."""
        self.list_models.clear()
        self.models_list = []
        self.settings_data = {}

        # Update file info
        size_str, mtime_str = _file_info(SETTINGS_PATH)
        self.lbl_file_info.setText(
            f"File: {SETTINGS_PATH}  |  Size: {size_str}  |  "
            f"Modified: {mtime_str}"
        )

        if not SETTINGS_PATH.exists():
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr(
                    "Configuration file not found:\n"
                    "{path}\n\n"
                    "Make sure you have run Qwen Code at least once."
                ).format(path=SETTINGS_PATH),
            )
            self.statusBar().showMessage(self.tr("File not found."))
            return

        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                self.settings_data = json.load(f)
        except json.JSONDecodeError as e:
            QMessageBox.critical(
                self,
                self.tr("JSON Error"),
                self.tr(
                    "The settings.json file is corrupted:\n"
                    "{error}\n\n"
                    "You must fix it manually before using this tool."
                ).format(error=e),
            )
            self.statusBar().showMessage(self.tr("Corrupt JSON."))
            return
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error"),
                self.tr("Could not read file:\n{error}").format(error=e)
            )
            return

        # Extract models from the real structure
        providers = self.settings_data.get("modelProviders", {})
        for provider_name, models in providers.items():
            if isinstance(models, list):
                for model in models:
                    model_id = model.get("id", "no-id")
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

        # Display in list with provider indicator
        for idx, m in enumerate(self.models_list):
            env_info = ""
            if m["envKey"]:
                env_info = " | Key: " + m["envKey"][-12:]

            # Active model indicator
            current = self.settings_data.get("model", {})
            is_active = (
                current.get("name") == m["name"]
                and current.get("baseUrl") == m["baseUrl"]
            )
            prefix = "[ACTIVE] " if is_active else "          "

            item_text = (
                f"{prefix}{m['name']}\n"
                f"    Provider: {m['provider']}  |  URL: {m['baseUrl']}{env_info}"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            self.list_models.addItem(item)

        # Update current status
        current = self.settings_data.get("model", {})
        current_name = current.get("name", "None")
        current_baseurl = current.get("baseUrl", "N/A")
        auth_type = (
            self.settings_data.get("security", {})
            .get("auth", {})
            .get("selectedType", "N/A")
        )

        self.lbl_current_model.setText(
            self.tr("Active model: {name}").format(name=current_name)
        )
        self.lbl_current_baseurl.setText(
            self.tr("Active base URL: {url}").format(url=current_baseurl)
        )
        self.lbl_auth_type.setText(
            self.tr("Auth type: {type}").format(type=auth_type)
        )

        # JSON preview
        self.text_preview.setText(
            json.dumps(self.settings_data, indent=2, ensure_ascii=False)
        )

        count = len(self.models_list)
        provider_count = len(providers)
        self.statusBar().showMessage(
            self.tr(
                "Loaded {count} model(s) in {providers} provider(s). "
                "Select one to view details."
            ).format(count=count, providers=provider_count)
        )

    def _on_selection_changed(self):
        selected = self.list_models.selectedItems()
        if not selected:
            self.btn_delete.setEnabled(False)
            self.btn_edit.setEnabled(False)
            self.btn_set_active.setEnabled(False)
            self.lbl_model_id.setText(self.tr("Select a model from the list"))
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

        # Masked API key
        env_vars = self.settings_data.get("env", {})
        key_val = env_vars.get(model["envKey"], "")
        self.lbl_api_key.setText(f"<b>API Key:</b> {_mask_key(key_val)}")

        # Sharing info
        env_key = model["envKey"]
        shared_count = sum(
            1 for m in self.models_list if m["envKey"] == env_key
        )
        if shared_count > 1:
            self.lbl_shared_info.setText(
                self.tr(
                    "[SHARED] This API Key is used by {count} models. "
                    "It will be preserved on deletion."
                ).format(count=shared_count)
            )
        elif env_key:
            self.lbl_shared_info.setText(
                self.tr("[UNIQUE] Only this model uses this API Key.")
            )
        else:
            self.lbl_shared_info.setText("")

        self.btn_delete.setEnabled(True)
        self.btn_edit.setEnabled(True)
        self.btn_set_active.setEnabled(True)

    def _validate_json(self, data):
        """Validate that data is serializable and re-readable JSON."""
        try:
            serialized = json.dumps(data, indent=2, ensure_ascii=False)
            json.loads(serialized)
            return True, self.tr("Valid JSON.")
        except (TypeError, ValueError) as e:
            return False, self.tr("Validation error: {error}").format(error=e)

    def _save_settings(self):
        """Save JSON safely with backup and validation."""
        # Validate before saving
        valid, msg = self._validate_json(self.settings_data)
        if not valid:
            QMessageBox.critical(
                self,
                self.tr("Validation Error"),
                self.tr("Cannot save JSON:\n{msg}").format(msg=msg),
            )
            return False

        # Backup
        backup_path = SETTINGS_PATH.with_suffix(".json.backup")
        try:
            if SETTINGS_PATH.exists():
                shutil.copy2(SETTINGS_PATH, backup_path)
        except Exception:
            pass

        # Save preserving format
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(self.settings_data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            return True
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Save Error"),
                self.tr("Could not save file:\n{error}").format(error=e)
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

        # Count models using the same envKey
        shared_count = sum(
            1 for m in self.models_list if m["envKey"] == env_key_to_check
        )
        will_delete_key = shared_count <= 1

        key_msg = ""
        if will_delete_key and env_key_to_check:
            key_msg = (
                "\n\nIts API Key will also be removed from the file."
            )
        elif env_key_to_check:
            key_msg = (
                "\n\nThe API Key is PRESERVED because other models use it."
            )

        reply = QMessageBox.question(
            self,
            self.tr("Confirm Deletion"),
            self.tr(
                "You are about to delete the model:\n\n"
                "  {name}\n"
                "  ID: {id}\n"
                "  Provider: {provider}\n"
                "  envKey: {envkey}"
                "{keymsg}\n\n"
                "Are you sure?"
            ).format(
                name=model_name, id=model_id, provider=provider,
                envkey=env_key_to_check, keymsg=key_msg,
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Safe deletion
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

            # Delete API key only if no other model uses it
            if will_delete_key and env_key_to_check:
                env_vars = self.settings_data.get("env", {})
                if env_key_to_check in env_vars:
                    del env_vars[env_key_to_check]

            # If the deleted model was active, select another one
            current_model = self.settings_data.get("model", {})
            if current_model.get("name") == model_name:
                self._auto_select_new_active()

            if not self._save_settings():
                return

            QMessageBox.information(
                self,
                self.tr("Success"),
                self.tr(
                    "Successfully deleted:\n\n"
                    "  - {name}\n"
                    "{keyline}\n"
                    "Restart Qwen Code to apply changes."
                ).format(
                    name=model_name,
                    keyline=(
                        f"  - {env_key_to_check}\n"
                        if will_delete_key and env_key_to_check
                        else ""
                    ),
                ),
            )

            self._load_settings()

        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Delete Error"),
                self.tr(
                    "An error occurred:\n{error}\n\n"
                    "The file may be damaged. Check it manually:\n"
                    "{path}"
                ).format(error=e, path=SETTINGS_PATH),
            )

    def _auto_select_new_active(self):
        """Automatically select another model as active."""
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
        """Change the active model without deleting any."""
        selected = self.list_models.selectedItems()
        if not selected:
            return

        idx = selected[0].data(Qt.ItemDataRole.UserRole)
        model = self.models_list[idx]

        # Check if already active
        current = self.settings_data.get("model", {})
        if (
            current.get("name") == model["name"]
            and current.get("baseUrl") == model["baseUrl"]
        ):
            QMessageBox.information(
                self, self.tr("Info"),
                self.tr("This model is already active.")
            )
            return

        reply = QMessageBox.question(
            self,
            self.tr("Activate Model"),
            self.tr(
                "Do you want to activate the model:\n\n"
                "  {name}\n"
                "  Base URL: {url}\n"
                "  Provider: {provider}\n\n"
                "This will change the active model in Qwen Code."
            ).format(
                name=model["name"], url=model["baseUrl"],
                provider=model["provider"],
            ),
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
                self.tr("Success"),
                self.tr(
                    "Active model changed to:\n\n  {name}\n\n"
                    "Restart Qwen Code to apply changes."
                ).format(name=model["name"]),
            )
            self._load_settings()

    def _add_model(self, preset=None):
        """Add a new model to settings.json."""
        providers = self.settings_data.get("modelProviders", {})
        env_vars = self.settings_data.get("env", {})

        dlg = AddEditModelDialog(
            self, model=None, providers=providers, env_vars=env_vars,
            preset=preset,
        )
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

        # Add to provider
        if provider not in self.settings_data.get("modelProviders", {}):
            self.settings_data.setdefault("modelProviders", {})[provider] = []

        self.settings_data["modelProviders"][provider].append(new_model)

        # Only add envKey if non-empty and new; store the pasted key value
        if data["envKey"].strip():
            if data["envKey"] not in self.settings_data.get("env", {}):
                self.settings_data.setdefault("env", {})[data["envKey"]] = ""
            if data["apiKey"]:
                self.settings_data["env"][data["envKey"]] = data["apiKey"]

        if self._save_settings():
            if data["apiKey"]:
                msg = self.tr(
                    "Model added:\n\n  {name}\n\n"
                    "The API key was saved to env[{envkey}]."
                ).format(name=data["name"], envkey=data["envKey"])
            else:
                msg = self.tr(
                    "Model added:\n\n  {name}\n\n"
                    "Remember to assign the API key in settings.json "
                    "if you used a new envKey."
                ).format(name=data["name"])
            QMessageBox.information(self, self.tr("Success"), msg)
            self._load_settings()

    def _edit_model(self):
        """Edit an existing model."""
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
        old_provider = model["provider"]
        new_provider = data["provider"]

        updated_model = {
            "id": data["id"],
            "name": data["name"],
            "baseUrl": data["baseUrl"],
            "envKey": data["envKey"],
        }

        # 1. Remove from old provider
        old_list = self.settings_data["modelProviders"].get(old_provider, [])
        old_list = [
            m for m in old_list
            if not (m.get("id") == model["id"] and m.get("baseUrl") == model["baseUrl"])
        ]
        if old_list:
            self.settings_data["modelProviders"][old_provider] = old_list
        else:
            del self.settings_data["modelProviders"][old_provider]

        # 2. Add to new provider
        if new_provider not in self.settings_data["modelProviders"]:
            self.settings_data["modelProviders"][new_provider] = []
        self.settings_data["modelProviders"][new_provider].append(updated_model)

        # 3. If envKey is new, add to env dict; store the pasted key value
        if data["envKey"] and data["envKey"] not in self.settings_data.get("env", {}):
            self.settings_data.setdefault("env", {})[data["envKey"]] = ""
        if data["envKey"] and data["apiKey"]:
            self.settings_data.setdefault("env", {})[data["envKey"]] = data["apiKey"]

        # 4. If it was the active model, update it
        current = self.settings_data.get("model", {})
        if current.get("name") == model["name"] and current.get("baseUrl") == model["baseUrl"]:
            self.settings_data["model"] = {
                "name": data["name"],
                "baseUrl": data["baseUrl"],
            }
            self.settings_data["security"] = self.settings_data.get("security", {})
            self.settings_data["security"]["auth"] = {"selectedType": new_provider}

        if self._save_settings():
            QMessageBox.information(
                self,
                self.tr("Success"),
                self.tr("Model updated:\n\n  {name}").format(name=data["name"]),
            )
            self._load_settings()

    def _create_backup(self):
        """Create a timestamped backup in ~/.qwen/backups/."""
        backup_dir = Path.home() / ".qwen" / "backups"
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error"),
                self.tr("Could not create backups folder:\n{error}").format(error=e)
            )
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"settings_backup_{timestamp}.json"

        try:
            if SETTINGS_PATH.exists():
                shutil.copy2(SETTINGS_PATH, backup_path)
                QMessageBox.information(
                    self,
                    self.tr("Backup Created"),
                    self.tr("Backup saved to:\n\n{path}").format(path=backup_path),
                )
            else:
                QMessageBox.warning(
                    self, self.tr("Warning"),
                    self.tr("settings.json does not exist to back up.")
                )
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error"),
                self.tr("Could not create backup:\n{error}").format(error=e)
            )

    def _restore_backup(self):
        """Restore settings.json from a selected backup."""
        backup_dir = Path.home() / ".qwen" / "backups"
        start_dir = str(backup_dir) if backup_dir.exists() else str(Path.home())

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select backup to restore"),
            start_dir,
            self.tr("JSON files (*.json);;All files (*)"),
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                restored_data = json.load(f)
        except (json.JSONDecodeError, Exception) as e:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Could not read backup file:\n{error}").format(error=e),
            )
            return

        reply = QMessageBox.question(
            self,
            self.tr("Confirm Restore"),
            self.tr(
                "The current settings.json will be replaced with:\n\n"
                "  {path}\n\n"
                "A backup of the current file will be created before restoring.\n\n"
                "Are you sure?"
            ).format(path=file_path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # Backup current file before restoring
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
                self.tr("Restored"),
                self.tr(
                    "Backup restored successfully.\n\n"
                    "Restart Qwen Code to apply changes."
                ),
            )
            self._load_settings()
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Error"),
                self.tr("Could not restore backup:\n{error}").format(error=e)
            )

    def _open_folder(self):
        """Open the .qwen folder in the file explorer."""
        qwen_dir = Path.home() / ".qwen"
        if not qwen_dir.exists():
            QMessageBox.warning(
                self,
                self.tr("Warning"),
                self.tr("Folder does not exist:\n{path}").format(path=qwen_dir),
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
                self, self.tr("Error"),
                self.tr("Could not open folder:\n{error}").format(error=e)
            )


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # --- Load translations based on system locale ---
    translator = QTranslator()
    locale = QLocale.system().name()  # e.g. "es_ES", "en_US"
    ts_file = TRANSLATIONS_DIR / f"{locale}.qm"
    if ts_file.exists():
        translator.load(str(ts_file))
        app.installTranslator(translator)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f5f6fa"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#2f3640"))
    app.setPalette(palette)

    window = QwenModelManager()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
