# Qwen Model Manager

A graphical interface built with PyQt6 to manage the AI models configured in [Qwen Code](https://github.com/nicepkg/qwen-code) through its `settings.json` file.

## Features

- **View models** - List all AI models configured across different providers
- **Add models** - Register new models with provider, ID, name, base URL, and environment key
- **OpenRouter quick-add** - One-click preset for OpenRouter models (`https://openrouter.ai/api/v1`, `envKey: OPENROUTER_API_KEY`) where you can paste the real API key and it is stored in the `env` section
- **Edit models** - Modify any model property, including changing its provider
- **Delete models** - Remove models safely, preserving shared API keys
- **Activate models** - Switch the active model used by Qwen Code
- **Backups** - Create timestamped backups and restore from any previous backup
- **Live preview** - See the full JSON configuration in real time
- **Safe by default** - Automatic backup before every save, JSON validation, and confirmation dialogs

## Requirements

- Python 3.9+
- PyQt6

## Installation

```bash
pip install PyQt6
```

## Usage

```bash
python3 qwen_model_manager.py
```

![](image/01-qwen-model-manager.png)

The application reads and writes `~/.qwen/settings.json`. Make sure you have run Qwen Code at least once so the file exists.

## OpenRouter Support

OpenRouter is OpenAI-compatible, so its models are registered under the `openai` provider. Click the **+ OpenRouter** button to open the add dialog pre-filled with:

- `baseUrl`: `https://openrouter.ai/api/v1`
- `envKey`: `OPENROUTER_API_KEY`

Enter the model ID (e.g. `minimax/minimax-m3:free`) and paste your OpenRouter API key (`sk-or-v1-...`) in the **API Key Value** field. The key is saved to the `env` section of `settings.json` automatically. You can also paste a key value when adding or editing any model, or leave it empty to keep the existing key.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+R` | Reload configuration |
| `Delete` | Delete selected model |

## Configuration File Structure

The tool manages the `modelProviders`, `env`, `model`, and `security` sections of the Qwen Code settings file:

```
~/.qwen/settings.json
  +-- modelProviders    # Models grouped by provider
  |     +-- openai      # List of models for each provider
  |     +-- anthropic
  +-- env               # Environment variables (API keys)
  +-- model             # Currently active model
  +-- security          # Auth configuration
  +-- ui                # UI preferences (preserved as-is)
  +-- permissions       # Permissions (preserved as-is)
  +-- mcpServers        # MCP servers (preserved as-is)
```

## Safety Features

- **Pre-save backup** - A `.json.backup` file is created before every write
- **JSON validation** - Data is validated before saving to prevent corruption
- **Shared key detection** - When deleting a model, the app warns if its API key is shared with other models and preserves it accordingly
- **Confirmation dialogs** - Destructive actions require explicit confirmation
- **Auto-select on delete** - If the active model is deleted, another one is automatically selected

## License

MIT
