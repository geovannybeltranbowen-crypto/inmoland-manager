import os
import django
from decimal import Decimal

# Configurar Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from core.models import Lot, Project

def corregir_precios():
    print("Iniciando corrección de precios...")
    
    # Buscamos el proyecto de GARDEN
    try:
        project = Project.objects.get(name="GARDEN_ETAPA_2")
    except Project.DoesNotExist:
        print("ERROR: No se encontró el proyecto GARDEN_ETAPA_2.")
        return

    lotes = Lot.objects.filter(project=project)
    corregidos = 0

    for lote in lotes:
        # Si el precio es mayor a 100,000, asumimos que se multiplicó por 100 por error
        if lote.sale_price and lote.sale_price > Decimal("100000.00"):
            precio_correcto = lote.sale_price / Decimal("100")
            print(f"Lote {lote.number}: ${lote.sale_price} -> ${precio_correcto}")
            lote.sale_price = precio_correcto
            lote.save(update_fields=["sale_price"])
            corregidos += 1

    print(f"\n¡LISTO! Se corrigieron {corregidos} lotes.")

if __name__ == "__main__":
    corregir_precios()