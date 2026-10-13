# Moímetro

Sistema **local** de apoyo administrativo a consultas médicas, registro de pacientes y adquisición de signos vitales mediante ESP32. Destinado al **Consultorio Popular Tipo III Las Cayenas**.

> [!WARNING]
> **PROTOTIPO TÉCNICO — NO VALIDADO CLÍNICAMENTE.** No usar para diagnóstico, tratamiento ni priorización autónoma. Solo datos ficticios hasta completar protección de datos, pruebas técnicas, revisión clínica y autorización del centro. La API **rechaza SpO₂ enviado por el firmware**; no muestra un 98 % inventado. El motor de triaje permanece deshabilitado.

## Instalación fácil en Windows 7 y posteriores

Moímetro incorpora instaladores **.exe autocontenidos**: el usuario no necesita instalar Python ni usar una terminal. El instalador crea accesos directos y el primer inicio ofrece un asistente para crear el administrador. La base se conserva fuera del directorio de instalación.

Se generan tres variantes: **Windows 7 SP1+ x86**, **Windows 7 SP1+ x64** y **Windows 8.1+ x64 moderna**. El paquete legacy solo es apto para pruebas con datos ficticios debido a la falta de actualizaciones de seguridad de Windows 7 y Python 3.8.

**[Descargar instaladores directamente desde GitHub Releases](https://github.com/Dr3amyBerry/Moimetro/releases/tag/v0.3.1-beta.1)** · [Guía de instalación para Windows](docs/INSTALACION_WINDOWS.md).

**Importante:** la existencia de la receta de empaquetado no garantiza todavía ejecución en Windows 7 real; la prueba física de ambas arquitecturas sigue pendiente.

## Funcionalidades implementadas en código

- Registro y búsqueda de pacientes por tipo/número de documento, sin conexión a Internet.
- Consultas con fecha, motivo, evaluación, diagnóstico, tratamiento e historial.
- Usuarios con roles: recepción, enfermería, médico y administrador.
- Personal: bloqueo, cambios de rol, contraseñas, revocación de sesiones y prevención del autobloqueo del último administrador.
- Historial de cambios de pacientes, antecedentes y consultas con versiones append-only, autor y motivo, visible según permisos.
- Autenticación por contraseña PBKDF2 y tokens de sesión limitados a 8 horas.
- SQLite local, auditoría básica de accesos/operaciones y controles de integridad.
- Sesiones de captura vinculadas explícitamente con la consulta y el dispositivo.
- API para lecturas del ESP32: calidad de señal, rechazo de datos inválidos y aceptación humana de mediciones.
- Registro manual identificado como tal, con nota obligatoria sobre procedencia.
- Interfaz empresarial en grises: directorio paginado, formularios separados, búsqueda por apellido y cédula, filtros y administración de personal.
- SQLite FTS5 indexado y paginación por cursor para no cargar listados completos en memoria.
- Paneles y pestañas con altura controlada y desplazamiento interno; los formularios de medición manual y personal se abren en ventanas, sin desplazar el contenido.
- Lecturas paginadas de 25 en 25, sin cargar todas las mediciones de una consulta.
- Interfaz web responsive, sin recursos externos ni dependencia de Internet.
- Pruebas automatizadas de flujos críticos de API.

**No se han probado aún cargas reales de 50 000–100 000 expedientes ni el rendimiento físico de Windows 7.** [Diseño del directorio](docs/DIRECTORIO_Y_ESCALABILIDAD.md).

**No se ha acreditado aún:** compilación o precisión de sensores reales, seguridad de una red compartida de consultorio, validez clínica, estrategia integral de backups, migraciones, o despliegue autorizado.

## Estructura

| Carpeta | Contenido |
|---|---|
| `app/main.py` | Servidor web local FastAPI. |
| `app/api/auth.py` | Autenticación y administración de cuentas. |
| `app/api/records.py` | Pacientes, expedientes y consultas. |
| `app/api/sensors.py` | Sesiones, telemetría y revisión de mediciones. |
| `app/storage.py` | Esquema SQLite e historial de auditoría. |
| `app/static/` | Interfaz HTML, CSS y JavaScript. |
| `firmware/` | ESP32 + sensores, configurado en PlatformIO. |
| `tests/` | Pruebas con pacientes ficticios y DB temporal. |
| `docs/` | Arquitectura, seguridad y validación pendiente. |
| `PLAN_MAESTRO.md` | Roadmap rector de ambos grupos. |

## Instalación en PC (Windows / Linux / macOS)

**Requisitos:** Python 3.11+, entorno virtual, dependencias Python instaladas. Internet solo puede requerirse una vez para descargar dependencias; la aplicación funciona desconectada después.

```bash
git clone https://github.com/Dr3amyBerry/Moimetro.git
cd Moimetro
python -m venv .venv
```

Activar en **Windows PowerShell**:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m app.manage create-admin --username admin
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Activar en **Linux/macOS**:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m app.manage create-admin --username admin
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Abrir **http://127.0.0.1:8000**. Introducir el usuario creado. La contraseña se solicita durante la creación, **no** está incluida en el repositorio.

La base de datos se guarda en `data/moimetro.sqlite3`, ignorada por Git. Para usar otra ubicación, definir `MOIMETRO_DB_PATH` antes del arranque. **No almacenar información clínica real durante el prototipo.**

## Conectar ESP32 (solo banco de pruebas y LAN aislada)

1. Instalar [PlatformIO](https://platformio.org/) y abrir la carpeta `firmware/`.
2. Copiar `firmware/include/secrets.example.h` a `firmware/include/secrets.h`. Este último se ignora en Git.
3. Configurar SSID/contraseña de la red local, `MOI_API_BASE` con IP LAN de la computadora, `MOI_DEVICE_ID` y `MOI_DEVICE_KEY`.
4. Crear una clave aleatoria con `python -c "import secrets; print(secrets.token_urlsafe(32))"`. Colocar el mismo valor en la configuración local del servidor (`MOIMETRO_DEVICE_KEY`) y en `secrets.h`.
5. Para **pruebas de laboratorio exclusivamente**, iniciar el servidor en la LAN: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`, con firewall restringido al entorno de pruebas.
6. Compilar y cargar el firmware, abrir monitor serial a 115200. Desde la interfaz, iniciar una sesión de captura en una consulta abierta con cuenta de enfermería/médico/admin.
7. La interfaz muestra lecturas **pendientes**. El operador autorizado las acepta o rechaza. El firmware calcula R experimental, pero **no registra SpO₂ de dispositivo en expedientes** hasta calibración y validación. El triaje permanece deshabilitado.

En PowerShell, para establecer variables antes de arrancar el servidor:

```powershell
$env:MOIMETRO_DEVICE_KEY="PEGAR_CLAVE_GENERADA_AQUI"
$env:MOIMETRO_DEVICE_ID="esp32-01"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Importante:** la telemetría actual usa HTTP local sin TLS y transmite la clave del dispositivo en la LAN. No usar esta topología para pacientes reales. Antes de un piloto con información personal se requiere HTTPS, segmentación de red, evaluación de amenazas y cumplimiento aplicable.

### Conexiones físicas previstas

| Componente | ESP32 |
|---|---|
| DHT11 | Datos: GPIO18 |
| DS18B20 | OneWire: GPIO4, resistencia pull-up apropiada |
| MAX30102 SDA | GPIO21 |
| MAX30102 SCL | GPIO22 |

Verificar tensiones admisibles, alimentación, tierra común, versión de módulos y cableado con sus hojas técnicas antes de encender.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Las pruebas crean una base SQLite **temporal** con datos ficticios. Existe un workflow GitHub Actions para ejecutarlas en `main`; sus resultados deben comprobarse antes de declarar validada la implementación. La compilación real de firmware y calibración de sensores requieren herramientas y hardware adicionales.

## API local (principales rutas)

| Método | Ruta | Uso |
|---|---|---|
| POST | `/api/auth/login` | Inicio de sesión |
| POST | `/api/admin/users` | Alta de usuario (admin) |
| GET/POST | `/api/patients` | Búsqueda/registro |
| GET/POST | `/api/encounters` | Historial/nueva consulta |
| PATCH | `/api/encounters/{id}` | Evolución clínica |
| POST | `/api/encounters/{id}/capture` | Iniciar captura |
| POST | `/api/capture/{id}/stop` | Terminar captura |
| GET | `/api/device/active-session` | Sesión disponible para ESP32 |
| POST | `/api/device/measurements` | Envío protegido por clave de dispositivo |
| GET | `/api/measurements?encounter_id={id}` | Lecturas |
| POST | `/api/measurements/{id}/accept` | Aceptar lectura |
| POST | `/api/encounters/{id}/manual-measurements` | Registro manual |
| GET | `/api/encounters/{id}/triage` | «No validado» sin prioridad |

El token de usuario se envía en `Authorization: Bearer ...`. El ESP32 usa `X-Device-Key` con clave distinta de la del usuario. **No habilitar puertos hacia Internet ni incrustar claves reales en Git.**

## Manual de operación

Consulte [Manual de usuario (borrador)](docs/MANUAL_USUARIO.md), [Arquitectura](docs/ARCHITECTURE.md), [Seguridad](docs/SEGURIDAD.md) y [Validación](docs/VALIDACION.md).

## Próximos bloqueos antes del piloto

Requieren trabajo explícito: medición real/calibrada de SpO₂ y temperatura, pruebas con hardware y tiempos de captura, seguridad de red/TLS, restauración verificada de backups, migraciones de base de datos, consentimiento y tratamiento legal de los datos clínicos, protocolo de triaje revisado por profesionales, y manuales definitivos. Ver tareas y dependencias en [PLAN_MAESTRO.md](PLAN_MAESTRO.md).

## SpO₂ experimental

El ESP32 calcula la relación PPG rojo/infrarrojo real, pero **NO registra porcentajes SpO₂ hasta validar una curva de calibración específica del hardware**. Consulte [algoritmo y validación](docs/SPO2_CALIBRACION.md).
