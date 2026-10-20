"""Aplicación lista para desplegar en Streamlit Community Cloud."""

import re
import secrets
from urllib.parse import urlparse

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

from optimizer import ErrorDeDatos, crear_excel, firma_de_datos, informes, optimizar, validar

st.set_page_config(page_title='School Class Shuffler', page_icon='🎓', layout='centered')

st.title('🎓 School Class Shuffler')
st.caption('Pegá el enlace del Google Sheets para crear dos cursos equilibrados.')

with st.expander('Formato de la planilla'):
    st.write('La pestaña debe llamarse **Alumnos** y tener estas columnas:')
    st.code('Nombre | Curso | Genero | A1 | A2 | A3 | B1 | B2 | B3 | No_estar_1 | No_estar_2', language='text')
    st.caption('Cada alumno elige 3 del A y 3 del B, todos con el mismo peso. Podés agregar No_estar_3, etc.')

with st.form('planilla'):
    url = st.text_input('URL de Google Sheets', placeholder='https://docs.google.com/spreadsheets/d/...')
    generar = st.form_submit_button('🔀 Generar cursos', type='primary', use_container_width=True)

with st.expander('Opciones avanzadas'):
    mezcla = st.slider('Mezcla mínima por curso original (%)', 0, 50, 35, 5)
    st.caption('35 % implica que cada curso nuevo tenga, como mínimo, un 35 % de los alumnos del A y del B originales, respectivamente.')


def leer_sheet(link: str):
    if not link.strip():
        raise ErrorDeDatos('Primero pegá la URL del Google Sheets.')
    parsed = urlparse(link.strip())
    match = re.fullmatch(r'/spreadsheets/d/([a-zA-Z0-9_-]+)(?:/.*)?', parsed.path)
    if parsed.hostname != 'docs.google.com' or not match or parsed.scheme != 'https':
        raise ErrorDeDatos('Pegá una URL válida de Google Sheets (https://docs.google.com/spreadsheets/d/...).')
    if 'gcp_service_account' not in st.secrets:
        raise ErrorDeDatos(
            'Todavía falta configurar el acceso privado a Google Sheets. '
            'La persona que publicó la app debe configurar la cuenta de servicio en Streamlit Secrets.'
        )
    info = dict(st.secrets['gcp_service_account'])
    scopes = ['https://www.googleapis.com/auth/spreadsheets.readonly']
    credenciales = Credentials.from_service_account_info(info, scopes=scopes)
    cliente = gspread.authorize(credenciales)
    try:
        hoja = cliente.open_by_key(match.group(1)).worksheet('Alumnos')
        return hoja.get_all_records(default_blank='')
    except gspread.exceptions.WorksheetNotFound:
        raise ErrorDeDatos('No encuentro una pestaña llamada "Alumnos".') from None
    except gspread.exceptions.APIError:
        raise ErrorDeDatos(
            'No se pudo abrir la hoja: revisá que esté compartida con '
            f'{info.get("client_email", "la cuenta de servicio")} como Lector.'
        ) from None


def procesar(link: str, mezcla_fraccion: float, reintento: bool):
    datos = validar(leer_sheet(link))
    firma = firma_de_datos(datos, mezcla_fraccion)
    if st.session_state.get('firma') != firma:
        st.session_state['firma'] = firma
        st.session_state['soluciones'] = []
    anteriores = [s['asignacion'] for s in st.session_state['soluciones']] if reintento else []
    if not reintento:
        st.session_state['soluciones'] = []
    solucion = optimizar(
        datos,
        anteriores=anteriores,
        mezcla=mezcla_fraccion,
        segundos=30,
        semilla=secrets.randbelow(2_000_000_000),
    )
    st.session_state['soluciones'].append(solucion)
    st.session_state['informe'] = informes(datos, solucion)
    st.session_state['excel'] = crear_excel(st.session_state['informe'])
    st.session_state['url'] = link
    st.session_state['mezcla'] = mezcla_fraccion
    return solucion


if generar:
    try:
        with st.spinner('Buscando una buena distribución...'):
            procesar(url, mezcla / 100, False)
    except (ErrorDeDatos, ValueError) as error:
        st.error(str(error))
    except Exception:
        st.error('No se pudo completar la operación. Verificá que el acceso a Google Sheets esté configurado.')

if st.session_state.get('excel') is not None:
    informe = st.session_state['informe']
    soluciones = st.session_state.get('soluciones', [])
    ultimo = soluciones[-1]

    st.success(f'✅ Distribución #{len(soluciones)} creada')
    total = len(informe['filas'])
    elegidos = sum(f['Elegidos juntos'] > 0 for f in informe['filas'])
    excl_cumplidas = sum(f['Exclusiones respetadas'] for f in informe['filas'])
    excl_total = sum(f['Exclusiones solicitadas'] for f in informe['filas'])
    c1, c2, c3 = st.columns(3)
    c1.metric('Con ≥1 elegido', f'{elegidos}/{total}')
    c2.metric('Exclusiones respetadas', f'{excl_cumplidas}/{excl_total}')
    c3.metric('Casos para revisar', len(informe['revisar']))

    st.subheader('Resumen')
    st.dataframe(informe['resumen'], use_container_width=True, hide_index=True)
    st.download_button(
        '⬇️ Descargar Excel de los cursos',
        data=st.session_state['excel'],
        file_name=f'nuevos_cursos_opcion_{len(soluciones)}.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        type='primary', use_container_width=True,
    )
    if len(soluciones) > 1:
        anterior = soluciones[-2]['asignacion']
        cambios = sum(a != b for a, b in zip(anterior, ultimo['asignacion']))
        st.caption(f'Esta opción cambia de curso a {cambios} alumnos respecto de la anterior (sin contar un simple renombrado).')
    if ultimo['estado'] == 'FEASIBLE':
        st.caption('El optimizador encontró una buena solución, pero no demostró que sea la óptima.')
    if not ultimo['garantia_amigo']:
        st.warning('No se pudo garantizar un elegido para todos; revisá el Excel.')

    if st.button('🔄 Reintentar — otra distribución', use_container_width=True):
        try:
            with st.spinner('Buscando otra opción distinta...'):
                procesar(st.session_state['url'], st.session_state['mezcla'], True)
            st.rerun()
        except ErrorDeDatos as error:
            st.warning(str(error))
        except Exception:
            st.error('No se pudo generar otra distribución. Conservá la opción anterior.')

st.caption('Los datos se procesan en la sesión de la aplicación; no se guardan en una base de datos.')
