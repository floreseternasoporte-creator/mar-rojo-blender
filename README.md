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
   - **Agua fotorrealista**: transmisión real (IOR 1.333) + absorción volumétrica — el color depende del grosor
     del agua, como en la vida real. Ya no se ve negra.
   - **Escenario grande**: pasillo de 900 m, suelo de 2400 m, cordilleras lejanas y mar abierto.
4. **Cielo tormentoso** — nubes procedurales en dos capas, niebla, rayos de luz y polvo en el aire.
5. **Cámaras del cortometraje** — 7 planos con cambio automático (marcadores en la línea de tiempo):
   1. Establecimiento aéreo (1-70) · 2. Dolly lateral junto al muro (70-140) ·
   3. Persecución de pájaros en el aire (140-210) · 4. Pasillo a nivel de suelo, muros gigantes a los lados (210-290) ·
   5. Colapso en gran angular (290-345) · 6. Caída del muro de cerca, con sacudida (345-410) ·
   7. **Cámara SUBMARINA**: cuando el colapso inunda el pasillo, la cámara baja al agua y graba la inundación
   desde dentro, con volumen azul bajo el agua (410-600).
6. **Tres tomas**: apertura → muros → colapso (+ inundación submarina).
7. **Efectos especiales BRUTALES**:
   - ⚡ **Relámpagos** — 7 rayos con geometría quebrada que parpadean como relámpagos reales; dos caen
     detrás de los muros para iluminarlos desde adentro.
   - 💦 **Spray** — salpicaduras en la base y la cresta de los muros que siguen su crecimiento, más
     explosión de espuma en el colapso.
   - 🌫️ **Niebla de impacto** — nube de bruma enorme que avanza con la inundación.
   - 🐦 **Pájaros huyendo** — 3 bandadas (24 pájaros) con aleteo animado escapando del mar.
   - 🎥 **Cámara lenta** — la escena `MARROJO_SlowMo` aplica velocidad 0.30x durante el colapso;
     solo cambia a esa escena y dale a Render Animation.

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
