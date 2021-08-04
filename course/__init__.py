from __future__ import absolute_import, unicode_literals

from django.contrib import messages
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .celery import app as celery_app


@receiver(user_logged_in)
def on_login(sender, user, request, **kwargs):
    print(f'"{user.username}" logging in...')
    request.session["on_behalf_of"] = ""
    messages.info(request, "Welcome!")


__all__ = ("celery_app",)


"""

  <!-- this may be computationally more complex than needed ... may be slowing things down -->
{% if '/accounts/login/' in request.META.HTTP_REFERER %}

<div class="alert alert-warning alert-dismissible fade show" role="alert" style="margin:10px;z-index:inherit;">
<h4 class="alert-heading">Heading!</h4>
<!--<strong>strong text!</strong>-->
<p>
Courses taught through Graduate School of Education (GSE), Penn Law, The School of Veterinary Medicine and Wharton cannot be requested through our Course Request Form.
</p>
<p> For further assistance setting up your course site please contact the appropriate address below.  </p>
<ul>
<li>Graduate School of Education (GSE): gse-help@lists.upenn.edu | GSE Site Request Form </li>
<li>Law: itshelp@law.upenn.edu </li>
<li>Veterinary Medicine: phl-help@vet.upenn.edu </li>
<li>Wharton: courseware@wharton.upenn.edu </li>
</ul>
<hr>
<p class="mb-0">If you believe you are receiving this message in error, please contact canvas@pobox.upenn.edu</p>
<div class="close" data-dismiss="alert" aria-label="Close">
<span aria-hidden="true"><i class="fas fa-times"></i></span>
</div>
</div>
{% endif %}
"""
