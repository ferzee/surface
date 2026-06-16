from django.contrib import admin
from django.urls import path, include
from api import views as api_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('', api_views.serve_public, {'filepath': 'index.html'}),
    path('<path:filepath>', api_views.serve_public),
]
