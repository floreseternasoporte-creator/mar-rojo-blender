"""
=====================================================================
  LA APERTURA DEL MAR ROJO  -  VFX CINEMATOGRAFICO PARA BLENDER
=====================================================================
  Compatible con Blender 3.6 LTS, 4.0, 4.1, 4.2+, 5.0  (Cycles)

  QUE HACE ESTE SCRIPT
  --------------------
  1. Limpia la escena y configura Cycles con calidad de produccion.
  2. Genera un desierto rocoso realista (suelo agrietado + arena humeda
     que va apareciendo conforme el agua se retira).
  3. Genera cordilleras procedurales al fondo (roca, estratos, nieve
     de polvo) mas acantilados laterales.
  4. Crea el mar y dos muros de agua GIGANTES. El mar se abre como una
     cremallera (empieza en un punto y avanza), el agua se retira del
     centro hacia afuera y los muros SUBEN desde la base. Al final
     COLAPSAN EN CASCADA desde una esquina, como un tsunami.
  5. Cielo tormentoso, nublado, con nubes procedurales, niebla,
     rayos de luz (god rays) y polvo en el aire.
  6. DOS camaras: aerea cinematografica (recorrido, foco, viento, sacudida)
     y SUBMARINA que baja al agua cuando el colapso inunda el pasillo.
  7. CORTOMETRAJE: 7 planos con cambio automatico de camara por marcadores:
     establecimiento aereo -> dolly lateral del muro -> persecucion de
     pajaros -> pasillo a nivel de suelo -> colapso en gran angular ->
     caida del muro de cerca -> inundacion submarina.
  8. Efectos extra BRUTALES: relampagos que iluminan los muros, spray de
     particulas en la base y la cresta, niebla de impacto del colapso,
     bandadas de pajaros huyendo y escena MARROJO_SlowMo con camara lenta
     (0.30x) durante el colapso.

  NOVEDADES DE ESTA VERSION (sobre tu script)
  -------------------------------------------
  - Muros mas altos y anchos (CONFIG.ALTURA_MURO / ANCHO_PASILLO).
  - crear_mar_continuo: ya no es UNA sola clave "Abierto/Colapso".
    Ahora cada punto del agua tiene su propio reloj: el mar se abre
    desde CONFIG.ORIGEN_APERTURA_Y, el muro crece de abajo hacia
    arriba y el colapso arranca en la esquina CONFIG.ESQUINA_COLAPSO_Y
    y se propaga como una ola (con inundacion del pasillo).
  - Material del agua: color de cuerpo, cascadas/estrias de agua
    cayendo por el muro, espuma en la base y en el caos del colapso,
    y ondas animadas.
  - Mar con movimiento real (el oceano ya no se queda quieto).
  - crear_cielo: cielo nublado realista (nubes procedurales).
  - Camara y flujos FLIP ajustados a la nueva cronologia.

  COMO USARLO
  -----------
  Opcion A (interfaz):
     Blender > pestana "Scripting" > Open > mar_rojo.py > Run Script
  Opcion B (terminal):
     blender --python mar_rojo.py

  SIMULACION (OPCIONAL)
  ---------------------
  El agua principal ya se ve SIN hornear (Mar_Continuo). Si quieres
  ademas la simulacion FLIP:
     - Selecciona "Dominio_Fluido" > Physics > Fluid > Bake All
       (o ejecuta bake_fluid() desde la consola de Python).
  Luego Render > Render Animation (Ctrl+F12).

  AJUSTES RAPIDOS: edita la clase CONFIG de abajo.
=====================================================================
"""

import bpy
import bmesh
import math
import random
import numpy as np
from mathutils import Vector, Euler

# ---------------------------------------------------------------------
#  CONFIGURACION GLOBAL
# ---------------------------------------------------------------------
class CONFIG:
    SEED = 7                      # semilla para variacion aleatoria
    FPS = 24
    FRAME_START = 1
    FRAME_END = 600               # 25 segundos

    # Cronologia (frames)
    T_CALMA_FIN = 40              # mar tranquilo
    T_APERTURA_INI = 40           # el mar empieza a abrirse
    T_APERTURA_FIN = 260          # muros completamente formados
    T_SOSTENIDO_FIN = 340         # muros estables (toma mas espectacular)
    T_COLAPSO_INI = 340           # el agua empieza a desplomarse (esquina)
    T_COLAPSO_FIN = 590
    T_SUBMARINA_INI = 400         # la camara baja al agua con la inundacion

    # Como se ABRE el mar (cremallera que avanza)
    ORIGEN_APERTURA_Y = 20.0      # punto donde nace la grieta (eje Y)
    V_APERTURA = 6.0              # metros por frame que avanza la apertura
    DURACION_LOCAL = 48           # frames que tarda cada tramo en subir

    # Como COLAPSA (tsunami desde una esquina)
    ESQUINA_COLAPSO_Y = 40.0      # donde cae el primer trozo (muro izquierdo)
    V_COLAPSO = 4.6               # metros por frame que avanza el derrumbe
    DELAY_LADO = 40.0             # frames de retraso del muro derecho
    DURACION_COLAPSO = 64         # frames que tarda en caer cada trozo
    VEL_BORE = 0.85               # m/frame a la que la inundacion cruza el pasillo

    # Escena (unidades = metros) - ESCENARIO GRANDE
    ANCHO_PASILLO = 56.0          # separacion final entre muros
    ALTURA_MURO = 80.0            # altura de los muros de agua
    ANCHO_MURO_AGUA = 90.0        # grosor (ladera trasera) del muro
    LARGO_ESCENA = 900.0          # longitud del pasillo (eje Y)
    TAMANO_SUELO = 2400.0

    # Muestreo del agua (cada cuantos frames se guarda una forma)
    PASO_MUESTREO = 10

    # Render
    RES_X = 3840                  # 4K UHD
    RES_Y = 2160
    RES_PORCENTAJE = 50           # sube a 100 para render final
    SAMPLES = 256
    USE_GPU = True

    # Simulacion de fluido (mas alto = mas detalle, mas RAM/tiempo)
    RESOLUCION_FLUIDO = 220       # 128 preview, 220 buena, 320+ extrema
    PARTICULAS_POR_CELDA = 8

    # Colores
    COLOR_AGUA_PROFUNDA = (0.004, 0.09, 0.14, 1.0)
    COLOR_AGUA_SOMERA = (0.03, 0.30, 0.34, 1.0)


# Direccion del sol (la usan la luz Y el cielo, para que coincidan)
SOL_EULER = Euler((math.radians(76), math.radians(8), math.radians(-38)))

random.seed(CONFIG.SEED)


# ---------------------------------------------------------------------
#  UTILIDADES
# ---------------------------------------------------------------------
def limpiar_escena():
    """Elimina todo objeto, material, mundo y coleccion previos."""
    if bpy.context.object and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)

    for coleccion in (bpy.data.meshes, bpy.data.materials, bpy.data.textures,
                      bpy.data.images, bpy.data.cameras, bpy.data.lights,
                      bpy.data.curves, bpy.data.particles):
        for bloque in list(coleccion):
            coleccion.remove(bloque)

    for col in list(bpy.data.collections):
        bpy.data.collections.remove(col)


def crear_coleccion(nombre):
    col = bpy.data.collections.new(nombre)
    bpy.context.scene.collection.children.link(col)
    return col


def mover_a_coleccion(obj, coleccion):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coleccion.objects.link(obj)


def obtener_fcurves(idb):
    """
    Devuelve las fcurves de un objeto/dato en CUALQUIER version de Blender.
    (En Blender 4.4+ / 5.0 las acciones cambiaron y 'action.fcurves' ya no
    existe; esto lo resuelve.)
    """
    ad = getattr(idb, "animation_data", None)
    if not ad or not ad.action:
        return []
    act = ad.action
    try:
        return list(act.fcurves)
    except Exception:
        pass
    salida = []
    try:
        slot = ad.action_slot
        for capa in act.layers:
            for tira in capa.strips:
                cb = tira.channelbag(slot)
                if cb:
                    salida.extend(list(cb.fcurves))
    except Exception as e:
        print("[aviso] No se pudieron leer las fcurves:", e)
    return salida


def keyframe(obj, data_path, frame, value, index=-1, interpolacion='BEZIER'):
    """Inserta un keyframe con interpolacion suave."""
    if index >= 0:
        setattr_path(obj, data_path, index, value)
        obj.keyframe_insert(data_path=data_path, index=index, frame=frame)
    else:
        setattr_path(obj, data_path, None, value)
        obj.keyframe_insert(data_path=data_path, frame=frame)

    for fc in obtener_fcurves(obj):
        if fc.data_path == data_path:
            for kp in fc.keyframe_points:
                if int(kp.co[0]) == frame:
                    kp.interpolation = interpolacion


def setattr_path(obj, path, index, value):
    if index is None:
        setattr(obj, path, value)
    else:
        getattr(obj, path)[index] = value


def suavizar_fcurves(obj, tipo='BEZIER'):
    for fc in obtener_fcurves(obj):
        for kp in fc.keyframe_points:
            kp.interpolation = tipo
            kp.handle_left_type = 'AUTO_CLAMPED'
            kp.handle_right_type = 'AUTO_CLAMPED'


def animar_con_frame(destino, ruta, expresion, indice=-1):
    """
    Conduce una propiedad con el numero de frame (movimiento LINEAL, sin
    aceleracion al inicio/fin). Ej: animar_con_frame(mod, "time", "frame/24").
    """
    try:
        fc = destino.driver_add(ruta) if indice < 0 else destino.driver_add(ruta, indice)
        d = fc.driver
        d.type = 'SCRIPTED'
        d.expression = expresion
        return True
    except Exception as e:
        print(f"[aviso] No se pudo crear el driver de {ruta}: {e}")
        return False


def animar_tiempo_ocean(mod, velocidad=1.0):
    """El oceano SIEMPRE se mueve: tiempo lineal = frame/FPS * velocidad."""
    if animar_con_frame(mod, "time", f"frame/{CONFIG.FPS}*{velocidad}"):
        return
    # Plan B: dos keyframes con interpolacion lineal
    try:
        prefs = bpy.context.preferences.edit
        anterior = prefs.keyframe_new_interpolation_type
        prefs.keyframe_new_interpolation_type = 'LINEAR'
        mod.time = 0.0
        mod.keyframe_insert(data_path="time", frame=CONFIG.FRAME_START)
        mod.time = (CONFIG.FRAME_END - CONFIG.FRAME_START) / CONFIG.FPS * velocidad
        mod.keyframe_insert(data_path="time", frame=CONFIG.FRAME_END)
        prefs.keyframe_new_interpolation_type = anterior
    except Exception as e:
        print("[aviso] No se pudo animar el oceano:", e)


def nodo_valor(nodes, valor, x, y, nombre=None):
    n = nodes.new("ShaderNodeValue")
    n.outputs[0].default_value = valor
    n.location = (x, y)
    if nombre:
        n.label = nombre
    return n


def nodo_tiempo(nodes, x=-1500, y=700, expresion=None):
    """Nodo 'Tiempo' en segundos, conducido por el frame (para animar shaders)."""
    n = nodes.new("ShaderNodeValue")
    n.label = "Tiempo (s)"
    n.location = (x, y)
    animar_con_frame(n.outputs[0], "default_value", expresion or f"frame/{CONFIG.FPS}")
    return n


def set_input(node, nombres, valor):
    """Asigna un input probando varios nombres (compatibilidad 3.x / 4.x)."""
    for nombre in nombres:
        if nombre in node.inputs:
            try:
                node.inputs[nombre].default_value = valor
                return True
            except Exception:
                pass
    return False


def seguro(obj, atributo, valor):
    """Asigna una propiedad solo si existe en esta version de Blender."""
    try:
        if hasattr(obj, atributo):
            setattr(obj, atributo, valor)
            return True
    except Exception as e:
        print(f"[aviso] No se pudo asignar {atributo}: {e}")
    return False


# ---- Ayudantes para armar nodos rapido (solo hacen el codigo mas corto) ----
def _in(nodo, indice, valor):
    """Conecta un socket, o asigna un numero/vector/color."""
    if valor is None:
        return
    sock = nodo.inputs[indice]
    if hasattr(valor, "node"):
        nodo.id_data.links.new(valor, sock)
    else:
        sock.default_value = valor


def mat(nodes, op, a=None, b=None, c=None, clamp=False, loc=(0, 0)):
    n = nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    n.location = loc
    _in(n, 0, a)
    _in(n, 1, b)
    _in(n, 2, c)
    return n.outputs[0]


def vmat(nodes, op, a=None, b=None, loc=(0, 0)):
    n = nodes.new("ShaderNodeVectorMath")
    n.operation = op
    n.location = loc
    _in(n, 0, a)
    _in(n, 1, b)
    return n


def rango(nodes, valor, a, b, loc=(0, 0)):
    """Smoothstep: 0 cuando valor<=a, 1 cuando valor>=b."""
    n = nodes.new("ShaderNodeMapRange")
    n.interpolation_type = 'SMOOTHSTEP'
    n.clamp = True
    n.location = loc
    _in(n, 0, valor)
    n.inputs["From Min"].default_value = a
    n.inputs["From Max"].default_value = b
    n.inputs["To Min"].default_value = 0.0
    n.inputs["To Max"].default_value = 1.0
    return n.outputs["Result"]


def rampa_color(nodes, fac, paradas, loc=(0, 0)):
    """ColorRamp con paradas [(posicion, (r,g,b,a)), ...]."""
    n = nodes.new("ShaderNodeValToRGB")
    n.location = loc
    paradas = sorted(paradas, key=lambda p: p[0])
    el = n.color_ramp.elements
    el[0].position, el[0].color = paradas[0]
    el[1].position, el[1].color = paradas[-1]
    for pos, col in paradas[1:-1]:
        e = el.new(pos)
        e.color = col
    _in(n, 0, fac)
    return n.outputs["Color"]


# ---- Ruido con numpy (vectorizado, sin dependencias) ----
def _hash01(ix, iy, semilla):
    n = (ix * 374761393 + iy * 668265263 + semilla * 1013904223) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    n = n ^ (n >> 16)
    return (n & 0xFFFFFF) / 16777215.0


