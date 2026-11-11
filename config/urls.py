from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from core.views import dashboard, lotes_disponibles_por_proyecto
from core.plano_views import plano_lotes, guardar_geometria_lote
from core.gestion_lotes_views import importar_lotes, lista_cuadras, plano_referencia
from core.ventas_views import lista_ventas
from core.pagos_views import registrar_pago_cuota, anular_pago
from core.importar_clientes_views import importar_clientes
from core.reportes_views import (
    index as reportes_index,
    cartera as reporte_cartera,
    mora as reporte_mora,
    recaudacion as reporte_recaudacion,
    ventas_mes as reporte_ventas_mes,
    comisiones_mes as reporte_comisiones_mes,
    creditos as reporte_creditos,
    mejores_clientes as reporte_mejores_clientes,
    sri as reporte_sri,
    sri_excel as reporte_sri_excel,
)
from django.contrib import admin
admin.site.site_url = "/"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", dashboard, name="dashboard"),
    path(
        "lotes-disponibles-por-proyecto/",
        lotes_disponibles_por_proyecto,
        name="lotes_disponibles_por_proyecto",
    ),
    path("plano-lotes/", plano_lotes, name="plano_lotes"),
    path("importar-lotes/", importar_lotes, name="importar_lotes"),
    path("cuadras/", lista_cuadras, name="lista_cuadras"),
    path("plano-referencia/", plano_referencia, name="plano_referencia"),
    path("ventas/", lista_ventas, name="lista_ventas"),
    path(
        "guardar-geometria-lote/",
        guardar_geometria_lote,
        name="guardar_geometria_lote",
    ),
    path(
        "cuotas/<int:installment_id>/pagar/",
        registrar_pago_cuota,
        name="registrar_pago_cuota",
    ),
    path(
        "pagos/<int:payment_id>/anular/",
        anular_pago,
        name="anular_pago",
    ),
    path("reportes/", reportes_index, name="reportes_index"),
    path("reportes/cartera/", reporte_cartera, name="reporte_cartera"),
    path("reportes/mora/", reporte_mora, name="reporte_mora"),
    path("reportes/recaudacion/", reporte_recaudacion, name="reporte_recaudacion"),
    path("reportes/ventas-mes/", reporte_ventas_mes, name="reporte_ventas_mes"),
    path("reportes/comisiones-mes/", reporte_comisiones_mes, name="reporte_comisiones_mes"),
    path("reportes/creditos/", reporte_creditos, name="reporte_creditos"),
    path("reportes/mejores-clientes/", reporte_mejores_clientes, name="reporte_mejores_clientes"),
    path("reportes/sri/", reporte_sri, name="reporte_sri"),
    path("reportes/sri/excel/", reporte_sri_excel, name="reporte_sri_excel"),
    path("importar-clientes/", importar_clientes, name="importar_clientes"),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )