from django.contrib import admin
from django.urls import path
from mill import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.landing_page, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('mills/', views.mill_list, name='mill_list'),
    path('mills/create/', views.mill_create, name='mill_create'),
    
    # Routes bila mill_slug (fallback)
    path('stock/', views.stock_view, name='stock_view'),
    path('jobs/', views.job_list, name='job_list'),
    path('jobs/create/', views.job_create, name='job_create'),
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/create/', views.sale_create, name='sale_create'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('report/daily/', views.daily_report, name='daily_report'),

    # Routes zenye mill_slug - HIZI NDIZO MUHIMU
    path('<slug:mill_slug>/', views.dashboard, name='dashboard_with_mill'),
    path('<slug:mill_slug>/stock/', views.stock_view, name='stock_view_with_mill'),
    path('<slug:mill_slug>/stock/reset/', views.stock_reset, name='stock_reset_with_mill'),
    path('<slug:mill_slug>/jobs/', views.job_list, name='job_list_with_mill'),
    path('<slug:mill_slug>/jobs/create/', views.job_create, name='job_create_with_mill'),
    path('<slug:mill_slug>/jobs/<int:id>/delete/', views.job_delete, name='job_delete_with_mill'),
    path('<slug:mill_slug>/sales/', views.sale_list, name='sale_list_with_mill'),
    path('<slug:mill_slug>/sales/create/', views.sale_create, name='sale_create_with_mill'),
    path('<slug:mill_slug>/sales/<int:id>/delete/', views.sale_delete, name='sale_delete_with_mill'),
    path('<slug:mill_slug>/expenses/', views.expense_list, name='expense_list_with_mill'),
    path('<slug:mill_slug>/expenses/<int:id>/delete/', views.expense_delete, name='expense_delete_with_mill'),
    path('<slug:mill_slug>/expenses/<int:id>/edit/', views.expense_edit, name='expense_edit_with_mill'),
    path('<slug:mill_slug>/report/daily/', views.daily_report, name='daily_report_with_mill'), # <-- HII NDIO ILIKUWA INAKOSekana
]