# INMOLAND Manager — Expediente Maestro del Proyecto

> **Para cualquier IA o desarrollador que reciba este archivo:**
> Este documento contiene TODO lo necesario para continuar el proyecto
> INMOLAND Manager sin necesidad de explicaciones previas del usuario.
> Léelo completo antes de tocar código.

**Última actualización:** 05/11/2026
**Estado del proyecto:** funcional, 7 de 7 reportes operativos hechos
**Próximo paso pendiente:** módulo SRI (hay que definir formato)

---

## 1. Qué es INMOLAND Manager

Sistema de gestión inmobiliaria para **compra-venta de lotes/terrenos**,
desarrollado para el negocio "Compra-Venta Bienes INMOLAND" (Ecuador).
Gestiona:

- Proyectos inmobiliarios (ej. "Proyecto 85").
- Lotes (85 lotes en Proyecto 85, más otros proyectos).
- Clientes, vendedores.
- Ventas al contado y a crédito directo.
- Calendario de cuotas (sistema francés con o sin interés).
- Pagos (parciales, totales, anulación).
- Promesas de compraventa.
- Comisiones de vendedores.
- Plano interactivo con marcadores y contornos de lotes.
- Reportes operativos (7 hechos).
- Módulo SRI (pendiente de definir formato).

**Moneda:** USD.
**Ubicación:** Ecuador (zona horaria America/Guayaquil, idioma es-ec).

---

## 2. Arquitectura técnica

### Stack
- **Python:** 3.12.10
- **Django:** 6.1.2
- **Base de datos:** SQLite (`db.sqlite3`)
- **Servidor:** `python manage.py runserver` (desarrollo)
- **Entorno virtual:** `.venv`
- **Editor:** VS Code

### Estructura de carpetas
C:\Proyectos\inmoland-manager
├── manage.py
├── requirements.txt
├── db.sqlite3 ← BD con datos reales
├── db_backup_*.sqlite3 ← respaldos
├── PENDIENTES.md ← lista de pendientes
├── EXPEDIENTE_MAESTRO.md ← este archivo
├── PROMPT_CONTINUIDAD_INMOLAND.md ← expediente original
├── cargar_medidas_lotes.py ← script auxiliar (ya ejecutado)
├── crear_documento_codigo_inmoland.py ← script auxiliar (genera .docx)
├── .venv/ ← entorno virtual (no tocar)
├── config/
│ ├── settings.py
│ ├── urls.py
│ ├── wsgi.py
│ └── asgi.py
├── core/
│ ├── admin.py
│ ├── admin_respaldo.py ← ⚠️ DUPLICADO OBSOLETO, se puede borrar
│ ├── apps.py
│ ├── models.py
│ ├── views.py ← dashboard + lotes_disponibles_por_proyecto
│ ├── ventas_views.py ← lista_ventas con filtros
│ ├── plano_views.py ← plano_lotes + guardar_geometria_lote
│ ├── gestion_lotes_views.py ← importar_lotes, lista_cuadras, plano_referencia
│ ├── pagos_views.py ← registrar_pago_cuota, anular_pago
│ ├── reportes_views.py ← los 7 reportes (ver sección 6)
│ ├── migrations/
│ │ ├── 0001_initial.py
│ │ ├── 0002_lot_back_m_lot_front_m_lot_left_side_m_and_more.py
│ │ ├── 0003_lot_street_alter_lot_block_block_lot_block_ref_and_more.py
│ │ ├── 0004_project_plan_image.py
│ │ ├── 0005_sale_credit_months_sale_interest_type_and_more.py
│ │ └── 0006_payment_installment.py
│ ├── static/core/
│ │ ├── js/venta_proyecto.js
│ │ └── plano/marcadores_etapa2.json (huérfano, se puede borrar)
│ └── templates/
│ ├── admin/inmoland_index.html
│ └── core/
│ ├── cuadras.html
│ ├── importar_lotes.html
│ ├── lista_ventas.html
│ ├── pagar_cuota.html
│ ├── plano_referencia.html
│ └── reportes/
│ ├── _base_reportes.html
│ ├── index.html
│ ├── cartera.html
│ ├── mora.html
│ ├── recaudacion.html
│ ├── creditos.html
│ ├── mejores_clientes.html
│ ├── ventas_mes.html
│ └── comisiones_mes.html
└── templates/
├── base.html
├── core/
│ ├── dashboard.html
│ └── plano_lotes.html
└── registration/login.html

