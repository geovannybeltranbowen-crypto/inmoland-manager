from django.contrib import admin
from django.core.exceptions import ValidationError
from django import forms
from django.db import models
from django.db import transaction
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    Project, Block, Lot, Client, Seller, Sale, Payment,
    Promise, Commission, LegalFee, Installment,
)
from django.utils import timezone
from decimal import Decimal

@admin.action(description="Cancelar crédito (Pagar saldo total)")
def cancelar_credito_action(self, request, queryset):
    from .models import Installment, Payment
    for sale in queryset:
        if sale.sale_type != Sale.SaleType.CREDIT:
            self.message_user(request, f"La venta {sale.pk} no es a crédito.", level=messages.WARNING)
            continue
        cuotas_pendientes = sale.installments.filter(status__in=[Installment.Status.PENDING, Installment.Status.PARTIAL, Installment.Status.OVERDUE])
        if not cuotas_pendientes.exists():
            continue
        saldo_total = sum((c.remaining_amount for c in cuotas_pendientes), Decimal("0.00"))
        if saldo_total <= 0:
            continue
        with transaction.atomic():
            Payment.objects.create(
                sale=sale,
                amount=saldo_total,
                payment_date=timezone.localdate(),
                reference="Cancelación anticipada de crédito",
                notes="Pago total del saldo restante."
            )
            for cuota in cuotas_pendientes:
                cuota.status = Installment.Status.PAID
                cuota.save(update_fields=["status"])
        self.message_user(request, f"Crédito de la venta {sale.pk} cancelado. Pago de ${saldo_total}.", level=messages.SUCCESS)

    @admin.action(description="Descargar PDF de Reserva / Promesa")
    def descargar_pdf_reserva(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Por favor, selecciona solo UNA venta para descargar el PDF.", level=messages.WARNING)
            return
        
        venta = queryset.first()
        url = f"/pdf/reserva/{venta.id}/"
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(url)

admin.site.site_header = "INMOLAND Manager"
admin.site.site_title = "INMOLAND"
admin.site.index_title = "Administración de Compra-Venta Bienes INMOLAND"
admin.site.index_template = "admin/inmoland_index.html"

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "location", "acquisition_cost", "development_costs")
    search_fields = ("name", "location")

@admin.register(Lot)
class LotAdmin(admin.ModelAdmin):
    list_display = ("number", "project", "block", "area_m2", "front_m", "back_m", "right_side_m", "left_side_m", "sale_price", "status")
    list_filter = ("project", "status", "block")
    search_fields = ("number", "block", "project__name")

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "identification", "phone", "email")
    search_fields = ("first_name", "last_name", "identification", "phone", "email")

@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = ("name", "fixed_commission", "is_sales_manager", "active")
    list_filter = ("is_sales_manager", "active")
    search_fields = ("name",)

class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0

class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0
    can_delete = False
    fields = (
        "number",
        "due_date",
        "principal_amount",
        "interest_amount",
        "amount",
        "status",
    )
    readonly_fields = fields
    show_change_link = True

