"""Optimizador y exportador. No requiere Streamlit para poder probarse."""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import unicodedata
from typing import Any

import xlsxwriter
from ortools.sat.python import cp_model


class ErrorDeDatos(ValueError):
    pass


def normalizar(valor: Any) -> str:
    s = unicodedata.normalize('NFKD', str(valor or '').strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.casefold().split())


def _columna(valor: Any) -> str:
    return re.sub(r'[^a-z0-9]+', '_', normalizar(valor)).strip('_')


def validar(datos: list[dict[str, Any]]) -> dict[str, Any]:
    if not datos:
        raise ErrorDeDatos('La pestaña Alumnos está vacía.')

    alumnos = [{_columna(k): str(v or '').strip() for k, v in fila.items()} for fila in datos]
    alumnos = [a for a in alumnos if any(v for v in a.values())]
    columnas_amigos = [f'{c}{j}' for c in 'ab' for j in (1, 2, 3)]
    columnas_obligatorias = ['nombre', 'curso', 'genero', *columnas_amigos]
    faltantes = [c for c in columnas_obligatorias if c not in alumnos[0]]
    if faltantes:
        raise ErrorDeDatos('Faltan columnas en la hoja: ' + ', '.join(faltantes))

    nombres = [a['nombre'] for a in alumnos]
    if any(not nombre for nombre in nombres):
        raise ErrorDeDatos('Hay filas con el nombre vacío.')

    indices = {normalizar(nombre): i for i, nombre in enumerate(nombres)}
    if len(indices) != len(nombres):
        raise ErrorDeDatos('Hay nombres duplicados. Usá nombres únicos para cada alumno.')

    cursos = [a['curso'].strip().upper() for a in alumnos]
    if any(c not in ('A', 'B') for c in cursos):
        raise ErrorDeDatos('La columna Curso solo acepta A o B.')

    mapa_generos = {
        'h': 'H', 'b': 'H', 'v': 'H', 'hombre': 'H', 'varon': 'H',
        'boy': 'H', 'masculino': 'H',
        'm': 'M', 'f': 'M', 'mujer': 'M', 'femenino': 'M', 'girl': 'M',
    }
    generos = [mapa_generos.get(normalizar(a['genero'])) for a in alumnos]
    if any(g is None for g in generos):
        raise ErrorDeDatos('La columna Genero/Género solo acepta H/B/V o M/F.')

    no_cols = sorted(
        (c for c in alumnos[0] if re.fullmatch(r'no_estar_\d+', c)),
        key=lambda c: int(c.split('_')[-1]),
    )
    amigos: list[list[int]] = []
    excluir: list[list[int]] = []
    for i, alumno in enumerate(alumnos):
        preferencias = []
        for c in columnas_amigos:
            referencia = alumno.get(c, '')
            j = indices.get(normalizar(referencia))
            if j is None:
                raise ErrorDeDatos(f'{nombres[i]}: alumno no encontrado en {c.upper()}: "{referencia}".')
            if i == j or cursos[j] != c[0].upper():
                raise ErrorDeDatos(f'{nombres[i]}: {c.upper()} debe elegir otro alumno del curso {c[0].upper()}.')
            preferencias.append(j)
        if len(set(preferencias)) != 6:
            raise ErrorDeDatos(f'{nombres[i]}: sus 6 elecciones deben ser diferentes.')

        exclusiones = []
        for c in no_cols:
            referencia = alumno.get(c, '')
            if not referencia:
                continue
            j = indices.get(normalizar(referencia))
            if j is None or j == i:
                raise ErrorDeDatos(f'{nombres[i]}: exclusión inválida en {c}: "{referencia}".')
            exclusiones.append(j)
        exclusiones = list(dict.fromkeys(exclusiones))
        if set(preferencias).intersection(exclusiones):
            raise ErrorDeDatos(f'{nombres[i]}: hay alumnos elegidos y excluidos al mismo tiempo.')
        amigos.append(preferencias)
        excluir.append(exclusiones)

    if len(alumnos) < 8:
        raise ErrorDeDatos('Se necesitan al menos 8 estudiantes para hacer las 6 elecciones.')

    return {
        'nombres': nombres, 'cursos': cursos, 'generos': generos,
        'amigos': amigos, 'excluir': excluir,
    }