---

## 3. Modelos de datos (`core/models.py`)

### `Project`
Proyecto inmobiliario.

| Campo | Tipo | Notas |
|---|---|---|
| name | CharField(150) | Nombre del proyecto |
| location | CharField(200) | Ubicación |
| acquisition_cost | Decimal(14,2) | Costo adquisición |
| development_costs | Decimal(14,2) | Gastos urbanización |
| notes | TextField | Notas |
| created_at | DateTimeField | auto |
| plan_image | ImageField | Plano imagen (opcional) |

Relaciones inversas: `lots`, `blocks`, `plans`.

### `Lot`
Lote o terreno.

| Campo | Tipo | Notas |
|---|---|---|
| project | FK(Project, PROTECT) | Proyecto |
| number | CharField(30) | Número de lote |
| block | CharField(30) | Manzana/cuadra (texto) |
| block_ref | FK(Block, SET_NULL) | Cuadra (objeto) |
| street | CharField(150) | Calle/ubicación |
| area_m2 | Decimal(10,2) | Superficie m² |
| front_m | Decimal(8,2) null | Frente (m) |
| back_m | Decimal(8,2) null | Fondo (m) |
| left_side_m | Decimal(8,2) null | Lado izquierdo (m) |
| right_side_m | Decimal(8,2) null | Lado derecho (m) |
| sale_price | Decimal(14,2) | Precio venta |
| status | CharField(20) | disponible/reservado/promesa/escriturado/contado/crédito |
| notes | TextField | Notas |

**Restricción:** único `(project, number)`.

### `Block`
Cuadra o manzana.

| Campo | Tipo |
|---|---|
| project | FK(Project, CASCADE) |
| code | CharField(30) |
| name | CharField(100) |
| streets | CharField(250) |
| notes | TextField |
| created_at | DateTimeField |

**Restricción:** único `(project, code)`.

### `Client`
Cliente.

| Campo | Tipo |
|---|---|
| first_name | CharField(100) |
| last_name | CharField(100) |
| identification | CharField(20) (cédula/RUC) |
| phone | CharField(30) |
| email | EmailField |
| whatsapp | CharField(30) |
| accepts_notifications | BooleanField |
| notes | TextField |

### `Seller`
Vendedor.

| Campo | Tipo |
|---|---|
| user | OneToOne(User, SET_NULL) null |
| name | CharField(150) |
| fixed_commission | Decimal(12,2) default 1000.00 |
| is_sales_manager | BooleanField |
| active | BooleanField |

### `Sale`
Venta (contado o crédito).

| Campo | Tipo | Notas |
|---|---|---|
| lot | FK(Lot, PROTECT) | |
| client | FK(Client, PROTECT) | |
| seller | FK(Seller, PROTECT) | |
| sale_type | CharField(10) | cash / credit |
| sale_date | DateField | |
| final_price | Decimal(14,2) | Precio final |
| initial_payment | Decimal(14,2) | Abono inicial |
| credit_months | PositiveSmallInteger(30) | Plazo (si crédito) |
| interest_type | CharField(15) | none / monthly_rate |
| monthly_interest_rate | Decimal(6,3) | Tasa mensual % |
| notes | TextField | |

Métodos:
- `total_paid` → `initial_payment + sum(payments.amount)`
- `paid_percentage` → % pagado
- `amount_to_half` → monto para llegar al 50%
- `generate_installments()` → genera calendario (sistema francés)
- `refresh_commission()` → recalcula el estado de la comisión

### `Installment`
Cuota programada.

| Campo | Tipo |
|---|---|
| sale | FK(Sale, CASCADE) |
| number | PositiveSmallInteger |
| due_date | DateField |
| principal_amount | Decimal(14,2) |
| interest_amount | Decimal(14,2) |
| amount | Decimal(14,2) |
| status | CharField(10): pending/partial/paid/overdue |
| notes | TextField |

**Restricción:** único `(sale, number)`.

Métodos: `total_paid`, `remaining_amount`, `refresh_status()`.

### `Payment`
Pago de una cuota.

| Campo | Tipo |
|---|---|
| sale | FK(Sale, CASCADE) |
| installment | FK(Installment, SET_NULL) null |
| payment_date | DateField |
| amount | Decimal(14,2) min 0.01 |
| reference | CharField(100) |
| notes | TextField |

