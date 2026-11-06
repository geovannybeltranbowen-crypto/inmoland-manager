# -*- coding: utf-8 -*-
"""
Actualiza superficies y linderos de lotes de Proyecto 85.
Ejecutar desde C:\\Proyectos\\inmoland-manager:
    python cargar_medidas_lotes.py

Solo modifica area_m2, front_m, back_m, left_side_m y right_side_m.
No cambia precios, estados, clientes, reservas ni ventas.
No modifica los lotes 1 al 11.
"""
from pathlib import Path
from datetime import datetime
import shutil
import os
import sys

ROOT = Path.cwd()
if not (ROOT / "manage.py").is_file():
    print("ERROR: Este archivo debe ejecutarse desde la carpeta que contiene manage.py.")
    print("Abra PowerShell en C:\\Proyectos\\inmoland-manager y vuelva a intentarlo.")
    sys.exit(1)

DB_PATH = ROOT / "db.sqlite3"
if not DB_PATH.is_file():
    print(f"ERROR: No se encontró la base de datos: {DB_PATH}")
    sys.exit(1)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from decimal import Decimal
from django.db import transaction
from core.models import Project, Lot

# Cada fila: superficie, frente, fondo, lindero izquierdo, lindero derecho.
DATA = {
    "12": ('280.56', '31.27', '31.03', '9', '9'),
    "13": ('278.15', '31.03', '30.78', '9', '9'),
    "14": ('275.84', '30.78', '29.63', '9', '9'),
    "15": ('273.43', '29.63', '30.25', '9', '9'),
    "16": ('271.02', '30.25', '29.98', '9', '9'),
    "17": ('268.61', '29.98', '29.71', '9', '9'),
    "18": ('266.13', '29.71', '29.44', '9', '9'),
    "19": ('263.77', '29.44', '29.17', '9', '9'),
    "20": ('277.29', '12.84', '13.31', '19.38', '24.94'),
    "21": ('253.27', '16.33', '16.19', '9', '19.38'),
    "22": ('206.34', '11.50', '7.95', '16.24', '16.08'),
    "23": ('205.95', '15.05', '14.39', '13.72', '16.24'),
    "24": ('217.18', '14.50', '14.96', '17.05', '13.72'),
    "25": ('215.14', '19', '21.37', '20.60', '7.05'),
    "26": ('215.93', '11', '12.46', '22.43', '20.60'),
    "27": ('312.70', '16.76', '16.69', '18.26', '18.43'),
    "28": ('210.20', '18.17', '16.76', '12.08', '12'),
    "29": ('204.96', '13.66', '18.17', '9.62', '12'),
    "30": ('200', '10', '10', '20', '20'),
    "31": ('200', '10', '10', '20', '20'),
    "32": ('200', '10', '10', '20', '20'),
    "33": ('200', '20', '14.5', '10', '10'),
    "34": ('200', '17.03', '20.05', '10', '7'),
    "35": ('200', '17', '20', '10', '7'),
    "36": ('200', '20', '20', '10', '10'),
    "37": ('200', '10', '10', '20', '20'),
    "38": ('200', '10', '10', '20', '20'),
    "39": ('200', '10', '10', '20', '20'),
    "40": ('200', '10', '10', '20', '20'),
    "41": ('207.10', '19.04', '18.95', '5.61', '10'),
    "42": ('201.47', '14.1', '18.95', '13.32', '12.3'),
    "43": ('202.31', '8.77', '14.10', '4.79', '16.70'),
    "44": ('200', '10', '10', '20', '20'),
    "45": ('200', '10', '10', '20', '20'),
    "46": ('200', '10', '10', '20', '20'),
    "47": ('200', '10', '10', '20', '20'),
    "48": ('200', '20', '20', '10', '10'),
    "49": ('200', '17', '20', '10', '7'),
    "50": ('200', '17', '20', '7', '10'),
    "51": ('200', '20', '20', '10', '10'),
    "52": ('200', '10', '10', '20', '20'),
    "53": ('200', '10', '10', '20', '20'),
    "54": ('200', '10', '10', '20', '20'),
    "55": ('200', '10', '10', '20', '20'),
    "56": ('200', '10', '10', '20', '20'),
    "57": ('204.44', '6.54', '11.36', '17.41', '20'),
    "58": ('245.80', '10.14', '11.36', '16.78', '20'),
    "59": ('200', '10', '10', '20', '20'),
    "60": ('200', '10', '10', '20', '20'),
    "61": ('200', '10.03', '10', '20', '20'),
    "62": ('200', '9.97', '10', '20', '20'),
    "63": ('200', '17', '10', '20', '10'),
    "64": ('200', '20', '10', '10', '10'),
    "65": ('200', '20', '17', '8', '10'),
    "66": ('200', '17', '20', '7', '10'),
    "67": ('200', '20', '20', '10', '10'),
    "68": ('200', '10', '10', '20', '20'),
    "69": ('200', '10', '10', '20', '20'),
    "70": ('200', '10', '10', '20', '20'),
    "71": ('200', '10', '10', '20', '20'),
    "72": ('200', '10', '10', '20', '20'),
    "73": ('227.89', '11.62', '13', '12.39', '15'),
    "74": ('218.40', '10', '15.22', '13.07', '13'),
    "75": ('214.49', '15.22', '15.22', '8.73', '12'),
    "76": ('200', '10', '10', '20', '20'),
    "77": ('200', '10', '10', '20', '20'),
    "78": ('200', '10', '10', '20', '20'),
    "79": ('200', '10', '10', '20', '20'),
    "80": ('200', '10', '10', '20', '20'),
    "81": ('200', '20', '17', '10', '10'),
    "82": ('200', '17', '10', '7', '10'),
    "83": ('206.01', '15.15', '15', '14.81', '12.66'),
    "84": ('202.79', '12.99', '12.90', '16.39', '14.81'),
    "85": ('314.20', '21.06', '20.84', '12.31', '16.39'),
    "81.1": ('201.21', '24.75', '21.50', '10.06', '8.23'),
    "82.2": ('204.53', '18.18', '18.00', '12.66', '10.06'),
}

