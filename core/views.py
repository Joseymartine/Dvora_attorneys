from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.urls import reverse


class RoleLoginView(LoginView):
    def get_success_url(self):
        redirect_url = self.get_redirect_url()
        if redirect_url:
            return redirect_url
        user = self.request.user
        if user.has_perm('cases.view_case'):
            return reverse('cases:list')
        return reverse('appointments:list')


def home(request):
    return render(request, 'core/home.html')