Al guardar: refresca comisión y estado de la cuota.

### `Promise`
Promesa de compraventa.

| Campo | Tipo |
|---|---|
| sale | OneToOne(Sale, CASCADE) |
| signed_date | DateField |
| notary | CharField(150) |
| legal_fee | Decimal(10,2) default 280 |
| notes | TextField |

Al guardar: pone el lote en estado PROMISE.

### `Commission`
Comisión del vendedor.

| Campo | Tipo |
|---|---|
| sale | OneToOne(Sale, CASCADE) |
| seller | FK(Seller, PROTECT) |
| amount | Decimal(12,2) |
| status | CharField: pending/blocked/enabled/paid |
| paid_date | DateField null |
| notes | TextField |

**Regla:** la comisión se habilita si hay promesa firmada Y `paid_percentage >= 50%`.
- Sin promesa: `pending`
- Con promesa y < 50%: `blocked`
- Con promesa y >= 50%: `enabled`
- Si ya está `paid`, no se toca.

### `LegalFee`
Rubros legales configurables.

### `ProjectPlan`
PDF de referencia por proyecto.

### `LotGeometry`
Contorno gráfico de un lote (JSON con puntos 0..1).

### `Block`
Cuadras/manzanas.

---

## 4. Rutas (config/urls.py)

| URL | Nombre | Qué hace | Login |
|---|---|---|---|
| `/admin/` | admin | Admin Django | staff |
| `/accounts/login/` | login | Login | — |
| `/accounts/logout/` | logout | Logout | — |
| `/` | dashboard | Panel con métricas | ✅ |
| `/lotes-disponibles-por-proyecto/` | lotes_disponibles_por_proyecto | JSON para JS | staff |
| `/plano-lotes/` | plano_lotes | Plano interactivo | ✅ |
| `/guardar-geometria-lote/` | guardar_geometria_lote | POST JSON | ✅ |
| `/importar-lotes/` | importar_lotes | Importar Excel | ✅ |
| `/cuadras/` | lista_cuadras | Ver cuadras | ✅ |
| `/plano-referencia/` | plano_referencia | Subir PDF | ✅ |
| `/ventas/` | lista_ventas | Lista con filtros | ✅ |
| `/cuotas/<id>/pagar/` | registrar_pago_cuota | Pagar cuota | ✅ |
| `/pagos/<id>/anular/` | anular_pago | Anular pago | ✅ |
| `/reportes/` | reportes_index | Índice reportes | ✅ |
| `/reportes/cartera/` | reporte_cartera | R1 Cartera | ✅ |
| `/reportes/mora/` | reporte_mora | R2 Mora | ✅ |
| `/reportes/recaudacion/` | reporte_recaudacion | R3 Recaudación | ✅ |
| `/reportes/creditos/` | reporte_creditos | R4 Créditos | ✅ |
| `/reportes/mejores-clientes/` | reporte_mejores_clientes | R5 Mejores clientes | ✅ |
| `/reportes/ventas-mes/` | reporte_ventas_mes | R6 Ventas por mes | ✅ |
| `/reportes/comisiones-mes/` | reporte_comisiones_mes | R7 Comisiones por mes | ✅ |

---

## 5. Templates y qué hacen

| Template | Función |
|---|---|
| `base.html` | Layout común (menú superior con Panel, Reportes, Administración) |
| `core/dashboard.html` | Panel principal con tarjetas |
| `core/plano_lotes.html` | Plano interactivo (JS grande, SVG, dibujo de contornos) |
| `core/lista_ventas.html` | Listado de ventas con filtros |
| `core/pagar_cuota.html` | Pantalla de pago de cuota (módulo pagos) |
| `core/cuadras.html` | Vista de cuadras/manzanas |
| `core/importar_lotes.html` | Importación Excel con vista previa |
| `core/plano_referencia.html` | Subir PDF de referencia |
| `core/reportes/_base_reportes.html` | Layout común de reportes (menú lateral) |
| `core/reportes/index.html` | Índice con tarjetas de reportes |
| `core/reportes/cartera.html` | R1 |
| `core/reportes/mora.html` | R2 |
| `core/reportes/recaudacion.html` | R3 |
| `core/reportes/creditos.html` | R4 |
| `core/reportes/mejores_clientes.html` | R5 |
| `core/reportes/ventas_mes.html` | R6 |
| `core/reportes/comisiones_mes.html` | R7 |
| `registration/login.html` | Login |

