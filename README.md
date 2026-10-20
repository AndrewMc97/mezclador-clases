# School Class Shuffler — app web independiente de Colab

## ¿Qué hace?
- Pegás la URL de una planilla de Google Sheets.
- Equilibra el tamaño de los cursos y la cantidad de varones/mujeres.
- Cada alumno selecciona 6 amistades: 3 del A y 3 del B, sin orden de prioridad.
- Intenta asegurar al menos una amistad, y prioriza un segundo amigo y exclusiones.
- Impide una mezcla trivial: 35 % mínimo de cada curso original en ambos nuevos, por defecto.
- Reintentar: exige cambios reales frente a **todas** las opciones previas de esa sesión.
- Descarga un Excel con Curso 1, Curso 2, Resumen, Revisar y Todos.

## Publicación (una sola vez, por la persona que administra la app)

1. Creá un repositorio **privado** en https://github.com y cargá los archivos de este paquete, manteniendo `app.py` y `requirements.txt` en la raíz. NO subas claves ni un archivo `secrets.toml` real.
2. En Google Cloud creá un proyecto, habilitá **Google Sheets API** y creá una **cuenta de servicio** (service account). Generá una clave JSON para esa cuenta. Mantené la clave fuera de GitHub.
3. En https://share.streamlit.io elegí **Create app**, seleccioná el repositorio y `app.py` (usá Python 3.11 o 3.12). En la configuración avanzada **Secrets**, pegá los campos de la clave JSON bajo `[gcp_service_account]` como se indica abajo.
4. Configurá la aplicación como **privada** e invitá a tu novia y a las personas autorizadas desde **Share**.
5. Compartí cada Google Sheet privado con el correo de la cuenta de servicio como **Lector** (por ejemplo `nombre@proyecto.iam.gserviceaccount.com`). Alternativamente compartí una carpeta con esa cuenta y guardá allí las planillas.

Después de esta configuración, quien tenga permiso de usar la app **solo tiene que pegar la URL**, tocar **Generar cursos**, descargar el Excel o **Reintentar**.

### Ejemplo de estructura de Secrets

```toml
[gcp_service_account]
type = "service_account"
project_id = "TU_PROYECTO"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "cuenta@proyecto.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

> Las claves indicadas son un ejemplo sin datos reales. Copiá los campos de tu JSON privado. **Nunca** incluyas la clave privada en código o GitHub.

## Formato de la pestaña `Alumnos`

Columnas exactas: `Nombre`, `Curso`, `Genero`, `A1`, `A2`, `A3`, `B1`, `B2`, `B3`, `No_estar_1`, `No_estar_2`... Podés agregar tantas `No_estar_N` como necesites; pueden estar en blanco.

`Curso` admite A/B. `Genero` admite H o B para varones; M para mujeres. Los seis elegidos deben ser distintos, tres de A y tres de B. Los nombres deben coincidir con el listado y ser únicos.

## Privacidad de datos

- No publiques los Sheets con permiso de “cualquiera con el enlace”. **La app usa el acceso privado de una cuenta de servicio**.
- En Streamlit Community Cloud, restringí la app a espectadores autorizados. El enlace por sí solo no debe brindar acceso.
- Solo se procesan datos en memoria durante la sesión; no se suben reportes a una base de datos. La plataforma de alojamiento y Google sí procesan datos según sus propias condiciones: verificá la política del colegio antes de subir información personal de estudiantes.
- Los espectadores autorizados con una URL a una planilla accesible por la cuenta de servicio pueden procesarla. Compartí únicamente planillas correspondientes a usuarios autorizados.

## Restricciones del algoritmo

El reparto balanceado y la mezcla mínima son obligatorios. Las preferencias y las exclusiones se maximizan mediante pesos. Si el reparto con al menos un elegido para todos es imposible, el sistema busca una alternativa y la informa. `OPTIMAL` significa óptimo probado; `FEASIBLE`, solución encontrada antes de agotar el tiempo.

Para cambiar el mínimo de mezcla, ajustá el control **Opciones avanzadas** en la app. Para conservar varias propuestas, descargá cada Excel antes de presionar Reintentar.