class SaleAdminForm(forms.ModelForm):
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        label="Proyecto",
        required=True,
        empty_label="Seleccione un proyecto",
    )

    class Meta:
        model = Sale
        fields = (
        "project",
        "lot",
        "client",
        "seller",
        "sale_type",
        "etapa",
        "sale_date",
        "final_price",
        "initial_payment",
        "credit_months",
        "interest_type",
        "monthly_interest_rate",
        "notes",
    )

    class Media:
        js = ("core/js/venta_proyecto.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 1. Si estamos editando una venta existente, fijamos el proyecto y el lote
        if self.instance.pk and self.instance.lot_id:
            self.fields['project'].initial = self.instance.lot.project_id
            self.fields['lot'].initial = self.instance.lot_id
            
            # Hacemos que los campos sean de solo lectura para que no se puedan cambiar por error
            self.fields['project'].disabled = True
            self.fields['lot'].disabled = True

        # 2. Si es una venta nueva, mostramos los lotes disponibles
        else:
            project_id = self.data.get("project") if self.is_bound else self.initial.get("project")
            lotes = Lot.objects.none()
            if project_id:
                lotes = Lot.objects.filter(project_id=project_id, status=Lot.Status.AVAILABLE)
            
            self.fields["lot"].queryset = lotes.order_by("number")

    def clean_lot(self):
        lot = self.cleaned_data.get("lot")
        project = self.cleaned_data.get("project")

        if not lot:
            return lot

        if project and lot.project_id != project.id:
            raise ValidationError(
                "El lote seleccionado no pertenece al proyecto elegido."
            )

        es_lote_actual = (
            self.instance.pk
            and lot.pk == self.instance.lot_id
        )

        if not es_lote_actual:
            if lot.status != Lot.Status.AVAILABLE:
                raise ValidationError(
                    "Este terreno ya no está disponible para la venta."
                )

            if Sale.objects.filter(lot_id=lot.pk).exists():
                raise ValidationError(
                    "Este terreno ya tiene una venta registrada."
                )

        return lot


    def clean(self):
        cleaned_data = super().clean()
        sale_type = cleaned_data.get("sale_type")
        final_price = cleaned_data.get("final_price")
        initial_payment = cleaned_data.get("initial_payment")
        credit_months = cleaned_data.get("credit_months")

        if sale_type == Sale.SaleType.CREDIT:
            if (
                final_price is not None
                and initial_payment is not None
                and initial_payment > final_price
            ):
                self.add_error(
                    "initial_payment",
                    "El abono inicial no puede superar el precio de venta.",
                )

            if credit_months is not None and credit_months < 1:
                self.add_error(
                    "credit_months",
                    "El plazo debe ser de al menos un mes.",
                )

        return cleaned_data



@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    form = SaleAdminForm
    

    fields = (
        "project",
        "lot",
        "client",
        "seller",
        "sale_type",
        "etapa",
        "sale_date",
        "first_due_date",  # <-- AÑADIR AQUÍ
        "initial_irregular_payments",
        "final_price",
        "initial_payment",
        "credit_months",
        "interest_type",
        "monthly_interest_rate",
        "notes",
    )
    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if obj and obj.etapa == Sale.Etapa.RESERVA:
            campos_ocultos = ["credit_months", "interest_type", "monthly_interest_rate"]
            fields = [f for f in fields if f not in campos_ocultos]
        return fields

    list_display = (
    "lot", "client", "seller", "sale_type", "sale_date", "final_price", "ver_pdf", "ver_minuta"
    )
    list_filter = ("lot__project", "lot__status")
    search_fields = (
        "lot__number",
        "lot__block",
        "lot__project__name",
        "client__first_name",
        "client__last_name",
        "seller__name",
    )
    actions = ["generate_installments_action", cancelar_credito_action, "descargar_pdf_reserva"]
    inlines = [PaymentInline, InstallmentInline]

    @admin.display(description="PDF Reserva")
    def ver_pdf(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<a class="button" style="background:#2157a5; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="/pdf/reserva/{}/" target="_blank">📄 Ver</a>',
            obj.id
        )

    @admin.display(description="Minuta")
    def ver_minuta(self, obj):
        from django.utils.html import format_html
        url = f"/pdf/minuta/{obj.id}/"
        return format_html(
            '<a class="button" style="background:#a32929; color:white; padding:6px 12px; border-radius:5px; text-decoration:none; font-weight:bold;" href="{}" target="_blank">📄 Minuta</a>',
        url
    )
    
    @admin.action(description="Generar calendario de cuotas (Limpiando anteriores)")
    def generate_installments_action(self, request, queryset):
        created = 0
        errors = []

        for sale in queryset:
            try:
                # --- AQUÍ ESTÁ LA MAGIA ---
                # 1. Borramos cualquier cuota vieja para evitar el error Duplicate
                sale.installments.all().delete()
                
                # 2. Ahora sí, generamos las nuevas
                created += sale.generate_installments()
            except ValidationError as exc:
                errors.append(f"Venta {sale.pk}: {exc}")
            except Exception as exc:
                errors.append(f"Venta {sale.pk}: Error inesperado - {exc}")

        if created:
            self.message_user(
                request,
                f"Se generaron {created} cuotas correctamente.",
                level=messages.SUCCESS,
            )

        for error in errors:
            self.message_user(
                request,
                error,
                level=messages.ERROR,
            )

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            lot = Lot.objects.get(pk=obj.lot_id)

            if not change:
                if lot.status != Lot.Status.AVAILABLE:
                    raise ValidationError("El terreno ya no está disponible.")
                if Sale.objects.filter(lot_id=lot.pk).exists():
                    raise ValidationError("Este terreno ya tiene una venta registrada.")

            super().save_model(request, obj, form, change)

            # Actualizar el estado del terreno según la etapa
            if obj.etapa == Sale.Etapa.RESERVA:
                lot.status = Lot.Status.RESERVED
            elif obj.etapa == Sale.Etapa.PROMESA:
                lot.status = Lot.Status.PROMISE
            elif obj.sale_type == Sale.SaleType.CASH:
                lot.status = Lot.Status.CASH
            elif obj.sale_type == Sale.SaleType.CREDIT:
                lot.status = Lot.Status.CREDIT

            lot.save(update_fields=["status"])

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        # Agregamos la URL del PDF al contexto del admin
        extra_context['pdf_reserva_url'] = f"/pdf/reserva/{object_id}/"
        return super().change_view(request, object_id, form_url, extra_context)
    
    def response_change(self, request, obj):
        # Si el usuario pulsa el botón "Descargar PDF"
        if "_descargar_pdf" in request.POST:
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(f"/pdf/reserva/{obj.id}/")
        return super().response_change(request, obj)
    
    @admin.display(description="PDF Reserva")
    def ver_pdf(self, obj):
        from django.utils.html import format_html
        return format_html(
            '<a class="button" style="background:#2157a5; color:white; padding:4px 8px; border-radius:4px; text-decoration:none;" href="/pdf/reserva/{}/" target="_blank">📄 Ver</a>',
            obj.id
        )

class InstallmentClientFilter(admin.SimpleListFilter):
    title = "Por cliente"
    parameter_name = "cliente"

    def lookups(self, request, model_admin):
        clientes = Client.objects.filter(
            sales__installments__isnull=False
        ).distinct().order_by("last_name", "first_name")

        return [
            (str(cliente.pk), str(cliente))
            for cliente in clientes
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(sale__client_id=self.value())
        return queryset


class InstallmentLotFilter(admin.SimpleListFilter):
    title = "Por lote"
    parameter_name = "lote"

    def lookups(self, request, model_admin):
        lotes = Lot.objects.filter(
            sales__installments__isnull=False
        ).distinct().order_by("project__name", "number")

        return [
            (str(lote.pk), str(lote))
            for lote in lotes
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(sale__lot_id=self.value())
        return queryset 

class SoloLotesConCuotasFilter(admin.SimpleListFilter):
    title = "Lotes con cuotas programadas"
    parameter_name = "con_cuotas"

    def lookups(self, request, model_admin):
        # Solo mostramos esta opción, no hay más que elegir
        return (
            ("si", "Solo lotes con cuotas generadas"),
        )

    def queryset(self, request, queryset):
        if self.value() == "si":
            # Filtra las cuotas que pertenecen a lotes que tienen más de 0 cuotas
            return queryset.filter(sale__lot__in=queryset.values('sale__lot'))
        return queryset
     
@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = (
        "get_lote_corto",  # <-- En lugar de "sale", mostramos solo el lote
        "get_client",      # <-- Ya lo tenías
        "number",
        "due_date",
        "principal_amount",
        "interest_amount",
        "amount",
        "status",
        "registrar_pago_link",
    )

    list_filter = (
        InstallmentClientFilter,  # Se convierte en desplegable automáticamente
        InstallmentLotFilter,     # Se convierte en desplegable automáticamente
        "status",                 # Desplegable automático
        "due_date",               # Desplegable automático
        SoloLotesConCuotasFilter, # Desplegable automático
    )

    search_fields = (
        "sale__lot__number",
        "sale__lot__block",
        "sale__client__first_name",
        "sale__client__last_name",
        "sale__client__identification",
    )

    # Agregamos esta función para mostrar el lote de forma corta en la primera columna
    @admin.display(description="Lote", ordering="sale__lot__number")
    def get_lote_corto(self, obj):
        return obj.sale.lot.number

    @admin.display(description="Cliente", ordering="sale__client__last_name")
    def get_client(self, obj):
        return obj.sale.client

    @admin.display(description="Pago")
    def registrar_pago_link(self, obj):
        if obj.status == Installment.Status.PAID:
            return mark_safe(
                '<span style="color:#1f6b3a;font-weight:600;">✓ Pagada</span>'
            )
        url = reverse("registrar_pago_cuota", args=[obj.pk])
        return format_html(
            '<a class="button" '
            'style="background:#2157a5;color:#fff;padding:4px 10px;'
            'border-radius:6px;text-decoration:none;font-size:12px;" '
            'href="{}">💵 Pagar</a>',
            url,
        )

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("sale", "payment_date", "amount", "reference", "ver_recibo")
    list_filter = ("payment_date", "sale__lot__project")
    search_fields = ("sale__lot__number", "reference", "sale__client__first_name", "sale__client__last_name")
    
    # Aquí le decimos que TODOS los campos se puedan editar
    fields = ("sale", "installment", "payment_date", "amount", "reference", "notes")
    
    # Esto permite que los campos se guarden correctamente al editarlos
    def get_readonly_fields(self, request, obj=None):
        # Si el pago ya existe (obj no es None), permitimos editar todo
        # Si es nuevo, también permitimos editar todo
        return []
    @admin.display(description="Recibo")
    def ver_recibo(self, obj):
        from django.utils.html import format_html
        url = f"/pdf/recibo/{obj.id}/"
        return format_html(
            '<a class="button" style="background:#16a34a; color:white; padding:6px 12px; border-radius:5px; text-decoration:none; font-weight:bold;" href="{}" target="_blank">🧾 Recibo</a>',
            url
        )

@admin.register(Promise)
class PromiseAdmin(admin.ModelAdmin):
    list_display = ("sale", "signed_date", "notary", "legal_fee")
    list_filter = ("signed_date",)

@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ("seller", "sale", "amount", "status", "paid_date")
    list_filter = ("status", "paid_date", "seller")
    search_fields = ("seller__name", "sale__lot__number")
    readonly_fields = ("seller", "sale", "amount")

@admin.register(LegalFee)
class LegalFeeAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "active")
    list_filter = ("active",)
    search_fields = ("name",)
    
# Actualizar cuotas vencidas automáticamente al entrar al Admin
def actualizar_cuotas_vencidas():
    hoy = timezone.localdate()
    Installment.objects.filter(due_date__lt=hoy, status__in=["pending", "partial"]).update(status="overdue")

class Media:
        js = ('admin/js/pdf_button.js',)