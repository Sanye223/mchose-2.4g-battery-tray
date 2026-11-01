<p align="center">
  <a href="README.md">简体中文</a> | <a href="README.en.md">English</a> | <a href="README.ja.md">日本語</a> | <b>Español</b> | <a href="README.ru.md">Русский</a>
</p>

# MCHOSE 2.4G Battery Tray

<p align="center">
  <img src="https://img.shields.io/badge/platform-Windows%2010%2F11-0078D4" alt="Windows 10/11">
  <img src="https://img.shields.io/badge/python-3.13+-3776AB" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/protocol-HID%20vendor%20page%200xFF01-8A2BE2" alt="HID">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
  <a href="https://github.com/Sanye223/mchose-2.4g-battery-tray/releases"><img src="https://img.shields.io/badge/release-v1.0.1-blue" alt="release v1.0.1"></a>
  <img src="https://img.shields.io/badge/verified%20on-MCHOSE%20A7%20Pro-orange" alt="A7 Pro">
</p>

Una aplicación de bandeja para Windows que **no depende del software del fabricante**: muestra de forma permanente el nivel de batería de tu ratón inalámbrico MCHOSE en el área de notificación de la barra de tareas, permite cambiar directamente los niveles de DPI y registra cada cambio de batería. Toda la comunicación se realiza a través del canal HID personalizado del firmware oficial, por lo que no es necesario instalar MCHOSE M HUB.

<p align="center">
  <img src="docs/panel-dark.png" width="360" alt="panel oscuro">
  &nbsp;&nbsp;
  <img src="docs/panel-light.png" width="360" alt="panel claro">
</p>

## ✨ Funciones

**Visualización de la batería**
- El icono de la bandeja es el propio indicador: una silueta de ratón que se llena desde abajo, se invierte automáticamente según la barra de tareas clara u oscura y se pone roja por debajo del umbral. También hay tres estilos adicionales (batería / número / anillo)
- Clic izquierdo abre un panel estilo Win11 Fluent: tarjeta de cristal esmerilado, esquinas redondeadas DWM, porcentaje en tamaño grande, barra de progreso e insignia de carga
- Información al pasar el cursor: nombre del dispositivo · batería · DPI actual · modo de conexión · última actualización

**Cambio de DPI**
- Seis niveles de DPI en el menú contextual (400 / 800 / 1600 / 3200 / 6400 / 26000 por defecto), escritos en tiempo real en la configuración integrada del ratón
- Se aplican a la vez en los canales USB y 2.4G; cada escritura se verifica leyendo de vuelta. Si la tabla de niveles no coincide, se muestra un error claro en lugar de fingir que todo salió bien
- El nivel activo depende del modo de conexión: con cable se lee el canal USB, e inalámbrico el canal 2.4G

**Registro de batería**
- Una entrada por cada cambio del 1 %, con marca de tiempo al segundo. Al conectar el cable, el sondeo se acelera automáticamente a 10 segundos; al desconectarlo, vuelve al intervalo original
- Consulta agrupada por día (con encabezados de día de la semana y estadísticas) y borrado con un clic
- Triple protección contra datos sucios: filtrado de paquetes corruptos (los saltos superiores al 10 % no se aceptan), la línea base del registro se toma del último valor guardado (las reinicios no pierden el hilo) y los cambios individuales mayores del 5 % no se registran

**Otros**
- Umbral de batería baja (ajustable entre 10 % y 40 %), inicio automático, intervalo de actualización de 30 segundos a 10 minutos
- Si una lectura falla, se conserva el último valor para que el icono no parpadee en gris; al conectar el cable, se cambia automáticamente a la lectura por el enlace por cable

<p align="center">
  <img src="docs/history-window.png" width="420" alt="ventana de registro de batería">
</p>

## 📦 Obtenerlo

