from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Sale, Lot, Client, Seller

# ==========================================
# 1. FORMULARIO Y VISTA DE RESERVA
# ==========================================
class ReservaForm(forms.ModelForm):
    monto_reserva = forms.DecimalField(
        label="Monto de la Reserva ($)", 
        max_digits=10, 
        decimal_places=2, 
        initial=200.00
    )
    
    class Meta:
        model = Sale
        fields = ['lot', 'client', 'seller']
        labels = {
            'lot': 'Lote a Reservar',
            'client': 'Cliente',
            'seller': 'Vendedor',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lot'].queryset = Lot.objects.filter(status=Lot.Status.AVAILABLE).order_by('number')

    def save(self, commit=True):
        sale = super().save(commit=False)
        sale.etapa = Sale.Etapa.RESERVA
        sale.sale_type = Sale.SaleType.CASH
        sale.sale_date = timezone.localdate()
        sale.final_price = self.cleaned_data['lot'].sale_price
        sale.initial_payment = self.cleaned_data['monto_reserva']
        if commit:
            sale.save()
            sale.lot.status = Lot.Status.RESERVED
            sale.lot.save()
        return sale

@login_required
def nueva_reserva(request):
    if request.method == 'POST':
        form = ReservaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Reserva registrada correctamente. El lote está separado.")
            return redirect('admin:core_sale_changelist')
    else:
        form = ReservaForm()
    
    return render(request, 'core/form_reserva.html', {'form': form})


# ==========================================
# 2. FORMULARIO Y VISTA DE VENTA FINAL
# ==========================================
class VentaFinalForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = [
            'client', 'seller', 'sale_type', 'final_price', 
            'initial_payment', 'credit_months', 'interest_type', 'monthly_interest_rate'
        ]
        labels = {
            'sale_type': 'Modalidad (Contado o Crédito)',
            'final_price': 'Precio Final Acordado ($)',
            'initial_payment': 'Abono Inicial o Entrega ($)',
            'credit_months': 'Plazo del Crédito (Meses)',
            'interest_type': 'Tipo de Interés',
            'monthly_interest_rate': 'Tasa Mensual (%)',
        }

    def __init__(self, *args, **kwargs):
        self.lot = kwargs.pop('lot', None)
        super().__init__(*args, **kwargs)
        
        if self.lot and self.lot.sales.exists():
            reserva = self.lot.sales.first()
            self.fields['client'].initial = reserva.client
            self.fields['seller'].initial = reserva.seller
            self.fields['final_price'].initial = self.lot.sale_price
    # ¡AGREGA ESTO JUSTO DEBAJO DEL __init__!
        def clean_final_price(self):
        valor = self.cleaned_data.get('final_price')
        if valor:
            # Si por alguna razón llega como texto con coma, lo convertimos
            if isinstance(valor, str):
                valor = valor.replace(',', '.')
            return valor
        return valor

    def clean_initial_payment(self):
        valor = self.cleaned_data.get('initial_payment')
        if valor:
            if isinstance(valor, str):
                valor = valor.replace(',', '.')
            return valor
        return valor

    def clean(self):
        cleaned_data = super().clean()
        sale_type = cleaned_data.get('sale_type')
        final_price = cleaned_data.get('final_price')
        initial_payment = cleaned_data.get('initial_payment')

        if final_price and initial_payment and initial_payment > final_price:
            self.add_error('initial_payment', 'El abono no puede ser mayor al precio final.')

        if sale_type == Sale.SaleType.CREDIT:
            credit_months = cleaned_data.get('credit_months')
            if not credit_months or credit_months < 1:
                self.add_error('credit_months', 'Debe indicar un plazo válido en meses para el crédito.')
        return cleaned_data

@login_required
def registrar_venta_final(request, lot_id):
    lot = get_object_or_404(Lot, pk=lot_id)
    reserva_existente = lot.sales.filter(etapa=Sale.Etapa.RESERVA).first()

    if request.method == 'POST':
        form = VentaFinalForm(request.POST, lot=lot)
        if form.is_valid():
            if reserva_existente:
                reserva_existente.delete()
            
            sale = form.save(commit=False)
            sale.lot = lot
            sale.etapa = Sale.Etapa.PROMESA
            sale.sale_date = timezone.localdate()
            sale.save()

            lot.status = Lot.Status.PROMISE if sale.sale_type == Sale.SaleType.CREDIT else Lot.Status.CASH
            lot.save()

            if sale.sale_type == Sale.SaleType.CREDIT:
                try:
                    sale.generate_installments()
                    messages.success(request, "Venta registrada a crédito y calendario de cuotas generado.")
                except Exception as e:
                    messages.warning(request, f"Venta guardada, pero no se pudieron generar las cuotas: {e}")
            else:
                messages.success(request, "Venta al contado registrada correctamente.")

            return redirect('admin:core_sale_changelist')
    else:
        form = VentaFinalForm(lot=lot)

    return render(request, 'core/form_venta_final.html', {
        'form': form, 
        'lot': lot,
        'es_reserva': reserva_existente is not None
    })

@login_required
def desistir_reserva(request, lot_id):
    lot = get_object_or_404(Lot, pk=lot_id)
    reserva = lot.sales.filter(etapa=Sale.Etapa.RESERVA).first()
    
    if reserva:
        reserva.payments.all().delete()
        reserva.delete()
        lot.status = Lot.Status.AVAILABLE
        lot.save()
        messages.success(request, f"Reserva del lote {lot.number} cancelada. El lote está disponible nuevamente.")
    else:
        messages.error(request, "No se encontró una reserva para este lote.")
        
    return redirect('plano_lotes')