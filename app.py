# app.py - Versión corregida con pestañas y nombres exactos
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html
import os
import json
import urllib.request

# ==========================
# CONFIGURACIÓN DE RUTAS
# ==========================
DATA_PATH = "data"

# ==========================
# CARGA DE DATOS CON PESTAÑAS CORRECTAS
# ==========================

# 1. Códigos de muerte - Pestaña: "final", inicia en fila 9
df_codigos = pd.read_excel(
    f"{DATA_PATH}/CodigosDeMuerte.xlsx",
    sheet_name="Final",
    header=None,  # Sin encabezado, lo asignamos manualmente
    skiprows=8    # Saltar las primeras 8 filas (índice 0-7)
)

# Asignar nombres de columnas según tu descripción
df_codigos.columns = [
    "Capítulo", "Nombre capítulo", "Código CIE-10 (3)", "Descripción 3",
    "Código CIE-10 (4)", "Descripción 4"
]

# Limpiar códigos: quitar espacios y nulos
df_codigos = df_codigos.dropna(subset=["Código CIE-10 (4)"])
df_codigos["Código CIE-10 (4)"] = df_codigos["Código CIE-10 (4)"].astype(str).str.strip()

# ==========================
# CARGA DIVIPOLA
# ==========================
try:
    df_divipola_raw = pd.read_excel(
        f"{DATA_PATH}/Divipola.xlsx",
        sheet_name="Hoja3",
        header=None
    )
    
    headers = df_divipola_raw.iloc[0].tolist()
    df_divipola = df_divipola_raw.iloc[1:].copy()
    df_divipola.columns = headers

    df_divipola.columns = [
        'Código Depto', 'Nombre Depto', 'Código Mun', 'Nombre Mun', 
        'Tipo', 'Longitud', 'Latitud'
    ]

    # === FILTRAR ANTES DE CONVERTIR ===
    df_divipola = df_divipola[
        df_divipola['Código Depto'].astype(str).str.match(r'^\d+$') &
        df_divipola['Código Mun'].astype(str).str.match(r'^\d+$')
    ].copy()

    # === COD_DANE = 5 DÍGITOS ===
    df_divipola['Código Depto'] = df_divipola['Código Depto'].astype(str).str.zfill(2)
    df_divipola['Código Mun'] = df_divipola['Código Mun'].astype(str).str.zfill(3)  # 3 dígitos
    # COD_DANE = 5 dígitos: 2 depto + 3 municipio
    df_divipola['COD_DANE'] = df_divipola['Código Depto'] + df_divipola['Código Mun']

    df_divipola['Nombre Mun'] = df_divipola['Nombre Mun'].str.strip()
    df_divipola['Nombre Depto'] = df_divipola['Nombre Depto'].str.strip()

    # COD_DANE = 5 dígitos exactos
    df_divipola['COD_DANE'] = (df_divipola['Código Depto'] + df_divipola['Código Mun']).str.zfill(5)
    df_divipola['COD_DANE'] = df_divipola['COD_DANE'].str[-5:]

except Exception as e:
    print(f"Error Divipola: {e}")
    raise

# ==========================
# CARGA NOFETAL
# ==========================

# 3. Mortalidad - Pestaña: "No_Fetales_2019"
df_mort = pd.read_excel(
    f"{DATA_PATH}/NoFetal2019.xlsx",
    sheet_name="No_Fetales_2019"
)

# Limpiar columnas
df_mort.columns = df_mort.columns.str.strip()
# COD_DANE debe ser 5 dígitos (DANE estándar)
df_mort["COD_DANE"] = df_mort["COD_DANE"].astype(str).str.zfill(5)
df_mort["COD_DANE"] = df_mort["COD_DANE"].str[-5:]  # Forzar últimos 5 dígitos
df_mort["COD_DEPARTAMENTO"] = df_mort["COD_DEPARTAMENTO"].astype(str).str.zfill(2)
df_mort["COD_MUNICIPIO"] = df_mort["COD_MUNICIPIO"].astype(str).str.zfill(3)

# ==========================
# MAPEO DE SEXO (DESPUÉS DE CARGAR df_mort)
# ==========================
sexo_map = {1: 'Hombre', 2: 'Mujer'}
df_mort['Sexo_Nombre'] = df_mort['SEXO'].map(sexo_map).fillna('Desconocido')

