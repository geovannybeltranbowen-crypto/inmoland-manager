from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Sale, Lot, Client, Seller
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

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
    
    # Forzamos el campo de fecha para que sea un calendario visual
    sale_date = forms.DateField(
        label="Fecha de la Reserva / Venta",
        widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        input_formats=['%Y-%m-%d']
    )
    
    class Meta:
        model = Sale
        fields = ['lot', 'client', 'seller', 'sale_date']
        labels = {
            'lot': 'Lote a Reservar',
            'client': 'Cliente',
            'seller': 'Vendedor',
            'sale_date': 'Fecha de la Reserva / Venta',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lot'].queryset = Lot.objects.filter(status=Lot.Status.AVAILABLE).order_by('number')

    def save(self, commit=True):
        sale = super().save(commit=False)
        sale.etapa = Sale.Etapa.RESERVA
        sale.sale_type = Sale.SaleType.CASH
        
        # Si el usuario no puso fecha, usamos la de hoy
        if not sale.sale_date:
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
    # Leemos el ID del lote que viene desde el mapa en la URL
    lot_id = request.GET.get('lot')
    initial_data = {}
    
    if lot_id:
        try:
            lote = Lot.objects.get(pk=lot_id)
            initial_data['lot'] = lote.id
        except Lot.DoesNotExist:
            pass

    if request.method == 'POST':
        form = ReservaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Reserva registrada correctamente. El lote está separado.")
            return redirect('admin:core_sale_changelist')
    else:
        # Pasamos los datos iniciales al formulario para que aparezca el lote ya seleccionado
        form = ReservaForm(initial=initial_data)
    
    return render(request, 'core/form_reserva.html', {'form': form})


# ==========================================
# 2. FORMULARIO Y VISTA DE VENTA FINAL
# ==========================================
class VentaFinalForm(forms.ModelForm):

    first_due_date = forms.CharField(label="Fecha de Primer Vencimiento", required=False)


    # Usamos CharField para que Django no intente validar los decimales automáticamente
    final_price = forms.CharField(label="Precio Final Acordado ($)", required=True)
    initial_payment = forms.CharField(label="Abono Inicial o Entrega ($)", required=False)
    
    class Meta:
        model = Sale
        fields = [
             'client', 'seller', 'sale_type', 'final_price', 
             'initial_payment', 'credit_months', 'interest_type', 
             'monthly_interest_rate', 
             'first_due_date',
             'initial_irregular_payments',
        ]

    def __init__(self, *args, **kwargs):
        self.lot = kwargs.pop('lot', None)
        super().__init__(*args, **kwargs)
        
        if self.lot and self.lot.sales.exists():
            reserva = self.lot.sales.first()
            self.fields['client'].initial = reserva.client
            self.fields['seller'].initial = reserva.seller
            # Convertimos a string para que no haya conflicto
            self.fields['final_price'].initial = str(self.lot.sale_price)

    def _a_decimal(self, valor):
        """Convierte texto con coma o punto a Decimal con 2 decimales exactos."""
        valor = str(valor).strip().replace(',', '.')
        try:
            return Decimal(valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except InvalidOperation:
            raise forms.ValidationError("Escribe un número válido.")

    def clean_final_price(self):
        valor = self.cleaned_data.get('final_price')
        if valor not in (None, ''):
            return self._a_decimal(valor)
        return valor

    def clean_first_due_date(self):
        valor = self.cleaned_data.get('first_due_date')
        if valor:
            import datetime
            # Intentamos adivinar el formato de la fecha
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
                try:
                    return datetime.datetime.strptime(valor, fmt).date()
                except ValueError:
                    continue
            raise forms.ValidationError("Formato de fecha inválido. Usa AAAA-MM-DD o DD/MM/AAAA")
        return None
    def clean_initial_payment(self):
        valor = self.cleaned_data.get('initial_payment')
        if valor not in (None, ''):
            return self._a_decimal(valor)
        return Decimal('0.00')

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
                    # Borrar cuotas viejas si es que quedaron a medias
                    sale.installments.all().delete()
                    # Generar las nuevas
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