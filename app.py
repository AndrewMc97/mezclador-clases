"""School Class Shuffler sin Google Cloud ni Streamlit Secrets.

Para proteger los datos de menores, la carga de Excel es la opción recomendada.
Un enlace a Sheets solo puede descargarse sin autenticación si se compartió públicamente
(con cualquier persona que tenga la URL). Nunca se guardan archivos en disco.
"""

import io
import re
import secrets
from urllib.parse import quote, urlparse

import pandas as pd
import requests
import streamlit as st

from optimizer import ErrorDeDatos, crear_excel, informes, optimizar, validar

st.set_page_config(page_title='School Class Shuffler', page_icon='🎓', layout='centered')
st.title('🎓 School Class Shuffler')
st.write('Generá dos cursos equilibrados respetando preferencias y exclusiones.')

with st.expander('¿Cómo preparo mi planilla?'):
    st.code('Nombre | Curso | Genero | A1 | A2 | A3 | B1 | B2 | B3 | No_estar_1 | No_estar_2', language='text')
    st.caption('La pestaña debe llamarse Alumnos. 3 elecciones de A y 3 de B, todas de igual prioridad. Las columnas No_estar_N son opcionales.')

modo = st.radio('¿Cómo querés cargar los alumnos?',
                ['Subir un Excel (recomendado)', 'Pegar enlace de Google Sheets'], horizontal=False)

archivo = None
url = ''
if modo.startswith('Subir'):
    archivo = st.file_uploader('Elegí el Excel descargado de Google Sheets', type=['xlsx'])
    st.caption('Google Sheets → Archivo → Descargar → Microsoft Excel (.xlsx). No hace falta cambiar los permisos de tu planilla.')
else:
    url = st.text_input('URL del Google Sheets', placeholder='https://docs.google.com/spreadsheets/d/...')
    st.warning('Esta opción solo funciona sin autenticación si el Google Sheet está compartido con «Cualquier persona con el enlace: Lector». No la uses con datos personales de alumnos.')

with st.expander('Opciones avanzadas'):
    mezcla = st.slider('Mezcla mínima entre cursos originales (%)', 0, 50, 35, 5)
    st.caption('Ejemplo: 35 % asegura que ambos cursos nuevos tengan al menos un 35 % de alumnos de cada curso original.')


def leer_excel(subida):
    if subida is None:
        raise ErrorDeDatos('Seleccioná un archivo .xlsx para continuar.')
    try:
        tabla = pd.read_excel(io.BytesIO(subida.getvalue()), sheet_name='Alumnos', dtype=str, keep_default_na=False)
        return tabla.fillna('').to_dict(orient='records')
    except ValueError as exc:
        raise ErrorDeDatos('El Excel tiene que tener una pestaña llamada «Alumnos».') from exc
    except Exception as exc:
        raise ErrorDeDatos('No pude leer ese Excel. Descargalo nuevamente como .xlsx.') from exc


def leer_sheet_compartido(link):
    if not link.strip():
        raise ErrorDeDatos('Pegá la URL de un Google Sheet.')
    parsed = urlparse(link.strip())
    match = re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?', parsed.path)
    if parsed.scheme != 'https' or parsed.hostname != 'docs.google.com' or not match:
        raise ErrorDeDatos('Pegá una URL válida de Google Sheets.')

    # URL construida por la aplicación, sin seguir destinos suministrados por usuarios.
    csv_url = (f'https://docs.google.com/spreadsheets/d/{match.group(1)}/gviz/tq'
               f'?tqx=out:csv&sheet={quote("Alumnos")}')
    try:
        r = requests.get(csv_url, timeout=15)
        r.raise_for_status()
        if len(r.content) > 8_000_000:
            raise ErrorDeDatos('La planilla es demasiado grande para procesarla desde la URL.')
        if ('text/html' in r.headers.get('Content-Type', '').lower()
                or r.content[:200].lstrip().startswith(b'<!DOCTYPE')):
            raise ErrorDeDatos('No pude leer el Google Sheet. Revisá que sea accesible por cualquier persona con el enlace.')
        tabla = pd.read_csv(io.BytesIO(r.content), dtype=str, keep_default_na=False)
        return tabla.fillna('').to_dict(orient='records')
    except requests.RequestException as exc:
        raise ErrorDeDatos('No puedo acceder al Google Sheet. Si es privado, usá «Subir un Excel».') from exc
    except (pd.errors.ParserError, UnicodeError) as exc:
        raise ErrorDeDatos('Google no devolvió una tabla CSV válida. Probá la opción Excel.') from exc