# Forzar COD_DANE a 5 dígitos (ej: 11001 → 11001)
df_mort["COD_DANE"] = df_mort["COD_DANE"].astype(str).str.zfill(5)
df_mort["COD_DANE"] = df_mort["COD_DANE"].str[-5:]  # últimos 5

# ==========================
# PREPROCESAMIENTO
# ==========================

# --- 1. Mapa: Muertes por departamento ---
muertes_depto = df_mort.groupby('COD_DEPARTAMENTO').size().reset_index(name='Total Muertes')
muertes_depto = muertes_depto.merge(
    df_divipola[['Código Depto', 'Nombre Depto']].drop_duplicates(),
    left_on='COD_DEPARTAMENTO',
    right_on='Código Depto',
    how='left'
)
muertes_depto['Nombre Departamento'] = muertes_depto['Nombre Depto'].fillna("Desconocido")
muertes_depto['COD_DEPARTAMENTO_STR'] = muertes_depto['COD_DEPARTAMENTO'].astype(str).str.zfill(2)

print("\n=== VERIFICACIÓN MAPA ===")
print(muertes_depto[['COD_DEPARTAMENTO', 'COD_DEPARTAMENTO_STR', 'Total Muertes', 'Nombre Departamento']].head())

# --- 2. Líneas: Muertes por mes ---
muertes_mes = df_mort['MES'].value_counts().sort_index().reset_index()
muertes_mes.columns = ['Mes', 'Total Muertes']
meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
muertes_mes['Mes Nombre'] = meses_nombres

# --- 3. Ciudades más violentas ---
homicidios = df_mort[df_mort['COD_MUERTE'] == 'X994']
homicidios_mun = homicidios['COD_DANE'].value_counts().head(5).reset_index()
homicidios_mun.columns = ['COD_DANE', 'Homicidios']
homicidios_mun = homicidios_mun.merge(
    df_divipola[['COD_DANE', 'Nombre Mun']],
    on='COD_DANE',
    how='left'
)
homicidios_mun['Nombre Municipio'] = homicidios_mun['Nombre Mun'].fillna("Desconocido")

# --- 4. Ciudades con menor mortalidad ---
muertes_mun = df_mort['COD_DANE'].value_counts().reset_index()
muertes_mun.columns = ['COD_DANE', 'Total Muertes']
muertes_menor = muertes_mun.nsmallest(10, 'Total Muertes')
muertes_menor = muertes_menor.merge(
    df_divipola[['COD_DANE', 'Nombre Mun']],
    on='COD_DANE',
    how='left'
)
muertes_menor['Nombre Municipio'] = muertes_menor['Nombre Mun'].fillna("Desconocido")

# --- 5. 10 principales causas ---
causas = df_mort['COD_MUERTE'].value_counts().head(10).reset_index()
causas.columns = ['Código Causa', 'Total Casos']
causas = causas.merge(
    df_codigos[['Código CIE-10 (4)', 'Descripción 4']],
    left_on='Código Causa',
    right_on='Código CIE-10 (4)',
    how='left'
)
causas['Causa'] = causas['Código Causa'] + " - " + causas['Descripción 4'].fillna("Desconocida")
causas = causas[['Código Causa', 'Causa', 'Total Casos']]

# --- 6. Barras apiladas ---
muertes_sexo_depto = df_mort.groupby(['COD_DEPARTAMENTO', 'Sexo_Nombre']).size().unstack(fill_value=0)
muertes_sexo_depto = muertes_sexo_depto.reset_index()
muertes_sexo_depto = muertes_sexo_depto.melt(
    id_vars=['COD_DEPARTAMENTO'],
    value_vars=['Hombre', 'Mujer'],
    var_name='Sexo',
    value_name='Muertes'
)
muertes_sexo_depto = muertes_sexo_depto.merge(
    df_divipola[['Código Depto', 'Nombre Depto']].drop_duplicates(),
    left_on='COD_DEPARTAMENTO',
    right_on='Código Depto',
    how='left'
)
muertes_sexo_depto['Nombre Departamento'] = muertes_sexo_depto['Nombre Depto'].fillna("Desconocido")

# --- 7. Histograma: GRUPO_EDAD1 ---
edad_map = {
    0: "Mortalidad neonatal (0–4)", 5: "Mortalidad infantil (5–6)", 7: "Primera infancia (7–8)",
    9: "Niñez (9–10)", 11: "Adolescencia (11)", 12: "Juventud (12–13)",
    14: "Adultez temprana (14–16)", 17: "Adultez intermedia (17–19)",
    20: "Vejez (20–24)", 25: "Longevidad (25–28)", 29: "Edad desconocida"
}
df_mort['Grupo Edad'] = df_mort['GRUPO_EDAD1'].map(edad_map).fillna("Otro")
dist_edad = df_mort['Grupo Edad'].value_counts().reset_index()
dist_edad.columns = ['Grupo Edad', 'Muertes']