def firma_de_datos(datos: dict[str, Any], mezcla: float) -> str:
    cuerpo = json.dumps([datos, round(mezcla, 5)], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(cuerpo.encode('utf-8')).hexdigest()


def _modelo(datos: dict[str, Any], mezcla: float, anteriores: list[list[int]],
            minimo_cambios: int, garantizar_amigo: bool) -> tuple[Any, list[Any]]:
    n = len(datos['nombres'])
    modelo = cp_model.CpModel()
    x = [modelo.NewBoolVar(f'grupo_{i}') for i in range(n)]

    # Ancla el nombre de los cursos para que 'retry' no se limite a invertirlos.
    modelo.Add(x[0] == 0)

    # Tamaños de clase y de cada género equilibrados al máximo posible.
    modelo.Add(sum(x) >= n // 2)
    modelo.Add(sum(x) <= (n + 1) // 2)
    for genero in ('H', 'M'):
        indices = [i for i, g in enumerate(datos['generos']) if g == genero]
        modelo.Add(sum(x[i] for i in indices) >= len(indices) // 2)
        modelo.Add(sum(x[i] for i in indices) <= (len(indices) + 1) // 2)

    # Exige alumnos de ambos cursos originales en AMBOS cursos nuevos.
    for curso in ('A', 'B'):
        indices = [i for i, c in enumerate(datos['cursos']) if c == curso]
        minimo = math.ceil(mezcla * len(indices) - 1e-9)
        modelo.Add(sum(x[i] for i in indices) >= minimo)
        modelo.Add(sum(x[i] for i in indices) <= len(indices) - minimo)

    # Al solicitar otra opción, cada reparto previo debe cambiar realmente.
    for anterior in anteriores:
        if len(anterior) != n:
            continue
        modelo.Add(sum((x[i] if anterior[i] == 0 else 1-x[i]) for i in range(n)) >= minimo_cambios)

    cache_parejas = {}

    def juntos(i: int, j: int):
        a, b = sorted((i, j))
        clave = a, b
        if clave not in cache_parejas:
            v = modelo.NewBoolVar(f'juntos_{a}_{b}')
            modelo.Add(x[a] == x[b]).OnlyEnforceIf(v)
            modelo.Add(x[a] != x[b]).OnlyEnforceIf(v.Not())
            cache_parejas[clave] = v
        return cache_parejas[clave]

    puntos = []

    def premio_al_menos(terminos, cuantos, peso, nombre):
        b = modelo.NewBoolVar(nombre)
        modelo.Add(sum(terminos) >= cuantos).OnlyEnforceIf(b)
        modelo.Add(sum(terminos) <= cuantos - 1).OnlyEnforceIf(b.Not())
        puntos.append(peso * b)

    for i in range(n):
        amigos = [juntos(i, j) for j in datos['amigos'][i]]
        if garantizar_amigo:
            modelo.Add(sum(amigos) >= 1)
        premio_al_menos(amigos, 1, 1200, f'amigo_uno_{i}')
        premio_al_menos(amigos, 2, 700, f'amigo_dos_{i}')
        puntos.extend(35 * b for b in amigos)  # A1, A2, A3, B1, B2, B3 equivalentes.

        separados = [1 - juntos(i, j) for j in datos['excluir'][i]]
        if separados:
            premio_al_menos(separados, 1, 1200, f'no_uno_{i}')
            if len(separados) > 1:
                premio_al_menos(separados, 2, 700, f'no_dos_{i}')
            puntos.extend(35 * b for b in separados)

    modelo.Maximize(sum(puntos))
    return modelo, x


def optimizar(datos: dict[str, Any], anteriores: list[list[int]] | None = None,
             mezcla: float = 0.35, segundos: int = 25,
             semilla: int = 13) -> dict[str, Any]:
    if not (0 <= mezcla <= 0.5):
        raise ErrorDeDatos('El porcentaje de mezcla debe estar entre 0 % y 50 %.')
    anteriores = anteriores or []
    n = len(datos['nombres'])
    if anteriores:
        niveles_cambio = list(dict.fromkeys([max(2, math.ceil(n * .15)), max(2, math.ceil(n * .08)), 1]))
    else:
        niveles_cambio = [0]

    for cambios in niveles_cambio:
        for garantizar in (True, False):
            modelo, x = _modelo(datos, mezcla, anteriores, cambios, garantizar)
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = segundos
            solver.parameters.num_search_workers = 8
            solver.parameters.random_seed = semilla
            solver.parameters.randomize_search = True
            estado = solver.Solve(modelo)
            if estado in (cp_model.FEASIBLE, cp_model.OPTIMAL):
                asignacion = [int(solver.Value(v)) for v in x]
                return {
                    'asignacion': asignacion,
                    'estado': solver.StatusName(estado),
                    'puntaje': float(solver.ObjectiveValue()),
                    'garantia_amigo': garantizar,
                    'cambios_minimos_exigidos': cambios,
                }
            # Una búsqueda que no llegó a una solución no prueba que sea imposible.
            if estado == cp_model.UNKNOWN:
                raise ErrorDeDatos(
                    'El optimizador no encontró un reparto dentro del tiempo disponible. '
                    'Probá de nuevo o aumentá el tiempo de cálculo.'
                )
    raise ErrorDeDatos(
        'No se encontró otra distribución diferente que respete el equilibrio y la mezcla. '
        'Podés conservar la opción anterior.'
    )


def informes(datos: dict[str, Any], solucion: dict[str, Any]) -> dict[str, Any]:
    asignacion = solucion['asignacion']
    nombres = datos['nombres']
    filas = []
    for i, nombre in enumerate(nombres):
        amigos = [nombres[j] for j in datos['amigos'][i] if asignacion[j] == asignacion[i]]
        incumplidas = [nombres[j] for j in datos['excluir'][i] if asignacion[j] == asignacion[i]]
        respetadas = len(datos['excluir'][i]) - len(incumplidas)
        filas.append({
            'Nombre': nombre,
            'Curso nuevo': f'Curso {asignacion[i] + 1}',
            'Curso original': datos['cursos'][i],
            'Género': datos['generos'][i],
            'Elegidos juntos': len(amigos),
            'Elegidos juntos (nombres)': ', '.join(amigos),
            'Exclusiones respetadas': respetadas,
            'Exclusiones solicitadas': len(datos['excluir'][i]),
            'Exclusiones incumplidas': ', '.join(incumplidas),
        })
    filas.sort(key=lambda fila: (fila['Curso nuevo'], normalizar(fila['Nombre'])))

    resumen = []
    for grupo in (1, 2):
        nuevo = f'Curso {grupo}'
        grupo_filas = [f for f in filas if f['Curso nuevo'] == nuevo]
        resumen.append({
            'Curso': nuevo,
            'Alumnos': len(grupo_filas),
            'Varones': sum(f['Género'] == 'H' for f in grupo_filas),
            'Mujeres': sum(f['Género'] == 'M' for f in grupo_filas),
            'Del A original': sum(f['Curso original'] == 'A' for f in grupo_filas),
            'Del B original': sum(f['Curso original'] == 'B' for f in grupo_filas),
            'Sin elegidos': sum(f['Elegidos juntos'] == 0 for f in grupo_filas),
            'Con 2+ elegidos': sum(f['Elegidos juntos'] >= 2 for f in grupo_filas),
            'Exclusiones incumplidas': sum(bool(f['Exclusiones incumplidas']) for f in grupo_filas),
        })

    revisar = [f for f in filas if f['Elegidos juntos'] < 2 or f['Exclusiones incumplidas']]
    return {'filas': filas, 'resumen': resumen, 'revisar': revisar}


def crear_excel(informe: dict[str, Any]) -> bytes:
    salida = io.BytesIO()
    with xlsxwriter.Workbook(salida, {'in_memory': True}) as libro:
        cabecera = libro.add_format({
            'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#173A4A',
            'valign': 'vcenter', 'text_wrap': True, 'border': 0,
        })
        texto = libro.add_format({'valign': 'top', 'text_wrap': True})
        alerta = libro.add_format({'bg_color': '#FDE9E7', 'font_color': '#9E2820', 'text_wrap': True})

        def escribir(pestana: str, filas: list[dict], headers: list[str]):
            hoja = libro.add_worksheet(pestana)
            hoja.freeze_panes(1, 0)
            hoja.set_row(0, 34)
            for col, encabezado in enumerate(headers):
                hoja.write(0, col, encabezado, cabecera)
                ancho = 37 if ('nombres' in encabezado.lower() or 'incumplidas' in encabezado.lower()) else 21
                hoja.set_column(col, col, ancho)
            for numero, fila in enumerate(filas, 1):
                for col, header in enumerate(headers):
                    valor = fila.get(header, '')
                    estilo = alerta if (header == 'Exclusiones incumplidas' and valor) or (header == 'Elegidos juntos' and valor == 0) else texto
                    # Evita fórmulas inyectadas a través de nombres de alumnos.
                    if isinstance(valor, str) and valor.startswith(('=', '+', '-', '@')):
                        hoja.write_string(numero, col, valor, estilo)
                    else:
                        hoja.write(numero, col, valor, estilo)
                hoja.set_row(numero, 22)
            if filas:
                hoja.autofilter(0, 0, len(filas), len(headers) - 1)

        filas = informe['filas']
        cols = list(filas[0].keys()) if filas else []
        escribir('Curso 1', [f for f in filas if f['Curso nuevo'] == 'Curso 1'], cols)
        escribir('Curso 2', [f for f in filas if f['Curso nuevo'] == 'Curso 2'], cols)
        escribir('Resumen', informe['resumen'], list(informe['resumen'][0].keys()))
        escribir('Revisar', informe['revisar'], cols)
        escribir('Todos', filas, cols)
    return salida.getvalue()