def generar_solucion(nueva):
    if nueva:
        if modo.startswith('Subir'):
            bruto = leer_excel(archivo)
        else:
            bruto = leer_sheet_compartido(url)
        st.session_state['datos_shuffler'] = validar(bruto)
        st.session_state['soluciones_shuffler'] = []
        st.session_state['mezcla_shuffler'] = mezcla / 100

    datos = st.session_state['datos_shuffler']
    anteriores = [s['asignacion'] for s in st.session_state['soluciones_shuffler']]
    solucion = optimizar(datos, anteriores=anteriores,
                         mezcla=st.session_state['mezcla_shuffler'], segundos=30,
                         semilla=secrets.randbelow(2_000_000_000))
    informe = informes(datos, solucion)
    st.session_state['soluciones_shuffler'].append(solucion)
    st.session_state['informe_shuffler'] = informe
    st.session_state['excel_shuffler'] = crear_excel(informe)


if st.button('🔀 Generar cursos', type='primary', use_container_width=True):
    try:
        with st.spinner('Buscando una buena distribución...'):
            generar_solucion(True)
    except ErrorDeDatos as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error('No se pudo generar la distribución. Revisá el archivo y volvé a intentar.')

if st.session_state.get('excel_shuffler') is not None:
    informe = st.session_state['informe_shuffler']
    soluciones = st.session_state['soluciones_shuffler']
    ultimo = soluciones[-1]

    st.success(f'✅ Opción #{len(soluciones)} generada')
    filas = informe['filas']
    elegidos = sum(f['Elegidos juntos'] > 0 for f in filas)
    respetadas = sum(f['Exclusiones respetadas'] for f in filas)
    pedidos = sum(f['Exclusiones solicitadas'] for f in filas)
    col1, col2, col3 = st.columns(3)
    col1.metric('Con ≥1 elegido', f'{elegidos}/{len(filas)}')
    col2.metric('Exclusiones respetadas', f'{respetadas}/{pedidos}')
    col3.metric('Casos para revisar', len(informe['revisar']))

    st.subheader('Resumen de los cursos')
    st.dataframe(informe['resumen'], use_container_width=True, hide_index=True)

    st.download_button('⬇️ Descargar Excel de los nuevos cursos',
        data=st.session_state['excel_shuffler'],
        file_name=f'nuevos_cursos_opcion_{len(soluciones)}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        type='primary', use_container_width=True)

    if len(soluciones) > 1:
        anterior = soluciones[-2]['asignacion']
        cambios = sum(a != b for a, b in zip(anterior, ultimo['asignacion']))
        st.caption(f'Esta opción cambia a {cambios} alumnos respecto de la anterior.')
    if not ultimo['garantia_amigo']:
        st.warning('No se pudo garantizar un compañero elegido a todos. Revisá el Excel.')
    if ultimo['estado'] != 'OPTIMAL':
        st.caption('El optimizador halló una solución, pero no pudo demostrar que fuera la óptima.')

    if st.button('🔄 Reintentar (buscar otro reparto)', use_container_width=True):
        try:
            with st.spinner('Buscando una alternativa distinta...'):
                generar_solucion(False)
            st.rerun()
        except ErrorDeDatos as exc:
            st.warning(str(exc))
        except Exception:
            st.error('No se pudo generar una alternativa. Conservá la opción anterior.')

st.caption('Los datos se procesan durante la sesión. Esta app no los escribe en una base de datos. No ingreses información personal sin autorización del colegio.')
