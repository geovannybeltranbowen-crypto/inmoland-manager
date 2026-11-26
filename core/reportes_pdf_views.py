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