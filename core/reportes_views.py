from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, DecimalField, F, Max, Min, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import render

from .models import Commission, Installment, Lot, Payment, Project, Sale, Seller


CERO = Value(Decimal("0.00"), output_field=DecimalField(max_digits=14, decimal_places=2))


@login_required
def index(request):
    """Página de inicio del módulo de reportes."""
    return render(request, "core/reportes/index.html")


@login_required
@login_required
def cartera(request):
    """
    R1 — Cartera: cuánto me deben.
    Suma de saldos pendientes de cuotas no pagadas al 100%.
    """
    from django.db.models import OuterRef, Subquery

    proyecto_id = request.GET.get("proyecto", "").strip()
    proyectos = Project.objects.order_by("name")

    # Subquery: total pagado por cuota (0 si no hay pagos).
    pagos_por_cuota = (
        Payment.objects.filter(installment=OuterRef("pk"))
        .values("installment")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    cuotas_qs = Installment.objects.filter(
        status__in=[
            Installment.Status.PENDING,
            Installment.Status.PARTIAL,
            Installment.Status.OVERDUE,
        ]
    )
    if proyecto_id:
        cuotas_qs = cuotas_qs.filter(sale__lot__project_id=proyecto_id)

    # Anotamos el total pagado por cuota y el saldo (amount - pagado).
    cuotas_qs = cuotas_qs.annotate(
        pagado_cuota=Coalesce(
            Subquery(pagos_por_cuota, output_field=DecimalField(max_digits=14, decimal_places=2)),
            CERO,
        )
    ).annotate(
        saldo_cuota=F("amount") - F("pagado_cuota")
    ).filter(saldo_cuota__gt=0)

    # Totales generales
    totales = cuotas_qs.aggregate(
        total_por_cobrar=Coalesce(Sum("saldo_cuota"), CERO),
        n_cuotas=Count("id"),
    )

    # Desglose por proyecto
    por_proyecto = (
        cuotas_qs.values(
            "sale__lot__project_id",
            "sale__lot__project__name",
        )
        .annotate(
            total=Coalesce(Sum("saldo_cuota"), CERO),
            n_cuotas=Count("id"),
        )
        .order_by("-total")
    )

    # Desglose por estado
    por_estado_qs = (
        cuotas_qs.values("status")
        .annotate(
            total=Coalesce(Sum("saldo_cuota"), CERO),
            n_cuotas=Count("id"),
        )
        .order_by("status")
    )
    etiquetas = dict(Installment.Status.choices)
    por_estado = [
        {
            "codigo": row["status"],
            "etiqueta": etiquetas.get(row["status"], row["status"]),
            "total": row["total"],
            "n_cuotas": row["n_cuotas"],
        }
        for row in por_estado_qs
    ]

    # Top 20 clientes que más deben
    por_cliente = (
        cuotas_qs.values(
            "sale__client_id",
            "sale__client__first_name",
            "sale__client__last_name",
            "sale__client__identification",
        )
        .annotate(
            total=Coalesce(Sum("saldo_cuota"), CERO),
            n_cuotas=Count("id"),
        )
        .order_by("-total")[:20]
    )

    contexto = {
        "proyectos": proyectos,
        "proyecto_id": proyecto_id,
        "total_por_cobrar": totales["total_por_cobrar"] or Decimal("0.00"),
        "n_cuotas": totales["n_cuotas"] or 0,
        "por_proyecto": por_proyecto,
        "por_estado": por_estado,
        "por_cliente": por_cliente,
    }
    return render(request, "core/reportes/cartera.html", contexto)
@login_required
def mora(request):
    """
    R2 — Mora: clientes con cuotas vencidas sin pagar.
    Una cuota cuenta como vencida si due_date < hoy y saldo > 0.
    """
    from datetime import date

    from django.db.models import Min, OuterRef, Subquery

    proyecto_id = request.GET.get("proyecto", "").strip()
    dias_min = request.GET.get("dias", "0").strip()

    try:
        dias_min_int = int(dias_min)
    except ValueError:
        dias_min_int = 0

    hoy = date.today()
    proyectos = Project.objects.order_by("name")

    pagos_por_cuota = (
        Payment.objects.filter(installment=OuterRef("pk"))
        .values("installment")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    cuotas_vencidas = (
        Installment.objects
        .filter(due_date__lt=hoy)
        .annotate(
            pagado_cuota=Coalesce(
                Subquery(
                    pagos_por_cuota,
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
                CERO,
            )
        )
        .annotate(
            saldo_cuota=F("amount") - F("pagado_cuota")
        )
        .filter(saldo_cuota__gt=0)
    )

    if proyecto_id:
        cuotas_vencidas = cuotas_vencidas.filter(
            sale__lot__project_id=proyecto_id
        )

    por_cliente_qs = (
        cuotas_vencidas.values(
            "sale__client_id",
            "sale__client__first_name",
            "sale__client__last_name",
            "sale__client__identification",
        )
        .annotate(
            total_mora=Coalesce(Sum("saldo_cuota"), CERO),
            n_cuotas=Count("id"),
            cuota_mas_vieja=Min("due_date"),
            cuota_mas_reciente=Min("due_date"),
        )
        .order_by("cuota_mas_vieja")
    )

    clientes_mora = []
    for fila in por_cliente_qs:
        dias_atraso = (hoy - fila["cuota_mas_vieja"]).days
        if dias_atraso < dias_min_int:
            continue
        clientes_mora.append({
            "client_id": fila["sale__client_id"],
            "nombre": f'{fila["sale__client__first_name"]} {fila["sale__client__last_name"]}',
            "identificacion": fila["sale__client__identification"] or "—",
            "total_mora": fila["total_mora"],
            "n_cuotas": fila["n_cuotas"],
            "cuota_mas_vieja": fila["cuota_mas_vieja"],
            "dias_atraso": dias_atraso,
        })

    clientes_mora.sort(key=lambda x: x["dias_atraso"], reverse=True)

    total_en_mora = sum(
        (c["total_mora"] for c in clientes_mora),
        Decimal("0.00"),
    )
    n_clientes = len(clientes_mora)
    n_cuotas_totales = sum(c["n_cuotas"] for c in clientes_mora)
    promedio = (
        (total_en_mora / n_clientes).quantize(Decimal("0.01"))
        if n_clientes else Decimal("0.00")
    )

    contexto = {
        "proyectos": proyectos,
        "proyecto_id": proyecto_id,
        "dias_min": dias_min_int,
        "opciones_dias": [0, 15, 30, 60, 90],
        "clientes_mora": clientes_mora,
        "total_en_mora": total_en_mora,
        "n_clientes": n_clientes,
        "n_cuotas": n_cuotas_totales,
        "promedio_por_cliente": promedio,
    }
    return render(request, "core/reportes/mora.html", contexto)
@login_required
def recaudacion(request):
    """
    R3 — Recaudación por mes.
    Entradas iniciales (Sale.initial_payment por sale_date)
    + cuotas cobradas (Payment.amount por payment_date).
    """
    from datetime import date

    from dateutil.relativedelta import relativedelta
    from django.db.models.functions import TruncMonth

    proyecto_id = request.GET.get("proyecto", "").strip()
    rango = request.GET.get("rango", "6").strip()
    try:
        rango_int = int(rango)
    except ValueError:
        rango_int = 6
    if rango_int not in (1, 3, 6, 12):
        rango_int = 6

    hoy = date.today()
    # Primer día del mes inicial (hace rango_int-1 meses) hasta hoy.
    primer_dia_mes_actual = hoy.replace(day=1)
    desde = primer_dia_mes_actual - relativedelta(months=rango_int - 1)

    proyectos = Project.objects.order_by("name")

    # Entradas iniciales por mes de venta.
    ventas_qs = Sale.objects.filter(sale_date__gte=desde)
    if proyecto_id:
        ventas_qs = ventas_qs.filter(lot__project_id=proyecto_id)
    entradas_por_mes = (
        ventas_qs
        .annotate(mes=TruncMonth("sale_date"))
        .values("mes")
        .annotate(total=Coalesce(Sum("initial_payment"), CERO))
        .order_by("mes")
    )

    # Cuotas cobradas por mes de pago.
    pagos_qs = Payment.objects.filter(payment_date__gte=desde)
    if proyecto_id:
        pagos_qs = pagos_qs.filter(sale__lot__project_id=proyecto_id)
    cuotas_por_mes = (
        pagos_qs
        .annotate(mes=TruncMonth("payment_date"))
        .values("mes")
        .annotate(total=Coalesce(Sum("amount"), CERO))
        .order_by("mes")
    )

    # Unir ambas series en un dict {mes: {entradas, cuotas}}.
    meses = {}
    for row in entradas_por_mes:
        meses.setdefault(row["mes"], {"entradas": Decimal("0.00"), "cuotas": Decimal("0.00")})
        meses[row["mes"]]["entradas"] = row["total"]
    for row in cuotas_por_mes:
        meses.setdefault(row["mes"], {"entradas": Decimal("0.00"), "cuotas": Decimal("0.00")})
        meses[row["mes"]]["cuotas"] = row["total"]

    # Rellenar meses sin datos para que la tabla sea continua.
    filas = []
    cursor = desde
    while cursor <= primer_dia_mes_actual:
        datos = meses.get(cursor, {"entradas": Decimal("0.00"), "cuotas": Decimal("0.00")})
        total = datos["entradas"] + datos["cuotas"]
        filas.append({
            "mes": cursor,
            "entradas": datos["entradas"],
            "cuotas": datos["cuotas"],
            "total": total,
        })
        cursor = cursor + relativedelta(months=1)

    # Totales del período.
    total_entradas = sum((f["entradas"] for f in filas), Decimal("0.00"))
    total_cuotas = sum((f["cuotas"] for f in filas), Decimal("0.00"))
    total_recaudado = total_entradas + total_cuotas
    n_pagos = pagos_qs.count()

    contexto = {
        "proyectos": proyectos,
        "proyecto_id": proyecto_id,
        "rango": rango_int,
        "opciones_rango": [1, 3, 6, 12],
        "filas": filas,
        "total_entradas": total_entradas,
        "total_cuotas": total_cuotas,
        "total_recaudado": total_recaudado,
        "n_pagos": n_pagos,
    }
    return render(request, "core/reportes/recaudacion.html", contexto)
@login_required
def ventas_mes(request):
    """
    R6 — Ventas por mes.
    Cuenta ventas y suma montos, separando contado vs crédito.
    Agrupado por mes de sale_date.
    """
    from datetime import date

    from dateutil.relativedelta import relativedelta
    from django.db.models.functions import TruncMonth

    proyecto_id = request.GET.get("proyecto", "").strip()
    vendedor_id = request.GET.get("vendedor", "").strip()
    rango = request.GET.get("rango", "6").strip()
    try:
        rango_int = int(rango)
    except ValueError:
        rango_int = 6
    if rango_int not in (1, 3, 6, 12):
        rango_int = 6

    hoy = date.today()
    primer_dia_mes_actual = hoy.replace(day=1)
    desde = primer_dia_mes_actual - relativedelta(months=rango_int - 1)

    proyectos = Project.objects.order_by("name")
    vendedores = Seller.objects.filter(active=True).order_by("name")

    ventas_qs = Sale.objects.filter(sale_date__gte=desde)
    if proyecto_id:
        ventas_qs = ventas_qs.filter(lot__project_id=proyecto_id)
    if vendedor_id:
        ventas_qs = ventas_qs.filter(seller_id=vendedor_id)

    # Totales del período
    totales = ventas_qs.aggregate(
        n_ventas=Count("id"),
        monto_total=Coalesce(Sum("final_price"), CERO),
    )

    # Contado vs crédito
    contado_qs = ventas_qs.filter(sale_type=Sale.SaleType.CASH)
    credito_qs = ventas_qs.filter(sale_type=Sale.SaleType.CREDIT)

    total_contado = contado_qs.aggregate(
        monto=Coalesce(Sum("final_price"), CERO),
        n=Count("id"),
    )
    total_credito = credito_qs.aggregate(
        monto=Coalesce(Sum("final_price"), CERO),
        n=Count("id"),
    )

    # Agrupación por mes
    por_mes_qs = (
        ventas_qs
        .annotate(mes=TruncMonth("sale_date"))
        .values("mes")
        .annotate(
            n_ventas=Count("id"),
            monto_contado=Coalesce(
                Sum("final_price", filter=Q(sale_type=Sale.SaleType.CASH)),
                CERO,
            ),
            monto_credito=Coalesce(
                Sum("final_price", filter=Q(sale_type=Sale.SaleType.CREDIT)),
                CERO,
            ),
            monto_total=Coalesce(Sum("final_price"), CERO),
        )
        .order_by("mes")
    )

    # Rellenar meses sin datos para que la tabla sea continua
    meses_dict = {row["mes"]: row for row in por_mes_qs}
    filas = []
    cursor = desde
    while cursor <= primer_dia_mes_actual:
        row = meses_dict.get(cursor, {
            "mes": cursor,
            "n_ventas": 0,
            "monto_contado": Decimal("0.00"),
            "monto_credito": Decimal("0.00"),
            "monto_total": Decimal("0.00"),
        })
        filas.append(row)
        cursor = cursor + relativedelta(months=1)

    contexto = {
        "proyectos": proyectos,
        "vendedores": vendedores,
        "proyecto_id": proyecto_id,
        "vendedor_id": vendedor_id,
        "rango": rango_int,
        "opciones_rango": [1, 3, 6, 12],
        "filas": filas,
        "total_ventas": totales["n_ventas"] or 0,
        "monto_total": totales["monto_total"] or Decimal("0.00"),
        "total_contado": total_contado["monto"] or Decimal("0.00"),
        "n_contado": total_contado["n"] or 0,
        "total_credito": total_credito["monto"] or Decimal("0.00"),
        "n_credito": total_credito["n"] or 0,
    }
    return render(request, "core/reportes/ventas_mes.html", contexto)
@login_required
def comisiones_mes(request):
    """
    R7 — Comisiones por mes y por vendedor.
    Agrupadas por mes de venta (sale.sale_date).
    """
    from datetime import date

    from dateutil.relativedelta import relativedelta
    from django.db.models.functions import TruncMonth

    vendedor_id = request.GET.get("vendedor", "").strip()
    rango = request.GET.get("rango", "6").strip()
    try:
        rango_int = int(rango)
    except ValueError:
        rango_int = 6
    if rango_int not in (1, 3, 6, 12):
        rango_int = 6

    hoy = date.today()
    primer_dia_mes_actual = hoy.replace(day=1)
    desde = primer_dia_mes_actual - relativedelta(months=rango_int - 1)

    vendedores = Seller.objects.filter(active=True).order_by("name")

    comisiones_qs = Commission.objects.filter(sale__sale_date__gte=desde)
    if vendedor_id:
        comisiones_qs = comisiones_qs.filter(seller_id=vendedor_id)

    # Totales por estado
    totales = comisiones_qs.aggregate(
        total=Coalesce(Sum("amount"), CERO),
        n=Count("id"),
    )
    pagadas = comisiones_qs.filter(status=Commission.Status.PAID).aggregate(
        monto=Coalesce(Sum("amount"), CERO),
        n=Count("id"),
    )
    habilitadas = comisiones_qs.filter(status=Commission.Status.ENABLED).aggregate(
        monto=Coalesce(Sum("amount"), CERO),
        n=Count("id"),
    )
    pendientes = comisiones_qs.filter(
        status__in=[
            Commission.Status.PENDING,
            Commission.Status.BLOCKED,
        ]
    ).aggregate(
        monto=Coalesce(Sum("amount"), CERO),
        n=Count("id"),
    )

    # Agrupación por mes y vendedor
    por_mes_qs = (
        comisiones_qs
        .annotate(mes=TruncMonth("sale__sale_date"))
        .values("mes", "seller__name", "seller_id")
        .annotate(
            total=Coalesce(Sum("amount"), CERO),
            n_comisiones=Count("id"),
            monto_pagado=Coalesce(
                Sum("amount", filter=Q(status=Commission.Status.PAID)),
                CERO,
            ),
            monto_pendiente=Coalesce(
                Sum("amount", filter=Q(
                    status__in=[
                        Commission.Status.PENDING,
                        Commission.Status.BLOCKED,
                        Commission.Status.ENABLED,
                    ]
                )),
                CERO,
            ),
        )
        .order_by("mes", "seller__name")
    )

    filas = list(por_mes_qs)

    contexto = {
        "vendedores": vendedores,
        "vendedor_id": vendedor_id,
        "rango": rango_int,
        "opciones_rango": [1, 3, 6, 12],
        "filas": filas,
        "total_comisiones": totales["total"] or Decimal("0.00"),
        "n_comisiones": totales["n"] or 0,
        "total_pagado": pagadas["monto"] or Decimal("0.00"),
        "n_pagado": pagadas["n"] or 0,
        "total_habilitado": habilitadas["monto"] or Decimal("0.00"),
        "n_habilitado": habilitadas["n"] or 0,
        "total_pendiente": pendientes["monto"] or Decimal("0.00"),
        "n_pendiente": pendientes["n"] or 0,
    }
    return render(request, "core/reportes/comisiones_mes.html", contexto)
@login_required
def creditos(request):
    """
    R4 — Créditos: financiado vs cobrado vs pendiente.
    Solo considera ventas a crédito.
    """
    from datetime import date

    from django.db.models import OuterRef, Subquery
    from django.db.models.functions import TruncMonth

    proyecto_id = request.GET.get("proyecto", "").strip()
    proyectos = Project.objects.order_by("name")
    hoy = date.today()

    # Subquery: total pagado por venta (suma de Payments).
    pagos_por_venta = (
        Payment.objects.filter(sale=OuterRef("pk"))
        .values("sale")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    # Ventas a crédito con el total pagado anotado.
    ventas_credito = Sale.objects.filter(sale_type=Sale.SaleType.CREDIT)
    if proyecto_id:
        ventas_credito = ventas_credito.filter(lot__project_id=proyecto_id)

    ventas_credito = ventas_credito.annotate(
        pagado_total=Coalesce(
            Subquery(
                pagos_por_venta,
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
            CERO,
        )
    ).annotate(
        financiado=F("final_price") - F("initial_payment"),
        pendiente=F("final_price") - F("initial_payment") - F("pagado_total"),
    )

    # Totales generales
    totales = ventas_credito.aggregate(
        total_financiado=Coalesce(Sum("financiado"), CERO),
        total_cobrado=Coalesce(Sum("pagado_total"), CERO),
        total_pendiente=Coalesce(Sum("pendiente"), CERO),
        n_ventas=Count("id"),
    )

    total_financiado = totales["total_financiado"] or Decimal("0.00")
    total_cobrado = totales["total_cobrado"] or Decimal("0.00")
    total_pendiente = totales["total_pendiente"] or Decimal("0.00")
    porcentaje_cobrado = (
        (total_cobrado * Decimal("100") / total_financiado).quantize(Decimal("0.01"))
        if total_financiado > 0 else Decimal("0.00")
    )

    # Por proyecto
    por_proyecto_qs = (
        ventas_credito.values("lot__project__name")
        .annotate(
            financiado=Coalesce(Sum("financiado"), CERO),
            cobrado=Coalesce(Sum("pagado_total"), CERO),
            pendiente=Coalesce(Sum("pendiente"), CERO),
            n_ventas=Count("id"),
        )
        .order_by("-financiado")
    )
    por_proyecto = []
    for row in por_proyecto_qs:
        pct = (
            (row["cobrado"] * Decimal("100") / row["financiado"]).quantize(Decimal("0.01"))
            if row["financiado"] > 0 else Decimal("0.00")
        )
        por_proyecto.append({
            "proyecto": row["lot__project__name"],
            "financiado": row["financiado"],
            "cobrado": row["cobrado"],
            "pendiente": row["pendiente"],
            "n_ventas": row["n_ventas"],
            "porcentaje": pct,
        })

    # Proyección mes a mes: cuotas futuras con saldo pendiente.
    pagos_por_cuota = (
        Payment.objects.filter(installment=OuterRef("pk"))
        .values("installment")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    cuotas_futuras = (
        Installment.objects
        .filter(due_date__gte=hoy)
        .filter(sale__sale_type=Sale.SaleType.CREDIT)
        .annotate(
            pagado_cuota=Coalesce(
                Subquery(
                    pagos_por_cuota,
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
                CERO,
            )
        )
        .annotate(saldo_cuota=F("amount") - F("pagado_cuota"))
        .filter(saldo_cuota__gt=0)
    )
    if proyecto_id:
        cuotas_futuras = cuotas_futuras.filter(sale__lot__project_id=proyecto_id)

    proyeccion_qs = (
        cuotas_futuras
        .annotate(mes=TruncMonth("due_date"))
        .values("mes")
        .annotate(
            n_cuotas=Count("id"),
            monto=Coalesce(Sum("saldo_cuota"), CERO),
        )
        .order_by("mes")
    )
    proyeccion = list(proyeccion_qs)

    contexto = {
        "proyectos": proyectos,
        "proyecto_id": proyecto_id,
        "total_financiado": total_financiado,
        "total_cobrado": total_cobrado,
        "total_pendiente": total_pendiente,
        "porcentaje_cobrado": porcentaje_cobrado,
        "n_ventas": totales["n_ventas"] or 0,
        "por_proyecto": por_proyecto,
        "proyeccion": proyeccion,
    }
    return render(request, "core/reportes/creditos.html", contexto)
@login_required
def mejores_clientes(request):
    """
    R5 — Mejores clientes.
    Ranking por total pagado, cumplimiento y ventas cerradas.
    """
    from datetime import date

    from dateutil.relativedelta import relativedelta

    proyecto_id = request.GET.get("proyecto", "").strip()
    rango = request.GET.get("rango", "12").strip()
    try:
        rango_int = int(rango)
    except ValueError:
        rango_int = 12
    if rango_int not in (1, 3, 6, 12):
        rango_int = 12

    hoy = date.today()
    primer_dia_mes_actual = hoy.replace(day=1)
    desde = primer_dia_mes_actual - relativedelta(months=rango_int - 1)

    proyectos = Project.objects.order_by("name")

    # Base: todas las ventas en el período, filtradas por proyecto.
    ventas_qs = Sale.objects.filter(sale_date__gte=desde)
    if proyecto_id:
        ventas_qs = ventas_qs.filter(lot__project_id=proyecto_id)

    # Por cliente: nº ventas, total inicial, última compra.
    por_cliente_qs = (
        ventas_qs.values(
            "client_id",
            "client__first_name",
            "client__last_name",
            "client__identification",
        )
        .annotate(
            n_ventas=Count("id"),
            total_inicial=Coalesce(Sum("initial_payment"), CERO),
            ultima_compra=Max("sale_date"),
        )
        .order_by("-total_inicial")
    )

    # Para cada cliente, sumar los pagos (cuotas) de sus ventas.
    clientes = []
    for row in por_cliente_qs:
        cliente_id = row["client_id"]
        pagos_qs = Payment.objects.filter(sale__client_id=cliente_id)
        if proyecto_id:
            pagos_qs = pagos_qs.filter(sale__lot__project_id=proyecto_id)
        total_cuotas = pagos_qs.aggregate(
            total=Coalesce(Sum("amount"), CERO)
        )["total"]

        # Cuotas: totales y pagadas
        cuotas_qs = Installment.objects.filter(sale__client_id=cliente_id)
        if proyecto_id:
            cuotas_qs = cuotas_qs.filter(sale__lot__project_id=proyecto_id)
        total_cuotas_n = cuotas_qs.count()
        pagadas_n = cuotas_qs.filter(status=Installment.Status.PAID).count()
        cumplimiento = (
            (Decimal(pagadas_n) * Decimal("100") / Decimal(total_cuotas_n)).quantize(Decimal("0.01"))
            if total_cuotas_n > 0 else Decimal("0.00")
        )

        total_pagado = row["total_inicial"] + total_cuotas

        clientes.append({
            "nombre": f'{row["client__first_name"]} {row["client__last_name"]}',
            "identificacion": row["client__identification"] or "—",
            "n_ventas": row["n_ventas"],
            "total_pagado": total_pagado,
            "cumplimiento": cumplimiento,
            "ultima_compra": row["ultima_compra"],
            "cuotas_pagadas": pagadas_n,
            "cuotas_total": total_cuotas_n,
        })

    # Ordenar por total pagado descendente y limitar a 20.
    clientes.sort(key=lambda c: c["total_pagado"], reverse=True)
    clientes = clientes[:20]

    # Totales para las tarjetas.
    n_clientes = len(clientes)
    mejor = clientes[0] if clientes else None
    promedio = (
        (sum((c["total_pagado"] for c in clientes), Decimal("0.00")) / n_clientes).quantize(Decimal("0.01"))
        if n_clientes else Decimal("0.00")
    )

    contexto = {
        "proyectos": proyectos,
        "proyecto_id": proyecto_id,
        "rango": rango_int,
        "opciones_rango": [1, 3, 6, 12],
        "clientes": clientes,
        "n_clientes": n_clientes,
        "mejor_cliente": mejor,
        "promedio_pagado": promedio,
    }
    return render(request, "core/reportes/mejores_clientes.html", contexto)
@login_required
def sri(request):
    """
    R8 — SRI: valores vendidos por mes (base imponible).
    Sin calcular IVA: el contador aplica la tasa.
    """
    from datetime import date

    from django.db.models.functions import TruncMonth

    proyecto_id = request.GET.get("proyecto", "").strip()
    hoy = date.today()
    desde_str = request.GET.get("desde", "").strip() or f"{hoy.year}-01-01"
    hasta_str = request.GET.get("hasta", "").strip() or hoy.isoformat()

    # Parsear fechas
    try:
        from datetime import date as _date
        desde = _date.fromisoformat(desde_str)
    except ValueError:
        desde = date(hoy.year, 1, 1)
        desde_str = desde.isoformat()
    try:
        hasta = _date.fromisoformat(hasta_str)
    except ValueError:
        hasta = hoy
        hasta_str = hasta.isoformat()

    proyectos = Project.objects.order_by("name")

    ventas_qs = Sale.objects.filter(
        sale_date__gte=desde,
        sale_date__lte=hasta,
    )
    if proyecto_id:
        ventas_qs = ventas_qs.filter(lot__project_id=proyecto_id)

    # Agrupación por mes
    por_mes_qs = (
        ventas_qs
        .annotate(mes=TruncMonth("sale_date"))
        .values("mes")
        .annotate(
            n_ventas=Count("id"),
            valor_vendido=Coalesce(Sum("final_price"), CERO),
        )
        .order_by("mes")
    )

    filas = list(por_mes_qs)

    # Totales
    totales = ventas_qs.aggregate(
        n_ventas=Count("id"),
        valor_vendido=Coalesce(Sum("final_price"), CERO),
    )

    contexto = {
        "proyectos": proyectos,
        "proyecto_id": proyecto_id,
        "desde": desde_str,
        "hasta": hasta_str,
        "filas": filas,
        "n_ventas": totales["n_ventas"] or 0,
        "valor_vendido": totales["valor_vendido"] or Decimal("0.00"),
    }
    return render(request, "core/reportes/sri.html", contexto)


@login_required
def sri_excel(request):
    """Exporta el reporte SRI a Excel (.xlsx)."""
    from datetime import date

    from django.http import HttpResponse
    from django.db.models.functions import TruncMonth
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment

    proyecto_id = request.GET.get("proyecto", "").strip()
    hoy = date.today()
    desde_str = request.GET.get("desde", "").strip() or f"{hoy.year}-01-01"
    hasta_str = request.GET.get("hasta", "").strip() or hoy.isoformat()

    try:
        desde = date.fromisoformat(desde_str)
    except ValueError:
        desde = date(hoy.year, 1, 1)
    try:
        hasta = date.fromisoformat(hasta_str)
    except ValueError:
        hasta = hoy

    ventas_qs = Sale.objects.filter(
        sale_date__gte=desde,
        sale_date__lte=hasta,
    )
    if proyecto_id:
        ventas_qs = ventas_qs.filter(lot__project_id=proyecto_id)

    por_mes_qs = (
        ventas_qs
        .annotate(mes=TruncMonth("sale_date"))
        .values("mes")
        .annotate(
            n_ventas=Count("id"),
            valor_vendido=Coalesce(Sum("final_price"), CERO),
        )
        .order_by("mes")
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "SRI Ventas"

    # Encabezado
    headers = ["Mes", "Nº de ventas", "Valor vendido (USD)"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    # Filas
    total_ventas = 0
    total_valor = Decimal("0.00")
    for row in por_mes_qs:
        mes_str = row["mes"].strftime("%Y-%m") if row["mes"] else ""
        ws.append([mes_str, row["n_ventas"], float(row["valor_vendido"])])
        total_ventas += row["n_ventas"]
        total_valor += row["valor_vendido"]

    # Total
    ws.append(["TOTAL", total_ventas, float(total_valor)])
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)

    # Anchos
    ws.column_dimensions["A"].width = 15
    ws.column_dimensions["B"].width = 15
    ws.column_dimensions["C"].width = 25

    # Formato de moneda en columna C
    for row in ws.iter_rows(min_row=2, max_col=3, max_row=ws.max_row):
        row[2].number_format = '#,##0.00'

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="SRI_ventas_{desde_str}_a_{hasta_str}.xlsx"'
    )
    wb.save(response)
    return response