# 🌊 LA APERTURA DEL MAR ROJO — VFX Cinematográfico para Blender

Script 100% procedural en Python que construye una escena cinematográfica completa en Blender:
el Mar Rojo abriéndose en dos muros de agua gigantes y colapsando como un tsunami.

**Compatible con Blender 3.6 LTS, 4.0, 4.1, 4.2+, 5.0 (Cycles).**

## 🎬 Qué construye el script

1. **Desierto rocoso realista** — suelo agrietado + arena húmeda que aparece conforme el agua se retira.
2. **Cordilleras procedurales** — roca estratificada, vetas, erosión, polvo + acantilados laterales.
3. **El mar y dos muros de agua GIGANTES** — el mar se abre como una cremallera (empieza en un punto y avanza),
   el agua se retira del centro hacia afuera y los muros suben desde la base. Al final **colapsan en cascada
   desde una esquina, como un tsunami**.
4. **Cielo tormentoso** — nubes procedurales en dos capas, niebla, rayos de luz y polvo en el aire.
5. **Cámara cinematográfica** — recorrido en tres actos, foco dinámico, viento y sacudida.
6. **Tres tomas**: apertura → muros → colapso.

## 🚀 Cómo usarlo

**Opción A (interfaz):**
Blender → pestaña *Scripting* → *Open* → `mar_rojo.py` → *Run Script*

**Opción B (terminal):**
```bash
blender --python mar_rojo.py
```

## 💧 Simulación (opcional)

El agua principal ya se ve **sin hornear** (`Mar_Continuo` con shape keys). Si quieres además la simulación FLIP:

- Selecciona `Dominio_Fluido` → *Physics* → *Fluid* → *Bake All*
  (o ejecuta `bake_fluid()` desde la consola de Python).

Luego: *Render* → *Render Animation* (Ctrl+F12).

## ⚙️ Ajustes rápidos

Edita la clase `CONFIG` al inicio del script:

| Parámetro | Qué hace |
|---|---|
| `ALTURA_MURO` | Altura de los muros de agua (m) |
| `ANCHO_PASILLO` | Separación final entre muros (m) |
| `FRAME_END` | Duración total en frames |
| `RES_X / RES_Y` | Resolución de render |
| `SAMPLES` | Calidad de Cycles |
| `USE_GPU` | Render por GPU si está disponible |

## 📁 Contenido

- `mar_rojo.py` — el script completo (~2400 líneas, sin dependencias externas salvo `numpy`).
