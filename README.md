# INMOLAND Manager — versión inicial

Aplicación de pruebas para Compra-Venta Bienes INMOLAND, desarrollada con Django 5.2 y preparada para SQLite local o PostgreSQL en Render.

## Incluye

- Panel con conteos de proyectos, lotes, clientes, ventas, cobros y comisiones.
- Administración Django para proyectos, lotes, clientes, vendedores, ventas, pagos, promesas, comisiones y rubros legales configurables.
- Lógica inicial de comisión del vendedor: la comisión se habilita cuando existe una promesa y los pagos registrados alcanzan al menos el 50% del precio final. Si hay promesa y falta completar el 50%, se bloquea.
- Configuración por variables de entorno y archivos base para Render.

## Requisitos

Python 3.12 recomendado y Git.

## Ejecutar localmente en Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Abrir http://127.0.0.1:8000/ e iniciar sesión. La administración está en http://127.0.0.1:8000/admin/.

Para entorno local, la app usa SQLite automáticamente si no existe `DATABASE_URL`.

## Despliegue en Render

1. Sube este proyecto a un repositorio privado en GitHub.
2. En Render, crea una base de datos PostgreSQL y un Web Service conectado al repositorio.
3. Build Command: `bash build.sh`
4. Start Command: `gunicorn config.wsgi:application`
5. En Environment configura:
   - `SECRET_KEY`: clave secreta aleatoria y robusta.
   - `DEBUG`: `False`
   - `DATABASE_URL`: URL interna de la base PostgreSQL de Render.
   - `ALLOWED_HOSTS`: se puede dejar vacío o `localhost`; Render añade `RENDER_EXTERNAL_HOSTNAME`.
6. Despliega el servicio.
7. Crea el administrador mediante una consola disponible en tu plan:
   `python manage.py createsuperuser`

No añadas `.env`, credenciales ni copias de bases de datos al repositorio. Consulta la documentación actual de Render para los límites y precios de cada plan.

## Importante antes de producción

Este es un MVP de pruebas, no un sistema contable/legal terminado. Antes de usarlo con clientes reales, requiere pruebas automatizadas, permisos por rol, auditoría de cambios, validación de pagos y ventas duplicadas, estrategia de respaldos, política de privacidad, y revisión de cálculos de amortización/intereses y comisiones. Las notificaciones por correo/WhatsApp, PDFs, Excel, tareas programadas y reportes financieros aún no están implementados.

## Migraciones de datos

Si cambias modelos, ejecuta:

```bash
python manage.py makemigrations
python manage.py migrate
```
