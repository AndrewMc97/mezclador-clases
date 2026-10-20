# School Class Shuffler — versión simple

**Sin Google Cloud, sin cuenta de servicio y sin Streamlit Secrets.**

## Uso
1. Abrí la app de Streamlit.
2. Elegí **Subir un Excel (recomendado)** y seleccioná el `.xlsx` descargado desde Google Sheets (Archivo → Descargar → Microsoft Excel).
3. Tocá **Generar cursos**.
4. Podés **Descargar Excel** o **Reintentar** para obtener otra distribución.

Opcionalmente, se puede **pegar una URL de Google Sheets**. Para que funcione sin cuenta de servicio ni inicio de sesión, la hoja debe tener «Cualquier persona con el enlace → Lector». Esto no es apropiado para datos personales de estudiantes.

## Publicar la actualización
1. Descomprimí este ZIP.
2. Abrí tu repositorio de GitHub.
3. Reemplazá los archivos `app.py`, `requirements.txt`, `optimizer.py` y `README.md` por los incluidos, directamente en la raíz del repositorio.
4. Si la aplicación ya está publicada en Streamlit Community Cloud, se actualizará al recibir los cambios (puede tardar un poco). **No necesitás configurar Secrets.**

## Formato de datos
La pestaña debe llamarse `Alumnos`. Campos: `Nombre`, `Curso`, `Genero`, `A1`, `A2`, `A3`, `B1`, `B2`, `B3`; opcionalmente `No_estar_1`, `No_estar_2`, etc. Las seis elecciones tienen idéntico peso.

## Reglas
Balance de tamaños y géneros, mezcla mínima por defecto del 35 % de cada clase de origen en cada nuevo curso, búsqueda de al menos un amigo para todos, optimización de exclusiones, y botón para obtener una solución distinta de todas las anteriores de la sesión.

## Privacidad
La carga de Excel permite mantener la hoja de Google sin compartirla públicamente, aunque el archivo sigue siendo procesado en el servidor de Streamlit. Esta app no persiste los datos en una base de datos propia. Si la URL de la app es pública, cualquiera que la conozca puede acceder a su interfaz (no a los datos de otras sesiones). Verificá que el tratamiento de datos de estudiantes esté permitido por la institución.
