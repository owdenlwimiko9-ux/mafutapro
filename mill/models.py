from django.db import models
from django.contrib.auth.models import User

# ================= MILL / TENANT =================
class Mill(models.Model):
    name = models.CharField(max_length=100) # Willa Foods, Mwanza Oil
    slug = models.SlugField(unique=True) # willa-foods - kwa URL
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mills')
    logo = models.ImageField(upload_to='mills/', blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self): 
        return self.name

class Customer(models.Model):
    mill = models.ForeignKey(Mill, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('mill', 'phone')
    
    def __str__(self): 
        return f"{self.name} - {self.phone}"

class Supplier(models.Model):
    mill = models.ForeignKey(Mill, on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self): 
        return self.name

class Product(models.Model):
    TYPES = [('OIL','Sunflower Oil'),('CAKE','Mashudu'),('SEED','Sunflower Seeds')]
    mill = models.ForeignKey(Mill, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TYPES)
    unit = models.CharField(max_length=20, default='Litre')
    buying_price = models.FloatField(default=0, blank=True)
    selling_price = models.FloatField(default=0, blank=True)
    
    class Meta:
        unique_together = ('mill', 'name')
    
    def __str__(self): 
        return self.name

class Stock(models.Model):
    mill = models.ForeignKey(Mill, on_delete=models.CASCADE, related_name='stocks')
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='stock')
    quantity = models.FloatField(default=0)
    low_alert = models.FloatField(default=10)
    
    def __str__(self): 
        return f"{self.mill.name} - {self.product.name}: {self.quantity}{self.product.unit}"

class MillingJob(models.Model):
    PAY_TYPES = [
        ('CASH','Cash Payment'),
        ('SHARE','Oil Sharing'),
        ('MASHUDU','Keep Cake'),
        ('OWNER','Alizeti za Kiwanda')
    ]
    STATUS = [('PENDING','Pending'),('PAID','Paid'),('DEBT','Debt')]
    
    mill = models.ForeignKey(Mill, on_delete=models.CASCADE, related_name='jobs')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, related_name='jobs')
    seed_weight_kg = models.FloatField()
    oil_produced_litre = models.FloatField(default=0)
    cake_produced_kg = models.FloatField(default=0)
    service_type = models.CharField(max_length=10, choices=PAY_TYPES, default='CASH')
    service_cost = models.FloatField(default=0)
    oil_share_customer_percent = models.IntegerField(default=100)
    payment_status = models.CharField(max_length=10, choices=STATUS, default='PENDING')
    amount_paid = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    @property
    def balance(self): 
        return float(self.service_cost or 0) - float(self.amount_paid or 0)
    
    def __str__(self): 
        if self.customer:
            return f"{self.mill.name} Job #{self.id} - {self.customer.name}"
        return f"{self.mill.name} Job #{self.id} - KIWANDA {self.seed_weight_kg}KG"

class Sale(models.Model):
    SALE_TYPES = [('RETAIL','Retail'),('WHOLESALE','Wholesale')]
    mill = models.ForeignKey(Mill, on_delete=models.CASCADE, related_name='sales')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    customer_name = models.CharField(max_length=100, blank=True, default="")
    customer_phone = models.CharField(max_length=20, blank=True, default="")  # <-- HII NDIO MPYA KWA SIMU
    quantity = models.FloatField()
    price_per_unit = models.FloatField()
    sale_type = models.CharField(max_length=10, choices=SALE_TYPES, default='RETAIL')
    total = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        try:
            self.total = float(self.quantity or 0) * float(self.price_per_unit or 0)
        except:
            self.total = 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.mill.name} Sale #{self.id} {self.product.name} - {self.customer_name} {self.sale_type}"

class Expense(models.Model):
    CATS = [
        ('PACKAGING','Packaging'),
        ('TRANSPORT','Transport'),
        ('POWER','Luku/Umeme'),
        ('REPAIR','Machine Repair'),
        ('PURCHASE','Ununuzi wa Alizeti'),
        ('OTHER','Other')
    ]
    mill = models.ForeignKey(Mill, on_delete=models.CASCADE, related_name='expenses')
    category = models.CharField(max_length=20, choices=CATS)
    description = models.CharField(max_length=200)
    amount = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.mill.name} - {self.category} - {self.amount}"

class Purchase(models.Model):
    mill = models.ForeignKey(Mill, on_delete=models.CASCADE, related_name='purchases')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchases')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.FloatField()
    cost_per_unit = models.FloatField()
    total_cost = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        try:
            self.total_cost = float(self.quantity or 0) * float(self.cost_per_unit or 0)
        except:
            self.total_cost = 0
        super().save(*args, **kwargs)
    
    def __str__(self): 
        return f"{self.mill.name} Purchase {self.product.name}"

class StockMovement(models.Model):
    TYPES = [('IN','Ingia'),('OUT','Toka')]
    mill = models.ForeignKey(Mill, on_delete=models.CASCADE, related_name='movements')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    type = models.CharField(max_length=3, choices=TYPES)
    quantity = models.FloatField()
    reason = models.CharField(max_length=100, default='General')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.mill.name} {self.type} {self.product.name} {self.quantity}"