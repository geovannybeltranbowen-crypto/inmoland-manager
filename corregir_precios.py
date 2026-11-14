import os
import django
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from core.models import Lot, Project

def corregir():
    project = Project.objects.get(name="GARDEN_ETAPA_2")
    lotes = Lot.objects.filter(project=project)
    corregidos = 0

    for lote in lotes:
        if lote.sale_price and lote.sale_price > Decimal("100000.00"):
            lote.sale_price = lote.sale_price / Decimal("100")
            lote.save(update_fields=["sale_price"])
            corregidos += 1
    print(f"¡ÉXITO! Se corrigieron {corregidos} lotes.")

if __name__ == "__main__":
    corregir()