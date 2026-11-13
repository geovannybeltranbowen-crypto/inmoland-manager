import json
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from .models import Project, Lot, Block

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None

REQUIRED_COLUMNS = {
    "proyecto": ("proyecto", "project", "nombre del proyecto"),
    "numero": ("numero de lote", "número de lote", "lote", "numero", "número"),
}

ALIASES = {
    "block": ("cuadra", "manzana", "cuadra/manzana", "block"),
    "area_m2": ("superficie", "superficie m2", "area", "área", "area m2", "superficie (m²)", "area_m2"),
    "front_m": ("frente", "frente m", "front_m"),
    "back_m": ("atras", "atrás", "fondo", "lado posterior", "back_m"),
    "left_side_m": ("izquierda", "lado izquierdo", "left_side_m"),
    "right_side_m": ("derecha", "lado derecho", "right_side_m"),
    "north_boundary": ("lindero norte", "norte", "colindante norte"),
    "south_boundary": ("lindero sur", "sur", "colindante sur"),
    "east_boundary": ("lindero este", "este", "colindante este"),
    "west_boundary": ("lindero oeste", "oeste", "colindante oeste"),
    "commission_percentage": ("porcentaje", "comision", "comisión", "porcentaje comision"),
    "street": ("calle", "ubicacion", "ubicación", "calle o ubicacion"),
    "sale_price": ("precio", "precio de venta", "sale_price"),
    "status": ("estado", "status"),
    "notes": ("observaciones", "notas", "notes"),
}

STATUS_MAP = {
    "disponible": "available", "available": "available",
    "separado": "reserved", "separada": "reserved", "reserved": "reserved",
    "promesa firmada": "promise", "promise": "promise",
    "escriturado": "deed", "deed": "deed",
    "vendido al contado": "cash", "contado": "cash", "cash": "cash",
    "vendido a credito": "credit", "vendido a crédito": "credit", "credito": "credit", "crédito": "credit", "credit": "credit",
}

DECIMAL_FIELDS = ("area_m2", "front_m", "back_m", "left_side_m", "right_side_m", "sale_price", "commission_percentage")

def _norm(value):
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())

def _decimal(value, label, required=False):
    if value in (None, ""):
        if required:
            raise ValueError(f"Falta el valor de {label}.")
        return None
    if isinstance(value, str):
        value = value.strip().replace("$", "").replace(" ", "")
        # Acepta 1234.56 y 1234,56; si hay punto y coma, interpreta punto de miles.
        if "," in value and "." in value:
            if value.rfind(",") > value.rfind("."):
                value = value.replace(".", "").replace(",", ".")
            else:
                value = value.replace(",", "")
        elif "," in value:
            value = value.replace(",", ".")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"El valor de {label} no es numérico: {value!s}.")
    if result < 0:
        raise ValueError(f"{label} no puede ser negativo.")
    return result

