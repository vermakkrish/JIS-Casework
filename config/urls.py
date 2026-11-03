from django.urls import path, reverse_lazy
from django.contrib.auth.views import PasswordChangeView
from core import views

urlpatterns=[path('',views.dashboard,name='dashboard'),path('login/',views.sign_in,name='login'),
    path('logout/',views.sign_out,name='logout'),path('health/',views.health,name='health'),
    path('cases/',views.cases,name='cases'),path('cases/new/',views.case_new,name='case_new'),
    path('cases/<uuid:pk>/',views.case_detail,name='case_detail'),path('cases/<uuid:pk>/assignments/',views.assignments,name='assignments'),
    path('cases/<uuid:pk>/schedule/',views.hearing_action,{'action':'schedule'},name='schedule'),
    path('cases/<uuid:pk>/hearings/<int:hearing_id>/reschedule/',views.hearing_action,{'action':'reschedule'},name='reschedule'),
    path('cases/<uuid:pk>/hearings/<int:hearing_id>/adjourn/',views.hearing_action,{'action':'adjourn'},name='adjourn'),
    path('cases/<uuid:pk>/hearings/<int:hearing_id>/summary/',views.hearing_action,{'action':'summary'},name='summary'),
    path('cases/<uuid:pk>/judgment/',views.judgment,name='judgment'),path('cases/<uuid:pk>/slots/',views.slots,name='slots'),
    path('agenda/',views.agenda,name='agenda'),path('accounts/',views.accounts,name='accounts'),
    path('accounts/new/',views.account_new,name='account_new'),path('accounts/<int:pk>/deactivate/',views.account_deactivate,name='deactivate'),
    path('guide/',views.guide,name='guide'),path('password/',PasswordChangeView.as_view(template_name='password.html',success_url=reverse_lazy('password_done')),name='password'),
    path('password/done/',lambda r: views.render(r,'password_done.html'),name='password_done')]
