from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F
from django.utils import timezone
import calendar
from .models import Customer, Product, Stock, MillingJob, Sale, Expense, Supplier, Purchase, StockMovement, Mill
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from functools import wraps

def to_f(x):
    try: return float(x or 0)
    except: return 0.0

def get_mill(request, mill_slug=None):
    if mill_slug:
        mill = Mill.objects.filter(slug=mill_slug).first()
        if not mill: return None
        if request.user.is_authenticated:
            if request.user.is_superuser: return mill
            if mill.owner != request.user: return None
        return mill
    if request.user.is_authenticated:
        if request.user.is_superuser: return Mill.objects.first()
        return Mill.objects.filter(owner=request.user, is_active=True).first()
    return Mill.objects.filter(slug='willa-foods').first() or Mill.objects.first()

def check_access(request, mill):
    if not mill: return False
    if not request.user.is_authenticated: return False
    if request.user.is_superuser: return True
    return mill.owner == request.user

def mill_owner_required(view_func):
    @wraps(view_func)
    def wrapper(request, mill_slug=None, *args, **kwargs):
        mill = get_mill(request, mill_slug)
        if not mill:
            messages.error(request, f'Huna ruhusa ya kuingia {mill_slug}')
            return redirect('mill_list')
        if mill_slug and not check_access(request, mill):
            messages.error(request, f'{mill.name} ni ya {mill.owner.username}')
            return redirect('/mills/')
        return view_func(request, mill_slug=mill_slug, *args, **kwargs)
    return wrapper

def landing_page(request, mill_slug=None):
    if request.user.is_authenticated:
        first_mill = Mill.objects.filter(owner=request.user, is_active=True).first()
        if first_mill: return redirect(f'/{first_mill.slug}/')
        return redirect('mill_list')
    return render(request, 'mill/landing.html')

def login_view(request, mill_slug=None):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user:
            login(request, user)
            return redirect('mill_list')
        messages.error(request, 'Username au password sio sahihi')
    return render(request, 'mill/login.html')

def register_view(request, mill_slug=None):
    if request.method == 'POST':
        username = request.POST.get('username'); email = request.POST.get('email')
        password = request.POST.get('password'); mill_name = request.POST.get('mill_name')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username tayari ipo')
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            slug = mill_name.lower().replace(' ', '-').replace('/', '-')
            mill = Mill.objects.create(name=mill_name, slug=slug, owner=user, location='Dar')
            data = [('Alizeti','SEED','KG',100,20),('Dumu Tupu 20L','OIL','Dumu',5,0),('Dumu Tupu 10L','OIL','Dumu',5,0),('Dumu Tupu 5L','OIL','Dumu',5,0),('Dumu Tupu 3L','OIL','Dumu',5,0),('Dumu Tupu 1L','OIL','Dumu',5,0),('Mafuta ya Alizeti','OIL','Litre',20,80),('Mashudu','CAKE','KG',50,60)]
            for name,t,u,low,qty in data:
                p = Product.objects.create(mill=mill, name=name, type=t, unit=u)
                Stock.objects.create(mill=mill, product=p, quantity=qty, low_alert=low)
            login(request, user)
            return redirect(f'/{mill.slug}/stock/')
    return render(request, 'mill/register.html')

def logout_view(request, mill_slug=None): logout(request); return redirect('/')

def mill_list(request, mill_slug=None):
    if not request.user.is_authenticated: return redirect('/login/')
    mills = Mill.objects.filter(is_active=True).order_by('-id') if request.user.is_superuser else Mill.objects.filter(owner=request.user, is_active=True)
    return render(request, 'mill/mill_list.html', {'mills': mills, 'mill': get_mill(request, mill_slug), 'is_super': request.user.is_superuser})

def mill_create(request, mill_slug=None):
    if request.method == 'POST':
        name = request.POST.get('name'); slug = name.lower().replace(' ', '-').replace('/', '-')
        owner = request.user if request.user.is_authenticated else User.objects.first()
        Mill.objects.create(name=name, slug=slug, owner=owner, location='Dar')
        return redirect('mill_list')
    return render(request, 'mill/mill_create.html', {'mill': get_mill(request, mill_slug)})