def _parse_rows(sheet_rows, project):
    rows = list(sheet_rows)
    if not rows:
        return [], ["El archivo no contiene filas."]
    headers = [_norm(v) for v in rows[0]]
    header_map = {}
    all_aliases = {"proyecto": REQUIRED_COLUMNS["proyecto"], "numero": REQUIRED_COLUMNS["numero"], **ALIASES}
    
    for key, aliases in all_aliases.items():
        for idx, header in enumerate(headers):
            if header in {_norm(a) for a in aliases}:
                header_map[key] = idx
                break
                
    errors = []
    for required in ("proyecto", "numero"):
        if required not in header_map:
            errors.append("Falta una columna obligatoria: Proyecto o Número de lote.")
    if errors:
        return [], errors

    parsed, seen = [], set()
    for excel_row, raw in enumerate(rows[1:], start=2):
        if not any(v not in (None, "") for v in raw):
            continue
            
        def get(key):
            idx = header_map.get(key)
            return raw[idx] if idx is not None and idx < len(raw) else None
            
        project_name = str(get("proyecto") or "").strip()
        number = str(get("numero") or "").strip()
        row_errors = []
        
        if _norm(project_name) != _norm(project.name):
            row_errors.append(f'El proyecto "{project_name}" no coincide con "{project.name}".')
        if not number:
            row_errors.append("Falta el número de lote.")
        if number in seen:
            row_errors.append(f"El lote {number} está duplicado dentro del Excel.")
        seen.add(number)
        
        item = {
            "number": number, 
            "block": str(get("block") or "").strip(), 
            "street": str(get("street") or "").strip(), 
            "notes": str(get("notes") or "").strip(),
            "north_boundary": str(get("north_boundary") or "").strip(),
            "south_boundary": str(get("south_boundary") or "").strip(),
            "east_boundary": str(get("east_boundary") or "").strip(),
            "west_boundary": str(get("west_boundary") or "").strip(),
            "status": STATUS_MAP.get(_norm(get("status")), "") if get("status") not in (None, "") else ""
        }
        
        for field in DECIMAL_FIELDS:
            value = get(field)
            try:
                item[field] = _decimal(value, field.replace("_", " "), required=(field == "sale_price" and value not in (None, "")))
            except ValueError as exc:
                row_errors.append(str(exc))
                
        if item["status"] == "" and get("status") not in (None, ""):
            row_errors.append(f"Estado no reconocido: {get('status')!s}.")
            
        existing = Lot.objects.filter(project=project, number=number).first() if number else None
        item["action"] = "Actualizar" if existing else "Crear"
        
        if existing is None and item.get("sale_price") is None:
            row_errors.append("Para crear un lote nuevo es obligatorio indicar el precio de venta.")
            
        item["existing_id"] = existing.pk if existing else None
        item["errors"] = row_errors
        item["excel_row"] = excel_row
        parsed.append(item)
        
        errors.extend([f"Fila {excel_row}: {e}" for e in row_errors])
        
    return parsed, errors

