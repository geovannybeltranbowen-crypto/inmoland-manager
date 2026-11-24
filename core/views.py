
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from django.utils import timezone
from .models import Installment
from .models import Project, Lot, Client, Sale, Payment, Commission


@login_required
def dashboard(request):
    from .models import Installment # Aseguramos que Installment esté importado
    
    hoy = timezone.localdate()
    
    # 1. Contar cuántas cuotas están vencidas (fecha pasada y no pagadas)
    cuotas_vencidas = Installment.objects.filter(
        due_date__lt=hoy, 
        status__in=["pending", "partial", "overdue"]
    ).count()
    
    # 2. Calcular cuánto dinero hay en la calle (saldo pendiente de esas cuotas)
    saldo_vencido = sum(
        (c.remaining_amount for c in Installment.objects.filter(due_date__lt=hoy, status__in=["pending", "partial", "overdue"])),
        Decimal("0.00")
    )

    paid_total = Payment.objects.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    
    context = {
        "projects_count": Project.objects.count(),
        "lots_count": Lot.objects.count(),
        "available_count": Lot.objects.filter(status=Lot.Status.AVAILABLE).count(),
        "clients_count": Client.objects.count(),
        "sales_count": Sale.objects.count(),
        "paid_total": paid_total,
        "blocked_commissions": Commission.objects.filter(status=Commission.Status.BLOCKED).count(),
        "enabled_commissions": Commission.objects.filter(status=Commission.Status.ENABLED).count(),
        "recent_sales": Sale.objects.select_related("lot", "lot__project", "client", "seller")[:8],
        "recent_lots": Lot.objects.select_related("project").order_by("status", "number")[:8],
        
        # --- AQUÍ ESTÁ LO NUEVO ---
        "cuotas_vencidas_count": cuotas_vencidas,
        "saldo_vencido": saldo_vencido,
    }
    return render(request, "core/dashboard.html", context)

@staff_member_required
def lotes_disponibles_por_proyecto(request):
    project_id = request.GET.get("project_id")

    if not project_id:
        return JsonResponse({"lotes": []})

    lotes = Lot.objects.filter(
        project_id=project_id,
        status=Lot.Status.AVAILABLE,
    ).order_by("number")

    datos = [
        {
            "id": lote.id,
            "numero": lote.number,
            "manzana": lote.block,
        }
        for lote in lotes
    ]

    return JsonResponse({"lotes": datos})
