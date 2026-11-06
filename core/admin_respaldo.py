from django.contrib import admin
from django.core.exceptions import ValidationError
from django import forms
from django.db import models
from django.db import transaction
from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import Project, Block, Lot, Client, Seller, Sale, Payment, Promise, Commission, LegalFee

admin.site.site_header = "INMOLAND Manager"
admin.site.site_title = "INMOLAND"
admin.site.index_title = "Administración de Compra-Venta Bienes INMOLAND"

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
            "notes",
        )

    class Media:
        js = ("core/js/venta_proyecto.js",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        project_id = None

        # Al editar una venta, obtener el proyecto de su lote actual.
        if self.instance.pk and self.instance.lot_id:
            project_id = self.instance.lot.project_id

        # Al enviar el formulario, utilizar el proyecto seleccionado.
        if self.is_bound:
            project_id = self.data.get("project")

        # Si el formulario llega con valores iniciales desde otra pantalla.
        if not project_id:
            project_id = self.initial.get("project")

        if project_id:
            lotes = Lot.objects.filter(
                project_id=project_id,
            )

            # Al crear una venta, solo mostrar lotes disponibles.
            if not self.instance.pk:
                lotes = lotes.filter(
                    status=Lot.Status.AVAILABLE,
                )

            # Al editar, conservar también el lote de la venta actual.
            elif self.instance.lot_id:
                lotes = lotes.filter(
                    models.Q(status=Lot.Status.AVAILABLE)
                    | models.Q(pk=self.instance.lot_id)
                )

            self.fields["lot"].queryset = lotes.order_by("number")
        else:
            self.fields["lot"].queryset = Lot.objects.none()

    
    def clean_lot(self):
        lot = self.cleaned_data.get("lot")
        project = self.cleaned_data.get("project")

        if not lot:
            return lot

        if project and lot.project_id != project.id:
            raise ValidationError(
                "El lote seleccionado no pertenece al proyecto elegido."
            )

        # Si se está editando una venta, permitir conservar su lote.
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


    class Meta:
        model = Sale
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["lot"].queryset = Lot.objects.none()

        if self.is_bound:
            project_id = self.data.get("project")
            if project_id:
                self.fields["lot"].queryset = Lot.objects.filter(
                    project_id=project_id,
                    status=Lot.Status.AVAILABLE,
                ).order_by("number")




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
    inlines = [PaymentInline]
    
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