@login_required
@require_http_methods(["GET", "POST"])
def importar_lotes(request):
    projects = Project.objects.all()
    
    if load_workbook is None:
        return render(request, "core/importar_lotes.html", {"projects": projects, "dependency_missing": True})

    if request.method == "POST" and request.POST.get("confirm_import") == "1":
        preview_data = request.session.get("lot_import_preview")
        if not preview_data:
            messages.error(request, "La vista previa expiró. Vuelve a cargar el Excel.")
            return redirect("importar_lotes")
        if preview_data.get("errors"):
            messages.error(request, "Corrige los errores antes de confirmar la importación.")
            return redirect("importar_lotes")
            
        project = get_object_or_404(Project, pk=preview_data["project_id"])
        created = updated = 0
        
        with transaction.atomic():
            for item in preview_data["rows"]:
                number = item["number"]
                lot = Lot.objects.filter(project=project, number=number).first()
                if lot is None:
                    if item.get("sale_price") is None:
                        raise ValidationError(f"El lote {number} necesita precio de venta para crearse.")
                    lot = Lot(project=project, number=number, sale_price=Decimal(item["sale_price"]))
                    created += 1
                else:
                    updated += 1
                    
                if item.get("block"):
                    lot.block = item["block"]
                    block, _ = Block.objects.get_or_create(project=project, code=item["block"])
                    lot.block_ref = block
                if item.get("street"): lot.street = item["street"]
                
                # Guardar linderos (medidas)
                for field in ("area_m2", "front_m", "back_m", "left_side_m", "right_side_m", "sale_price", "commission_percentage"):
                    if item.get(field) is not None:
                        setattr(lot, field, Decimal(item[field]))
                        
                # Guardar nombres de linderos
                if item.get("north_boundary"): lot.north_boundary = item["north_boundary"]
                if item.get("south_boundary"): lot.south_boundary = item["south_boundary"]
                if item.get("east_boundary"): lot.east_boundary = item["east_boundary"]
                if item.get("west_boundary"): lot.west_boundary = item["west_boundary"]

                if item.get("status"): lot.status = item["status"]
                if item.get("notes"): lot.notes = item["notes"]
                
                lot.full_clean()
                lot.save()
                
        request.session.pop("lot_import_preview", None)
        messages.success(request, f"Importación completada: {created} lotes creados y {updated} actualizados. Los campos vacíos no borraron datos existentes.")
        return redirect("importar_lotes")

    if request.method == "POST":
        project_id = request.POST.get("project_id")
        project = get_object_or_404(Project, pk=project_id)
        upload = request.FILES.get("excel_file")
        
        if not upload or not upload.name.lower().endswith((".xlsx", ".xlsm")):
            messages.error(request, "Selecciona un archivo Excel .xlsx o .xlsm.")
            return render(request, "core/importar_lotes.html", {"projects": projects, "selected_project": project.pk})
            
        try:
            workbook = load_workbook(upload, read_only=True, data_only=True)
            sheet = workbook.active
            parsed, errors = _parse_rows(sheet.iter_rows(values_only=True), project)
            workbook.close()
        except Exception as exc:
            messages.error(request, f"No se pudo leer el Excel: {exc}")
            return render(request, "core/importar_lotes.html", {"projects": projects, "selected_project": project.pk})
            
        if not parsed:
            messages.error(request, "No se encontraron filas de lotes para revisar.")
            return render(request, "core/importar_lotes.html", {"projects": projects, "selected_project": project.pk, "errors": errors})
            
        # Session stores only normalized data needed for the explicit confirmation step.
        serializable = []
        for item in parsed:
            copy = dict(item)
            for field in DECIMAL_FIELDS:
                if copy.get(field) is not None:
                    copy[field] = str(copy[field])
            serializable.append(copy)
            
        request.session["lot_import_preview"] = {"project_id": project.pk, "rows": serializable, "errors": errors}
        request.session.modified = True
        return render(request, "core/importar_lotes.html", {"projects": projects, "selected_project": project.pk, "preview": parsed, "errors": errors, "can_confirm": not errors})

    return render(request, "core/importar_lotes.html", {"projects": projects})


@login_required
def lista_cuadras(request):
    projects = Project.objects.prefetch_related("blocks").all()
    selected_id = request.GET.get("project")
    selected_project = get_object_or_404(Project, pk=selected_id) if selected_id else projects.first()
    blocks = selected_project.blocks.prefetch_related("lots").all() if selected_project else []
    return render(request, "core/cuadras.html", {"projects": projects, "selected_project": selected_project, "blocks": blocks})
@login_required
@require_http_methods(["GET", "POST"])
def plano_referencia(request):
    from .models import ProjectPlan
    projects = Project.objects.all()
    
    if request.method == "POST":
        project = get_object_or_404(
            Project,
            pk=request.POST.get("project_id")
        )
        pdf = request.FILES.get("pdf_file")
        
        if not pdf or not pdf.name.lower().endswith(".pdf"):
            messages.error(request, "Selecciona un archivo PDF válido.")
        else:
            plan = ProjectPlan(
                project=project,
                title=request.POST.get("title") or "Plano de referencia",
                pdf_file=pdf,
                notes=request.POST.get("notes", "")
            )
            plan.full_clean()
            plan.save()
            messages.success(
                request,
                "PDF guardado como referencia. No se modificaron los lotes ni los archivos anteriores."
            )
            return redirect("plano_referencia")
            
    # Mostrar solamente el plano más reciente de cada proyecto.
    planes_recientes = {}
    for plan in (
        ProjectPlan.objects
        .select_related("project")
        .order_by("-uploaded_at", "-pk")
    ):
        if plan.project_id not in planes_recientes:
            planes_recientes[plan.project_id] = plan
            
    plans = list(planes_recientes.values())
    
    return render(
        request,
        "core/plano_referencia.html",
        {
            "projects": projects,
            "plans": plans,
        }
    )