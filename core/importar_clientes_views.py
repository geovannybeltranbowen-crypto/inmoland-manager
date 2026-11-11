import openpyxl
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from .models import Client

@login_required
@require_http_methods(["GET", "POST"])
def importar_clientes(request):
    if request.method == "POST" and request.POST.get("confirm_import") == "1":
        # Confirmar e importar
        datos = request.session.get("clientes_preview", [])
        creados = 0
        actualizados = 0
        for c in datos:
            # Buscamos si ya existe por cédula
            cliente, created = Client.objects.get_or_create(
                identification=c["identification"],
                defaults={
                    "first_name": c["first_name"],
                    "last_name": c["last_name"],
                    "phone": c["phone"],
                    "email": c["email"],
                    "notes": c["notes"],
                }
            )
            if created:
                creados += 1
            else:
                # Si ya existía, actualizamos los datos
                cliente.first_name = c["first_name"]
                cliente.last_name = c["last_name"]
                cliente.phone = c["phone"]
                cliente.email = c["email"]
                cliente.save()
                actualizados += 1
        
        request.session.pop("clientes_preview", None)
        messages.success(request, f"Importación completada: {creados} creados, {actualizados} actualizados.")
        return redirect("importar_clientes")

    if request.method == "POST":
        upload = request.FILES.get("excel_file")
        if not upload or not upload.name.lower().endswith((".xlsx", ".xlsm")):
            messages.error(request, "Selecciona un archivo Excel válido (.xlsx).")
            return render(request, "core/importar_clientes.html")

        try:
            wb = openpyxl.load_workbook(upload, read_only=True, data_only=True)
            sheet = wb.active
            rows = list(sheet.iter_rows(values_only=True))
            
            if not rows:
                messages.error(request, "El archivo está vacío.")
                return render(request, "core/importar_clientes.html")

            # Detectar columnas (asumimos orden: Nombres, Apellidos, Cedula, Telefono, Email, Notas)
            # Ignoramos la primera fila (encabezados)
            preview = []
            for row in rows[1:]:
                if not any(row): # Fila vacía
                    continue
                
                first_name = str(row[0] or "").strip()
                last_name = str(row[1] or "").strip()
                identification = str(row[2] or "").strip()
                phone = str(row[3] or "").strip()
                email = str(row[4] or "").strip()
                notes = str(row[5] or "").strip()

                if not first_name or not last_name or not identification:
                    continue # Saltar si faltan datos clave

                exists = Client.objects.filter(identification=identification).exists()
                
                preview.append({
                    "first_name": first_name,
                    "last_name": last_name,
                    "identification": identification,
                    "phone": phone,
                    "email": email,
                    "notes": notes,
                    "exists": exists,
                })
            
            wb.close()
            
            if not preview:
                messages.error(request, "No se encontraron datos válidos en el Excel.")
                return render(request, "core/importar_clientes.html")

            # Guardar en sesión para confirmar después
            request.session["clientes_preview"] = preview
            request.session.modified = True

            return render(request, "core/importar_clientes.html", {
                "preview": preview,
                "can_confirm": True
            })

        except Exception as e:
            messages.error(request, f"Error al leer el Excel: {e}")
            return render(request, "core/importar_clientes.html")

    return render(request, "core/importar_clientes.html")