from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


class Project(models.Model):
    name = models.CharField("Nombre del proyecto", max_length=150)
    location = models.CharField("Ubicación", max_length=200, blank=True)
    acquisition_cost = models.DecimalField("Costo de adquisición", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    development_costs = models.DecimalField("Gastos de urbanización", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    notes = models.TextField("Notas", blank=True)
    created_at = models.DateTimeField("Creado", auto_now_add=True)
    plan_image = models.ImageField(
    "Plano del proyecto",
    upload_to="planos_proyectos/",
    blank=True,
    null=True,
)

    class Meta:
        ordering = ["name"]
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"

    def __str__(self):
        return self.name


class Lot(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Disponible"
        RESERVED = "reserved", "Separado"
        PROMISE = "promise", "Promesa firmada"
        DEED = "deed", "Escriturado"
        CASH = "cash", "Vendido al contado"
        CREDIT = "credit", "Vendido a crédito"

    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="lots", verbose_name="Proyecto")
    number = models.CharField("Número de lote", max_length=30)
    block = models.CharField("Manzana / cuadra", max_length=30, blank=True)
    block_ref = models.ForeignKey("Block", on_delete=models.SET_NULL, null=True, blank=True, related_name="lots", verbose_name="Cuadra o manzana")
    street = models.CharField("Calle / ubicación", max_length=150, blank=True)
    area_m2 = models.DecimalField("Superficie (m²)", max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    front_m = models.DecimalField("Frente / Norte (m)", max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    back_m = models.DecimalField("Fondo / Sur (m)", max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    right_side_m = models.DecimalField("Derecho / Este (m)", max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    left_side_m = models.DecimalField("Izquierdo / Oeste (m)", max_digits=8, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    sale_price = models.DecimalField("Precio de venta", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    status = models.CharField("Estado", max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    notes = models.TextField("Notas", blank=True)

    class Meta:
        ordering = ["project", "block", "number"]
        constraints = [models.UniqueConstraint(fields=["project", "number"], name="unique_lot_number_per_project")]
        verbose_name = "Lote"
        verbose_name_plural = "Lotes"

    def __str__(self):
        return f"{self.project} — Lote {self.number}"


class Client(models.Model):
    first_name = models.CharField("Nombres", max_length=100)
    last_name = models.CharField("Apellidos", max_length=100)
    identification = models.CharField("Cédula/RUC", max_length=20, blank=True)
    phone = models.CharField("Teléfono", max_length=30, blank=True)
    email = models.EmailField("Correo electrónico", blank=True)
    whatsapp = models.CharField("WhatsApp", max_length=30, blank=True)
    accepts_notifications = models.BooleanField("Acepta notificaciones", default=False)
    notes = models.TextField("Notas", blank=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Seller(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuario vinculado")
    name = models.CharField("Nombre del vendedor", max_length=150)
    fixed_commission = models.DecimalField("Comisión por lote", max_digits=12, decimal_places=2, default=Decimal("1000.00"))
    is_sales_manager = models.BooleanField("Es jefe de ventas", default=False)
    active = models.BooleanField("Activo", default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Vendedor"
        verbose_name_plural = "Vendedores"

    def __str__(self):
        return self.name


class Sale(models.Model):
    class SaleType(models.TextChoices):
        CASH = "cash", "Contado"
        CREDIT = "credit", "Crédito directo"

    lot = models.ForeignKey(Lot, on_delete=models.PROTECT, related_name="sales", verbose_name="Lote")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="sales", verbose_name="Cliente")
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name="sales", verbose_name="Vendedor")
    sale_type = models.CharField("Modalidad", max_length=10, choices=SaleType.choices)
    sale_date = models.DateField("Fecha de venta", default=timezone.localdate)
    final_price = models.DecimalField("Precio final", max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    initial_payment = models.DecimalField("Abono inicial", max_digits=14, decimal_places=2, default=0, validators=[MinValueValidator(0)])
        # Configuración del crédito
    credit_months = models.PositiveSmallIntegerField(
        "Plazo del crédito (meses)",
        default=30,
    )

    interest_type = models.CharField(
        "Tipo de interés",
        max_length=15,
        choices=[
            ("none", "Sin intereses"),
            ("monthly_rate", "Con tasa mensual"),
        ],
        default="none",
    )

    monthly_interest_rate = models.DecimalField(
    "Tasa de interés mensual (%)",
    max_digits=6,
    decimal_places=3,
    default=0,
    validators=[MinValueValidator(0)],
)
    notes = models.TextField("Notas", blank=True)

    class Meta:
        ordering = ["-sale_date", "-id"]
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"

    def __str__(self):
        return f"{self.lot} — {self.client}"

    
    @property
    def total_paid(self):
        """Abono inicial más pagos posteriores registrados."""
        payments_total = self.payments.aggregate(
            total=models.Sum("amount")
        )["total"] or Decimal("0.00")

        return self.initial_payment + payments_total

    @property
    def paid_percentage(self):
        """Porcentaje pagado considerando el abono inicial."""
        if self.final_price <= Decimal("0.00"):
            return Decimal("0.00")

        percentage = self.total_paid * Decimal("100") / self.final_price
        return min(Decimal("100.00"), percentage)

    @property
    def amount_to_half(self):
        """Monto que falta para llegar al 50 % del precio de venta."""
        target = self.final_price * Decimal("0.50")
        return max(Decimal("0.00"), target - self.total_paid)
    
    def generate_installments(self):
        """
        Genera el calendario de una venta a crédito.
        No modifica calendarios que ya existan.
        """
        from calendar import monthrange
        from decimal import ROUND_HALF_UP
        from django.db import transaction

        with transaction.atomic():
            sale = Sale.objects.select_for_update().get(pk=self.pk)

            if sale.sale_type != Sale.SaleType.CREDIT:
                raise ValidationError(
                    "Solo se puede generar un calendario para ventas a crédito."
                )

            if sale.installments.exists():
                raise ValidationError(
                    "Esta venta ya tiene cuotas programadas. "
                    "No se generará otro calendario."
                )

            if sale.credit_months < 1:
                raise ValidationError(
                    "El plazo del crédito debe ser de al menos un mes."
                )

            if sale.initial_payment < 0 or sale.initial_payment > sale.final_price:
                raise ValidationError(
                    "El abono inicial debe estar entre cero y el precio de venta."
                )

            balance = sale.final_price - sale.initial_payment

            if balance <= 0:
                raise ValidationError(
                    "No existe saldo pendiente para financiar."
                )

            months = sale.credit_months
            rate = (
                sale.monthly_interest_rate / Decimal("100")
                if sale.interest_type == "monthly_rate"
                else Decimal("0")
            )

            if rate > 0:
                payment_amount = (
                    balance * rate
                    / (Decimal("1") - (Decimal("1") + rate) ** (-months))
                )
            else:
                payment_amount = balance / months

            payment_amount = payment_amount.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

            start_date = sale.sale_date
            installments = []
            remaining_balance = balance

            for number in range(1, months + 1):
                month_index = start_date.month - 1 + number
                year = start_date.year + month_index // 12
                month = month_index % 12 + 1
                day = min(
                    start_date.day,
                    monthrange(year, month)[1],
                )
                due_date = start_date.replace(
                    year=year,
                    month=month,
                    day=day,
                )

                if rate > 0:
                    interest = (
                        remaining_balance * rate
                    ).quantize(
                        Decimal("0.01"),
                        rounding=ROUND_HALF_UP,
                    )
                else:
                    interest = Decimal("0.00")

                if number == months:
                    principal = remaining_balance
                    amount = principal + interest
                else:
                    amount = payment_amount
                    principal = amount - interest

                    if principal > remaining_balance:
                        principal = remaining_balance
                        amount = principal + interest

                principal = principal.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
                interest = interest.quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
                amount = (principal + interest).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )

                installments.append(
                    Installment(
                        sale=sale,
                        number=number,
                        due_date=due_date,
                        principal_amount=principal,
                        interest_amount=interest,
                        amount=amount,
                    )
                )

                remaining_balance -= principal

            Installment.objects.bulk_create(installments)

        return len(installments)

    
    def refresh_commission(self):
        commission, _ = Commission.objects.get_or_create(
            sale=self,
            defaults={
                "seller": self.seller,
                "amount": self.seller.fixed_commission,
            },
        )

        commission.seller = self.seller
        commission.amount = self.seller.fixed_commission

        if Promise.objects.filter(sale=self).exists():
            if self.paid_percentage >= Decimal("50.00"):
                # No cambiar una comisión que ya fue pagada.
                if commission.status != Commission.Status.PAID:
                    commission.status = Commission.Status.ENABLED
            else:
                if commission.status != Commission.Status.PAID:
                    commission.status = Commission.Status.BLOCKED
        else:
            if commission.status != Commission.Status.PAID:
                commission.status = Commission.Status.PENDING

        commission.save()



class Payment(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="payments", verbose_name="Venta")
    installment = models.ForeignKey(
        "Installment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
        verbose_name="Cuota relacionada",
    )
    payment_date = models.DateField("Fecha de pago", default=timezone.localdate)
    amount = models.DecimalField("Monto pagado", max_digits=14, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    reference = models.CharField("Referencia / comprobante", max_length=100, blank=True)
    notes = models.TextField("Notas", blank=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"

    def __str__(self):
        return f"{self.sale} — ${self.amount}"

    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Actualizar la comisión de la venta.
        self.sale.refresh_commission()

        # Actualizar el estado de la cuota relacionada.
        if self.installment_id:
            self.installment.refresh_status()
    
    def delete(self, *args, **kwargs):
        installment = self.installment
        sale = self.sale

        result = super().delete(*args, **kwargs)

        if installment:
            installment.refresh_status()

        sale.refresh_commission()

        return result



class Promise(models.Model):
    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name="promise", verbose_name="Venta")
    signed_date = models.DateField("Fecha de firma", default=timezone.localdate)
    notary = models.CharField("Notaría", max_length=150, blank=True)
    legal_fee = models.DecimalField("Rubro promesa", max_digits=10, decimal_places=2, default=Decimal("280.00"))
    notes = models.TextField("Notas", blank=True)

    class Meta:
        verbose_name = "Promesa de compraventa"
        verbose_name_plural = "Promesas de compraventa"

    def __str__(self):
        return f"Promesa — {self.sale}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sale.lot.status = Lot.Status.PROMISE
        self.sale.lot.save(update_fields=["status"])
        self.sale.refresh_commission()


class Commission(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente de promesa"
        BLOCKED = "blocked", "Bloqueada: falta completar 50%"
        ENABLED = "enabled", "Habilitada para pago"
        PAID = "paid", "Pagada"

    sale = models.OneToOneField(Sale, on_delete=models.CASCADE, related_name="commission", verbose_name="Venta")
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name="commissions", verbose_name="Vendedor")
    amount = models.DecimalField("Monto", max_digits=12, decimal_places=2, default=Decimal("1000.00"))
    status = models.CharField("Estado", max_length=12, choices=Status.choices, default=Status.PENDING)
    paid_date = models.DateField("Fecha de pago", null=True, blank=True)
    notes = models.TextField("Notas", blank=True)

    class Meta:
        ordering = ["status", "seller"]
        verbose_name = "Comisión"
        verbose_name_plural = "Comisiones"

    def __str__(self):
        return f"{self.seller} — ${self.amount} ({self.get_status_display()})"


class LegalFee(models.Model):
    name = models.CharField("Rubro", max_length=100)
    amount = models.DecimalField("Valor (USD)", max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    active = models.BooleanField("Activo", default=True)
    notes = models.TextField("Notas", blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Rubro legal configurable"
        verbose_name_plural = "Rubros legales configurables"

    def __str__(self):
        return f"{self.name} — ${self.amount}"


class Block(models.Model):
    """Cuadra/manzana identificada por texto libre (A, B, 1, 2, etc.)."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="blocks", verbose_name="Proyecto")
    code = models.CharField("Código de cuadra/manzana", max_length=30)
    name = models.CharField("Nombre visible", max_length=100, blank=True)
    streets = models.CharField("Calles relacionadas", max_length=250, blank=True)
    notes = models.TextField("Observaciones", blank=True)
    created_at = models.DateTimeField("Creado", auto_now_add=True)

    class Meta:
        ordering = ["project", "code"]
        constraints = [models.UniqueConstraint(fields=["project", "code"], name="unique_block_code_per_project")]
        verbose_name = "Cuadra o manzana"
        verbose_name_plural = "Cuadras y manzanas"

    def __str__(self):
        return f"{self.project} — {self.name or self.code}"


class ProjectPlan(models.Model):
    """PDF opcional de referencia; no sustituye los datos ni la geometría de los lotes."""
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="plans", verbose_name="Proyecto")
    title = models.CharField("Nombre del plano", max_length=150, default="Plano de referencia")
    pdf_file = models.FileField("PDF de referencia", upload_to="planos_referencia/%Y/%m/")
    page_number = models.PositiveIntegerField("Página de referencia", default=1)
    is_active = models.BooleanField("Mostrar como plano principal", default=True)
    uploaded_at = models.DateTimeField("Fecha de carga", auto_now_add=True)
    notes = models.TextField("Notas", blank=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Plano PDF de referencia"
        verbose_name_plural = "Planos PDF de referencia"

    def __str__(self):
        return f"{self.project} — {self.title}"

    def clean(self):
        if self.pdf_file and not self.pdf_file.name.lower().endswith(".pdf"):
            raise ValidationError({"pdf_file": "El archivo debe estar en formato PDF."})


class LotGeometry(models.Model):
    """Contorno gráfico de un lote en coordenadas normalizadas 0..1 respecto al plano."""
    lot = models.OneToOneField(Lot, on_delete=models.CASCADE, related_name="geometry", verbose_name="Lote")
    points = models.JSONField("Puntos del contorno", default=list, blank=True)
    page_number = models.PositiveIntegerField("Página del plano", default=1)
    updated_at = models.DateTimeField("Última actualización", auto_now=True)

    class Meta:
        verbose_name = "Contorno gráfico de lote"
        verbose_name_plural = "Contornos gráficos de lotes"

    def __str__(self):
        return f"Contorno — {self.lot}"

class Installment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pendiente"
        PARTIAL = "partial", "Pago parcial"
        PAID = "paid", "Pagada"
        OVERDUE = "overdue", "Vencida"

    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name="installments",
        verbose_name="Venta",
    )
    number = models.PositiveSmallIntegerField("Número de cuota")
    due_date = models.DateField("Fecha de vencimiento")
    principal_amount = models.DecimalField(
        "Capital",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    interest_amount = models.DecimalField(
        "Interés",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    amount = models.DecimalField(
        "Total de la cuota",
        max_digits=14,
        decimal_places=2,
    )
    status = models.CharField(
        "Estado",
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    notes = models.TextField("Notas", blank=True)

    class Meta:
        ordering = ["sale", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["sale", "number"],
                name="unique_installment_per_sale",
            )
        ]
        verbose_name = "Cuota programada"
        verbose_name_plural = "Cuotas programadas"

    def __str__(self):
        return (
            f"Cuota {self.number} — {self.sale} — "
            f"${self.amount}"
        )

    @property
    def total_paid(self):
        """Total de pagos reales asociados a esta cuota."""
        total = self.payments.aggregate(
            total=models.Sum("amount")
        )["total"]

        return total or Decimal("0.00")

    @property
    def remaining_amount(self):
        """Saldo pendiente de la cuota."""
        return max(
            Decimal("0.00"),
            self.amount - self.total_paid,
        )

    def refresh_status(self):
        """Actualizar el estado según los pagos y el vencimiento."""
        if self.remaining_amount <= Decimal("0.00"):
            new_status = self.Status.PAID
        elif self.total_paid > Decimal("0.00"):
            new_status = self.Status.PARTIAL
        elif self.due_date < timezone.localdate():
            new_status = self.Status.OVERDUE
        else:
            new_status = self.Status.PENDING

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=["status"])