# Evita ejecutar contra un proyecto equivocado.
projects = list(Project.objects.filter(id=1, name="Proyecto 85"))
if len(projects) != 1:
    print('ERROR: No se encontró exactamente el proyecto id=1, nombre "Proyecto 85".')
    print("No se realizó ningún cambio.")
    sys.exit(1)
project = projects[0]

# Confirma que los nombres de los campos coincidan con el modelo instalado.
required_fields = {"area_m2", "front_m", "back_m", "left_side_m", "right_side_m"}
actual_fields = {f.name for f in Lot._meta.get_fields()}
missing_fields = required_fields - actual_fields
if missing_fields:
    print("ERROR: Faltan campos esperados en el modelo Lot:", ", ".join(sorted(missing_fields)))
    print("No se realizó ningún cambio. Revise los nombres en core/models.py.")
    sys.exit(1)

existing = {lot.number: lot for lot in Lot.objects.filter(project=project, number__in=DATA.keys())}
missing_lots = sorted(set(DATA) - set(existing), key=lambda x: (float(x.split(".")[0]), x))
if missing_lots:
    print("ERROR: No existen estos lotes en Proyecto 85:", ", ".join(missing_lots))
    print("No se realizó ningún cambio ni se crearon lotes automáticamente.")
    sys.exit(1)

# Copia de seguridad con nombre único; nunca sobrescribe respaldos previos.
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_path = ROOT / f"db_respaldo_antes_cargar_medidas_{stamp}.sqlite3"
if backup_path.exists():
    print(f"ERROR: Ya existe el respaldo {backup_path}. No se realizó ningún cambio.")
    sys.exit(1)

shutil.copy2(DB_PATH, backup_path)
print(f"Respaldo creado: {backup_path.name}")

fields_to_update = ["area_m2", "front_m", "back_m", "left_side_m", "right_side_m"]
updated = 0
try:
    with transaction.atomic():
        for number, values in DATA.items():
            area, front, back, left, right = values
            lot = existing[number]
            lot.area_m2 = Decimal(area)
            lot.front_m = Decimal(front)
            lot.back_m = Decimal(back)
            lot.left_side_m = Decimal(left)
            lot.right_side_m = Decimal(right)
            lot.save(update_fields=fields_to_update)
            updated += 1
except Exception:
    print("ERROR durante la actualización. Django revirtió la transacción.")
    print(f"Respaldo disponible: {backup_path.name}")
    raise

print()
print(f"LISTO: se actualizaron {updated} lotes del proyecto {project.name}.")
print("Campos actualizados: superficie, frente, fondo, lindero izquierdo y lindero derecho.")
print("Los lotes 1 al 11 y los demás campos (precio, estado, clientes y ventas) no se modificaron.")
print(f"Respaldo: {backup_path.name}")