@mill_owner_required
def dashboard(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    stock_qs = Stock.objects.filter(mill=mill)
    sale_qs = Sale.objects.filter(mill=mill)
    expense_qs = Expense.objects.filter(mill=mill)
    job_qs = MillingJob.objects.filter(mill=mill)
    oil = stock_qs.filter(product__type='OIL').aggregate(Sum('quantity'))['quantity__sum'] or 0
    seed = stock_qs.filter(product__type='SEED').aggregate(Sum('quantity'))['quantity__sum'] or 0
    cake = stock_qs.filter(product__type='CAKE').aggregate(Sum('quantity'))['quantity__sum'] or 0
    income_sales = sum([to_f(s.quantity)*to_f(s.price_per_unit) for s in sale_qs])
    income_jobs = job_qs.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    total_exp = expense_qs.aggregate(Sum('amount'))['amount__sum'] or 0
    today = timezone.now().date()
    return render(request, 'mill/dashboard.html', {
        'mill': mill, 'oil_stock': oil, 'seed_stock': seed, 'cake_stock': cake,
        'income': income_sales + to_f(income_jobs), 'expense': total_exp,
        'profit': (income_sales + to_f(income_jobs)) - to_f(total_exp),
        'low_stocks': stock_qs.filter(quantity__lte=F('low_alert')),
        'jobs': job_qs.order_by('-created_at')[:10],
        'jobs_today': job_qs.filter(created_at__date=today),
        'today': today, 'stock_data': stock_qs.select_related('product')
    })

@mill_owner_required
def job_list(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    filter_date = request.GET.get('date', 'leo')
    today = timezone.now().date()
    qs_all = MillingJob.objects.filter(mill=mill)
    if filter_date == 'leo':
        qs = qs_all.filter(created_at__date=today).order_by('-created_at')
    elif filter_date == 'jana':
        yest = today - timezone.timedelta(days=1)
        qs = qs_all.filter(created_at__date=yest).order_by('-created_at')
    elif filter_date == 'wiki':
        start = today - timezone.timedelta(days=today.weekday())
        qs = qs_all.filter(created_at__date__gte=start).order_by('-created_at')
    else:
        qs = qs_all.order_by('-created_at')
    today_jobs = qs_all.filter(created_at__date=today)
    today_count = today_jobs.count()
    today_kg = sum([to_f(j.seed_weight_kg) for j in today_jobs])
    today_oil = sum([to_f(j.oil_produced_litre) for j in today_jobs])
    today_cash = sum([to_f(j.amount_paid) for j in today_jobs.filter(customer__isnull=False)])
    today_debt = sum([to_f(j.service_cost) - to_f(j.amount_paid) for j in today_jobs.filter(customer__isnull=False)])
    total_cash = sum([to_f(j.amount_paid) for j in qs])
    total_service = sum([to_f(j.service_cost) for j in qs])
    year = today.year; month = today.month
    _, num_days = calendar.monthrange(year, month)
    days_data = []
    return render(request, 'mill/job_list.html', {
        'jobs': qs, 'mill': mill, 'today': today,
        'today_count': today_count, 'today_kg': today_kg, 'today_oil': today_oil,
        'today_cash': today_cash, 'today_debt': today_debt,
        'total_cash': total_cash, 'total_service': total_service,
        'filter_date': filter_date,
        'selected_year': year, 'selected_month': month, 'selected_day': None,
        'days_data': days_data, 'years': range(2023, timezone.now().year+2), 'months': range(1, 13)
    })

@mill_owner_required
def job_create(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'MTEJA')
        if form_type == 'KIWANDA':
            seed = to_f(request.POST.get('seed_weight_owner'))
            oil = to_f(request.POST.get('oil_produced_owner'))
            cake = to_f(request.POST.get('cake_produced_owner'))
            buy_cost = to_f(request.POST.get('buying_cost'))
            MillingJob.objects.create(mill=mill, customer=None, seed_weight_kg=seed, oil_produced_litre=oil, cake_produced_kg=cake, service_type='KIWANDA', service_cost=buy_cost, amount_paid=buy_cost, payment_status='PAID')
            if oil > 0:
                prod = Product.objects.filter(mill=mill, name__icontains='Mafuta ya Alizeti').first() or Product.objects.filter(mill=mill, type='OIL').first()
                if prod:
                    st,_ = Stock.objects.get_or_create(mill=mill, product=prod, defaults={'quantity':0,'low_alert':10})
                    st.quantity = to_f(st.quantity) + oil
                    st.save()
                    StockMovement.objects.create(mill=mill, product=prod, type='IN', quantity=oil, reason='Kiwanda - Kusaga')
            if cake > 0:
                prod_c = Product.objects.filter(mill=mill, name__icontains='Mashudu').first()
                if prod_c:
                    st,_ = Stock.objects.get_or_create(mill=mill, product=prod_c, defaults={'quantity':0,'low_alert':10})
                    st.quantity = to_f(st.quantity) + cake
                    st.save()
            if buy_cost > 0:
                Expense.objects.create(mill=mill, category='MANUNUZI - Alizeti za Kiwanda', description=f'Manunuzi alizeti {seed}KG kwa kusaga kiwanda', amount=buy_cost)
        else:
            cust = None
            sel = request.POST.get('customer')
            if sel: cust = Customer.objects.filter(id=sel, mill=mill).first()
            name = request.POST.get('new_customer_name'); phone = request.POST.get('new_customer_phone')
            if not cust and name and phone:
                cust,_ = Customer.objects.get_or_create(mill=mill, phone=phone, defaults={'name': name})
            MillingJob.objects.create(mill=mill, customer=cust, seed_weight_kg=to_f(request.POST.get('seed_weight')), oil_produced_litre=to_f(request.POST.get('oil_produced')), cake_produced_kg=to_f(request.POST.get('cake_produced')), service_type=request.POST.get('service_type') or 'CASH', service_cost=to_f(request.POST.get('service_cost')), amount_paid=to_f(request.POST.get('amount_paid')), payment_status='PAID')
        return redirect(f'/{mill.slug}/jobs/')
    return render(request, 'mill/job_form.html', {'customers': Customer.objects.filter(mill=mill), 'mill': mill})

@mill_owner_required
def job_delete(request, id, mill_slug=None):
    mill = get_mill(request, mill_slug)
    get_object_or_404(MillingJob, id=id, mill=mill).delete()
    return redirect(f'/{mill.slug}/jobs/')

@mill_owner_required
def sale_list(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    day = request.GET.get('day')
    sales_all = Sale.objects.filter(mill=mill)
    qs = sales_all.filter(created_at__year=year, created_at__month=month).order_by('-created_at')
    if day: qs = qs.filter(created_at__day=int(day))
    total_month = sum([to_f(s.quantity)*to_f(s.price_per_unit) for s in sales_all.filter(created_at__year=year, created_at__month=month)])
    total_filtered = sum([to_f(s.quantity)*to_f(s.price_per_unit) for s in qs])
    _, num_days = calendar.monthrange(year, month)
    days_data = []
    for d in range(1, num_days+1):
        f_qs = sales_all.filter(created_at__year=year, created_at__month=month, created_at__day=d)
        days_data.append({'day': d, 'total': sum([to_f(s.quantity)*to_f(s.price_per_unit) for s in f_qs]), 'count': f_qs.count()})
    return render(request, 'mill/sale_list.html', {'sales': qs, 'total_month': total_month, 'total_filtered': total_filtered, 'days_data': days_data, 'selected_year': year, 'selected_month': month, 'selected_day': day, 'mill': mill, 'years': range(2023, timezone.now().year+2), 'months': range(1, 13)})

@mill_owner_required
def sale_create(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    if request.method == 'POST':
        prod = get_object_or_404(Product, id=request.POST.get('product'), mill=mill)
        qty = to_f(request.POST.get('quantity'))
        stock, _ = Stock.objects.get_or_create(mill=mill, product=prod, defaults={'quantity': 0, 'low_alert': 10})
        if to_f(stock.quantity) >= qty:
            Sale.objects.create(mill=mill, product=prod, quantity=qty, price_per_unit=to_f(request.POST.get('price')), sale_type=request.POST.get('sale_type') or 'RETAIL')
            stock.quantity = to_f(stock.quantity) - qty
            stock.save()
            StockMovement.objects.create(mill=mill, product=prod, type='OUT', quantity=qty, reason="Sale")
        return redirect(f'/{mill.slug}/sales/')
    return render(request, 'mill/sale_form.html', {'products': Product.objects.filter(mill=mill), 'mill': mill})

@mill_owner_required
def sale_delete(request, id, mill_slug=None):
    mill = get_mill(request, mill_slug)
    s = get_object_or_404(Sale, id=id, mill=mill)
    st, _ = Stock.objects.get_or_create(mill=mill, product=s.product, defaults={'quantity': 0, 'low_alert': 10})
    st.quantity = to_f(st.quantity) + to_f(s.quantity)
    st.save()
    s.delete()
    return redirect(f'/{mill.slug}/sales/')

def sale_edit(request, id, mill_slug=None):
    return redirect(f'/{mill_slug}/sales/')

@mill_owner_required
def expense_list(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    day = request.GET.get('day')
    expenses_all = Expense.objects.filter(mill=mill)
    qs = expenses_all.filter(created_at__year=year, created_at__month=month).order_by('-created_at')
    if day: qs = qs.filter(created_at__day=int(day))
    if request.method == 'POST':
        desc = request.POST.get('description') or 'Matumizi'
        cat = request.POST.get('category') or desc[:20] or 'GENERAL'
        Expense.objects.create(mill=mill, category=cat, description=desc, amount=to_f(request.POST.get('amount')))
        return redirect(f'/{mill.slug}/expenses/?year={year}&month={month}&day={day or ""}')
    total_month = sum([to_f(e.amount) for e in expenses_all.filter(created_at__year=year, created_at__month=month)])
    total_filtered = sum([to_f(e.amount) for e in qs])
    _, num_days = calendar.monthrange(year, month)
    days_data = []
    for d in range(1, num_days+1):
        f_qs = expenses_all.filter(created_at__year=year, created_at__month=month, created_at__day=d)
        days_data.append({'day': d, 'total': sum([to_f(e.amount) for e in f_qs]), 'count': f_qs.count()})
    return render(request, 'mill/expense_list.html', {
        'expenses': qs, 'total_month': total_month, 'total_filtered': total_filtered,
        'days_data': days_data, 'selected_year': year, 'selected_month': month,
        'selected_day': day, 'mill': mill,
        'years': range(2023, timezone.now().year+2), 'months': range(1, 13)
    })

@mill_owner_required
def expense_delete(request, id, mill_slug=None):
    mill = get_mill(request, mill_slug)
    get_object_or_404(Expense, id=id, mill=mill).delete()
    return redirect(f'/{mill.slug}/expenses/')

def expense_edit(request, id, mill_slug=None):
    return redirect(f'/{mill_slug}/expenses/')

# ===== STOCK VIEW FIXED - HAKUNA 500 TENA =====
@mill_owner_required
def stock_view(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    if request.method == 'POST':
        try:
            prod = get_object_or_404(Product, id=request.POST.get('product'), mill=mill)
            qty = to_f(request.POST.get('quantity'))
            cost = to_f(request.POST.get('cost'))
            if qty > 0:
                Purchase.objects.create(mill=mill, product=prod, quantity=qty, cost_per_unit=cost)
                st, _ = Stock.objects.get_or_create(mill=mill, product=prod, defaults={'quantity': 0, 'low_alert': 10})
                st.quantity = to_f(st.quantity) + qty
                st.save()
                StockMovement.objects.create(mill=mill, product=prod, type='IN', quantity=qty, reason="Purchase")
                total_cost = qty * cost
                if total_cost > 0:
                    Expense.objects.create(mill=mill, category=f'MANUNUZI - {prod.name[:20]}', description=f'Manunuzi {prod.name} {qty}', amount=total_cost)
        except Exception as e:
            print(f"Stock POST error: {e}")
        return redirect(f'/{mill.slug}/stock/')

    try:
        stocks = Stock.objects.filter(mill=mill).select_related('product')
        stock_data = []
        for s in stocks:
            try:
                q = to_f(s.quantity)
                low = to_f(s.low_alert)
                stock_data.append({'stock': s, 'product': s.product, 'quantity': q, 'is_low': q <= low})
            except:
                stock_data.append({'stock': s, 'product': s.product, 'quantity': 0, 'is_low': False})
    except Exception as e:
        print(f"Stock GET error: {e}")
        stock_data = []

    return render(request, 'mill/stock.html', {
        'stock_data': stock_data,
        'products': Product.objects.filter(mill=mill),
        'suppliers': Supplier.objects.filter(mill=mill),
        'movements': StockMovement.objects.filter(mill=mill).order_by('-created_at')[:20],
        'purchases': Purchase.objects.filter(mill=mill).order_by('-created_at')[:20],
        'mill': mill
    })

@mill_owner_required
def stock_reset(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    Stock.objects.filter(mill=mill).update(quantity=0)
    return redirect(f'/{mill.slug}/stock/')

@mill_owner_required
def stock_movement_reset(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    StockMovement.objects.filter(mill=mill).delete()
    return redirect(f'/{mill.slug}/stock/')

def owner_milling_create(request, mill_slug=None):
    return redirect(f'/{mill_slug}/jobs/')

@mill_owner_required
def daily_report(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    year = int(request.GET.get('year', timezone.now().year))
    month = int(request.GET.get('month', timezone.now().month))
    day = int(request.GET.get('day', timezone.now().day))
    from datetime import date
    try:
        target_date = date(year, month, day)
    except:
        target_date = timezone.now().date()
        year, month, day = target_date.year, target_date.month, target_date.day
    jobs = MillingJob.objects.filter(mill=mill, created_at__year=year, created_at__month=month, created_at__day=day).order_by('created_at')
    sales = Sale.objects.filter(mill=mill, created_at__year=year, created_at__month=month, created_at__day=day)
    expenses = Expense.objects.filter(mill=mill, created_at__year=year, created_at__month=month, created_at__day=day)
    jobs_mteja = jobs.filter(customer__isnull=False)
    jobs_kiwanda = jobs.filter(customer__isnull=True)
    def sum_field(qs, field):
        return sum([to_f(getattr(j, field)) for j in qs])
    total_mbegu = sum_field(jobs, 'seed_weight_kg')
    total_oil = sum_field(jobs, 'oil_produced_litre')
    total_cake = sum_field(jobs, 'cake_produced_kg')
    total_mteja_mbegu = sum_field(jobs_mteja, 'seed_weight_kg')
    total_mteja_oil = sum_field(jobs_mteja, 'oil_produced_litre')
    total_mteja_cake = sum_field(jobs_mteja, 'cake_produced_kg')
    total_mteja_cash = sum_field(jobs_mteja, 'amount_paid')
    total_mteja_service = sum_field(jobs_mteja, 'service_cost')
    total_mteja_debt = total_mteja_service - total_mteja_cash
    total_kiwanda_mbegu = sum_field(jobs_kiwanda, 'seed_weight_kg')
    total_oil_kiwanda = sum_field(jobs_kiwanda, 'oil_produced_litre')
    total_cake_kiwanda = sum_field(jobs_kiwanda, 'cake_produced_kg')
    gharama_kiwanda = sum_field(jobs_kiwanda, 'service_cost')
    sales_total = sum([to_f(s.quantity)*to_f(s.price_per_unit) for s in sales])
    for s in sales:
        s.total = to_f(s.quantity)*to_f(s.price_per_unit)
    expenses_total = sum([to_f(e.amount) for e in expenses])
    return render(request, 'mill/daily_report.html', {
        'mill': mill, 'target_date': target_date,
        'jobs': jobs, 'jobs_mteja': jobs_mteja, 'jobs_kiwanda': jobs_kiwanda,
        'sales': sales, 'expenses': expenses,
        'sales_total': sales_total, 'expenses_total': expenses_total,
        'total_mbegu': total_mbegu, 'total_oil': total_oil, 'total_cake': total_cake,
        'total_mteja_mbegu': total_mteja_mbegu, 'total_mteja_oil': total_mteja_oil,
        'total_mteja_cake': total_mteja_cake, 'total_mteja_cash': total_mteja_cash,
        'total_mteja_service': total_mteja_service, 'total_mteja_debt': total_mteja_debt,
        'total_kiwanda_mbegu': total_kiwanda_mbegu, 'total_oil_kiwanda': total_oil_kiwanda,
        'total_cake_kiwanda': total_cake_kiwanda, 'gharama_kiwanda': gharama_kiwanda,
    })

@mill_owner_required
def sale_reset_all(request, mill_slug=None):
    mill = get_mill(request, mill_slug)
    Sale.objects.filter(mill=mill).delete()
    return redirect(f'/{mill.slug}/sales/')

def hard_reset_all(request, mill_slug=None):
    return redirect(f'/{mill_slug}/stock/')

def job_edit(request, id, mill_slug=None):
    return redirect(f'/{mill_slug}/jobs/')