def ruido2(x, y, semilla=0):
    """Ruido de valor suave 2D, resultado en [-1, 1]."""
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    xi = np.floor(x).astype(np.int64)
    yi = np.floor(y).astype(np.int64)
    xf, yf = x - xi, y - yi
    u = xf * xf * (3 - 2 * xf)
    v = yf * yf * (3 - 2 * yf)
    a = _hash01(xi, yi, semilla)
    b = _hash01(xi + 1, yi, semilla)
    c = _hash01(xi, yi + 1, semilla)
    d = _hash01(xi + 1, yi + 1, semilla)
    r = (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v
    return r * 2.0 - 1.0


def fbm2(x, y, octavas=3, semilla=0):
    total, amp, frec, norma = 0.0, 1.0, 1.0, 0.0
    for o in range(octavas):
        total = total + amp * ruido2(x * frec, y * frec, semilla + o * 7)
        norma += amp
        amp *= 0.5
        frec *= 2.03
    return total / norma


# ---------------------------------------------------------------------
#  1. CONFIGURACION DE RENDER
# ---------------------------------------------------------------------
def configurar_render():
    escena = bpy.context.scene
    escena.render.engine = 'CYCLES'
    escena.frame_start = CONFIG.FRAME_START
    escena.frame_end = CONFIG.FRAME_END
    escena.render.fps = CONFIG.FPS

    escena.render.resolution_x = CONFIG.RES_X
    escena.render.resolution_y = CONFIG.RES_Y
    escena.render.resolution_percentage = CONFIG.RES_PORCENTAJE
    escena.render.filepath = "//render/marrojo_"

    cy = escena.cycles
    cy.samples = CONFIG.SAMPLES
    cy.preview_samples = 48
    cy.use_denoising = True
    try:
        cy.denoiser = 'OPENIMAGEDENOISE'
    except Exception:
        pass
    cy.max_bounces = 10
    cy.diffuse_bounces = 3
    cy.glossy_bounces = 4
    cy.transmission_bounces = 12
    seguro(cy, "volume_bounces", 2)
    seguro(cy, "transparent_max_bounces", 12)
    seguro(cy, "caustics_reflective", False)
    seguro(cy, "caustics_refractive", False)
    seguro(cy, "use_adaptive_sampling", True)
    seguro(cy, "adaptive_threshold", 0.01)
    seguro(cy, "volume_step_rate", 1.0)
    seguro(cy, "volume_max_steps", 256)

    # GPU si esta disponible
    if CONFIG.USE_GPU:
        try:
            prefs = bpy.context.preferences.addons['cycles'].preferences
            for tipo in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
                try:
                    prefs.compute_device_type = tipo
                    prefs.get_devices()
                    if any(d.type == tipo for d in prefs.devices):
                        for d in prefs.devices:
                            d.use = True
                        escena.cycles.device = 'GPU'
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # Look cinematografico
    vs = escena.view_settings
    try:
        vs.view_transform = 'AgX'          # Blender 4.x
    except Exception:
        vs.view_transform = 'Filmic'       # Blender 3.x
    try:
        vs.look = 'AgX - Punchy'
    except Exception:
        try:
            vs.look = 'High Contrast'
        except Exception:
            pass
    vs.exposure = 0.15

    escena.render.image_settings.file_format = 'PNG'
    escena.render.image_settings.color_depth = '16'

    # Motion blur
    escena.render.use_motion_blur = True
    try:
        escena.cycles.motion_blur_position = 'CENTER'
    except Exception:
        pass
    escena.render.motion_blur_shutter = 0.5

    # Formato de pelicula anamorfico
    escena.render.pixel_aspect_x = 1.0
    escena.render.pixel_aspect_y = 1.0


# ---------------------------------------------------------------------
#  2. TERRENO  (suelo del lecho marino + desierto)
# ---------------------------------------------------------------------
def crear_material_suelo():
    """
    Material del suelo con TRES zonas mezcladas por mascara:
      - Arena seca del desierto (lejos del pasillo)
      - Arena humeda oscura (recien descubierta)
      - Lecho marino: lodo, conchas, grietas, charcos
    Incluye desplazamiento real para relieve y micro-detalle.
    """
    mat = bpy.data.materials.new("Suelo_Desierto")
    mat.use_nodes = True
    try:
        mat.displacement_method = 'BOTH'
    except Exception:
        try:
            mat.cycles.displacement_method = 'BOTH'
        except Exception:
            pass

    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()

    salida = nodes.new("ShaderNodeOutputMaterial")
    salida.location = (1600, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (1300, 0)

    coord = nodes.new("ShaderNodeTexCoord")
    coord.location = (-1600, 0)
    mapa = nodes.new("ShaderNodeMapping")
    mapa.location = (-1400, 0)
    links.new(coord.outputs["Object"], mapa.inputs["Vector"])

    # --- Ruido grande: ondulaciones de dunas ---
    ruido_grande = nodes.new("ShaderNodeTexNoise")
    ruido_grande.location = (-1150, 400)
    ruido_grande.inputs["Scale"].default_value = 0.035
    ruido_grande.inputs["Detail"].default_value = 8.0
    ruido_grande.inputs["Roughness"].default_value = 0.6
    links.new(mapa.outputs["Vector"], ruido_grande.inputs["Vector"])

    # --- Ruido medio: rocas y terrones ---
    ruido_medio = nodes.new("ShaderNodeTexNoise")
    ruido_medio.location = (-1150, 150)
    ruido_medio.inputs["Scale"].default_value = 0.6
    ruido_medio.inputs["Detail"].default_value = 12.0
    ruido_medio.inputs["Roughness"].default_value = 0.65
    links.new(mapa.outputs["Vector"], ruido_medio.inputs["Vector"])

    # --- Ruido fino: granos de arena ---
    ruido_fino = nodes.new("ShaderNodeTexNoise")
    ruido_fino.location = (-1150, -100)
    ruido_fino.inputs["Scale"].default_value = 18.0
    ruido_fino.inputs["Detail"].default_value = 15.0
    ruido_fino.inputs["Roughness"].default_value = 0.7
    links.new(mapa.outputs["Vector"], ruido_fino.inputs["Vector"])

    # --- Voronoi: grietas de lodo seco ---
    voronoi = nodes.new("ShaderNodeTexVoronoi")
    voronoi.location = (-1150, -400)
    voronoi.feature = 'DISTANCE_TO_EDGE'
    voronoi.inputs["Scale"].default_value = 0.9
    links.new(mapa.outputs["Vector"], voronoi.inputs["Vector"])

    rampa_grietas = nodes.new("ShaderNodeValToRGB")
    rampa_grietas.location = (-900, -400)
    rampa_grietas.color_ramp.elements[0].position = 0.0
    rampa_grietas.color_ramp.elements[0].color = (0, 0, 0, 1)
    rampa_grietas.color_ramp.elements[1].position = 0.06
    rampa_grietas.color_ramp.elements[1].color = (1, 1, 1, 1)
    links.new(voronoi.outputs["Distance"], rampa_grietas.inputs["Fac"])

    # --- Mascara del pasillo: usa la coordenada X ---
    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1150, -700)
    links.new(coord.outputs["Object"], sep.inputs["Vector"])

    abs_x = nodes.new("ShaderNodeMath")
    abs_x.operation = 'ABSOLUTE'
    abs_x.location = (-950, -700)
    links.new(sep.outputs["X"], abs_x.inputs[0])

    # Mezcla lodo -> arena seca segun distancia al centro del pasillo
    rampa_pasillo = nodes.new("ShaderNodeValToRGB")
    rampa_pasillo.location = (-750, -700)
    mitad = CONFIG.ANCHO_PASILLO * 0.5
    rampa_pasillo.color_ramp.elements[0].position = 0.0
    rampa_pasillo.color_ramp.elements[0].color = (1, 1, 1, 1)
    rampa_pasillo.color_ramp.elements[1].position = 1.0
    rampa_pasillo.color_ramp.elements[1].color = (0, 0, 0, 1)
    dividir = nodes.new("ShaderNodeMath")
    dividir.operation = 'DIVIDE'
    dividir.location = (-850, -700)
    dividir.inputs[1].default_value = mitad * 3.5
    links.new(abs_x.outputs[0], dividir.inputs[0])
    links.new(dividir.outputs[0], rampa_pasillo.inputs["Fac"])

    # --- Colores base ---
    color_arena = nodes.new("ShaderNodeValToRGB")
    color_arena.location = (-600, 300)
    color_arena.color_ramp.elements[0].position = 0.35
    color_arena.color_ramp.elements[0].color = (0.32, 0.20, 0.11, 1)
    color_arena.color_ramp.elements[1].position = 0.7
    color_arena.color_ramp.elements[1].color = (0.62, 0.45, 0.27, 1)
    links.new(ruido_grande.outputs["Fac"], color_arena.inputs["Fac"])

    color_lodo = nodes.new("ShaderNodeValToRGB")
    color_lodo.location = (-600, 0)
    color_lodo.color_ramp.elements[0].position = 0.3
    color_lodo.color_ramp.elements[0].color = (0.035, 0.028, 0.022, 1)
    color_lodo.color_ramp.elements[1].position = 0.75
    color_lodo.color_ramp.elements[1].color = (0.16, 0.12, 0.085, 1)
    links.new(ruido_medio.outputs["Fac"], color_lodo.inputs["Fac"])

    # Grietas oscurecen el lodo
    mult_grietas = nodes.new("ShaderNodeMix")
    mult_grietas.data_type = 'RGBA'
    mult_grietas.blend_type = 'MULTIPLY'
    mult_grietas.location = (-350, 0)
    mult_grietas.inputs[0].default_value = 1.0
    links.new(color_lodo.outputs["Color"], mult_grietas.inputs[6])
    links.new(rampa_grietas.outputs["Color"], mult_grietas.inputs[7])

    # Mezcla final segun pasillo
    mezcla_color = nodes.new("ShaderNodeMix")
    mezcla_color.data_type = 'RGBA'
    mezcla_color.location = (-100, 150)
    links.new(rampa_pasillo.outputs["Color"], mezcla_color.inputs[0])
    links.new(color_arena.outputs["Color"], mezcla_color.inputs[6])
    links.new(mult_grietas.outputs[2], mezcla_color.inputs[7])
    # Nota: en algunos builds el output de Mix RGBA es el indice 2
    links.new(mezcla_color.outputs[2], bsdf.inputs["Base Color"])

    # --- Rugosidad: el lodo humedo brilla, la arena seca no ---
    rug = nodes.new("ShaderNodeMapRange")
    rug.location = (-100, -200)
    rug.inputs["To Min"].default_value = 0.25
    rug.inputs["To Max"].default_value = 0.92
    links.new(rampa_pasillo.outputs["Color"], rug.inputs["Value"])
    # Invertimos: cerca del centro (Fac alto) = mas humedo = menos rugoso
    rug.inputs["From Min"].default_value = 1.0
    rug.inputs["From Max"].default_value = 0.0
    links.new(rug.outputs["Result"], bsdf.inputs["Roughness"])

    # --- DESPLAZAMIENTO REAL ---
    suma1 = nodes.new("ShaderNodeMath")
    suma1.operation = 'MULTIPLY_ADD'
    suma1.location = (200, -500)
    suma1.inputs[1].default_value = 1.0
    links.new(ruido_grande.outputs["Fac"], suma1.inputs[0])
    links.new(ruido_medio.outputs["Fac"], suma1.inputs[2])

    suma2 = nodes.new("ShaderNodeMath")
    suma2.operation = 'MULTIPLY_ADD'
    suma2.location = (400, -500)
    suma2.inputs[1].default_value = 0.08
    links.new(ruido_fino.outputs["Fac"], suma2.inputs[0])
    links.new(suma1.outputs[0], suma2.inputs[2])

    resta_grietas = nodes.new("ShaderNodeMath")
    resta_grietas.operation = 'MULTIPLY'
    resta_grietas.location = (600, -500)
    conv = nodes.new("ShaderNodeRGBToBW")
    conv.location = (450, -650)
    links.new(rampa_grietas.outputs["Color"], conv.inputs["Color"])
    links.new(suma2.outputs[0], resta_grietas.inputs[0])
    links.new(conv.outputs["Val"], resta_grietas.inputs[1])

    despl = nodes.new("ShaderNodeDisplacement")
    despl.location = (1000, -400)
    despl.inputs["Midlevel"].default_value = 0.3
    despl.inputs["Scale"].default_value = 1.6
    links.new(resta_grietas.outputs[0], despl.inputs["Height"])
    links.new(despl.outputs["Displacement"], salida.inputs["Displacement"])

    # --- Bump fino extra ---
    bump = nodes.new("ShaderNodeBump")
    bump.location = (1050, -150)
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.05
    links.new(ruido_fino.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    links.new(bsdf.outputs["BSDF"], salida.inputs["Surface"])
    return mat


def crear_suelo(coleccion):
    """
    Suelo con malla REAL densa (rejilla) y borde hundido: el desierto
    desciende hacia el agua fuera de la zona de accion, asi el mar llega
    hasta el horizonte como una costa autentica.
    """
    n = 220                                  # divisiones por lado (48k vertices)
    tam = CONFIG.TAMANO_SUELO
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=n, y_segments=n, size=tam * 0.5)

    mitad = tam * 0.5

    def _caida(d, inicio, fin):
        t = max(0.0, min(1.0, (d - inicio) / (fin - inicio)))
        return t * t * (3 - 2 * t)

    for v in bm.verts:
        x, y = v.co.x, v.co.y
        # LATERAL: el desierto llega hasta las montanas (|x| ~ 600) y despues
        # cae bajo el agua base. Asi las montanas laterales apoyan en tierra firme.
        caida_x = _caida(abs(x), 700.0, 950.0)
        # FONDO (+Y): plano hasta pasar las montanas del fondo (y ~ 1000).
        caida_y_fondo = _caida(y, 950.0, 1150.0) if y > 0 else 0.0
        # FRENTE (-Y): la costa donde esta la camara; cae hacia el mar abierto.
        caida_y_frente = _caida(-y, 500.0, 750.0) if y < 0 else 0.0
        caida = max(caida_x, caida_y_fondo, caida_y_frente)
        v.co.z = -7.0 * caida

    malla = bpy.data.meshes.new("Suelo_Malla")
    bm.to_mesh(malla)
    bm.free()
    for p_ in malla.polygons:
        p_.use_smooth = True

    suelo = bpy.data.objects.new("Suelo", malla)
    bpy.context.scene.collection.objects.link(suelo)

    # Subdivision extra SOLO para el micro-desplazamiento del material
    mod = suelo.modifiers.new("Subsurf", 'SUBSURF')
    mod.subdivision_type = 'SIMPLE'
    mod.levels = 0
    mod.render_levels = 1
    try:
        suelo.cycles.use_adaptive_subdivision = True
    except Exception:
        pass

    suelo.data.materials.append(crear_material_suelo())
    mover_a_coleccion(suelo, coleccion)
    return suelo


# ---------------------------------------------------------------------
#  3. MONTANAS PROCEDURALES
# ---------------------------------------------------------------------
def crear_material_montana():
    """Roca estratificada con vetas, erosion, polvo y desplazamiento."""
    mat = bpy.data.materials.new("Roca_Montana")
    mat.use_nodes = True
    try:
        mat.displacement_method = 'BOTH'
    except Exception:
        try:
            mat.cycles.displacement_method = 'BOTH'
        except Exception:
            pass

    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()

    salida = nodes.new("ShaderNodeOutputMaterial")
    salida.location = (1500, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (1200, 0)

    coord = nodes.new("ShaderNodeTexCoord")
    coord.location = (-1500, 0)
    mapa = nodes.new("ShaderNodeMapping")
    mapa.location = (-1300, 0)
    links.new(coord.outputs["Object"], mapa.inputs["Vector"])

    # Estratos horizontales: onda deformada segun altura (Z)
    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1100, 350)
    links.new(mapa.outputs["Vector"], sep.inputs["Vector"])

    distorsion = nodes.new("ShaderNodeTexNoise")
    distorsion.location = (-1100, 100)
    distorsion.inputs["Scale"].default_value = 0.05
    distorsion.inputs["Detail"].default_value = 6.0
    links.new(mapa.outputs["Vector"], distorsion.inputs["Vector"])

    mult_dist = nodes.new("ShaderNodeMath")
    mult_dist.operation = 'MULTIPLY'
    mult_dist.location = (-900, 100)
    mult_dist.inputs[1].default_value = 25.0
    links.new(distorsion.outputs["Fac"], mult_dist.inputs[0])

    suma_z = nodes.new("ShaderNodeMath")
    suma_z.operation = 'ADD'
    suma_z.location = (-700, 250)
    links.new(sep.outputs["Z"], suma_z.inputs[0])
    links.new(mult_dist.outputs[0], suma_z.inputs[1])

    onda = nodes.new("ShaderNodeTexWave")
    onda.location = (-500, 250)
    onda.wave_type = 'BANDS'
    onda.bands_direction = 'Z'
    onda.inputs["Scale"].default_value = 0.12
    onda.inputs["Distortion"].default_value = 2.0
    onda.inputs["Detail"].default_value = 4.0
    links.new(mapa.outputs["Vector"], onda.inputs["Vector"])

    # Grano de roca
    grano = nodes.new("ShaderNodeTexNoise")
    grano.location = (-1100, -200)
    grano.inputs["Scale"].default_value = 3.5
    grano.inputs["Detail"].default_value = 15.0
    grano.inputs["Roughness"].default_value = 0.75
    links.new(mapa.outputs["Vector"], grano.inputs["Vector"])

    grieta = nodes.new("ShaderNodeTexVoronoi")
    grieta.location = (-1100, -500)
    grieta.feature = 'DISTANCE_TO_EDGE'
    grieta.inputs["Scale"].default_value = 0.35
    links.new(mapa.outputs["Vector"], grieta.inputs["Vector"])

    rampa_grieta = nodes.new("ShaderNodeValToRGB")
    rampa_grieta.location = (-850, -500)
    rampa_grieta.color_ramp.elements[0].position = 0.0
    rampa_grieta.color_ramp.elements[0].color = (0.02, 0.015, 0.012, 1)
    rampa_grieta.color_ramp.elements[1].position = 0.08
    rampa_grieta.color_ramp.elements[1].color = (1, 1, 1, 1)
    links.new(grieta.outputs["Distance"], rampa_grieta.inputs["Fac"])

    # Paleta de estratos: ocres, rojizos, marrones
    paleta = nodes.new("ShaderNodeValToRGB")
    paleta.location = (-250, 250)
    cr = paleta.color_ramp
    cr.elements[0].position = 0.0
    cr.elements[0].color = (0.16, 0.085, 0.05, 1)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.58, 0.40, 0.24, 1)
    e = cr.elements.new(0.35)
    e.color = (0.30, 0.16, 0.09, 1)
    e = cr.elements.new(0.65)
    e.color = (0.42, 0.27, 0.16, 1)
    links.new(onda.outputs["Fac"], paleta.inputs["Fac"])

    # Variacion por grano
    mezcla_grano = nodes.new("ShaderNodeMix")
    mezcla_grano.data_type = 'RGBA'
    mezcla_grano.blend_type = 'OVERLAY'
    mezcla_grano.location = (0, 150)
    mezcla_grano.inputs[0].default_value = 0.55
    links.new(paleta.outputs["Color"], mezcla_grano.inputs[6])
    links.new(grano.outputs["Color"], mezcla_grano.inputs[7])

    # Grietas
    mezcla_grieta = nodes.new("ShaderNodeMix")
    mezcla_grieta.data_type = 'RGBA'
    mezcla_grieta.blend_type = 'MULTIPLY'
    mezcla_grieta.location = (250, 100)
    mezcla_grieta.inputs[0].default_value = 1.0
    links.new(mezcla_grano.outputs[2], mezcla_grieta.inputs[6])
    links.new(rampa_grieta.outputs["Color"], mezcla_grieta.inputs[7])
    links.new(mezcla_grieta.outputs[2], bsdf.inputs["Base Color"])

    bsdf.inputs["Roughness"].default_value = 0.88
    set_input(bsdf, ["Specular IOR Level", "Specular"], 0.2)

    # Desplazamiento fuerte: relieve rocoso
    mult1 = nodes.new("ShaderNodeMath")
    mult1.operation = 'MULTIPLY'
    mult1.location = (250, -300)
    links.new(grano.outputs["Fac"], mult1.inputs[0])
    mult1.inputs[1].default_value = 1.0

    mult2 = nodes.new("ShaderNodeMath")
    mult2.operation = 'MULTIPLY_ADD'
    mult2.location = (450, -300)
    mult2.inputs[1].default_value = 0.35
    links.new(onda.outputs["Fac"], mult2.inputs[0])
    links.new(mult1.outputs[0], mult2.inputs[2])

    despl = nodes.new("ShaderNodeDisplacement")
    despl.location = (900, -350)
    despl.inputs["Midlevel"].default_value = 0.4
    despl.inputs["Scale"].default_value = 3.0
    links.new(mult2.outputs[0], despl.inputs["Height"])
    links.new(despl.outputs["Displacement"], salida.inputs["Displacement"])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (950, -100)
    bump.inputs["Strength"].default_value = 0.8
    links.new(grano.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    links.new(bsdf.outputs["BSDF"], salida.inputs["Surface"])
    return mat


def crear_montana_malla(nombre, ubicacion, escala, semilla, resolucion=110):
    """
    Genera una montana desde una rejilla desplazada con ruido fractal
    multi-octava + crestas (ridged noise) para siluetas dramaticas.
    """
    rnd = random.Random(semilla)
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=resolucion, y_segments=resolucion, size=1.0)

    # Parametros de forma
    desfase_x = rnd.uniform(0, 1000)
    desfase_y = rnd.uniform(0, 1000)

    def ruido_pseudo(x, y, escala_ruido, sx, sy):
        """Ruido de valor suave sin dependencias externas."""
        from mathutils import noise
        return noise.noise(Vector((x * escala_ruido + sx, y * escala_ruido + sy, 0.5)))

    for v in bm.verts:
        x, y = v.co.x, v.co.y
        distancia = math.sqrt(x * x + y * y)

        # Envolvente: cima central, bordes al nivel del suelo
        envolvente = max(0.0, 1.0 - distancia * 0.98) ** 1.6

        # Ruido fractal con crestas
        altura = 0.0
        amplitud = 1.0
        frecuencia = 2.2
        for octava in range(7):
            n = ruido_pseudo(x, y, frecuencia, desfase_x, desfase_y)
            cresta = 1.0 - abs(n)
            cresta = cresta * cresta
            altura += cresta * amplitud
            amplitud *= 0.48
            frecuencia *= 2.05

        # Terrazas sutiles (estratos erosionados)
        altura_terraza = altura * envolvente
        paso = 0.09
        terraza = round(altura_terraza / paso) * paso
        altura_final = altura_terraza * 0.72 + terraza * 0.28

        v.co.z = altura_final * 1.1

    malla = bpy.data.meshes.new(nombre)
    bm.to_mesh(malla)
    bm.free()

    obj = bpy.data.objects.new(nombre, malla)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = ubicacion
    obj.scale = escala

    for poly in obj.data.polygons:
        poly.use_smooth = True

    # Subdivision para mas detalle + material con desplazamiento
    mod = obj.modifiers.new("Subsurf", 'SUBSURF')
    mod.levels = 0
    mod.render_levels = 1
    try:
        obj.cycles.use_adaptive_subdivision = True
    except Exception:
        pass

    return obj


