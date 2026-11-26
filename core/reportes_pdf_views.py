from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from .models import Sale

def generar_pdf_reserva(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    client = sale.client
    lot = sale.lot
    
    context = {
        'sale': sale,
        'client': client,
        'lot': lot,
    }
    
    # Renderizar el HTML
    html_string = render_to_string('core/pdf_reserva.html', context)
    
    # Convertir a PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Ficha_Reserva_{client.last_name}.pdf"'
    
    pisa_status = pisa.CreatePDF(html_string, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    return response
def generar_pdf_minuta(request, sale_id):
    sale = get_object_or_404(Sale, pk=sale_id)
    client = sale.client
    lot = sale.lot
    
    # Área total del proyecto (ajústalo al área real de tu proyecto MIRANDA GARDEN)
    area_total_proyecto = 35000 
    porcentaje = (float(lot.area_m2) / area_total_proyecto) * 100
    
    # DATOS FIJOS DE LA VENDEDORA (Según la minuta que me enviaste)
    vendedora_nombre = "GENESIS ABIGAIL MOYA VELASCO"
    vendedora_cedula = "1723657373"
    vendedora_estado_civil = "casada con disolución de sociedad conyugal"
    vendedora_nacionalidad = "ecuatoriana"
    vendedora_direccion = "sector el Tingo, calle D y Francisco Gonzalez Suarez, cantón Quito y de tránsito por este cantón Rumiñahui"
    vendedora_correo = "erickbeltran1978@gmail.com"
    vendedora_telefono = "0983379047"

    # Datos del comprador (estos sí vienen del sistema)
    comprador_nombre = f"{client.first_name} {client.last_name}".upper()
    comprador_cedula = client.identification
    comprador_estado_civil = client.marital_status or "________"
    comprador_nacionalidad = client.nationality or "ecuatoriana"
    comprador_direccion = client.address or "________"
    comprador_correo = client.email or "________"
    comprador_telefono = client.phone or "________"

    context = {
        'sale': sale,
        'client': client,
        'lot': lot,
        'porcentaje': f"{porcentaje:.4f}%",
        'saldo_financiado': sale.final_price - sale.initial_payment,
        
        # Datos de la vendedora fijos
        'vendedora_nombre': vendedora_nombre,
        'vendedora_cedula': vendedora_cedula,
        'vendedora_estado_civil': vendedora_estado_civil,
        'vendedora_nacionalidad': vendedora_nacionalidad,
        'vendedora_direccion': vendedora_direccion,
        'vendedora_correo': vendedora_correo,
        'vendedora_telefono': vendedora_telefono,

        # Datos del comprador
        'comprador_nombre': comprador_nombre,
        'comprador_cedula': comprador_cedula,
        'comprador_estado_civil': comprador_estado_civil,
        'comprador_nacionalidad': comprador_nacionalidad,
        'comprador_direccion': comprador_direccion,
        'comprador_correo': comprador_correo,
        'comprador_telefono': comprador_telefono,
    }
    
    html_string = render_to_string('core/pdf_minuta.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Minuta_Lote_{lot.number}.pdf"'
    pisa_status = pisa.CreatePDF(html_string, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    return response

def generar_pdf_recibo(request, payment_id):
    from .models import Payment
    pago = get_object_or_404(Payment, pk=payment_id)
    sale = pago.sale
    client = sale.client
    lot = sale.lot
    
    # Obtenemos todas las cuotas de la venta ordenadas
    cuotas = sale.installments.all().order_by('number')
    
    concepto_cuotas = "ABONO"
    if pago.installment:
        concepto_cuotas = f"CUOTA {pago.installment.number}"
    
    context = {
        'pago': pago,
        'sale': sale,
        'client': client,
        'lot': lot,
        'cuotas': cuotas,
        'concepto_cuotas': concepto_cuotas,
    }
    
    html_string = render_to_string('core/pdf_recibo.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Recibo_{client.last_name}_{pago.id}.pdf"'
    pisa_status = pisa.CreatePDF(html_string, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    return response