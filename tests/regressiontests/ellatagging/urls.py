from os.path import dirname

from django.conf.urls.defaults import *
from django.contrib import admin
from django.conf import settings
import ella.tagging.views

admin_url = settings.ADMIN_MEDIA_PREFIX
if admin_url.startswith('/'):
    admin_url = admin_url[1:]
if admin_url.endswith('/'):
    admin_url = admin_url[:-1]

admin_root = '%s/static/admin/' % dirname(__file__)

urlpatterns = patterns('',
    (r'^%s/(?P<path>.*)$' % admin_url, 'django.views.static.serve', {'document_root': admin_root, 'show_indexes': True}),
    (r'^admin/(.*)', admin.site.root),
    # tag suggest: /t/?q=howgh
    url(r'^t/$', 'ella.tagging.views.tags_json_view', name='tag_suggester'),
    (r'^', include('ella.core.urls')),
)

