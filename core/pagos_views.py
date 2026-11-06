from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Installment, Payment


@login_required
@require_http_methods(["GET", "POST"])
def registrar_pago_cuota(request, installment_id):
    """Registrar un pago para una cuota concreta."""
    cuota = get_object_or_404(
        Installment.objects.select_related(
            "sale",
            "sale__lot",
            "sale__lot__project",
            "sale__client",
        ),
        pk=installment_id,
    )

    pagos_existentes = cuota.payments.select_related().order_by(
        "-payment_date", "-id"
    )

    if request.method == "POST":
        fecha_str = (request.POST.get("payment_date") or "").strip()
        monto_str = (request.POST.get("amount") or "").strip().replace(",", ".")
        referencia = (request.POST.get("reference") or "").strip()
        notas = (request.POST.get("notes") or "").strip()

        errores = []

        # Validar fecha
        fecha_pago = None
        if not fecha_str:
            errores.append("La fecha de pago es obligatoria.")
        else:
            try:
                from datetime import date

                partes = fecha_str.split("-")
                fecha_pago = date(
                    int(partes[0]), int(partes[1]), int(partes[2])
                )
            except (ValueError, IndexError):
                errores.append(
                    "La fecha de pago no tiene un formato válido."
                )

        # Validar monto
        monto = None
        if not monto_str:
            errores.append("El monto es obligatorio.")
        else:
            try:
                monto = Decimal(monto_str)
                if monto <= Decimal("0.00"):
                    errores.append("El monto debe ser mayor que cero.")
            except (InvalidOperation, ValueError):
                errores.append("El monto no es un número válido.")

        # Validar que no exceda el saldo pendiente de la cuota
        if monto is not None:
            saldo = cuota.remaining_amount
            if saldo <= Decimal("0.00"):
                errores.append(
                    "Esta cuota ya está totalmente pagada. "
                    "No se puede registrar otro pago."
                )
            elif monto > saldo:
                errores.append(
                    f"El monto (${monto}) supera el saldo pendiente "
                    f"de la cuota (${saldo})."
                )

        if errores:
            for e in errores:
                messages.error(request, e)
        else:
            with transaction.atomic():
                Payment.objects.create(
                    sale=cuota.sale,
                    installment=cuota,
                    payment_date=fecha_pago,
                    amount=monto,
                    reference=referencia,
                    notes=notas,
                )
            messages.success(
                request,
                f"Pago de ${monto} registrado en la cuota {cuota.number}.",
            )
            return redirect("registrar_pago_cuota", installment_id=cuota.pk)

    contexto = {
        "cuota": cuota,
        "pagos_existentes": pagos_existentes,
        "hoy": timezone.localdate().isoformat(),
        "saldo": cuota.remaining_amount,
        "total_pagado_cuota": cuota.total_paid,
    }
    return render(request, "core/pagar_cuota.html", contexto)


@login_required
@require_http_methods(["POST"])
def anular_pago(request, payment_id):
    """Anular un pago: se borra el Payment y la cuota se recalcula sola."""
    pago = get_object_or_404(Payment, pk=payment_id)
    cuota_id = pago.installment_id
    monto = pago.amount

    # Guardamos el id de la cuota antes de borrar para volver a su pantalla.
    with transaction.atomic():
        pago.delete()  # Payment.delete() ya refresca la cuota y la comisión.

    messages.success(
        request,
        f"Pago de ${monto} anulado correctamente.",
    )

    if cuota_id:
        return redirect("registrar_pago_cuota", installment_id=cuota_id)
    return redirect("admin:core_installment_changelist")