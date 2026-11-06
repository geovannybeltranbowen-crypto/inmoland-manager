
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render
from decimal import Decimal
from .models import Project, Lot, Sale, Seller


@login_required
def lista_ventas(request):
    ventas = Sale.objects.select_related(
        "lot",
        "lot__project",
        "client",
        "seller",
    ).prefetch_related("payments")

    proyectos = Project.objects.all()

    proyecto_id = request.GET.get("proyecto", "").strip()
    estado = request.GET.get("estado", "").strip()
    cliente = request.GET.get("cliente", "").strip()
    vendedor_id = request.GET.get("vendedor", "").strip()
    modalidad = request.GET.get("modalidad", "").strip()
    fecha_desde = request.GET.get("desde", "").strip()
    fecha_hasta = request.GET.get("hasta", "").strip()

    if proyecto_id:
        ventas = ventas.filter(lot__project_id=proyecto_id)

    if estado:
        ventas = ventas.filter(lot__status=estado)

    if cliente:
        ventas = ventas.filter(
            client__first_name__icontains=cliente
        ) | ventas.filter(
            client__last_name__icontains=cliente
        )

    if vendedor_id:
        ventas = ventas.filter(seller_id=vendedor_id)

    if modalidad:
        ventas = ventas.filter(sale_type=modalidad)

    if fecha_desde:
        ventas = ventas.filter(sale_date__gte=fecha_desde)

    if fecha_hasta:
        ventas = ventas.filter(sale_date__lte=fecha_hasta)

    ventas = ventas.distinct()

    total_ventas = ventas.count()
    
   
   
    total_cobrado = sum(
        (
            venta.initial_payment + venta.total_paid
            for venta in ventas
        ),
        start=Decimal("0.00"),
    )


    
    for venta in ventas:
        venta.total_pagado_calculado = (
            venta.initial_payment + venta.total_paid
        )
        venta.saldo_pendiente = max(
            Decimal("0.00"),
            venta.final_price - venta.total_pagado_calculado
        )

    

    contexto = {
        "ventas": ventas,
        "proyectos": proyectos,
        "estados_lote": Lot.Status.choices,
        "vendedores": Seller.objects.filter(active=True),
        "total_ventas": total_ventas,
        "total_cobrado": total_cobrado,
        "filtros": {
            "proyecto": proyecto_id,
            "estado": estado,
            "cliente": cliente,
            "vendedor": vendedor_id,
            "modalidad": modalidad,
            "desde": fecha_desde,
            "hasta": fecha_hasta,
        },
    }

    return render(request, "core/lista_ventas.html", contexto)