---

## 6. Reportes implementados (7)

Todos en `core/reportes_views.py`. Todos requieren login.

### R1 — Cartera
**Ruta:** `/reportes/cartera/`
**Qué hace:** saldo por cobrar de cuotas no pagadas al 100%.
**Filtros:** proyecto.
**Muestra:** total por cobrar, nº cuotas, promedio; por proyecto; por estado; top 20 clientes.

### R2 — Mora
**Ruta:** `/reportes/mora/`
**Qué hace:** clientes con cuotas vencidas (`due_date < hoy` y saldo > 0). Calculado al vuelo, no depende de que la cuota esté marcada como `overdue`.
**Filtros:** proyecto, días mínimos de atraso (0/15/30/60/90).
**Muestra:** total en mora, nº clientes, nº cuotas, promedio; tabla clientes con días de atraso, ordenados por peor.

### R3 — Recaudación
**Ruta:** `/reportes/recaudacion/`
**Qué hace:** entradas iniciales (por `sale_date`) + cuotas cobradas (por `payment_date`), agrupadas por mes.
**Filtros:** proyecto, rango (1/3/6/12 meses).
**Muestra:** total recaudado, entradas, cuotas, nº pagos; tabla por mes.

### R4 — Créditos
**Ruta:** `/reportes/creditos/`
**Qué hace:** financiado vs cobrado vs pendiente de ventas a crédito + proyección mes a mes.
**Filtros:** proyecto.
**Muestra:** totales, por proyecto, proyección cuotas futuras.

### R5 — Mejores clientes
**Ruta:** `/reportes/mejores-clientes/`
**Qué hace:** top 20 clientes por total pagado (inicial + cuotas), con % cumplimiento.
**Filtros:** proyecto, rango (1/3/6/12 meses).
**Muestra:** clientes activos, mejor cliente, promedio; tabla ranking.

### R6 — Ventas por mes
**Ruta:** `/reportes/ventas-mes/`
**Qué hace:** ventas agrupadas por mes de `sale_date`, separando contado/crédito.
**Filtros:** proyecto, vendedor, rango (1/3/6/12).
**Muestra:** total ventas, monto total, contado, crédito; tabla por mes.
**Uso:** base para el SRI.

### R7 — Comisiones por mes
**Ruta:** `/reportes/comisiones-mes/`
**Qué hace:** comisiones agrupadas por mes de venta y vendedor, con desglose por estado.
**Filtros:** vendedor, rango (1/3/6/12).
**Muestra:** total, pagadas, habilitadas, pendientes; tabla por mes y vendedor.

---

## 7. Lógica de negocio clave

### Generación de cuotas (`Sale.generate_installments()`)
- Solo ventas a crédito.
- No regenera si ya hay cuotas.
- Balance a financiar = `final_price - initial_payment`.
- Si `interest_type == "monthly_rate"`: **sistema francés** con tasa mensual.
- Si `interest_type == "none"`: cuota fija = balance / meses.
- Fecha de vencimiento: mismo día del mes siguiente (ajustado a fin de mes).
- Redondeo a 2 decimales con `ROUND_HALF_UP`.
- La última cuota se ajusta al saldo restante.

### Comisiones (`Sale.refresh_commission()`)
- Se crea/actualiza en `Commission` al guardar un pago o promesa.
- Estados:
  - `pending`: sin promesa firmada.
  - `blocked`: con promesa pero < 50% pagado.
  - `enabled`: con promesa y >= 50% pagado.
  - `paid`: pagada (no se toca).
- Monto = `Seller.fixed_commission` (default 1000).

### Estados de lote
- `available`: disponible.
- `reserved`: separado.
- `promise`: promesa firmada.
- `deed`: escriturado.
- `cash`: vendido al contado.
- `credit`: vendido a crédito.

Se actualiza a CASH/CREDIT al guardar una venta. Se actualiza a PROMISE al guardar una promesa.

---

## 8. Cómo arrancar el proyecto (nueva máquina)

**Requisitos previos:** Python 3.12 instalado y en PATH, VS Code (opcional).