Descarga el exe empaquetado desde [Releases](https://github.com/Sanye223/mchose-2.4g-battery-tray/releases) y ejecútalo con doble clic (los datos se guardan en tu directorio de usuario; no se toca el registro de Windows).

O compílalo desde el código fuente:

```bat
git clone https://github.com/Sanye223/mchose-2.4g-battery-tray.git
cd mchose-2.4g-battery-tray

:: Python 3.13+ (requiere tkinter)
python -m venv tkvenv
tkvenv\Scripts\python -m pip install pyinstaller hidapi pillow
tkvenv\Scripts\python -m PyInstaller --noconfirm --clean "2.4G电量托盘.spec"
```

> `fetch_wheels.py` es un script auxiliar: descarga sin conexión las dependencias de compilación cuando PyPI no está accesible directamente.

## 🚀 Uso

| Acción | Función |
|---|---|
| **Clic izquierdo** en el icono | Mostrar / ocultar el panel de batería |
| **Clic derecho → DPI 档位** | Cambiar el nivel de DPI (el punto de selección marca el nivel actual) |
| **Clic derecho → 电量记录…** | Ver los cambios de batería agrupados por día |
| **Clic derecho → 刷新间隔** | 30 s / 1 / 2 / 5 / 10 min (sube automáticamente a 10 s durante la carga) |
| **Clic derecho → 低电量阈值** | 10 %–40 %; el icono se pone rojo por debajo del umbral |
| **Clic derecho → 图标样式** | Ratón / batería / número / anillo |
| **Clic derecho → 开机自启** | Inicio automático (escribe la clave Run de HKCU, solo usuario actual) |

Parámetros de línea de comandos (para diagnóstico):

```bat
2.4G电量托盘.exe --cli          :: lee la batería una vez, la imprime y sale
2.4G电量托盘.exe --panel        :: abre el panel justo después de iniciar (útil si el icono está oculto)
2.4G电量托盘.exe --interval 10  :: anula temporalmente el intervalo de actualización
```

## 🖱 Adaptación de niveles de DPI

Clic derecho en el icono → **DPI 档位**: los seis niveles muestran sus valores reales (400–26000), el punto de selección marca el nivel actual y un solo clic lo escribe en la configuración integrada del ratón:

![Menú de niveles de DPI](docs/dpi-menu.png)

La información al pasar el cursor muestra el DPI vigente de forma sincronizada. El nivel activo sigue el modo de conexión: con cable se lee el canal USB, e inalámbrico el canal 2.4G. Si las sensibilidades X / Y son distintas, se muestra como `800/400`:

![DPI al pasar el cursor](docs/dpi-tooltip.png)

**Procedimiento de cambio**: leer la configuración integrada (con validación del byte de comando y filtrado de ecos en cero) → escribir de vuelta en el formato de trama del A7 Pro → esperar 250 ms y leer de nuevo para verificar "nivel aplicado + tabla intacta" → actualizar el menú y la información del cursor. Todo el proceso dura alrededor de un segundo; si algún paso falla, se registra en el log y se conserva la configuración original: la tabla nunca se corrompe en silencio.

> En el A7 Pro, el formato de la trama de escritura **no es isomorfo** al de lectura; escribir la trama de lectura directamente corrompe toda la tabla. Esta es la diferencia clave respecto a la implementación de FerrisPulse; consulta [docs/PROTOCOL.md](docs/PROTOCOL.md) para más detalles.

## 🗂 Ubicación de los datos

Todos los datos se guardan en `%APPDATA%\MchoseBattery\`:

| Archivo | Contenido |
|---|---|
| `tray.json` | Ajustes (intervalo / umbral / estilo / inicio automático) |
| `history.json` | Registro de cambios de batería (máximo 800 entradas, con rotación) |
| `tray.log` | Registro de ejecución (el detalle de lecturas fallidas y los resultados de los cambios de DPI quedan aquí) |

## 🔌 Notas sobre el protocolo e ingeniería inversa

Los formatos completos de trama están documentados en los comentarios del código de [`mchose_hid.py`](mchose_hid.py); el proceso completo de ingeniería inversa y sus trampas están en [`docs/PROTOCOL.md`](docs/PROTOCOL.md). Las conclusiones más importantes:

- La carga de la consulta de batería es `0x06`; **`F4 55` es un comando de recarga de perfil**: enviarlo hace que el ratón recargue su configuración integrada y restablece el DPI
- En el A7 Pro, la **trama de escritura de DPI no es isomorfa a la de lectura**: reenviar la trama de lectura con bytes modificados corrompe toda la tabla (en pruebas, X pasó a ser 26000/8193/16387)
- El enlace 2.4G ocasionalmente entrega paquetes corruptos (observado: 83 % → 6 % → 83 %); tanto la visualización como el registro necesitan filtrado de saltos
- Al conectar el cable, el ratón cambia a modo con cable bajo otro PID, por lo que la enumeración de dispositivos debe aceptar condiciones amplias

## ❓ Preguntas frecuentes

**P: Aparece "设备未响应" (dispositivo sin respuesta)**
Cuando el ratón está en suspensión o apagado, el firmware no responde. Es normal: mueve el ratón y se recupera. Si sigue sin responder, la línea "found N interfaces" del registro indica si el enlace está activo.

**P: No se lee la batería mientras carga**
Al conectar el cable, el ratón cambia a modo con cable (otro PID); el programa escanea automáticamente todas las interfaces candidatas. Si aun así falla, abre un issue adjuntando la parte "读取失败" de `tray.log`.

**P: Cambié el DPI pero no surte efecto en el juego**
Comprueba que el registro diga "已切换到 XXX DPI". Algunos motores de juego guardan en caché la configuración del ratón: reiniciar el juego lo resuelve.

**P: No aparece el icono en la bandeja**
Comprueba primero en el Administrador de tareas que `2.4G电量托盘.exe` se esté ejecutando. Windows guarda por defecto los iconos nuevos en el área de desbordamiento: haz clic en la flecha «^» junto al reloj. Para fijarlo: Configuración → Personalización → Barra de tareas → Otros iconos de la bandeja del sistema → activa el interruptor (Windows 10: Configuración de la barra de tareas → Selecciona los iconos que aparecen en la barra de tareas).

## 🧪 Compatibilidad

| Dispositivo | Estado |
|---|---|
| MCHOSE A7 Pro (PAW3395, 2.4G + cable) | ✅ Verificado por completo (batería / registro / DPI / cambio al cargar) |
| Otros MCHOSE serie A7 / A5 | Misma familia de protocolo; en teoría deberían funcionar — comentarios bienvenidos |

Se prueba cualquier interfaz cuyo VID empiece por `5253` / `3837`, por lo que otros modelos de MCHOSE podrían funcionar sin cambios.

## 🙏 Agradecimientos

- [marsuyone/mchose-battery-tray](https://github.com/marsuyone/mchose-battery-tray) — **el punto de partida de este proyecto**. El protocolo de batería del A7 (`0x11` + `0x06`, tramas XOR de 65 bytes, con relleno obligatorio de los 65 bytes o error 87) proviene de su ingeniería inversa del controlador web oficial de MCHOSE (WebHID); este proyecto construyó el panel, el registro y el cambio de DPI sobre ese protocolo
- [FerrisPulse](https://github.com/Ferris-echo/FerrisPulse) — referencia del marco del canal de configuración y del protocolo A5 V2
- [hidapi](https://github.com/libusb/hidapi) · [pystray](https://github.com/moses-palmer/pystray) · [Pillow](https://github.com/python-pillow/Pillow)

## License

[MIT](LICENSE) © 2026
