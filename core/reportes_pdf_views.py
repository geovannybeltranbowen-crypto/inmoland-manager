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
    
    # Aquí calculamos los porcentajes y montos exactos
    # Porcentaje de derechos y acciones (Area del lote / Area total del proyecto)
    # Nota: Necesitamos saber el área total del proyecto. Si no la tienes, la dejamos fija o calculada.
    area_total_proyecto = 35000  # Ejemplo: 35,000 m2 (ajustar según tu proyecto)
    porcentaje = (float(lot.area_m2) / area_total_proyecto) * 100
    
    context = {
        'sale': sale,
        'client': client,
        'lot': lot,
        'seller': sale.seller,
        'porcentaje': f"{porcentaje:.4f}%",
        'saldo_financiado': sale.final_price - sale.initial_payment,
    }
    
    html_string = render_to_string('core/pdf_minuta.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Minuta_Lote_{lot.number}.pdf"'
    pisa_status = pisa.CreatePDF(html_string, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Error al generar el PDF', status=500)
    return response