```powershell
# 1. Entrar a la carpeta
cd C:\Proyectos\inmoland-manager

# 2. Activar entorno virtual
.\.venv\Scripts\Activate.ps1
# Si falla por "execution policy":
# Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# 3. Si el .venv no existe (máquina nueva):
# python -m venv .venv
# .\.venv\Scripts\Activate.ps1
# pip install -r requirements.txt

# 4. Verificar
python manage.py check
python manage.py showmigrations core

# 5. Arrancar
python manage.py runserver

Abrir: http://127.0.0.1:8000/

⚠️ IMPORTANTE: siempre activar .venv antes de ejecutar python manage.py .... Si no, da ModuleNotFoundError: No module named 'django'.

9. Decisiones de diseño ya tomadas
Estas cosas YA se decidieron. No preguntarlas de nuevo.

Un pago = una cuota (no se reparte entre varias).

Se permiten pagos parciales.

Anular pago = borrar el Payment (sin campo anulado). La cuota se recalcula sola.

Reportes con login obligatorio (@login_required).

Rangos en reportes: 1, 3, 6, 12 meses (default 6, salvo R5 que es 12).

Recaudación = cuotas cobradas (por payment_date) + entradas iniciales (por sale_date).

Mora se calcula al vuelo (no se marca overdue en BD).

Reportes calculan todo al vuelo con Sum, Count, annotate, Subquery. Sin tablas intermedias.

Menú de reportes: enlace "Reportes" en el menú superior + bloque en el admin + menú lateral dentro de reportes.

Roles de vendedor: PENDIENTE. Cuando se haga: admin ve todo, vendedor ve solo sus ventas/comisiones. Requiere vincular Seller.user con User de Django.

Módulo SRI: PENDIENTE. Formato no definido. Se hará aparte. Se necesita confirmar con contador si las ventas llevan IVA.

Exportar a Excel en reportes: PENDIENTE. Se hará con openpyxl (ya instalado).

10. Historial de cambios
22/10/2026 — Sesión inicial
Creado módulo de pagos:

core/pagos_views.py con registrar_pago_cuota y anular_pago.

core/templates/core/pagar_cuota.html.

Botón "💵 Pagar" en InstallmentAdmin de core/admin.py.

Rutas /cuotas/<id>/pagar/ y /pagos/<id>/anular/ en config/urls.py.

Creado módulo de reportes:

core/reportes_views.py.

core/templates/core/reportes/_base_reportes.html + index.html.

R1 Cartera completo.

23/10/2026 — Migración a nueva máquina
ZIP limpio creado (INMOLAND_limpio_*.zip).

Instalado Python 3.12 en máquina nueva.

Creado .venv y pip install -r requirements.txt.

Proyecto migrado con datos reales.

05/11/2026 — Reportes completados
R2 Mora (función + template + ruta + menú).

R3 Recaudación (función + template + ruta + menú).

R6 Ventas por mes (función + template + ruta + menú).

R7 Comisiones por mes (función + template + ruta + menú).

R4 Créditos (función + template + ruta + menú).

R5 Mejores clientes (función + template + ruta + menú).

Página /reportes/ (índice) actualizada con tarjetas de todos.

Enlaces en menú superior (base.html) y en admin (inmoland_index.html).

11. Problemas conocidos / deuda técnica
Alta prioridad
settings.py tiene DEBUG = True hardcodeado. Peligroso en producción. Cambiar a DEBUG = os.environ.get("DEBUG", "False") == "True".

Media prioridad
core/admin_respaldo.py es un duplicado obsoleto. Borrar (Remove-Item core\admin_respaldo.py).

marcadores_etapa2.json huérfano. Borrar o usar.

config/urls.py tenía imports duplicados (algunos ya corregidos, revisar).

core/admin.py importa ValidationError dos veces. Cosmético.

core/models.py generate_installments() tiene from django.db import transaction dentro del método. Cosmético.

core/reportes_views.py tenía un @login_required duplicado en cartera (línea 20-21). Cosmético.

SaleAdminForm funciona pero es frágil.

No hay tests (core/tests.py no existe).

2 proyectos en BD (Proyecto 85 + otro). Confirmar si el segundo es real o basura.

Baja prioridad
requirements.txt dice Django 6.1.2 pero el .md de traspaso original decía 5.2.18. Actualizado el .md, no el requirements.txt (que está bien).

build.sh incluye collectstatic --noinput y migrate. Añadir python manage.py check --deploy antes de producción.

12. Pendientes funcionales
Reportes (✅ todos hechos)
R1 a R7 → ✅ completos.

Por hacer
Módulo SRI (aparte, formato no definido).

Necesita confirmar con contador si ventas de lotes llevan IVA.

Empezar con listado de ventas del período + Excel.

Después, XML del SRI cuando el formato esté confirmado.

Roles de vendedor (admin ve todo, vendedor ve solo sus ventas/comisiones).

Requiere vincular Seller.user con User en admin.

Añadir decorador vendedor_o_admin en reportes_views.py.

Filtrar por Seller.objects.get(user=request.user) si no es staff.

Ocultar menú completo a no-staff en base.html.

Excel en reportes (botón "Exportar" en cada uno).

Estado de cuenta por cliente (/clientes/<id>/estado-cuenta/).

Editar pagos ya registrados (botón "Editar" en pagar_cuota.html).

Marcar cuotas vencidas automáticamente (python manage.py marcar_vencidas).

PDF de promesa de compraventa (con reportlab o weasyprint).

Notificaciones por email/WhatsApp (recordatorios de cuotas).

Dashboard con gráficos (Chart.js).

Búsqueda global.

13. Datos actuales en la BD
(fecha 05/11/2026)

Proyectos: 2

Lotes: 99

Lotes disponibles: 95

Clientes: 20

Vendedores: 5

Ventas: 4 (2 contado + 2 crédito)

Cuotas: 60 (2 ventas a crédito × 30)

Cuotas pagadas: 4

Cuotas pendientes: 26 (más las nuevas generadas)

Pagos: 5

Comisiones: 4

Promesas: 0

Nota: se generaron cuotas faltantes y comisiones faltantes el 05/11/2026.

14. Reglas de trabajo con el usuario
El usuario prefiere:

Español siempre.

Comandos exactos de PowerShell (Windows).

Cambios pequeños y específicos, nunca reemplazar archivos enteros sin necesidad.

Paso a paso, un archivo por mensaje, verificando antes de avanzar.

Confirmación antes de migraciones o cambios destructivos.

No inventar modelos, campos ni funcionalidades sin revisar el código.

No decir que algo funciona hasta que el usuario lo confirme.

Si hay error, pedir el traceback completo y resolver primero ese error.

Editor: VS Code (¡ojo con el auto-guardado! A veces se olvida Ctrl+S).

Entorno: .venv debe estar activado para que python manage.py funcione.

Cómo verificar que un archivo se guardó
powershell
Select-String -Path <archivo> -Pattern "<texto buscado>"
Si no devuelve nada, el archivo no se guardó.

Si python no se reconoce en una máquina nueva
Instalar Python 3.12 desde https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe

Marcar "Add python.exe to PATH" durante la instalación.

Desactivar alias falsos de Microsoft Store: Configuración → Aplicaciones → Configuración avanzada → Alias de ejecución → desactivar python.exe y python3.exe.

Cerrar y abrir PowerShell.

Verificar: python --version.

---

# 📄 Cómo usar este archivo

## 1. Guárdalo en el proyecto

Ya lo tienes en `C:\Proyectos\inmoland-manager\EXPEDIENTE_MAESTRO.md`. **Forma parte del proyecto** y se copiará si vuelves a hacer un ZIP.

## 2. Cuando abras una nueva sesión de IA

Pégale este archivo completo (o súbelo como adjunto). La IA sabrá todo de tu proyecto sin que expliques nada.

## 3. Cada vez que hagamos algo importante

Actualiza el archivo con:
- Lo que hicimos (en "Historial de cambios").
- Lo que falta (en "Pendientes funcionales").
- Nuevas decisiones (en "Decisiones de diseño").

## 4. Si me pierdo en otra sesión

Dime: *"Aquí está el expediente maestro, léelo y continuamos"* y me lo pegas. Recupero todo el contexto.

---

👉 **Dime**:

1. ¿Creaste el archivo `EXPEDIENTE_MAESTRO.md`?
2. ¿Quieres que también te genere un **`.docx`** con lo mismo (más fácil de leer en Word) o el `.md` te vale?
3. ¿Seguimos con el **SRI** ahora o lo dejamos para la próxima sesión?
