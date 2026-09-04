# Tutorial: Usar la API de OpenRouter en OpenCode

Guía paso a paso para conectar **OpenRouter** (pasarela unificada de modelos de IA) con **OpenCode** (agente de codificacion de IA de codigo abierto).

Con OpenRouter obtienes acceso a cientos de modelos (Anthropic, OpenAI, Google, Meta, DeepSeek, Qwen, etc.) con **una sola API key**, sin necesidad de crear cuentas en cada proveedor. OpenCode lo soporta como proveedor integrado.

---

## 1. Que necesitas

- **OpenCode** instalado (terminal, escritorio o extension de IDE).
- **Una API key de OpenRouter** (empieza con `sk-or-v1-...`).
- Opcionalmente, un saldo en tu cuenta de OpenRouter para los modelos de pago (los modelos `:free` no requieren saldo).

---

## 2. Obtener tu API key de OpenRouter

1. Entra en <https://openrouter.ai> y crea una cuenta o inicia sesion.
2. Ve a la pagina de API Keys: <https://openrouter.ai/settings/keys>.
3. Haz clic en **Create API Key**.
4. Copia la clave generada (empieza con `sk-or-v1-...`).

> **Importante:** guarda la clave en un lugar seguro. Si la pierdes, tendras que crear una nueva.

---

## 3. Instalar OpenCode

Elige uno de estos metodos:

```bash
# Opcion 1: script de instalacion (recomendado)
curl -fsSL https://opencode.ai/install | bash

# Opcion 2: npm
npm install -g opencode-ai

# Opcion 3: Homebrew (macOS)
brew install anomalyco/tap/opencode
```

En Windows tambien hay instaladores nativos en la pagina de descargas de OpenCode (<https://opencode.ai/docs/>).

---

## 4. Conectar OpenRouter con el comando `/connect`

1. Abre una terminal en la carpeta de tu proyecto:

```bash
cd /ruta/a/tu/proyecto
opencode
```

2. Dentro de OpenCode, ejecuta el comando:

```
/connect
```

3. Busca **OpenRouter** en la lista de proveedores y seleccionalo.
4. Cuando te lo pida, pega tu API key de OpenRouter (`sk-or-v1-...`).
5. La clave queda guardada en `~/.local/share/opencode/auth.json` (la comparten la terminal y la app de escritorio).

---

## 5. Seleccionar un modelo

Ejecuta el comando `/models` dentro de OpenCode:

```
/models
```

Muchos modelos de OpenRouter ya vienen precargados. Selecciona el que quieras usar y listo: tus peticiones se enviaran a traves de OpenRouter.

**Alternativas para elegir modelo:**

- **Modelo por defecto en config:** ver seccion 7.
- **Por invocacion:** usa la bandera `-m`:

```bash
opencode -m openrouter/deepseek/deepseek-chat-v3-0324:free
```

---

## 6. Modelos gratuitos (`:free`)

OpenRouter tiene una categoria de modelos gratuitos que terminan en `:free` (por ejemplo, `minimax/minimax-m3:free` o `deepseek/deepseek-chat-v3-0324:free`). Son utiles para probar y para proyectos personales, aunque suelen tener limites de peticiones por dia (rate limits).

Puedes filtrarlos en la web: <https://openrouter.ai/models?max_price=0> o buscando el sufijo `:free` en el nombre.

---

## 7. Configuracion avanzada: archivo `opencode.json`

Los modelos que no esten precargados se pueden anadir manualmente en el archivo de configuracion.

- **Por proyecto:** `opencode.json` en la raiz del proyecto.
- **Para todos tus proyectos:** `~/.config/opencode/opencode.json`.

Ambos formatos aceptan JSONC (comentarios permitidos).

### Anadir modelos manualmente

Usa el "slug" del modelo de OpenRouter como clave (lo encuentras en <https://openrouter.ai/models>):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "openrouter": {
      "models": {
        "~anthropic/claude-sonnet-latest": {},
        "~google/gemini-flash-latest": {},
        "minimax/minimax-m3:free": {}
      }
    }
  }
}
```

> El `~` al inicio no es un error tipografico: son alias de OpenRouter que siempre resuelven al modelo mas reciente de ese laboratorio (por ejemplo, `~anthropic/claude-sonnet-latest`). Los slugs fijos como `anthropic/claude-sonnet-4.5` funcionan igual.

### Establecer un modelo por defecto

Para que OpenCode no pregunte por el modelo al iniciar, anade una clave `model` de nivel superior. Los IDs se componen como `proveedor/modelo`, asi que un modelo de OpenRouter lleva el prefijo `openrouter/`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "openrouter/~anthropic/claude-sonnet-latest"
}
```

Esto aplica a la terminal, a la app de escritorio y a `opencode run`. Tambien puedes sobrescribirlo por invocacion con `--model` / `-m`.

### Controlar el proveedor que responde (routing)

Puedes indicar que proveedor upstream maneje cada modelo, por ejemplo forzar Anthropic con fallback:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "openrouter": {
      "models": {
        "~anthropic/claude-sonnet-latest": {
          "options": {
            "provider": {
              "order": ["anthropic"],
              "allow_fallbacks": true
            }
          }
        }
      }
    }
  }
}
```

### Ocultar modelos del selector

Puedes ocultar modelos que no quieras ver en `/models`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "openrouter": {
      "blacklist": ["algun/modelo"]
    }
  }
}
```

O, al reves, conservar solo los que listes con `whitelist`.

---

## 8. Donde se guarda tu API key

Las claves que anades con `/connect` se guardan en:

```
~/.local/share/opencode/auth.json
```

Puedes verificarlo con:

```bash
opencode auth list
```

Tambien puedes escribir el archivo directamente (util para automatizar o para otra maquina):

```json
{
  "openrouter": {
    "type": "api",
    "key": "sk-or-v1-tu-clave-aqui"
  }
}
```

> Si usas la variable `XDG_DATA_HOME`, sustituye ese directorio por `~/.local/share`.

---

## 9. Solucion de problemas

| Problema | Solucion |
|---|---|
| **Error de autenticacion** | Revisa la clave con `/connect` y verifica que este guardada con `opencode auth list`. Confirma que la clave es valida en <https://openrouter.ai/settings/keys>. |
| **Modelo no encontrado** | Verifica el slug exacto en <https://openrouter.ai/models>, incluyendo el `~` inicial si lo lleva. En la clave `model` recuerda el prefijo `openrouter/`. |
| **No aparecen modelos tras conectar** | Cierra y abre OpenCode por completo: el catalogo de modelos se carga al iniciar. |
| **Un modelo no sale en el selector** | Anadelo en `provider.openrouter.models` de tu config y reinicia OpenCode. |

---

## 10. Resumen rapido

```bash
# 1. Instalar OpenCode
curl -fsSL https://opencode.ai/install | bash

# 2. Abrir en tu proyecto
cd /ruta/a/tu/proyecto
opencode

# 3. Dentro de OpenCode:
/connect    # busca "OpenRouter" y pega tu key sk-or-v1-...
/models     # elige un modelo

# 4. (Opcional) modelo por defecto en opencode.json
# "model": "openrouter/deepseek/deepseek-chat-v3-0324:free"
```

Con esto ya puedes usar OpenCode con cualquiera de los cientos de modelos de OpenRouter, pagando un solo proveedor y cambiando de modelo cuando quieras con `/models`.