def crear_montanas(coleccion):
    mat = crear_material_montana()
    montanas = []

    # Cordillera lejana (fondo del pasillo)
    configuracion_fondo = [
        # ubicacion,                     escala,                  semilla
        ((-300, 700, 0),  (300, 300, 150), 11),
        ((  80, 820, 0),  (380, 340, 200), 12),
        (( 420, 720, 0),  (320, 300, 160), 13),
        ((-620, 620, 0),  (260, 260, 130), 14),
        (( 680, 640, 0),  (270, 270, 135), 15),
        ((   0, 1000, 0), (520, 380, 280), 16),
    ]
    # Acantilados laterales (encajonan el pasillo)
    configuracion_lateral = [
        ((-560, 200, 0),  (240, 330, 105), 21),
        ((-590, -150, 0), (230, 300, 95),  22),
        (( 570, 220, 0),  (240, 330, 108), 23),
        (( 600, -140, 0), (230, 300, 98),  24),
        ((-520, 480, 0),  (220, 260, 100), 25),
        (( 530, 500, 0),  (220, 260, 102), 26),
    ]

    for i, (loc, esc, sem) in enumerate(configuracion_fondo + configuracion_lateral):
        m = crear_montana_malla(f"Montana_{i:02d}", loc, esc, sem)
        m.data.materials.append(mat)
        mover_a_coleccion(m, coleccion)
        montanas.append(m)

    return montanas


# ---------------------------------------------------------------------
#  4. AGUA  -  OCEANO + MUROS + SIMULACION DE FLUIDOS
# ---------------------------------------------------------------------
def crear_material_agua():
    """
    Agua fotorrealista para muros gigantes y mar (Cycles):
      - Principled BSDF con TRANSMISION real (IOR 1.333): se ve como agua
        de verdad, no como plastico oscuro
      - ABSORCION volumetrica: el color depende del grosor que atraviesa
        la luz (clara en lo fino, turquesa en lo profundo)
      - Reflejo del cielo (especular del Principled)
      - Ondas finas ANIMADAS en el tiempo
      - Cascadas / estrias de agua CAYENDO por las paredes
      - Espuma: cresta del muro, base (agua chocando), y caos del colapso
    """
    mat = bpy.data.materials.new("Agua_MarRojo")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()

    H = CONFIG.ALTURA_MURO

    salida = nodes.new("ShaderNodeOutputMaterial")
    salida.location = (2200, 0)

    # --- Tiempo (segundos) para animar ondas y cascadas ---
    T = nodo_tiempo(nodes, -1900, 700).outputs[0]

    coord = nodes.new("ShaderNodeTexCoord")
    coord.location = (-1900, 0)
    mapa = nodes.new("ShaderNodeMapping")
    mapa.location = (-1700, 0)
    links.new(coord.outputs["Object"], mapa.inputs["Vector"])
    P = mapa.outputs["Vector"]

    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1700, -300)
    links.new(coord.outputs["Object"], sep.inputs["Vector"])
    px, py, pz = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]

    # --- Ondas superficiales finas (movimiento continuo) ---
    def _desliz(vx, vy):
        v = nodes.new("ShaderNodeCombineXYZ")
        v.location = (-1500, 300)
        _in(v, 0, mat(nodes, 'MULTIPLY', T, vx))
        _in(v, 1, mat(nodes, 'MULTIPLY', T, vy))
        v.inputs[2].default_value = 0.0
        return v.outputs[0]

    pos1 = vmat(nodes, 'ADD', P, _desliz(0.9, 0.5), loc=(-1300, 300))
    onda1 = nodes.new("ShaderNodeTexNoise")
    onda1.location = (-1100, 300)
    seguro(onda1, "noise_dimensions", '4D')
    onda1.inputs["Scale"].default_value = 2.8
    onda1.inputs["Detail"].default_value = 10.0
    onda1.inputs["Roughness"].default_value = 0.55
    links.new(pos1.outputs[0], onda1.inputs["Vector"])
    if "W" in onda1.inputs:
        links.new(mat(nodes, 'MULTIPLY', T, 0.35), onda1.inputs["W"])

    pos2 = vmat(nodes, 'ADD', P, _desliz(-1.7, 1.2), loc=(-1300, 100))
    onda2 = nodes.new("ShaderNodeTexNoise")
    onda2.location = (-1100, 100)
    seguro(onda2, "noise_dimensions", '4D')
    onda2.inputs["Scale"].default_value = 14.0
    onda2.inputs["Detail"].default_value = 6.0
    links.new(pos2.outputs[0], onda2.inputs["Vector"])
    if "W" in onda2.inputs:
        links.new(mat(nodes, 'MULTIPLY', T, 0.9), onda2.inputs["W"])

    mezcla_ondas = nodes.new("ShaderNodeMath")
    mezcla_ondas.operation = 'MULTIPLY_ADD'
    mezcla_ondas.location = (-850, 200)
    mezcla_ondas.inputs[1].default_value = 0.4
    links.new(onda1.outputs["Fac"], mezcla_ondas.inputs[0])
    links.new(onda2.outputs["Fac"], mezcla_ondas.inputs[2])

    bump = nodes.new("ShaderNodeBump")
    bump.location = (-600, 200)
    bump.inputs["Strength"].default_value = 0.9
    bump.inputs["Distance"].default_value = 0.25
    links.new(mezcla_ondas.outputs[0], bump.inputs["Height"])
    N = bump.outputs["Normal"]

    # --- Inclinacion de la superficie (1 = pared vertical, 0 = plano) ---
    geo = nodes.new("ShaderNodeNewGeometry")
    geo.location = (-1900, -500)
    sepn = nodes.new("ShaderNodeSeparateXYZ")
    sepn.location = (-1700, -500)
    links.new(geo.outputs["Normal"], sepn.inputs["Vector"])
    inclin = mat(nodes, 'SUBTRACT', 1.0, mat(nodes, 'ABSOLUTE', sepn.outputs["Z"]),
                 loc=(-1500, -500))

    # --- Cascadas: estrias verticales que CAEN por la pared ---
    cae = nodes.new("ShaderNodeCombineXYZ")
    cae.location = (-1500, -800)
    _in(cae, 0, mat(nodes, 'MULTIPLY', px, 0.9))
    _in(cae, 1, mat(nodes, 'MULTIPLY', py, 0.9))
    # z se estira (rasgos largos) y avanza hacia abajo con el tiempo
    _in(cae, 2, mat(nodes, 'ADD', mat(nodes, 'MULTIPLY', pz, 0.06),
                    mat(nodes, 'MULTIPLY', T, 0.75)))
    estria = nodes.new("ShaderNodeTexNoise")
    estria.location = (-1300, -800)
    estria.inputs["Scale"].default_value = 2.4
    estria.inputs["Detail"].default_value = 5.0
    links.new(cae.outputs[0], estria.inputs["Vector"])
    estria_m = rango(nodes, estria.outputs["Fac"], 0.50, 0.70, loc=(-1100, -800))

    # --- Espuma base (ruido que hierve) ---
    espuma_ruido = nodes.new("ShaderNodeTexNoise")
    espuma_ruido.location = (-1300, -1100)
    seguro(espuma_ruido, "noise_dimensions", '4D')
    espuma_ruido.inputs["Scale"].default_value = 7.0
    espuma_ruido.inputs["Detail"].default_value = 12.0
    links.new(P, espuma_ruido.inputs["Vector"])
    if "W" in espuma_ruido.inputs:
        links.new(mat(nodes, 'MULTIPLY', T, 0.5), espuma_ruido.inputs["W"])
    esp_m = rango(nodes, espuma_ruido.outputs["Fac"], 0.55, 0.78, loc=(-1100, -1100))

    # (1) Espuma en la cresta del muro (por altura)
    f_cresta = mat(nodes, 'MULTIPLY', esp_m,
                   rango(nodes, pz, H * 0.55, H * 0.98), loc=(-800, -1000))
    # (2) Cascadas de espuma cayendo por la pared
    f_estria = mat(nodes, 'MULTIPLY',
                   mat(nodes, 'MULTIPLY', estria_m,
                       rango(nodes, inclin, 0.35, 0.85)), 0.95, loc=(-800, -900))
    # (3) Espuma del CAOS (olas rotas del colapso, crestas del mar)
    f_caos = mat(nodes, 'MULTIPLY', esp_m,
                 rango(nodes, inclin, 0.16, 0.5), loc=(-800, -1200))
    # (4) Espuma en la BASE del muro (agua golpeando el suelo)
    f_base = mat(nodes, 'MULTIPLY',
                 mat(nodes, 'MULTIPLY', esp_m,
                     mat(nodes, 'SUBTRACT', 1.0, rango(nodes, pz, 4.0, 22.0))),
                 rango(nodes, inclin, 0.25, 0.7), loc=(-800, -1350))
    espuma_total = mat(nodes, 'ADD',
                       mat(nodes, 'ADD', f_cresta, f_estria),
                       mat(nodes, 'ADD', f_caos, f_base),
                       clamp=True, loc=(-500, -1100))

    # --- AGUA REAL: Principled con transmision (IOR del agua = 1.333) ---
    # El agua deja de ser un plastico oscuro: transmite la luz de verdad.
    agua = nodes.new("ShaderNodeBsdfPrincipled")
    agua.location = (300, 300)
    agua.inputs["Base Color"].default_value = (0.55, 0.75, 0.78, 1.0)
    set_input(agua, ["Transmission Weight", "Transmission"], 1.0)
    agua.inputs["IOR"].default_value = 1.333
    set_input(agua, ["Specular IOR Level", "Specular"], 0.5)
    links.new(N, agua.inputs["Normal"])

    # La pared mojada es un poco mas rugosa donde caen las estrias
    rug_mix = nodes.new("ShaderNodeMath")
    rug_mix.operation = 'MULTIPLY_ADD'
    rug_mix.location = (100, 100)
    rug_mix.inputs[1].default_value = 0.05
    links.new(estria_m, rug_mix.inputs[0])
    links.new(mat(nodes, 'MULTIPLY', inclin, 0.25), rug_mix.inputs[2])
    links.new(rug_mix.outputs[0], agua.inputs["Roughness"])

    # --- VOLUMEN: absorcion (el grosor tine el agua, como en la vida real) ---
    # Poca agua = clara; mucha agua = turquesa profundo. Asi se ve real.
    absor = nodes.new("ShaderNodeVolumeAbsorption")
    absor.location = (300, -150)
    absor.inputs["Color"].default_value = (0.015, 0.28, 0.34, 1.0)
    absor.inputs["Density"].default_value = 0.05
    links.new(absor.outputs[0], salida.inputs["Volume"])

    # --- Espuma blanca ---
    espuma_shader = nodes.new("ShaderNodeBsdfPrincipled")
    espuma_shader.location = (1250, -300)
    espuma_shader.inputs["Base Color"].default_value = (0.93, 0.97, 1.0, 1.0)
    espuma_shader.inputs["Roughness"].default_value = 0.45

    final = nodes.new("ShaderNodeMixShader")
    final.location = (1850, 100)
    links.new(espuma_total, final.inputs[0])
    links.new(agua.outputs["BSDF"], final.inputs[1])
    links.new(espuma_shader.outputs["BSDF"], final.inputs[2])
    links.new(final.outputs["Shader"], salida.inputs["Surface"])

    return mat


