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

        # Determinar el proyecto del lote actual al editar una venta.
        project_id = None

        if self.instance.pk and self.instance.lot_id:
            project_id = self.instance.lot.project_id

        # Al enviar el formulario, respetar el proyecto elegido.
        if self.is_bound:
            project_id = self.data.get("project") or None
        else:
            project_id = (
                self.initial.get("project")
                or self.initial.get("lot")
                or project_id
            )

        # Si el lote llega desde el mapa, conservar su proyecto.
        lot_id = (
            self.data.get("lot")
            if self.is_bound
            else self.initial.get("lot")
        )

        if not project_id and lot_id:
            project_id = (
                Lot.objects.filter(pk=lot_id)
                .values_list("project_id", flat=True)
                .first()
            )

        # Mostrar solamente lotes del proyecto elegido.
        lotes = Lot.objects.none()

        if project_id:
            lotes = Lot.objects.filter(project_id=project_id)

            if self.instance.pk and self.instance.lot_id:
                lotes = lotes.filter(
                    models.Q(status=Lot.Status.AVAILABLE)
                    | models.Q(pk=self.instance.lot_id)
                )
            else:
                lotes = lotes.filter(status=Lot.Status.AVAILABLE)

        self.fields["lot"].queryset = lotes.order_by("number")

        # Seleccionar el lote que llega desde el mapa.
        if lot_id:
            self.initial["lot"] = lot_id

        # Mantener seleccionado el proyecto.
        if project_id:
            self.initial["project"] = project_id

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
        interest_type = cleaned_data.get("interest_type")
        monthly_interest_rate = cleaned_data.get(
            "monthly_interest_rate"
        )

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

            if (
                interest_type == "monthly_rate"
                and monthly_interest_rate is not None
                and monthly_interest_rate <= 0
            ):
                self.add_error(
                    "monthly_interest_rate",
                    "La tasa mensual debe ser mayor que cero.",
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
        "sale_date",
        "final_price",
        "initial_payment",
        "credit_months",
        "interest_type",
        "monthly_interest_rate",
        "notes",
    )

    list_display = ("lot", "client", "seller", "sale_type", "sale_date", "final_price")
    list_filter = ("lot__project", "lot__status")
    search_fields = (
        "lot__number",
        "lot__block",
        "lot__project__name",
        "client__first_name",
        "client__last_name",
        "seller__name",
    )
    actions = ["generate_installments_action"]
    inlines = [PaymentInline, InstallmentInline]

    
    @admin.action(description="Generar calendario de cuotas")
    def generate_installments_action(self, request, queryset):
        created = 0
        errors = []

        for sale in queryset:
            try:
                created += sale.generate_installments()
            except ValidationError as exc:
                errors.append(
                    f"Venta {sale.pk}: {exc}"
                )

        if created:
            self.message_user(
                request,
                f"Se generaron {created} cuotas.",
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

            # Comprobar otra vez antes de guardar una venta nueva.
            if not change:
                if lot.status != Lot.Status.AVAILABLE:
                    raise ValidationError(
                        "El terreno ya no está disponible."
                    )

                if Sale.objects.filter(lot_id=lot.pk).exists():
                    raise ValidationError(
                        "Este terreno ya tiene una venta registrada."
                    )

            super().save_model(request, obj, form, change)

            # Actualizar el estado del terreno.
            if obj.sale_type == Sale.SaleType.CASH:
                lot.status = Lot.Status.CASH
            elif obj.sale_type == Sale.SaleType.CREDIT:
                lot.status = Lot.Status.CREDIT

            lot.save(update_fields=["status"])

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
 
@admin.register(Installment)
class InstallmentAdmin(admin.ModelAdmin):
    list_display = (
        "sale",
        "get_lot",
        "get_client",
        "number",
        "due_date",
        "principal_amount",
        "interest_amount",
        "amount",
        "status",
        "registrar_pago_link",
    )

    list_filter = (
        InstallmentClientFilter,
        InstallmentLotFilter,
        "status",
        "due_date",
    )

    search_fields = (
        "sale__lot__number",
        "sale__lot__block",
        "sale__client__first_name",
        "sale__client__last_name",
        "sale__client__identification",
    )

    readonly_fields = (
        "sale",
        "number",
        "due_date",
        "principal_amount",
        "interest_amount",
        "amount",
        "status",
    )

    @admin.display(description="Lote", ordering="sale__lot__number")
    def get_lot(self, obj):
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
    list_display = ("sale", "payment_date", "amount", "reference")
    list_filter = ("payment_date",)
    search_fields = ("sale__lot__number", "reference")

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
