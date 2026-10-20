# Cómo trabajar con Git en el equipo

Guía para los integrantes del equipo. Para instalar el proyecto, ver [instalacion.md](instalacion.md).

## Conceptos básicos

| Término | Qué significa |
|---|---|
| **Git** | Programa que guarda el historial de cambios del código, en tu computadora. |
| **GitHub** | Sitio web donde está la copia compartida del proyecto. Todos suben y bajan cambios desde ahí. |
| **Repositorio** | La carpeta del proyecto con todo su historial. |
| **Clonar** (`clone`) | Descargar el repositorio por primera vez. Se hace **una sola vez**. |
| **Commit** | Una "foto" de los cambios, con un mensaje que dice qué se cambió. Queda guardada **solo en tu computadora**. |
| **Push** | Subir tus commits a GitHub, para que los demás los tengan. |
| **Pull** | Bajar de GitHub los commits de los demás. |
| **Conflicto** | Dos personas cambiaron las mismas líneas de un archivo y Git no sabe con cuál quedarse. |

**Idea clave:** cambiar un archivo **no** lo sube a GitHub. Para que los demás vean tus cambios hay que hacer tres pasos: `add` → `commit` → `push`.

## Configuración inicial (una sola vez por computadora)

**1. Crear una cuenta en GitHub** en [github.com](https://github.com) y pasarle el **nombre de usuario** a Santiago, para que te agregue al repositorio.

**2. Aceptar la invitación.** Llega por correo y también aparece en las notificaciones de GitHub (el ícono de la campana). Sin aceptarla, el repositorio no aparece y `git clone` falla.

**3. Instalar Git y la herramienta de GitHub (`gh`).** En Debian o Ubuntu:

```bash
sudo apt install git gh
```

**[SIN VERIFICAR]** En algunas versiones de Debian o Ubuntu, `gh` puede no estar en los repositorios oficiales. Si `apt` no lo encuentra, buscar "GitHub CLI install Linux" en la documentación oficial de GitHub.

**4. Decirle a Git quién sos.** Con tu nombre y el **mismo correo de tu cuenta de GitHub**:

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu-correo@ejemplo.com"
git config --global pull.rebase false
```

La última línea evita que `git pull` te pregunte cómo combinar cambios. Con eso, los combina de la forma más simple.

**5. Iniciar sesión en GitHub desde la terminal:**

```bash
gh auth login
```

Elegir **GitHub.com**, **HTTPS**, aceptar que autentique Git, e iniciar sesión **con el navegador**. Muestra un código: lo copiás, lo pegás en la página que se abre y autorizás. GitHub **no acepta tu contraseña** desde la terminal; por eso se usa `gh`.

**6. Clonar el repositorio** (ver [instalación en Linux](instalacion.md#linux), paso 2). Para comprobar que quedó bien conectado:

```bash
cd analizador-audio
git remote -v
```

Tiene que mostrar dos líneas con `github.com/eltruji04/analizador-audio.git`.

## Rutina de cada día de trabajo

Siempre desde la carpeta del proyecto (`cd analizador-audio`).

**1. Al empezar: bajar los cambios de los demás.**

```bash
git pull
```

Si nadie cambió nada, dice `Already up to date.` **No empieces a trabajar sin hacer esto.**

**2. Trabajar normalmente** en VS Code.

**3. Ver qué cambiaste:**

```bash
git status
```

Muestra en rojo los archivos modificados. Si aparece algo que no reconocés (por ejemplo `.venv/` o `.env`), **no lo agregues** y avisá.

**4. Elegir qué archivos guardar en el commit:**

```bash
git add arduino/leds_audio/leds_audio.ino
```

Se puede poner más de un archivo separado por espacios. Después de `git add`, `git status` los muestra en verde.

**5. Hacer el commit con un mensaje claro:**

```bash
git commit -m "Agrega lectura de los pulsadores"
```

El mensaje dice **qué** cambió, en pocas palabras. Ejemplos buenos: `"Corrige el rebote del botón de modo"`, `"Agrega modo desde el centro"`. Ejemplos malos: `"cambios"`, `"arreglos"`, `"asdf"`.

**6. Subir a GitHub:**

```bash
git push
```

**Conviene hacer commit y push cada vez que algo funciona**, no una vez por semana. Varios commits chicos son más fáciles de revisar y de deshacer que uno enorme.

## Quién edita qué

Para evitar conflictos, cada uno trabaja principalmente en su parte:

| Integrante | Edita principalmente |
|---|---|
| Santiago | `pc/` |
| Lucía | `arduino/` |
| Benjamín | Archivos de Blynk y documentación de hardware (carpeta a definir) |

Si necesitás cambiar un archivo de otra persona (por ejemplo, el formato de los mensajes del puerto serie, que afecta a `pc/serie.py` y al código del Arduino), **avisá antes** por el grupo.

## Problemas comunes

**`git push` da error con la palabra `rejected` o `fetch first`.**
Alguien subió cambios después de tu último `git pull`. Solución:

```bash
git pull
git push
```

**`git pull` dice `CONFLICT`.**
Dos personas cambiaron las mismas líneas. No pasa nada grave:

1. Abrir el archivo en VS Code. Las partes en conflicto aparecen marcadas, con opciones como *Accept Current Change* (quedarse con lo tuyo), *Accept Incoming Change* (quedarse con lo del otro) o *Accept Both Changes* (dejar las dos).
2. Elegir la opción correcta. **Si no estás seguro, preguntale a quien hizo el otro cambio.**
3. Guardar el archivo y terminar:
   ```bash
   git add <archivo>
   git commit -m "Resuelve conflicto en <archivo>"
   git push
   ```

**Se abre un editor raro en la terminal después de `git pull` o `git commit`.**
Git pide un mensaje para el commit y abrió un editor de texto en la terminal. Si dice `GNU nano` arriba: guardar con **Ctrl+O**, Enter, y salir con **Ctrl+X**. Si no se ve ningún menú (probablemente es `vim`): escribir **`:wq`** y Enter.

**Quiero descartar los cambios de un archivo y volver a la última versión guardada:**

```bash
git restore <archivo>
```

⚠️ Esto **borra tus cambios sin guardar de ese archivo** y no se puede deshacer.

**Cualquier otro error:** copiá el mensaje completo y mandalo al grupo antes de probar soluciones de internet.

## Lo que no hay que hacer nunca

- **`git push --force`** (o `-f`): puede borrar el trabajo de los demás en GitHub.
- **Subir el archivo `.env`** ni ninguna contraseña o token.
- **Borrar la carpeta oculta `.git`**: ahí está todo el historial.
- **Editar archivos directamente en la página de GitHub** mientras alguien trabaja en ellos: después genera conflictos.
- **Copiar archivos a mano** entre computadoras (por WhatsApp, pendrive, etc.): todo pasa por GitHub.

## Comandos útiles

| Comando | Para qué sirve |
|---|---|
| `git status` | Ver qué archivos cambiaron |
| `git diff` | Ver exactamente qué líneas cambiaste (sale con `q`) |
| `git log --oneline` | Ver la lista de commits (sale con `q`) |
| `git pull` | Bajar los cambios de los demás |
| `git push` | Subir tus commits |

## Alternativa visual: VS Code

VS Code tiene un panel de **Control de código fuente** (el ícono de ramas en la barra izquierda) que hace lo mismo con botones: muestra los archivos cambiados, permite agregarlos con **+**, escribir el mensaje del commit y sincronizar con GitHub. Se puede usar en vez de la terminal, pero conviene entender primero los comandos de arriba para saber qué está haciendo.

## Ramas (branches)

Por ahora **todos trabajan en la rama `main`**. Como cada uno edita su propia carpeta, en un equipo de tres es lo más simple. Si más adelante hay muchos conflictos, se puede pasar a usar ramas.