def crear_material_particulas_spray():
    """Material blanco translucido para espuma y spray del fluido."""
    mat = bpy.data.materials.new("Spray_Espuma")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    salida = nodes.new("ShaderNodeOutputMaterial")
    salida.location = (500, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (200, 0)
    bsdf.inputs["Base Color"].default_value = (0.96, 0.98, 1.0, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.35
    set_input(bsdf, ["Transmission Weight", "Transmission"], 0.55)
    set_input(bsdf, ["Alpha"], 0.85)
    links.new(bsdf.outputs["BSDF"], salida.inputs["Surface"])
    return mat


# ---- MAR CONTINUO CON SHAPE KEYS (v4: cada punto con su propio reloj) ----
def _suave(t):
    """Smoothstep: 0..1 suave (acepta numeros o arreglos numpy)."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _suave5(t):
    """Smootherstep (aun mas suave en los extremos)."""
    t = np.clip(t, 0.0, 1.0)
    return t * t * t * (t * (t * 6 - 15) + 10)


def _perfil_muro(x, mitad, alto, ancho_muro, curl, piso=-3.4):
    """
    Perfil CONTINUO de la seccion transversal (sin saltos), ahora con
    numpy para calcular todo el mar de una vez:

        alto |            ______
             |           /      \\___
             |          /            \\___
             |         |                  \\____
       0 ----|---------+                        \\______  (mar normal)
      piso   |_________|
             0        mitad   mitad+ancho     ...     x

    Tres tramos unidos con smoothstep, de modo que empalman sin escalon:
      1) piso del pasillo  -> nivel de lecho
      2) pared             -> sube hasta 'alto' con perfil casi vertical
      3) ladera            -> baja suavemente hasta el nivel del mar
    Devuelve (dz, dx): desplazamiento vertical y horizontal (cresta enroscada).
    """
    x = np.asarray(x, dtype=np.float64)
    d = np.abs(x)
    signo = np.where(x >= 0, 1.0, -1.0)
    alto = np.asarray(alto, dtype=np.float64) * np.ones_like(d)
    CIMA = alto - 1.0          # altura de la cresta
    base = piso + 0.35         # altura exacta donde termina el piso
    U1 = 0.30                  # fraccion del 'ancho' que ocupa la pared
    u = (d - mitad) / ancho_muro

    # --- Tramo 1: piso del pasillo (llano, apenas curvo) ---
    z1 = piso + 0.35 * _suave(d / mitad)

    # --- Tramo 2: PARED (sube de 'base' a 'CIMA') ---
    s2 = _suave(u / U1)
    z2 = base + (CIMA - base) * (s2 ** 0.85)
    zona = _suave((u - 0.05) / 0.20)
    dx2 = -signo * curl * zona * (CIMA * 0.14)   # la cresta se enrosca hacia el pasillo

    # --- Tramo 3: LADERA exterior (baja de 'CIMA' al nivel del mar) ---
    v = np.clip((u - U1) / (1.0 - U1), 0.0, 1.0)
    caida = 1.0 - _suave(v)
    cola = np.where(u > 1.0, np.exp(-np.maximum(u - 1.0, 0.0) * 0.9), 1.0)
    z_nivel_mar = -0.3
    z3 = z_nivel_mar + (CIMA - z_nivel_mar) * (0.12 + 0.88 * caida) * cola
    dx3 = -signo * curl * (CIMA * 0.14) * (1.0 - _suave(v * 2.2))

    dz = np.where(d <= mitad, z1, np.where(u <= U1, z2, z3))
    dx = np.where(d <= mitad, 0.0, np.where(u <= U1, dx2, dx3))
    return dz, dx


def _forma_mar(t, X0, Y0, mitad, alto, anc_m, piso):
    """
    Calcula la posicion (X, Z relativo) de TODOS los puntos del mar en el
    frame 't'. Aqui vive toda la logica de la apertura y del colapso.

    APERTURA
      - La grieta nace en ORIGEN_APERTURA_Y y avanza en ambos sentidos.
      - En cada tramo el agua se retira del centro hacia afuera y el muro
        sube DE ABAJO HACIA ARRIBA (la cresta sube la ultima).
      - Al terminar rebota un poco (el agua sigue 'viva').

    COLAPSO (tsunami)
      - El derrumbe empieza en la esquina ESQUINA_COLAPSO_Y del muro
        izquierdo y se propaga; el muro derecho cae despues.
      - Primero cae la cresta (se inclina hacia el pasillo), luego la base.
      - El agua INUNDA el pasillo como una ola (bore) desde cada muro.
      - Despues queda un mar caotico que se va calmando.
    """
    d = np.abs(X0)
    signo = np.where(X0 >= 0, 1.0, -1.0)

    # ventana del pasillo en Y (el pasillo se cierra suavemente en los extremos)
    borde = _suave((Y0 + 700.0) / 200.0) * (1.0 - _suave((Y0 - 900.0) / 220.0))

    # ---------------- APERTURA ----------------
    t_ap = CONFIG.T_APERTURA_INI + np.abs(Y0 - CONFIG.ORIGEN_APERTURA_Y) / CONFIG.V_APERTURA
    tau = t - t_ap
    # retraso segun la distancia al centro: piso -> base del muro -> cresta
    retraso = np.interp(d, [0.0, mitad, mitad + 0.30 * anc_m, mitad + anc_m, 1e6],
                        [0.0, 26.0, 70.0, 84.0, 84.0])
    A = _suave5((tau - retraso) / CONFIG.DURACION_LOCAL) * borde

    # variacion viva del muro (altura y enroscado cambian a lo largo y en el tiempo)
    alto_v = alto * (0.92 + 0.12 * fbm2(Y0 * 0.012 + 3.0, t * 0.004 + 1.7, 3, 5))
    curl_v = 1.4 + 0.5 * ruido2(Y0 * 0.015 + 9.0, t * 0.010, 3)
    dz, dx = _perfil_muro(X0, mitad, alto_v, anc_m, curl_v, piso)

    # rebote al terminar de formarse
    tf = np.maximum(tau - 132.0, 0.0)
    rebote = 1.0 + 0.12 * np.exp(-tf / 40.0) * np.cos(tf * 2 * math.pi / 52.0) * (tau > 132.0)
    dz = np.where(dz > 0, dz * rebote, dz)

    # turbulencia en la pared (irregularidad natural, se mueve en el tiempo)
    n1 = fbm2(X0 * 0.05 + t * 0.010, Y0 * 0.05 + t * 0.006, 2, 31)
    n2 = ruido2(X0 * 0.22 - t * 0.030, Y0 * 0.22 + t * 0.020, 41)
    turb = (n1 * 3.2 + n2 * 1.1) * np.where(d >= mitad, 1.0, 0.15)

    Zo = A * (dz + turb)
    Xo = X0 + A * dx

    # ---------------- COLAPSO ----------------
    u = (d - mitad) / anc_m
    jit = 9.0 * ruido2(Y0 * 0.02 + 5.0, 0.3, 77)
    tcL = CONFIG.T_COLAPSO_INI + np.abs(Y0 - CONFIG.ESQUINA_COLAPSO_Y) / CONFIG.V_COLAPSO + jit
    tcR = tcL + CONFIG.DELAY_LADO
    tc_lado = np.where(X0 < 0, tcL, tcR)
    # la cresta cae primero, la base despues; la ladera trasera al final
    delta = np.where(u < 0, 18.0,
             np.where(u < 0.30, 18.0 * (1.0 - u / 0.30), (u - 0.30) * anc_m * 0.25))

    # la inundacion cruza el pasillo desde cada muro (llega primero desde el que cae antes)
    xc = np.clip(X0, -mitad, mitad)
    t_arr = np.minimum(tcL + 18.0 + (xc + mitad) / CONFIG.VEL_BORE,
                       tcR + 18.0 + (mitad - xc) / CONFIG.VEL_BORE)
    tc = np.where(d <= mitad, t_arr, tc_lado + delta)

    C = _suave5((t - tc) / CONFIG.DURACION_COLAPSO)
    tc_pos = np.maximum(t - tc, 0.0)

    # forma posterior: mar caotico que se calma
    lejos = np.exp(-np.maximum(d - mitad, 0.0) / 260.0)
    amp = 7.0 * _suave(tc_pos / 25.0) * np.exp(-np.maximum(tc_pos - 25.0, 0.0) / 130.0)
    sl = 6.0 * np.exp(-tc_pos / 85.0) * (0.6 + 0.4 * np.cos(tc_pos * 2 * math.pi / 70.0))
    m1 = fbm2(X0 * 0.02 + t * 0.05, Y0 * 0.02 - t * 0.04, 3, 11)
    m2 = fbm2(X0 * 0.07 - t * 0.12, Y0 * 0.07 + t * 0.09, 3, 17)
    borde_suave = 0.15 + 0.85 * borde
    Zp = (sl + amp * (m1 + 0.45 * m2)) * lejos * borde_suave

    Cz = C ** 1.3
    Z = Zo * (1.0 - Cz) + Zp * Cz

    # la cresta se INCLINA hacia el pasillo mientras cae (y vuelve al terminar)
    gq = np.where(u < 0, 0.0,
          np.where(u < 0.30, np.clip(u / 0.30, 0, 1) ** 1.4,
                   np.exp(-(u - 0.30) * anc_m / 60.0)))
    X = Xo + (X0 - Xo) * C - signo * 22.0 * np.sin(math.pi * C) * gq

    # inundacion del pasillo (ola frontal con 'cabeza' de espuma)
    tau_f = t - t_arr
    r = np.clip(tau_f / 14.0, 0.0, 1.0)
    lvl = piso + (6.0 * np.exp(-np.maximum(tau_f, 0.0) / 90.0) - piso) * _suave(r) \
        + 10.0 * np.exp(-((tau_f - 9.0) / 14.0) ** 2) * (tau_f > 0)
    lvl = np.where(tau_f < 0, piso, lvl)
    w = np.where(d <= mitad, 1.0, 1.0 - _suave((d - mitad) / (0.12 * anc_m + 1.0)))
    Z = Z + w * borde * np.maximum(0.0, lvl - Z)

    return X, Z


def crear_mar_continuo(coleccion):
    """
    Mar como UNA malla con muchas 'claves de forma' muestreadas en el tiempo.
    Cada clave es la forma exacta del agua en un frame (calculada con
    _forma_mar) y Blender las mezcla linealmente: se ve sin hornear nada.
    """
    rnd = random.Random(CONFIG.SEED)
    mitad = CONFIG.ANCHO_PASILLO * 0.5
    alto = CONFIG.ALTURA_MURO
    anc_m = CONFIG.ANCHO_MURO_AGUA
    PISO = -3.4                     # el agua 'drenada' queda bajo el lecho

    # ------------------------------------------------------------------
    #  Malla base: rejilla ANISOTROPICA (muy densa en la cara del muro)
    #  Esto da detalle donde importa sin explotar el conteo de vertices.
    # ------------------------------------------------------------------
    u1 = np.linspace(0.0, mitad - 4.0, 10, endpoint=False)               # piso
    u2 = np.linspace(mitad - 4.0, mitad + 34.0, 66, endpoint=False)      # cara del muro (densa)
    u3 = (mitad + 34.0) + 170.0 * (np.linspace(0, 1, 52, endpoint=False) ** 1.3)   # ladera
    u4 = (mitad + 204.0) + (1500.0 - (mitad + 204.0)) * (np.linspace(0, 1, 30) ** 1.5)  # mar lejano
    u_all = np.concatenate([u1, u2, u3, u4])
    xs = np.concatenate([-u_all[:0:-1], u_all])          # simetrico

    n_y = 340
    y_min, y_max = -800.0, 1000.0
    ys = np.linspace(y_min, y_max, n_y + 1)

    nx, ny = len(xs), len(ys)
    gx, gy = np.meshgrid(xs, ys)                          # (ny, nx)
    verts = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)])
    idx = np.arange(nx * ny).reshape(ny, nx)
    caras = np.column_stack([idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel(),
                             idx[1:, 1:].ravel(), idx[1:, :-1].ravel()])

    malla = bpy.data.meshes.new("Mar_Continuo_Malla")
    malla.from_pydata(verts.tolist(), [], caras.tolist())
    malla.update()

    mar = bpy.data.objects.new("Mar_Continuo", malla)
    bpy.context.scene.collection.objects.link(mar)
    mar.location = (0, 0, 2.2)
    for p in mar.data.polygons:
        p.use_smooth = True

    X0 = verts[:, 0].copy()
    Y0 = verts[:, 1].copy()

    # ------------------------------------------------------------------
    #  SHAPE KEYS MUESTREADAS (una cada PASO_MUESTREO frames)
    # ------------------------------------------------------------------
    frames = list(range(CONFIG.FRAME_START, CONFIG.FRAME_END + 1, CONFIG.PASO_MUESTREO))
    if frames[-1] != CONFIG.FRAME_END:
        frames.append(CONFIG.FRAME_END)

    mar.shape_key_add(name="Basis", from_mix=False)          # mar cerrado (frame inicial)

    prefs = bpy.context.preferences.edit
    interp_anterior = prefs.keyframe_new_interpolation_type
    try:
        prefs.keyframe_new_interpolation_type = 'LINEAR'
    except Exception:
        pass

    for i in range(1, len(frames)):
        X, Z = _forma_mar(frames[i], X0, Y0, mitad, alto, anc_m, PISO)
        sk = mar.shape_key_add(name=f"F{frames[i]:04d}", from_mix=False)
        sk.data.foreach_set("co", np.column_stack([X, Y0, Z]).astype(np.float32).ravel())

        # la clave sube de 0 a 1 hasta su frame y baja hasta el siguiente
        f_prev = frames[i - 1]
        f_next = frames[i + 1] if i + 1 < len(frames) else frames[i] + 1
        for f, val in ((f_prev, 0.0), (frames[i], 1.0), (f_next, 0.0)):
            sk.value = val
            sk.keyframe_insert(data_path="value", frame=f)

    try:
        prefs.keyframe_new_interpolation_type = interp_anterior
    except Exception:
        pass

    # asegurar interpolacion LINEAL (mezcla exacta entre dos formas)
    for fc in obtener_fcurves(mar.data.shape_keys):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'

    # ------------------------------------------------------------------
    #  OLAS REALES ENCIMA (Ocean en modo displace) - SIEMPRE EN MOVIMIENTO
    # ------------------------------------------------------------------
    ocean = mar.modifiers.new("Olas", 'OCEAN')
    for attr, val in [
        ("geometry_mode", 'DISPLACE'),
        ("resolution", 20), ("spatial_size", 180),
        ("wave_scale", 2.0), ("wave_scale_min", 6.0),
        ("choppiness", 1.6), ("wind_velocity", 26.0),
        ("wave_alignment", 0.4), ("wave_direction", math.radians(90)),
        ("damping", 0.4), ("depth", 300),
        ("use_foam", True), ("foam_layer_name", "espuma"),
        ("foam_coverage", 0.55), ("random_seed", CONFIG.SEED),
        ("time", 0.0),
    ]:
        seguro(ocean, attr, val)
    animar_tiempo_ocean(ocean, 1.6)

    # Subdivision final (suaviza sin perder el perfil)
    sub = mar.modifiers.new("Suavizar", 'SUBSURF')
    sub.levels = 0
    sub.render_levels = 1

    # Grosor real: convierte la superficie en un volumen cerrado para que la
    # absorcion volumetrica del material funcione (color segun profundidad)
    sol = mar.modifiers.new("Grosor", 'SOLIDIFY')
    sol.thickness = 3.0
    sol.offset = 0.0

    mar.data.materials.append(
        bpy.data.materials.get("Agua_MarRojo") or crear_material_agua())
    mover_a_coleccion(mar, coleccion)
    return mar


def crear_oceano_base(coleccion):
    """
    Oceano lejano/cercano (fuera de la simulacion). Usa el modificador
    Ocean para olas realistas con espuma real.
    """
    bpy.ops.mesh.primitive_grid_add(
        x_subdivisions=400, y_subdivisions=400,
        size=CONFIG.TAMANO_SUELO,
        location=(0, -CONFIG.LARGO_ESCENA * 0.5 - 200, 0.0)
    )
    oceano = bpy.context.active_object
    oceano.name = "Oceano_Lejano"

    mod = oceano.modifiers.new("Ocean", 'OCEAN')
    for attr, val in [
        ("geometry_mode", 'GENERATE'), ("repeat_x", 1), ("repeat_y", 1),
        ("resolution", 18), ("spatial_size", 120), ("wave_scale", 3.2),
        ("wave_scale_min", 0.01), ("choppiness", 1.7), ("wind_velocity", 28.0),
        ("wave_alignment", 0.35), ("wave_direction", math.radians(90)),
        ("damping", 0.5), ("depth", 200), ("use_foam", True),
        ("foam_layer_name", "espuma"), ("foam_coverage", 0.6),
        ("random_seed", CONFIG.SEED), ("time", 0.0),
    ]:
        seguro(mod, attr, val)

    # Tiempo lineal (antes tenia easing y parecia quieto al inicio y al final)
    animar_tiempo_ocean(mod, 1.4)

    oceano.data.materials.append(bpy.data.materials.get("Agua_MarRojo") or crear_material_agua())
    mover_a_coleccion(oceano, coleccion)
    return oceano


def crear_fuente_de_fluido(coleccion):
    """
    Volumenes de agua (izquierdo y derecho) que actuan como emisores del
    fluido. Ahora cada muro esta partido en TRAMOS a lo largo de Y, y cada
    tramo se abre y colapsa con SU PROPIO retraso: la simulacion FLIP se
    abre como cremallera y se derrumba en cascada desde la esquina, igual
    que el mar visible.
    """
    material_agua = bpy.data.materials.get("Agua_MarRojo") or crear_material_agua()
    bloques = []

    mitad_pasillo = CONFIG.ANCHO_PASILLO * 0.5
    ancho_bloque = 90.0
    alto_bloque = CONFIG.ALTURA_MURO
    largo_total = CONFIG.LARGO_ESCENA
    n_seg = 10
    largo_seg = largo_total / n_seg

    for lado, signo in (("Izq", -1), ("Der", 1)):
        for k in range(n_seg):
            yc = -largo_total * 0.5 + largo_seg * (k + 0.5)
            off_ap = abs(yc - CONFIG.ORIGEN_APERTURA_Y) / CONFIG.V_APERTURA
            off_col = abs(yc - CONFIG.ESQUINA_COLAPSO_Y) / CONFIG.V_COLAPSO \
                + (CONFIG.DELAY_LADO if signo > 0 else 0.0)
            f_ap0 = int(round(CONFIG.T_CALMA_FIN + off_ap))
            f_ap1 = f_ap0 + 110
            f_c0 = int(round(CONFIG.T_COLAPSO_INI + off_col))
            f_c1 = f_c0 + 90

            bpy.ops.mesh.primitive_cube_add(size=1.0)
            b = bpy.context.active_object
            b.name = f"Muro_Agua_{lado}_{k:02d}"
            esc_xy = (ancho_bloque * 0.5, largo_seg * 0.5)

            # Posicion inicial: bloque unido al centro (mar cerrado)
            x_cerrado = signo * (ancho_bloque * 0.5)
            x_abierto = signo * (mitad_pasillo + ancho_bloque * 0.5)
            z_base = alto_bloque * 0.5 - 1.5

            b.location = (x_cerrado, yc, z_base)
            b.scale = (esc_xy[0], esc_xy[1], alto_bloque * 0.08)
            b.keyframe_insert(data_path="location", frame=f_ap0)
            b.keyframe_insert(data_path="scale", frame=f_ap0)

            # APERTURA: el bloque se desliza hacia afuera y crece
            b.location = (x_abierto, yc, z_base)
            b.scale = (esc_xy[0], esc_xy[1], alto_bloque * 0.5)
            b.keyframe_insert(data_path="location", frame=f_ap1)
            b.keyframe_insert(data_path="scale", frame=f_ap1)

            # SOSTENIDO
            b.keyframe_insert(data_path="location", frame=f_c0)
            b.keyframe_insert(data_path="scale", frame=f_c0)

            # COLAPSO: cada tramo cae cuando le toca (cascada)
            b.location = (signo * (ancho_bloque * 0.5 - 12), yc, z_base - 8)
            b.scale = (esc_xy[0], esc_xy[1], alto_bloque * 0.10)
            b.keyframe_insert(data_path="location", frame=f_c1)
            b.keyframe_insert(data_path="scale", frame=f_c1)

            suavizar_fcurves(b, 'BEZIER')

            # Modificador de fluido como FLOW (emisor de agua)
            mod = b.modifiers.new("Fluid", 'FLUID')
            mod.fluid_type = 'FLOW'
            seguro(mod.flow_settings, "flow_type", 'LIQUID')
            seguro(mod.flow_settings, "flow_behavior", 'GEOMETRY')
            seguro(mod.flow_settings, "use_initial_velocity", True)
            seguro(mod.flow_settings, "velocity_factor", 0.0)

            b.data.materials.append(material_agua)
            # El mar visible es 'Mar_Continuo'. Estos bloques solo alimentan la
            # simulacion FLIP (spray, espuma, colapso) y no se dibujan por si solos.
            b.hide_render = True
            b.display_type = 'WIRE'
            mover_a_coleccion(b, coleccion)
            bloques.append(b)

    return bloques


def crear_dominio_fluido(coleccion):
    """
    Dominio Mantaflow FLIP con espuma, spray y burbujas. Cubre todo el
    pasillo y los muros de agua.
    """
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    dom = bpy.context.active_object
    dom.name = "Dominio_Fluido"

    ancho = CONFIG.ANCHO_PASILLO + 210
    largo = CONFIG.LARGO_ESCENA
    alto = CONFIG.ALTURA_MURO * 2.1

    dom.scale = (ancho * 0.5, largo * 0.5, alto * 0.5)
    dom.location = (0, 0, alto * 0.5 - 4)

    mod = dom.modifiers.new("Fluid", 'FLUID')
    mod.fluid_type = 'DOMAIN'
    ds = mod.domain_settings
    omitidas = []

    def fijar(atributo, valor):
        """Asigna si la propiedad existe en esta version; si no, la anota."""
        if not seguro(ds, atributo, valor):
            omitidas.append(atributo)

    def fijar_primero(nombres, valor):
        """Prueba varios nombres posibles (cambian entre versiones)."""
        for nombre in nombres:
            if hasattr(ds, nombre):
                if seguro(ds, nombre, valor):
                    return True
        omitidas.append(" / ".join(nombres))
        return False

    fijar("domain_type", 'LIQUID')

    # --- Resolucion y particulas ---
    fijar("resolution_max", CONFIG.RESOLUCION_FLUIDO)
    fijar("particle_radius", 1.0)
    fijar("particle_number", 2)
    fijar("use_adaptive_timesteps", True)
    fijar("timesteps_max", 6)

    # --- Malla del liquido ---
    fijar("use_mesh", True)
    fijar("mesh_scale", 2)
    fijar("mesh_particle_radius", 1.5)
    fijar("use_speed_vectors", True)          # motion blur del fluido
    fijar("use_diffusion", False)
    fijar("use_fractions", True)              # colisiones suaves
    fijar("fractions_distance", 0.6)

    # --- Fisica: agua real ---
    fijar("use_viscosity", False)
    fijar("simulation_method", 'FLIP')
    fijar("flip_ratio", 0.97)
    fijar("gravity", (0.0, 0.0, -9.81))

    # --- ESPUMA, SPRAY Y BURBUJAS (nombres varian segun version) ---
    fijar_primero(["use_spray_particles"], True)
    fijar_primero(["use_foam_particles"], True)
    fijar_primero(["use_bubble_particles"], True)

    fijar("sndparticle_potential_min_wavecrest", 0.3)
    fijar("sndparticle_potential_max_wavecrest", 1.5)
    fijar("sndparticle_potential_min_trappedair", 0.5)
    fijar("sndparticle_potential_max_trappedair", 2.0)
    fijar("sndparticle_potential_min_energy", 0.2)
    fijar("sndparticle_potential_max_energy", 2.5)
    fijar("sndparticle_potential_radius", 2)
    fijar("sndparticle_potential_smoothing", 1)      # no existe en algunas versiones
    fijar("sndparticle_sampling_trappedair", 8)
    fijar("sndparticle_sampling_wavecrest", 8)
    fijar("sndparticle_life_min", 4.0)
    fijar("sndparticle_life_max", 22.0)
    fijar("sndparticle_bubble_buoyancy", 2.0)
    fijar("sndparticle_bubble_drag", 0.8)
    fijar("sndparticle_combined_export", 'OFF')

    # --- Cache ---
    fijar("cache_type", 'MODULAR')
    fijar("cache_frame_start", CONFIG.FRAME_START)
    fijar("cache_frame_end", CONFIG.FRAME_END)
    fijar("cache_directory", "//cache_mar_rojo")
    fijar("cache_data_format", 'OPENVDB')
    fijar("cache_mesh_format", 'BINARY')
    fijar("cache_particle_format", 'OPENVDB')

    if omitidas:
        print("[aviso] Propiedades de fluido no disponibles en tu version de Blender (omitidas):")
        for o in omitidas:
            print("        -", o)

    # El liquido horneado usa el mismo material del agua
    dom.data.materials.append(bpy.data.materials.get("Agua_MarRojo") or crear_material_agua())

    dom.display_type = 'WIRE'
    mover_a_coleccion(dom, coleccion)
    return dom


def crear_colision_suelo(suelo):
    """El suelo actua como obstaculo para el fluido."""
    mod = suelo.modifiers.new("FluidCol", 'FLUID')
    mod.fluid_type = 'EFFECTOR'
    seguro(mod.effector_settings, "effector_type", 'COLLISION')
    seguro(mod.effector_settings, "use_effector", True)
    seguro(mod.effector_settings, "surface_distance", 0.0)


def crear_spray_muros(coleccion):
    """
    SPRAY de agua BRUTAL: salpicaduras que salen disparadas de la BASE y
    la CRESTA de los muros mientras se forman, y una explosion de espuma
    cuando colapsan. Los emisores SIGUEN al muro: se abren (X) y crecen
    (Z) al ritmo de la apertura.
    """
    mat_spray = bpy.data.materials.new("Spray_Muro")
    mat_spray.use_nodes = True
    nt = mat_spray.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    salida = nodes.new("ShaderNodeOutputMaterial")
    emi = nodes.new("ShaderNodeEmission")
    emi.inputs["Color"].default_value = (0.82, 0.90, 0.95, 1.0)
    emi.inputs["Strength"].default_value = 1.2
    links.new(emi.outputs[0], salida.inputs["Surface"])

    emisores = []
    for lado, signo in (("Izq", -1), ("Der", 1)):
        for zona, z0, z1 in (("Base", 4.0, 6.0), ("Cresta", 14.0, 72.0)):
            bpy.ops.mesh.primitive_plane_add(size=1.0, location=(signo * 8, 100, z0))
            em = bpy.context.active_object
            em.name = f"Emisor_Spray_{lado}_{zona}"
            em.scale = (4.0, 450.0, 1.0)
            em.hide_render = True
            # el emisor sigue al muro mientras se abre y crece
            for f, x, z in [(CONFIG.T_APERTURA_INI, signo * 8, z0),
                            (150, signo * 20, (z0 + z1) * 0.55),
                            (CONFIG.T_APERTURA_FIN, signo * 30, z1)]:
                em.location = (x, 100, z)
                em.keyframe_insert(data_path="location", frame=f)
            suavizar_fcurves(em, 'BEZIER')
            em.data.materials.append(mat_spray)
            mover_a_coleccion(em, coleccion)
            emisores.append((em, zona, signo))

    def _sistema(em, nombre, f_ini, f_fin, cantidad, vel_normal, align_xyz,
                 gravedad, vida, tam):
        em.modifiers.new(nombre, 'PARTICLE_SYSTEM')
        ps = em.particle_systems[-1]
        st = ps.settings
        st.name = nombre
        st.count = cantidad
        st.frame_start = f_ini
        st.frame_end = f_fin
        st.lifetime = vida
        st.lifetime_random = 0.5
        st.emit_from = 'FACE'
        st.distribution = 'RANDOM'
        st.normal_factor = vel_normal
        st.object_align_factor = align_xyz
        st.factor_random = 0.6
        st.physics_type = 'NEWTON'
        st.effector_weights.gravity = gravedad
        st.brownian_factor = 2.0
        st.drag_factor = 0.4
        st.particle_size = tam
        st.size_random = 0.9
        st.render_type = 'HALO'

    for em, zona, signo in emisores:
        if zona == "Base":
            _sistema(em, "Spray_Formacion", 40, 340, 6000, 16.0,
                     (signo * 12.0, 0.0, 14.0), 0.35, 45, 0.35)
            _sistema(em, "Spray_Colapso", 340, 560, 8000, 26.0,
                     (signo * 22.0, 0.0, 10.0), 0.5, 70, 0.45)
        else:
            _sistema(em, "Spray_Formacion", 60, 340, 4000, 6.0,
                     (signo * 16.0, 0.0, -8.0), 0.6, 40, 0.3)
            _sistema(em, "Spray_Colapso", 340, 560, 6000, 12.0,
                     (signo * 26.0, 0.0, -12.0), 0.7, 60, 0.4)


def crear_mar_previo(coleccion):
    """
    Mar que existe ANTES de abrirse. Es una capa de agua plana que se
    aplana y desaparece del pasillo durante la apertura, revelando el
    lecho seco. Al colapsar, vuelve a aparecer.
    """
    bpy.ops.mesh.primitive_plane_add(size=1.0)
    mar = bpy.context.active_object
    mar.name = "Mar_Superficie"
    mar.scale = (CONFIG.TAMANO_SUELO * 0.5, CONFIG.LARGO_ESCENA * 0.5, 1)
    mar.location = (0, 0, 2.5)

    mod = mar.modifiers.new("Ocean", 'OCEAN')
    for attr, val in [("geometry_mode", 'GENERATE'), ("resolution", 16),
                      ("spatial_size", 80), ("wave_scale", 1.4),
                      ("choppiness", 1.2), ("wind_velocity", 14.0),
                      ("use_foam", True)]:
        seguro(mod, attr, val)

    mar.data.materials.append(bpy.data.materials.get("Agua_MarRojo") or crear_material_agua())
    mover_a_coleccion(mar, coleccion)
    return mar


# ---------------------------------------------------------------------
#  5. CIELO, ATMOSFERA, NIEBLA Y LUCES
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
#  AGUA BASE PROFUNDA + REFUERZO DE TEXTURAS
# ---------------------------------------------------------------------
def crear_agua_base_profunda(coleccion):
    """
    Plano de agua enorme y oscura bajo toda la escena. Rellena los huecos,
    da el horizonte oceanico y asegura que haya agua por todos lados. Como el
    lecho seco del pasillo queda por debajo del nivel del mar, esta capa
    tambien se ve en los charcos y las zonas bajas.
    """
    bpy.ops.mesh.primitive_plane_add(size=8000, location=(0, 0, -3.5))
    base = bpy.context.active_object
    base.name = "Agua_Base_Profunda"

    ocean = base.modifiers.new("Olas", 'OCEAN')
    for attr, val in [
        ("geometry_mode", 'GENERATE'), ("repeat_x", 10), ("repeat_y", 10),
        ("resolution", 14), ("spatial_size", 160), ("wave_scale", 2.2),
        ("choppiness", 1.4), ("wind_velocity", 20.0),
        ("wave_direction", math.radians(90)), ("depth", 400),
        ("use_foam", True), ("foam_coverage", 0.5),
        ("random_seed", CONFIG.SEED + 3), ("time", 0.0),
    ]:
        seguro(ocean, attr, val)
    animar_tiempo_ocean(ocean, 1.5)

    base.data.materials.append(
        bpy.data.materials.get("Agua_MarRojo") or crear_material_agua())
    mover_a_coleccion(base, coleccion)
    return base


def reforzar_texturas():
    """
    Anade a suelo, montanas y rocas un mapa de detalle extra a escala fina
    y una capa de variacion de color a gran escala, para romper la
    repeticion y que se vea real de cerca y de lejos.
    """
    def anadir_detalle(mat, escala_fina, fuerza, tinte):
        if not mat or not mat.use_nodes:
            return
        nt = mat.node_tree
        nodes, links = nt.nodes, nt.links
        bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
        if bsdf is None:
            return

        coord = nodes.new("ShaderNodeTexCoord")
        coord.location = (-1800, -900)

        # Micro-detalle (poros, granos)
        micro = nodes.new("ShaderNodeTexNoise")
        micro.location = (-1500, -900)
        micro.inputs["Scale"].default_value = escala_fina
        micro.inputs["Detail"].default_value = 16.0
        micro.inputs["Roughness"].default_value = 0.72
        links.new(coord.outputs["Object"], micro.inputs["Vector"])

        # Variacion de color a gran escala (manchas, suciedad, oxido)
        manchas = nodes.new("ShaderNodeTexNoise")
        manchas.location = (-1500, -1150)
        manchas.inputs["Scale"].default_value = 0.02
        manchas.inputs["Detail"].default_value = 5.0
        links.new(coord.outputs["Object"], manchas.inputs["Vector"])

        # Mezclar el tinte sobre el color base ya existente
        mezcla = nodes.new("ShaderNodeMix")
        mezcla.data_type = 'RGBA'
        mezcla.blend_type = 'SOFT_LIGHT'
        mezcla.location = (700, 250)
        mezcla.inputs[0].default_value = fuerza
        try:
            mezcla.inputs[7].default_value = tinte
        except Exception:
            pass

        enlace = bsdf.inputs["Base Color"].links
        if enlace:
            origen = enlace[0].from_socket
            links.new(origen, mezcla.inputs[6])
            links.new(manchas.outputs["Color"], mezcla.inputs[7])
            links.new(mezcla.outputs[2], bsdf.inputs["Base Color"])

        # Bump extra sumado al existente
        bump2 = nodes.new("ShaderNodeBump")
        bump2.location = (900, -450)
        bump2.inputs["Strength"].default_value = 0.35
        bump2.inputs["Distance"].default_value = 0.02
        links.new(micro.outputs["Fac"], bump2.inputs["Height"])
        normal_previa = bsdf.inputs["Normal"].links
        if normal_previa:
            links.new(normal_previa[0].from_socket, bump2.inputs["Normal"])
        links.new(bump2.outputs["Normal"], bsdf.inputs["Normal"])

    anadir_detalle(bpy.data.materials.get("Suelo_Desierto"), 45.0, 0.35, (0.5, 0.4, 0.3, 1))
    anadir_detalle(bpy.data.materials.get("Roca_Montana"), 22.0, 0.30, (0.45, 0.35, 0.28, 1))
    anadir_detalle(bpy.data.materials.get("Roca_Suelta"), 30.0, 0.25, (0.5, 0.45, 0.4, 1))



def crear_cielo():
    """
    Cielo TORMENTOSO y nublado (procedural, en el shader del mundo):
      - degradado oscuro con bruma calida en el horizonte
      - nubes densas en dos capas (masas grandes + detalle) que derivan
      - las nubes se abren cerca del sol (rayos de luz) y sus bordes brillan
      - resplandor calido detras de las montanas del fondo
    La direccion del sol coincide con la luz 'Sol_Principal'.
    """
    mundo = bpy.data.worlds.new("Cielo_Epico")
    bpy.context.scene.world = mundo
    try:
        mundo.use_nodes = True
    except Exception:
        pass
    nt = mundo.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()

    salida = nodes.new("ShaderNodeOutputWorld")
    salida.location = (2600, 0)
    fondo = nodes.new("ShaderNodeBackground")
    fondo.location = (2350, 0)
    fondo.inputs["Strength"].default_value = 1.35

    T = nodo_tiempo(nodes, -1900, 900).outputs[0]

    # Direccion de cada rayo de vista (vector unitario)
    coord = nodes.new("ShaderNodeTexCoord")
    coord.location = (-1900, 0)
    direccion = vmat(nodes, 'NORMALIZE', coord.outputs["Generated"], loc=(-1700, 0))
    sep = nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1500, 0)
    links.new(direccion.outputs[0], sep.inputs["Vector"])
    x, y, z = sep.outputs["X"], sep.outputs["Y"], sep.outputs["Z"]
    z_pos = mat(nodes, 'MAXIMUM', z, 0.0, loc=(-1300, -100))

    # Direccion HACIA el sol (misma que la luz)
    sol_dir = SOL_EULER.to_matrix() @ Vector((0.0, 0.0, -1.0))
    sol_dir = (-sol_dir).normalized()
    cs = vmat(nodes, 'DOT_PRODUCT', direccion.outputs[0],
              (sol_dir.x, sol_dir.y, sol_dir.z), loc=(-1300, 300)).outputs[1]
    cs_pos = mat(nodes, 'MAXIMUM', cs, 0.0, loc=(-1100, 300))

    # --- Degradado del cielo (oscuro arriba, bruma calida en el horizonte) ---
    cielo_col = rampa_color(nodes, z_pos, [
        (0.00, (0.36, 0.28, 0.21, 1.0)),
        (0.05, (0.24, 0.20, 0.18, 1.0)),
        (0.28, (0.075, 0.085, 0.105, 1.0)),
        (1.00, (0.020, 0.028, 0.045, 1.0)),
    ], loc=(-1000, 0))

    # --- Resplandor del sol y del fondo del pasillo ---
    glow_amplio = mat(nodes, 'POWER', cs_pos, 6.0, loc=(-900, 300))
    glow_nucleo = mat(nodes, 'POWER', cs_pos, 90.0, loc=(-900, 200))
    glow_sol = mat(nodes, 'ADD', mat(nodes, 'MULTIPLY', glow_amplio, 0.55),
                   mat(nodes, 'MULTIPLY', glow_nucleo, 2.5), loc=(-700, 250))
    a_fondo = mat(nodes, 'MAXIMUM', y, 0.0)
    glow_fondo = mat(nodes, 'MULTIPLY', mat(nodes, 'POWER', a_fondo, 5.0),
                     mat(nodes, 'SUBTRACT', 1.0, rango(nodes, z_pos, 0.0, 0.30)),
                     loc=(-700, 100))

    def _color_x(rgb, esc):
        n = nodes.new("ShaderNodeVectorMath")
        n.operation = 'SCALE'
        n.inputs[0].default_value = rgb
        n.location = (-500, 250)
        links.new(esc, n.inputs["Scale"])
        return n.outputs[0]

    luz_sol = _color_x((1.0, 0.62, 0.30), glow_sol)
    luz_fondo = _color_x((0.95, 0.55, 0.28), mat(nodes, 'MULTIPLY', glow_fondo, 0.45))
    cielo_1 = vmat(nodes, 'ADD', cielo_col, luz_sol, loc=(-300, 200))
    cielo_total = vmat(nodes, 'ADD', cielo_1.outputs[0], luz_fondo, loc=(-100, 200)).outputs[0]

    # --- NUBES: proyeccion plana (perspectiva correcta hacia el horizonte) ---
    denom = mat(nodes, 'ADD', z_pos, 0.10, loc=(-1300, -400))
    px = mat(nodes, 'DIVIDE', x, denom, loc=(-1100, -400))
    py = mat(nodes, 'DIVIDE', y, denom, loc=(-1100, -500))

    def _coord_nube(esc, vx, vy, vz):
        n = nodes.new("ShaderNodeCombineXYZ")
        n.location = (-900, -450)
        _in(n, 0, mat(nodes, 'ADD', mat(nodes, 'MULTIPLY', px, esc), mat(nodes, 'MULTIPLY', T, vx)))
        _in(n, 1, mat(nodes, 'ADD', mat(nodes, 'MULTIPLY', py, esc), mat(nodes, 'MULTIPLY', T, vy)))
        _in(n, 2, mat(nodes, 'MULTIPLY', T, vz))
        return n.outputs[0]

    def _ruido_nube(esc, detalle, rugosidad, vx, vy, vz, y_loc):
        n = nodes.new("ShaderNodeTexNoise")
        n.location = (-650, y_loc)
        n.inputs["Scale"].default_value = 1.0
        n.inputs["Detail"].default_value = detalle
        n.inputs["Roughness"].default_value = rugosidad
        links.new(_coord_nube(esc, vx, vy, vz), n.inputs["Vector"])
        return n.outputs["Fac"]

    masas = _ruido_nube(1.25, 7.0, 0.58, 0.020, 0.008, 0.010, -300)      # masas grandes
    detalle = _ruido_nube(5.0, 9.0, 0.60, 0.035, 0.014, 0.020, -600)     # relieve fino

    mezcla_n = mat(nodes, 'ADD', mat(nodes, 'MULTIPLY', masas, 0.72),
                   mat(nodes, 'MULTIPLY', detalle, 0.28), loc=(-350, -450))
    cobertura = rango(nodes, mezcla_n, 0.40, 0.64, loc=(-150, -450))

    # las nubes se abren cerca del sol y se funden con la bruma del horizonte
    hueco_sol = mat(nodes, 'SUBTRACT', 1.0,
                    mat(nodes, 'MULTIPLY', mat(nodes, 'POWER', cs_pos, 8.0), 0.85))
    horizonte = rango(nodes, z_pos, 0.0, 0.13)
    densidad = mat(nodes, 'MULTIPLY', mat(nodes, 'MULTIPLY', cobertura, hueco_sol),
                   horizonte, loc=(100, -450))

    # iluminacion de la nube: nucleo oscuro, bordes y lado del sol brillantes
    iluminacion = mat(nodes, 'ADD',
                      mat(nodes, 'ADD',
                          mat(nodes, 'MULTIPLY', mat(nodes, 'SUBTRACT', 1.0, cobertura), 0.55),
                          mat(nodes, 'MULTIPLY', mat(nodes, 'POWER', cs_pos, 3.0), 0.9)),
                      mat(nodes, 'MULTIPLY', detalle, 0.22),
                      clamp=True, loc=(100, -650))
    color_nube = rampa_color(nodes, iluminacion, [
        (0.00, (0.016, 0.018, 0.024, 1.0)),
        (0.40, (0.085, 0.088, 0.100, 1.0)),
        (0.72, (0.360, 0.320, 0.285, 1.0)),
        (1.00, (0.950, 0.720, 0.450, 1.0)),
    ], loc=(400, -650))

    mezcla = nodes.new("ShaderNodeMix")
    mezcla.data_type = 'RGBA'
    mezcla.location = (1900, 0)
    links.new(mat(nodes, 'MULTIPLY', densidad, 0.97), mezcla.inputs[0])
    links.new(cielo_total, mezcla.inputs[6])
    links.new(color_nube, mezcla.inputs[7])
    links.new(mezcla.outputs[2], fondo.inputs["Color"])
    links.new(fondo.outputs["Background"], salida.inputs["Surface"])


def crear_niebla_volumetrica(coleccion):
    """
    Cubo de volumen con bruma y polvo. Da profundidad atmosferica y
    hace que las montanas lejanas se difuminen (perspectiva aerea).
    """
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    caja = bpy.context.active_object
    caja.name = "Niebla_Volumen"
    caja.scale = (1500, 1500, 110)
    caja.location = (0, 300, 90)
    caja.display_type = 'WIRE'

    mat_ = bpy.data.materials.new("Volumen_Bruma")
    mat_.use_nodes = True
    nt = mat_.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()

    salida = nodes.new("ShaderNodeOutputMaterial")
    salida.location = (800, 0)

    scat = nodes.new("ShaderNodeVolumeScatter")
    scat.location = (500, 100)
    scat.inputs["Color"].default_value = (0.88, 0.75, 0.62, 1.0)
    scat.inputs["Anisotropy"].default_value = 0.55

    coord = nodes.new("ShaderNodeTexCoord")
    coord.location = (-500, 0)
    ruido = nodes.new("ShaderNodeTexNoise")
    ruido.location = (-250, 0)
    ruido.inputs["Scale"].default_value = 0.012
    ruido.inputs["Detail"].default_value = 5.0
    links.new(coord.outputs["Object"], ruido.inputs["Vector"])

    dens = nodes.new("ShaderNodeMapRange")
    dens.location = (0, 0)
    dens.inputs["From Min"].default_value = 0.35
    dens.inputs["From Max"].default_value = 0.75
    dens.inputs["To Min"].default_value = 0.0
    dens.inputs["To Max"].default_value = 0.0065
    links.new(ruido.outputs["Fac"], dens.inputs["Value"])
    links.new(dens.outputs["Result"], scat.inputs["Density"])
    links.new(scat.outputs[0], salida.inputs["Volume"])

    caja.data.materials.append(mat_)
    mover_a_coleccion(caja, coleccion)
    return caja


def crear_luces(coleccion):
    """Sol dramatico entre nubes + relleno frio + luz de rebote calida."""
    # Sol (su direccion es SOL_EULER: la misma que usa el cielo)
    bpy.ops.object.light_add(type='SUN', location=(120, -180, 90))
    sol = bpy.context.active_object
    sol.name = "Sol_Principal"
    sol.data.energy = 8.0
    sol.data.color = (1.0, 0.80, 0.58)
    sol.data.angle = math.radians(2.5)       # sombras mas suaves (cielo nublado)
    sol.rotation_euler = SOL_EULER.copy()
    mover_a_coleccion(sol, coleccion)

    # Relleno azulado del cielo
    bpy.ops.object.light_add(type='AREA', location=(-100, -120, 140))
    relleno = bpy.context.active_object
    relleno.name = "Relleno_Cielo"
    relleno.data.energy = 9000
    relleno.data.color = (0.55, 0.70, 1.0)
    relleno.data.size = 180
    relleno.rotation_euler = Euler((math.radians(55), 0, math.radians(30)))
    mover_a_coleccion(relleno, coleccion)

    # Rebote calido del suelo
    bpy.ops.object.light_add(type='AREA', location=(0, -60, 2))
    rebote = bpy.context.active_object
    rebote.name = "Rebote_Suelo"
    rebote.data.energy = 6000
    rebote.data.color = (1.0, 0.65, 0.40)
    rebote.data.size = 160
    rebote.rotation_euler = Euler((math.radians(180), 0, 0))
    mover_a_coleccion(rebote, coleccion)


def crear_relampagos(coleccion):
    """
    RAYOS de tormenta BRUTALES: geometria de relampago quebrada con
    emision + luz de destello sincronizada que ilumina los muros de agua.
    Varios caen durante la tormenta y mas durante el colapso; dos caen
    DETRAS de los muros para iluminarlos desde adentro. Cada rayo
    parpadea 2-3 veces como un relampago real.
    """
    rnd = random.Random(CONFIG.SEED + 500)

    mat_base = bpy.data.materials.new("Rayo_Emision")
    mat_base.use_nodes = True
    nt = mat_base.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    salida = nodes.new("ShaderNodeOutputMaterial")
    emi_base = nodes.new("ShaderNodeEmission")
    emi_base.inputs["Color"].default_value = (0.75, 0.85, 1.0, 1.0)
    emi_base.inputs["Strength"].default_value = 0.0
    links.new(emi_base.outputs[0], salida.inputs["Surface"])

    # (frame del golpe, x, y, energia de la luz del destello)
    golpes = [
        (90, -260, -80, 250000),
        (150, 300, 120, 300000),
        (215, -80, 420, 280000),     # detras de los muros: los ilumina desde adentro
        (285, 180, 260, 320000),     # detras de los muros
        (360, -200, 60, 380000),
        (430, 120, 330, 420000),
        (510, -60, 180, 380000),
    ]

    for i, (f0, bx, by, energia) in enumerate(golpes):
        mat_i = mat_base.copy()
        emi = next(n for n in mat_i.node_tree.nodes if n.type == 'EMISSION')

        # --- geometria del rayo: linea quebrada del cielo a la tierra ---
        n_seg = rnd.randint(8, 12)
        puntos = []
        x, y = bx, by
        for s in range(n_seg + 1):
            z = 460 - (460 - 10) * (s / n_seg)
            puntos.append((x, y, z))
            x += rnd.uniform(-28, 28)
            y += rnd.uniform(-28, 28)
        curva = bpy.data.curves.new(f"Rayo_Curva_{i:02d}", type='CURVE')
        curva.dimensions = '3D'
        curva.bevel_depth = 0.9
        curva.bevel_resolution = 1
        spline = curva.splines.new('POLY')
        spline.points.add(len(puntos) - 1)
        for j, p in enumerate(puntos):
            spline.points[j].co = (p[0], p[1], p[2], 1.0)
        # una ramificacion
        ram = curva.splines.new('POLY')
        base = puntos[rnd.randint(2, 4)]
        ram.points.add(3)
        rx, ry = base[0], base[1]
        for j in range(4):
            ram.points[j].co = (rx, ry, base[2] - j * 55, 1.0)
            rx += rnd.uniform(-35, 35)
            ry += rnd.uniform(-35, 35)

        rayo = bpy.data.objects.new(f"Rayo_{i:02d}", curva)
        bpy.context.scene.collection.objects.link(rayo)
        rayo.data.materials.append(mat_i)
        mover_a_coleccion(rayo, coleccion)

        # --- luz del destello ---
        bpy.ops.object.light_add(type='POINT', location=(bx, by, 200))
        luz = bpy.context.active_object
        luz.name = f"Destello_Rayo_{i:02d}"
        luz.data.energy = 0.0
        luz.data.color = (0.75, 0.85, 1.0)
        try:
            luz.data.use_shadow = False
        except Exception:
            pass
        mover_a_coleccion(luz, coleccion)

        # --- parpadeo: aparece, golpe doble, se apaga ---
        # (render Y viewport sincronizados: ves lo mismo que saldra en el render)
        for attr, f, valor in (("hide_render", f0 - 2, True),
                               ("hide_render", f0, False),
                               ("hide_render", f0 + 10, True),
                               ("hide_viewport", f0 - 2, True),
                               ("hide_viewport", f0, False),
                               ("hide_viewport", f0 + 10, True)):
            setattr(rayo, attr, valor)
            rayo.keyframe_insert(data_path=attr, frame=f)

        for f, e in [(f0, 0.0), (f0 + 2, 70.0), (f0 + 4, 6.0),
                     (f0 + 6, 55.0), (f0 + 10, 0.0)]:
            emi.inputs["Strength"].default_value = e
            emi.inputs["Strength"].keyframe_insert(data_path="default_value", frame=f)

        for f, e in [(f0, 0.0), (f0 + 2, energia), (f0 + 4, energia * 0.12),
                     (f0 + 6, energia * 0.8), (f0 + 10, 0.0)]:
            luz.data.energy = e
            luz.data.keyframe_insert(data_path="energy", frame=f)


# ---------------------------------------------------------------------
#  6. CAMARA CINEMATOGRAFICA
# ---------------------------------------------------------------------
def crear_camara(coleccion):
    """
    Recorrido en tres actos (ajustado a los muros gigantes):
      Acto 1 (1-260):    el mar se abre; la camara avanza hacia el pasillo
      Acto 2 (260-340):  travelling lento entre los muros
      Acto 3 (340-600):  la camara sube y retrocede mientras todo colapsa
    """
    bpy.ops.object.camera_add(location=(0, -285, 11))
    cam = bpy.context.active_object
    cam.name = "Camara_Epica"
    bpy.context.scene.camera = cam

    cd = cam.data
    cd.lens = 24
    cd.sensor_width = 36
    cd.clip_start = 0.5
    cd.clip_end = 5000
    seguro(cd.dof, "use_dof", True)
    seguro(cd.dof, "aperture_fstop", 2.8)
    seguro(cd.dof, "focus_distance", 120.0)

    # Objetivo al que apunta la camara
    bpy.ops.object.empty_add(type='SPHERE', location=(0, 90, 18))
    objetivo = bpy.context.active_object
    objetivo.name = "Camara_Objetivo"
    objetivo.empty_display_size = 3

    trk = cam.constraints.new('TRACK_TO')
    trk.target = objetivo
    trk.track_axis = 'TRACK_NEGATIVE_Z'
    trk.up_axis = 'UP_Y'

    # --- Trayectoria de la camara ---
    ruta = [
        # frame, posicion camara
        (1,                            (  0, -285, 11)),
        (CONFIG.T_APERTURA_INI,        (  0, -268, 12)),
        (150,                          (  0, -210, 15)),
        (CONFIG.T_APERTURA_FIN,        (  0, -110, 12)),
        (CONFIG.T_COLAPSO_INI,         (  0,  -70, 14)),
        (420,                          (  0, -150, 70)),
        (500,                          (  0, -230, 115)),
        (CONFIG.FRAME_END,             (  0, -310, 150)),
    ]
    for frame, pos in ruta:
        cam.location = pos
        cam.keyframe_insert(data_path="location", frame=frame)

    # --- Trayectoria del objetivo ---
    ruta_obj = [
        (1,                            (0,  90, 18)),
        (CONFIG.T_APERTURA_FIN,        (0, 170, 24)),
        (CONFIG.T_COLAPSO_INI,         (0, 150, 25)),
        (420,                          (0, 120, 10)),
        (CONFIG.FRAME_END,             (0,  80, 0)),
    ]
    for frame, pos in ruta_obj:
        objetivo.location = pos
        objetivo.keyframe_insert(data_path="location", frame=frame)

    # --- Distancia focal: zoom sutil dramatico ---
    for frame, lente in [(1, 24), (CONFIG.T_APERTURA_FIN, 28),
                         (CONFIG.T_COLAPSO_INI, 20), (CONFIG.FRAME_END, 30)]:
        cd.lens = lente
        cd.keyframe_insert(data_path="lens", frame=frame)

    # --- Enfoque dinamico ---
    for frame, dist in [(1, 300), (CONFIG.T_APERTURA_FIN, 200),
                        (CONFIG.T_COLAPSO_INI, 160), (CONFIG.FRAME_END, 300)]:
        cd.dof.focus_distance = dist
        cd.dof.keyframe_insert(data_path="focus_distance", frame=frame)

    suavizar_fcurves(cam, 'BEZIER')
    suavizar_fcurves(objetivo, 'BEZIER')

    # --- Sacudida (shake) durante el colapso: ruido en la posicion ---
    for fc in obtener_fcurves(cam):
        if fc.data_path == "location":
            idx = fc.array_index
            mod = fc.modifiers.new('NOISE')
            mod.scale = 6.0
            mod.strength = 0.12 if idx != 2 else 0.20
            mod.phase = random.uniform(0, 100)
            mod.use_restricted_range = True
            mod.frame_start = CONFIG.T_APERTURA_INI
            mod.frame_end = CONFIG.FRAME_END
            mod.blend_in = 25
            mod.blend_out = 25

    mover_a_coleccion(cam, coleccion)
    mover_a_coleccion(objetivo, coleccion)
    return cam


def crear_volumen_submarino(coleccion):
    """
    Volumen azul que aparece cuando la camara baja al agua: tine la vista
    submarina como agua real (se enciende con la inundacion y se apaga al final).
    """
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    caja = bpy.context.active_object
    caja.name = "Volumen_Submarino"
    caja.scale = (90, 700, 30)
    caja.location = (0, 150, 10)
    caja.display_type = 'WIRE'

    mat_ = bpy.data.materials.new("Volumen_AguaSub")
    mat_.use_nodes = True
    nt = mat_.node_tree
    nodes, links = nt.nodes, nt.links
    nodes.clear()
    salida = nodes.new("ShaderNodeOutputMaterial")
    salida.location = (600, 0)
    scat = nodes.new("ShaderNodeVolumeScatter")
    scat.location = (300, 0)
    scat.inputs["Color"].default_value = (0.12, 0.42, 0.55, 1.0)
    scat.inputs["Anisotropy"].default_value = 0.6
    scat.inputs["Density"].default_value = 0.0
    links.new(scat.outputs[0], salida.inputs["Volume"])
    caja.data.materials.append(mat_)

    # Aparece con la inundacion, se mantiene y se apaga al final
    t0 = CONFIG.T_SUBMARINA_INI
    for f, d in ((t0 - 30, 0.0), (t0 + 40, 0.035), (CONFIG.FRAME_END - 40, 0.035),
                 (CONFIG.FRAME_END, 0.0)):
        scat.inputs["Density"].default_value = d
        scat.inputs["Density"].keyframe_insert(data_path="default_value", frame=f)

    mover_a_coleccion(caja, coleccion)
    return caja


def crear_camara_submarina(col_camara, col_atmos):
    """
    Segunda camara: BAJO EL AGUA. Entra cuando el colapso inunda el pasillo
    (T_SUBMARINA_INI) y avanza CON la ola, grabando la inundacion desde dentro
    hasta el final. El cambio de camara se hace con marcadores de camara en
    la linea de tiempo (aerea -> submarina).
    """
    escena = bpy.context.scene
    t0 = CONFIG.T_SUBMARINA_INI

    bpy.ops.object.camera_add(location=(0, -60, 3.0))
    cam = bpy.context.active_object
    cam.name = "Camara_Submarina"
    cd = cam.data
    cd.lens = 18                      # gran angular bajo el agua
    cd.sensor_width = 36
    cd.clip_start = 0.3
    cd.clip_end = 5000
    seguro(cd.dof, "use_dof", True)
    seguro(cd.dof, "aperture_fstop", 2.0)
    seguro(cd.dof, "focus_distance", 40.0)

    bpy.ops.object.empty_add(type='SPHERE', location=(0, 60, 4))
    objetivo = bpy.context.active_object
    objetivo.name = "Objetivo_Submarino"
    objetivo.empty_display_size = 3

    trk = cam.constraints.new('TRACK_TO')
    trk.target = objetivo
    trk.track_axis = 'TRACK_NEGATIVE_Z'
    trk.up_axis = 'UP_Y'

    # La camara avanza CON la inundacion, a poca altura, dentro del agua
    for frame, pos in [(t0, (0, -60, 3.0)), (t0 + 60, (0, 20, 2.5)),
                       (t0 + 120, (0, 100, 3.0)), (CONFIG.FRAME_END, (0, 180, 4.0))]:
        cam.location = pos
        cam.keyframe_insert(data_path="location", frame=frame)
    for frame, pos in [(t0, (0, 60, 4.0)), (t0 + 100, (0, 160, 5.0)),
                       (CONFIG.FRAME_END, (0, 260, 6.0))]:
        objetivo.location = pos
        objetivo.keyframe_insert(data_path="location", frame=frame)

    suavizar_fcurves(cam, 'BEZIER')
    suavizar_fcurves(objetivo, 'BEZIER')

    # Sacudida bajo el agua (la ola empuja la camara)
    for fc in obtener_fcurves(cam):
        if fc.data_path == "location":
            idx = fc.array_index
            mod = fc.modifiers.new('NOISE')
            mod.scale = 4.0
            mod.strength = 0.25 if idx != 2 else 0.35
            mod.phase = random.uniform(0, 100)
            mod.use_restricted_range = True
            mod.frame_start = t0
            mod.frame_end = CONFIG.FRAME_END
            mod.blend_in = 20
            mod.blend_out = 20

    # Los marcadores de cambio de camara (los 7 planos del cortometraje)
    # se configuran en configurar_planos_cortometraje(), al final.

    crear_volumen_submarino(col_atmos)
    mover_a_coleccion(cam, col_camara)
    mover_a_coleccion(objetivo, col_camara)
    return cam


def _camara_con_objetivo(nombre, lente, coleccion):
    """Crea una camara + empty objetivo con TRACK_TO. Devuelve (cam, objetivo, data)."""
    bpy.ops.object.camera_add(location=(0, 0, 10))
    cam = bpy.context.active_object
    cam.name = nombre
    cd = cam.data
    cd.lens = lente
    cd.sensor_width = 36
    cd.clip_start = 0.5
    cd.clip_end = 5000
    seguro(cd.dof, "use_dof", True)
    seguro(cd.dof, "aperture_fstop", 2.8)
    bpy.ops.object.empty_add(type='SPHERE', location=(0, 0, 10))
    objetivo = bpy.context.active_object
    objetivo.name = nombre + "_Objetivo"
    objetivo.empty_display_size = 3
    trk = cam.constraints.new('TRACK_TO')
    trk.target = objetivo
    trk.track_axis = 'TRACK_NEGATIVE_Z'
    trk.up_axis = 'UP_Y'
    mover_a_coleccion(cam, coleccion)
    mover_a_coleccion(objetivo, coleccion)
    return cam, objetivo, cd


def _ruta_clave(obj, data_path, claves):
    for frame, valor in claves:
        if data_path == "location":
            obj.location = valor
            obj.keyframe_insert(data_path="location", frame=frame)
        elif data_path == "lens":
            obj.lens = valor
            obj.keyframe_insert(data_path="lens", frame=frame)
        elif data_path == "focus_distance":
            obj.dof.focus_distance = valor
            obj.dof.keyframe_insert(data_path="focus_distance", frame=frame)


def crear_camaras_cortometraje(coleccion):
    """
    CORTOMETRAJE: 4 camaras nuevas para cubrir los planos que faltaban.
    Cada una con su recorrido keyframeado y su objetivo con TRACK_TO.
    El cambio entre planos lo hacen los marcadores (configurar_planos_cortometraje).
    """
    # --- PLANO 2: dolly lateral junto al muro izquierdo mientras sube ---
    cam, obj, cd = _camara_con_objetivo("Cam_Apertura_Lateral", 35, coleccion)
    _ruta_clave(cam, "location", [
        (70, (-150, -180, 35)), (105, (-95, 40, 48)), (140, (-55, 260, 55)),
    ])
    _ruta_clave(obj, "location", [
        (70, (-35, -100, 30)), (140, (-35, 150, 45)),
    ])
    _ruta_clave(cd, "focus_distance", [(70, 90), (140, 90)])
    suavizar_fcurves(cam, 'BEZIER')
    suavizar_fcurves(obj, 'BEZIER')

    # --- PLANO 3: persecucion de pajaros (vuela con la bandada A) ---
    cam, obj, cd = _camara_con_objetivo("Cam_Pajaros", 50, coleccion)
    _ruta_clave(cam, "location", [
        (140, (-150, -10, 130)), (175, (-185, 60, 150)), (210, (-220, 130, 170)),
    ])
    _ruta_clave(obj, "location", [
        (140, (-200, 60, 100)), (210, (-270, 200, 140)),
    ])
    _ruta_clave(cd, "focus_distance", [(140, 70), (210, 70)])
    suavizar_fcurves(cam, 'BEZIER')
    suavizar_fcurves(obj, 'BEZIER')

    # --- PLANO 4: dentro del pasillo a nivel de suelo (el plano de escala) ---
    cam, obj, cd = _camara_con_objetivo("Cam_Pasillo", 24, coleccion)
    _ruta_clave(cam, "location", [
        (210, (-12, -120, 6)), (250, (8, 30, 7)), (290, (0, 180, 9)),
    ])
    _ruta_clave(obj, "location", [
        (210, (0, 60, 40)), (290, (0, 320, 45)),
    ])
    _ruta_clave(cd, "focus_distance", [(210, 120), (290, 120)])
    suavizar_fcurves(cam, 'BEZIER')
    suavizar_fcurves(obj, 'BEZIER')

    # --- PLANO 6: cerca de la esquina donde cae el primer trozo ---
    cam, obj, cd = _camara_con_objetivo("Cam_Colapso", 40, coleccion)
    _ruta_clave(cam, "location", [
        (345, (95, -70, 58)), (378, (65, 0, 48)), (410, (45, 70, 42)),
    ])
    _ruta_clave(obj, "location", [
        (345, (-30, 40, 35)), (410, (-30, 60, 25)),
    ])
    _ruta_clave(cd, "focus_distance", [(345, 110), (410, 90)])
    suavizar_fcurves(cam, 'BEZIER')
    suavizar_fcurves(obj, 'BEZIER')
    # sacudida fuerte cuando el muro se desploma
    for fc in obtener_fcurves(cam):
        if fc.data_path == "location":
            idx = fc.array_index
            mod = fc.modifiers.new('NOISE')
            mod.scale = 5.0
            mod.strength = 0.5 if idx != 2 else 0.7
            mod.phase = random.uniform(0, 100)
            mod.use_restricted_range = True
            mod.frame_start = 345
            mod.frame_end = 460
            mod.blend_in = 10
            mod.blend_out = 25


def configurar_planos_cortometraje():
    """
    CORTOMETRAJE: 7 planos con cambio AUTOMATICO de camara por marcadores.
      1. Establecimiento aereo ....... Camara_Epica ....... frames 1-70
      2. Dolly lateral del muro ....... Cam_Apertura_Lateral  frames 70-140
      3. Persecucion de pajaros ....... Cam_Pajaros ......... frames 140-210
      4. Pasillo a nivel de suelo ..... Cam_Pasillo ......... frames 210-290
      5. Colapso en gran angular ...... Camara_Epica ........ frames 290-345
      6. Caida del muro (de cerca) .... Cam_Colapso ......... frames 345-410
      7. Inundacion submarina ......... Camara_Submarina .... frames 410-600
    """
    escena = bpy.context.scene
    for mk in list(escena.timeline_markers):
        if mk.name in ("Aerea", "Submarina") or mk.name.startswith("Plano"):
            escena.timeline_markers.remove(mk)
    planos = [
        (1, "Plano1_Establecimiento", "Camara_Epica"),
        (70, "Plano2_Muro_Lateral", "Cam_Apertura_Lateral"),
        (140, "Plano3_Pajaros", "Cam_Pajaros"),
        (210, "Plano4_Pasillo", "Cam_Pasillo"),
        (290, "Plano5_Colapso_Amplio", "Camara_Epica"),
        (345, "Plano6_Caida_Muro", "Cam_Colapso"),
        (410, "Plano7_Submarina", "Camara_Submarina"),
    ]
    for f, nombre, cam_nombre in planos:
        cam = bpy.data.objects.get(cam_nombre)
        if cam is None:
            print(f"[aviso] No existe la camara {cam_nombre}")
            continue
        mk = escena.timeline_markers.new(nombre, frame=f)
        mk.camera_data = cam
    epica = bpy.data.objects.get("Camara_Epica")
    if epica is not None:
        escena.camera = epica
    print("[ok] 7 planos del cortometraje configurados (cambio auto de camara).")


# ---------------------------------------------------------------------
#  7. EFECTOS EXTRA: POLVO, PIEDRAS Y AGRIETAMIENTO
# ---------------------------------------------------------------------
def crear_polvo_flotante(coleccion):
    """Sistema de particulas de polvo/arena arrastrado por el viento."""
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(0, 0, 8))
    em = bpy.context.active_object
    em.name = "Emisor_Polvo"
    em.scale = (700, 500, 1)
    em.hide_render = True

    em.modifiers.new("Part", 'PARTICLE_SYSTEM')
    ps = em.particle_systems[0]
    st = ps.settings
    st.count = 90000
    st.frame_start = CONFIG.FRAME_START
    st.frame_end = CONFIG.FRAME_END
    st.lifetime = 300
    st.lifetime_random = 0.6
    st.emit_from = 'FACE'
    st.normal_factor = 0.0
    st.object_align_factor = (14.0, 3.0, 1.2)     # viento lateral
    st.physics_type = 'NEWTON'
    st.effector_weights.gravity = 0.0
    st.brownian_factor = 3.0
    st.drag_factor = 0.5
    st.particle_size = 0.05
    st.size_random = 0.8
    st.render_type = 'HALO'

    mat_ = bpy.data.materials.new("Polvo_Halo")
    mat_.use_nodes = True
    nodes = mat_.node_tree.nodes
    nodes.clear()
    salida = nodes.new("ShaderNodeOutputMaterial")
    emision = nodes.new("ShaderNodeEmission")
    emision.inputs["Color"].default_value = (0.9, 0.78, 0.6, 1.0)
    emision.inputs["Strength"].default_value = 0.6
    mat_.node_tree.links.new(emision.outputs[0], salida.inputs["Surface"])
    em.data.materials.append(mat_)

    mover_a_coleccion(em, coleccion)
    return em


def crear_niebla_impacto(coleccion):
    """
    NIEBLA DE IMPACTO: cuando el colapso inunda el pasillo, una nube de
    bruma ENORME avanza con la ola. Son esferas de volumen que crecen,
    se desplazan con la inundacion (+Y) y se disipan al final.
    """
    rnd = random.Random(CONFIG.SEED + 777)
    for i in range(10):
        f0 = 355 + i * 16
        x0 = rnd.uniform(-45, 45)
        y0 = rnd.uniform(-120, 60)

        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1.0,
                                              location=(x0, y0, 10))
        nube = bpy.context.active_object
        nube.name = f"Niebla_Impacto_{i:02d}"
        nube.display_type = 'WIRE'

        mat_ = bpy.data.materials.new(f"Volumen_Impacto_{i:02d}")
        mat_.use_nodes = True
        nt = mat_.node_tree
        nodes, links = nt.nodes, nt.links
        nodes.clear()
        salida = nodes.new("ShaderNodeOutputMaterial")
        scat = nodes.new("ShaderNodeVolumeScatter")
        scat.inputs["Color"].default_value = (0.72, 0.80, 0.86, 1.0)
        scat.inputs["Anisotropy"].default_value = 0.4
        scat.inputs["Density"].default_value = 0.0
        links.new(scat.outputs[0], salida.inputs["Volume"])
        nube.data.materials.append(mat_)

        s0 = rnd.uniform(28, 42)
        # crece y avanza con la ola, sube un poco
        for f, k in [(f0, 0.0), (f0 + 110, 1.0)]:
            nube.location = (x0 * (1 - k * 0.3), y0 + k * 170, 10 + k * 14)
            nube.scale = (s0 * (1 + k * 1.1), s0 * 0.8 * (1 + k * 1.1),
                          s0 * 0.45 * (1 + k * 0.8))
            nube.keyframe_insert(data_path="location", frame=f)
            nube.keyframe_insert(data_path="scale", frame=f)
        suavizar_fcurves(nube, 'BEZIER')

        for f, d in [(f0, 0.0), (f0 + 25, 0.055), (f0 + 90, 0.055), (f0 + 140, 0.0)]:
            scat.inputs["Density"].default_value = d
            scat.inputs["Density"].keyframe_insert(data_path="default_value", frame=f)

        mover_a_coleccion(nube, coleccion)


def crear_pajaro_base(nombre, fase, mat):
    """Pajaro simple (cuerpo + 2 alas) con shape key de aleteo animado."""
    verts = [
        (0.0, 0.7, 0.0),     # 0 pico
        (0.0, -0.7, 0.0),    # 1 cola
        (-0.55, 0.1, 0.0),   # 2 ala izq media
        (-1.4, 0.0, 0.0),    # 3 ala izq punta
        (0.55, 0.1, 0.0),    # 4 ala der media
        (1.4, 0.0, 0.0),     # 5 ala der punta
    ]
    caras = [(0, 3, 2), (0, 2, 1), (0, 1, 4), (0, 4, 5)]
    malla = bpy.data.meshes.new(nombre + "_Malla")
    malla.from_pydata(verts, [], caras)
    malla.update()
    obj = bpy.data.objects.new(nombre, malla)
    bpy.context.scene.collection.objects.link(obj)

    obj.shape_key_add(name="Basis", from_mix=False)
    sk = obj.shape_key_add(name="Aleteo", from_mix=False)
    for idx, dz in ((2, 0.35), (3, 0.95), (4, 0.35), (5, 0.95)):
        sk.data[idx].co.z += dz
    # aleteo continuo, cada pajaro con su fase
    drv = sk.driver_add("value")
    drv.driver.type = 'SCRIPTED'
    drv.driver.expression = f"0.5+0.5*sin(frame*0.85+{fase:.2f})"

    obj.data.materials.append(mat)
    return obj


def crear_pajaros(coleccion):
    """
    PAJAROS HUYENDO: 3 bandadas (24 pajaros) que escapan cuando el mar
    se abre. Cada pajaro vuela por su propia curva con desfase lateral,
    aletea con su propia fase y aparece cuando empieza la apertura.
    Dan escala y vida al cielo.
    """
    mat_pajaro = bpy.data.materials.new("Pajaro_Silueta")
    mat_pajaro.use_nodes = True
    bsdf = mat_pajaro.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.02, 0.02, 0.025, 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0

    rnd = random.Random(CONFIG.SEED + 300)
    # (punto inicial, punto de control, punto final) de cada bandada
    bandadas = [
        ((-140, -60, 70), (-230, 130, 120), (-340, 330, 175)),
        ((150, -90, 80), (250, 110, 125), (370, 350, 185)),
        ((0, -140, 60), (-50, 90, 135), (-100, 390, 205)),
    ]
    n = 0
    for p0, pc, p1 in bandadas:
        for k in range(8):
            pajaro = crear_pajaro_base(f"Pajaro_{n:02d}",
                                       rnd.uniform(0, 6.28), mat_pajaro)
            s = rnd.uniform(1.7, 2.5)
            pajaro.scale = (s, s, s)
            ini = int(40 + k * 6 + rnd.uniform(0, 12))
            dur = int(rnd.uniform(200, 260))
            # desfase lateral: no vuelan en fila india
            off = np.array([rnd.uniform(-25, 25), rnd.uniform(-20, 20),
                            rnd.uniform(-8, 14)])
            p0a = np.array(p0) + off
            pca = np.array(pc) + off * 1.5
            p1a = np.array(p1) + off * 2.0
            # curva de vuelo (bezier cuadratica) con keyframes
            for f in range(ini, ini + dur + 1, 15):
                t = (f - ini) / dur
                pos = (1 - t) ** 2 * p0a + 2 * (1 - t) * t * pca + t ** 2 * p1a
                pajaro.location = pos.tolist()
                pajaro.keyframe_insert(data_path="location", frame=f)
            suavizar_fcurves(pajaro, 'BEZIER')
            # aparecen cuando el mar empieza a abrirse
            pajaro.hide_render = True
            pajaro.keyframe_insert(data_path="hide_render", frame=ini - 5)
            pajaro.hide_render = False
            pajaro.keyframe_insert(data_path="hide_render", frame=ini)
            mover_a_coleccion(pajaro, coleccion)
            n += 1
    return n


def crear_rocas_dispersas(coleccion, cantidad=220):
    """Piedras y cantos rodados repartidos por el lecho seco."""
    rnd = random.Random(CONFIG.SEED + 99)
    rocas = []

    mat_ = bpy.data.materials.new("Roca_Suelta")
    mat_.use_nodes = True
    bsdf = mat_.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.20, 0.15, 0.11, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85

    for i in range(cantidad):
        tam = rnd.uniform(0.2, 2.4)
        x = rnd.uniform(-CONFIG.ANCHO_PASILLO * 0.5 + 2, CONFIG.ANCHO_PASILLO * 0.5 - 2)
        y = rnd.uniform(-CONFIG.LARGO_ESCENA * 0.45, CONFIG.LARGO_ESCENA * 0.45)

        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=tam,
                                              location=(x, y, tam * 0.25))
        r = bpy.context.active_object
        r.name = f"Roca_{i:03d}"
        r.scale = (rnd.uniform(0.8, 1.6), rnd.uniform(0.8, 1.6), rnd.uniform(0.4, 0.9))
        r.rotation_euler = (rnd.uniform(0, 6.28), rnd.uniform(0, 6.28), rnd.uniform(0, 6.28))

        dis = r.modifiers.new("Disp", 'DISPLACE')
        tex = bpy.data.textures.new(f"TexRoca_{i}", 'CLOUDS')
        tex.noise_scale = rnd.uniform(0.4, 0.9)
        dis.texture = tex
        dis.strength = tam * 0.5

        r.data.materials.append(mat_)
        for p in r.data.polygons:
            p.use_smooth = True
        mover_a_coleccion(r, coleccion)
        rocas.append(r)
    return rocas


# ---------------------------------------------------------------------
#  8. POST-PROCESADO (compositor)
# ---------------------------------------------------------------------
def _nodo_compositor(nodes, tipos, x, y):
    """Crea el primer nodo de compositor que exista en esta version."""
    for tipo in tipos:
        try:
            n = nodes.new(tipo)
            n.location = (x, y)
            return n
        except Exception:
            continue
    return None


def _entrada(nodo, nombres):
    """Devuelve el primer socket de entrada que exista con alguno de esos nombres."""
    for nombre in nombres:
        if nombre in nodo.inputs:
            return nodo.inputs[nombre]
    return nodo.inputs[0] if len(nodo.inputs) else None


def _salida(nodo, nombres):
    for nombre in nombres:
        if nombre in nodo.outputs:
            return nodo.outputs[nombre]
    return nodo.outputs[0] if len(nodo.outputs) else None


def configurar_compositor():
    """
    Post-proceso: bloom (glare), viñeta y correccion de color.
    TOLERANTE: si tu version de Blender cambio algun nodo, ese paso se omite
    y el resto de la escena sigue funcionando. Nunca detiene la construccion.
    """
    try:
        escena = bpy.context.scene
        try:
            escena.use_nodes = True
        except Exception:
            pass  # en Blender 5.x use_nodes esta obsoleto

        nt = getattr(escena, "node_tree", None)
        if nt is None:
            print("[aviso] Compositor no disponible: se omite el post-proceso.")
            return
        nodes, links = nt.nodes, nt.links
        nodes.clear()

        entrada = _nodo_compositor(nodes, ["CompositorNodeRLayers"], -700, 0)
        salida = _nodo_compositor(nodes, ["CompositorNodeComposite"], 900, 0)
        if entrada is None or salida is None:
            print("[aviso] Nodos base del compositor no disponibles. Se omite.")
            return

        actual = _salida(entrada, ["Image"])

        # --- Bloom / Glare ---
        glare = _nodo_compositor(nodes, ["CompositorNodeGlare"], -400, 100)
        if glare:
            seguro(glare, "glare_type", 'FOG_GLOW')
            seguro(glare, "quality", 'HIGH')
            seguro(glare, "threshold", 1.1)
            seguro(glare, "mix", -0.6)
            seguro(glare, "size", 7)
            try:
                links.new(actual, _entrada(glare, ["Image"]))
                actual = _salida(glare, ["Image"])
            except Exception as e:
                print("[aviso] Glare no conectado:", e)

        # --- Correccion de color ---
        balance = _nodo_compositor(nodes, ["CompositorNodeColorBalance"], 400, 0)
        if balance:
            seguro(balance, "correction_method", 'LIFT_GAMMA_GAIN')
            seguro(balance, "lift", (0.97, 0.98, 1.03))
            seguro(balance, "gamma", (1.02, 1.0, 0.97))
            seguro(balance, "gain", (1.06, 1.0, 0.92))
            try:
                links.new(actual, _entrada(balance, ["Image"]))
                actual = _salida(balance, ["Image"])
            except Exception as e:
                print("[aviso] Color balance no conectado:", e)

        # --- Salida ---
        try:
            links.new(actual, _entrada(salida, ["Image"]))
        except Exception as e:
            print("[aviso] Salida del compositor no conectada:", e)

        print("[ok] Compositor configurado (bloom + color).")
    except Exception as e:
        print(f"[aviso] Compositor omitido por incompatibilidad de version: {e}")


def configurar_slowmo_vse():
    """
    Escena 'MARROJO_SlowMo' con CAMARA LENTA en el colapso (puro cine):
    toma la escena principal como tira de video y le aplica un efecto de
    velocidad ANIMADO: normal -> 0.30x cuando cae el primer muro -> normal.
    Para usarla: cambia a la escena MARROJO_SlowMo y dale a
    Render > Render Animation. No necesita pre-renderizar nada.
    """
    try:
        main = bpy.context.scene
        nombre = "MARROJO_SlowMo"
        vieja = bpy.data.scenes.get(nombre)
        if vieja is not None:
            bpy.data.scenes.remove(vieja)
        vse = bpy.data.scenes.new(nombre)
        vse.render.resolution_x = main.render.resolution_x
        vse.render.resolution_y = main.render.resolution_y
        vse.render.resolution_percentage = main.render.resolution_percentage
        vse.render.fps = main.render.fps
        vse.frame_start = 1
        vse.frame_end = 920
        vse.render.filepath = "//render/marrojo_slowmo_"
        vse.render.image_settings.file_format = 'FFMPEG'
        seguro(vse.render.ffmpeg, "format", 'MPEG4')
        seguro(vse.render.ffmpeg, "codec", 'H264')

        se = vse.sequence_editor_create()
        toma = se.sequences.new_scene("Toma_Principal", main, 1, 1)
        toma.frame_final_duration = CONFIG.FRAME_END

        f0 = CONFIG.T_COLAPSO_INI
        lento = se.sequences.new_effect("Camara_Lenta", 'SPEED', 2, 1, 920,
                                        seq1=toma)
        seguro(lento, "scale_to_length", False)
        seguro(lento, "stretch_to_input", False)
        for f, v in [(1, 1.0), (f0 - 10, 1.0), (f0 + 15, 0.30),
                     (f0 + 120, 0.30), (f0 + 160, 1.0), (920, 1.0)]:
            lento.speed_factor = v
            lento.keyframe_insert(data_path="speed_factor", frame=f)

        print("[ok] Escena MARROJO_SlowMo lista: cambia a esa escena y")
        print("     renderiza la animacion para el video con camara lenta.")
    except Exception as e:
        print(f"[aviso] No se pudo crear la escena SlowMo: {e}")
        print("        Hazlo a mano: Video Editing > Add > Scene > escena")
        print("        principal, Add > Effect Strip > Speed, desactiva")
        print("        'Stretch to input' y anima 'Speed Factor' a 0.30")
        print("        durante el colapso.")


# ---------------------------------------------------------------------
#  9. CONTROL DE SIMULACION
# ---------------------------------------------------------------------
def bake_fluid():
    """Ejecutar despues de crear la escena: hornea la simulacion."""
    dom = bpy.data.objects.get("Dominio_Fluido")
    if not dom:
        print("[!] No existe Dominio_Fluido")
        return
    bpy.context.view_layer.objects.active = dom
    dom.select_set(True)
    bpy.ops.fluid.bake_data()
    try:
        bpy.ops.fluid.bake_mesh()
    except Exception as e:
        print("Mesh bake:", e)
    try:
        bpy.ops.fluid.bake_particles()
    except Exception as e:
        print("Particles bake:", e)
    print("[OK] Simulacion horneada.")


def renderizar_animacion(ruta="//render/marrojo_"):
    escena = bpy.context.scene
    escena.render.filepath = ruta
    bpy.ops.render.render(animation=True)


# ---------------------------------------------------------------------
#  CONSTRUCCION PRINCIPAL
# ---------------------------------------------------------------------
def _paso(numero, total, titulo, funcion, *args):
    """Ejecuta un paso de forma aislada. Si falla, informa y continua."""
    import traceback
    print(f"[{numero}/{total}] {titulo} ...")
    try:
        return funcion(*args)
    except Exception as e:
        print(f"    [ERROR en paso '{titulo}']: {type(e).__name__}: {e}")
        traceback.print_exc()
        ERRORES.append(titulo)
        return None


ERRORES = []


def construir_escena():
    print("=" * 60)
    print("  CONSTRUYENDO: LA APERTURA DEL MAR ROJO")
    print("=" * 60)
    ERRORES.clear()

    limpiar_escena()
    configurar_render()

    col_terreno = crear_coleccion("01_Terreno")
    col_montanas = crear_coleccion("02_Montanas")
    col_agua = crear_coleccion("03_Agua_Simulacion")
    col_atmos = crear_coleccion("04_Atmosfera")
    col_camara = crear_coleccion("05_Camara")
    col_detalle = crear_coleccion("06_Detalles")

    T = 19
    suelo = _paso(1, T, "Suelo del desierto", crear_suelo, col_terreno)
    _paso(2, T, "Montanas procedurales", crear_montanas, col_montanas)
    _paso(3, T, "MAR CONTINUO que se abre (visible sin bake)", crear_mar_continuo, col_agua)
    _paso(4, T, "Muros de agua (emisores FLIP para spray/colapso)", crear_fuente_de_fluido, col_agua)
    _paso(5, T, "Dominio de simulacion FLIP", crear_dominio_fluido, col_agua)
    if suelo is not None:
        _paso(6, T, "Colision del suelo", crear_colision_suelo, suelo)
    _paso(7, T, "Cielo", crear_cielo)
    _paso(8, T, "Agua base profunda (agua por todos lados)", crear_agua_base_profunda, col_agua)
    _paso(9, T, "Niebla y luces", lambda: (crear_niebla_volumetrica(col_atmos),
                                            crear_luces(col_atmos)))
    _paso(10, T, "Rocas y polvo", lambda: (crear_rocas_dispersas(col_detalle),
                                          crear_polvo_flotante(col_detalle)))
    _paso(11, T, "Camara cinematografica", crear_camara, col_camara)
    _paso(12, T, "Camara submarina + volumen bajo el agua",
          lambda: crear_camara_submarina(col_camara, col_atmos))
    _paso(13, T, "Relampagos (rayos + destellos)", crear_relampagos, col_atmos)
    _paso(14, T, "Spray de los muros (particulas)", crear_spray_muros, col_agua)
    _paso(15, T, "Niebla de impacto del colapso", crear_niebla_impacto, col_atmos)
    _paso(16, T, "Pajaros huyendo", crear_pajaros, col_detalle)
    _paso(17, T, "Refuerzo de texturas (suelo, montanas, rocas)", reforzar_texturas)
    _paso(18, T, "Compositor (bloom y color) + escena SlowMo", lambda: (configurar_compositor(),
                                                                        configurar_slowmo_vse()))
    _paso(19, T, "Camaras del cortometraje (7 planos con cambio auto)",
          lambda: (crear_camaras_cortometraje(col_camara),
                   configurar_planos_cortometraje()))

    try:
        bpy.context.scene.frame_set(CONFIG.FRAME_START)
    except Exception:
        pass

    print("=" * 60)
    if ERRORES:
        print("  ESCENA CONSTRUIDA CON AVISOS. Pasos que fallaron:")
        for e in ERRORES:
            print("    -", e)
        print("  Copia el mensaje de error de arriba si necesitas ayuda.")
    else:
        print("  ESCENA LISTA SIN ERRORES")
    print("  El mar ya se ve y anima SIN hornear (dale Play / mueve la linea de tiempo).")
    print("  Opcional (simulacion FLIP): 'Dominio_Fluido' > Physics > Bake All")
    print("  O en consola:  bake_fluid()")
    print("  Despues: Render > Render Animation (Ctrl+F12)")
    print("=" * 60)


if __name__ == "__main__":
    construir_escena()