# ==========================
# DASH APP
# ==========================
# GEOJSON DEPARTAMENTOS DANE (proyecto26 - 33 features, códigos "05")
GEOJSON_URL = "https://gist.githubusercontent.com/john-guerra/43c7656821069d00dcbc/raw/be6a6e239cd5b5b803c6e7c2ec405b793a9064dd/Colombia.geo.json"
app = Dash(__name__, title="Mortalidad Colombia 2019")

app.layout = html.Div([
    html.H1("Análisis Interactivo de Mortalidad en Colombia - 2019", 
            style={'textAlign': 'center', 'color': '#2c3e50', 'margin': '20px'}),

    # 1. Mapa
    html.Div([
        html.H3("Distribución de Muertes por Departamento"),
        dcc.Graph(figure=px.choropleth(
            muertes_depto,
            locations='COD_DEPARTAMENTO_STR',
            geojson=GEOJSON_URL,
            featureidkey="properties.DPTO",  # ← Clave exacta: "05", "11", etc.
            color='Total Muertes',
            color_continuous_scale="Reds",
            hover_name='Nombre Departamento',
            hover_data={'Total Muertes': True},
            title="Muertes Totales por Departamento (2019)"
        ).update_geos(fitbounds="locations", visible=False, projection_type="natural earth"))
    ], style={'margin': '20px'}),

    # 2. Líneas
    html.Div([
        html.H3("Tendencia Mensual de Mortalidad"),
        dcc.Graph(figure=px.line(
            muertes_mes, x='Mes Nombre', y='Total Muertes',
            markers=True, title="Muertes por Mes"
        ).update_layout(xaxis_title="Mes", yaxis_title="Total de Muertes"))
    ], style={'margin': '20px'}),

    # 3. Barras: Ciudades violentas
    html.Div([
        html.H3("5 Ciudades con Más Homicidios (X994)"),
        dcc.Graph(figure=px.bar(
            homicidios_mun, x='Nombre Municipio', y='Homicidios',
            color='Homicidios', color_continuous_scale="Oranges",
            title="Homicidios por Arma de Fuego"
        ))
    ], style={'margin': '20px'}),

    # 4. Circular
    html.Div([
        html.H3("10 Ciudades con Menor Mortalidad"),
        dcc.Graph(figure=px.pie(
            muertes_menor, names='Nombre Municipio', values='Total Muertes',
            title="Ciudades con Menos Defunciones"
        ))
    ], style={'margin': '20px'}),

    # 5. Tabla
    html.Div([
        html.H3("10 Principales Causas de Muerte"),
        html.Table([
            html.Thead(html.Tr([html.Th(col, style={'padding': '10px'}) for col in causas.columns])),
            html.Tbody([
                html.Tr([html.Td(causas.iloc[i][col], style={'padding': '8px'}) 
                        for col in causas.columns])
                for i in range(len(causas))
            ])
        ], style={'width': '100%', 'borderCollapse': 'collapse', 'fontSize': '14px'})
    ], style={'margin': '20px', 'padding': '15px', 'border': '1px solid #ccc', 'borderRadius': '8px'}),

    # 6. Barras apiladas
    html.Div([
        html.H3("Muertes por Sexo y Departamento"),
        dcc.Graph(figure=px.bar(
            muertes_sexo_depto, x='Nombre Departamento', y='Muertes', color='Sexo',
            barmode='stack', title="Comparación por Género"
        ).update_layout(xaxis={'categoryorder': 'total descending'}))
    ], style={'margin': '20px'}),

    # 7. Histograma
    html.Div([
        html.H3("Distribución por Grupo Etario"),
        dcc.Graph(figure=px.bar(
            dist_edad, x='Grupo Edad', y='Muertes',
            title="Mortalidad por Etapa de Vida"
        ).update_layout(xaxis={'categoryorder': 'total descending'}))
    ], style={'margin': '20px'})
], style={'fontFamily': 'Arial, sans-serif', 'backgroundColor': '#f9f9f9'})

# ==========================
# EJECUTAR
# ==========================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run_server(host='0.0.0.0', port=port, debug=False)