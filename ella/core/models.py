from datetime import datetime, timedelta

from django.db import models, transaction
from django.core.urlresolvers import reverse
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.contrib import admin
from django.template.defaultfilters import slugify
from django.utils.translation import ugettext_lazy as _

from ella.core.box import Box
from ella.core.managers import *
from ella.core.admin.models import *


class Author(models.Model):
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, blank=True, null=True)
    name = models.CharField(_('Name'), max_length=200, blank=True)
    slug = models.CharField(_("Slug"), max_length=200)
    #photo = models.ImageField(_('Photo'), upload_to='photos/%Y/%m/%d', blank=True)
    description = models.TextField(_('Description'), blank=True)
    text = models.TextField(_('Text'), blank=True)

    def __unicode__(self):
        return self.name

    class Meta:
        ordering=('name',)
        verbose_name = _('Author')
        verbose_name_plural = _('Authors')

class Source(models.Model):
    name = models.CharField(_('Name'), max_length=200)
    url = models.URLField(_('URL'), blank=True)
    description = models.TextField(_('Description'), blank=True)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = _('Source')
        verbose_name_plural = _('Sources')
        ordering = ('name',)

class CategoryBox(Box):
    def get_context(self):
        cont = super(CategoryBox, self).get_context()
        if 'photo_slug' in self.params:
            cont['photo_slug'] = self.params['photo_slug']
        return cont

def get_category_key(func, category):
    return 'ella.core.models.Category(%d)' % category.id

class Category(models.Model):
    title = models.CharField(_("Category Title"), max_length=200)
    slug = models.CharField(_("Slug"), max_length=200)
    tree_parent = models.ForeignKey('self', null=True, blank=True, verbose_name=_("Parent Category"))
    tree_path = models.CharField(max_length=255, editable=False)
    description = models.TextField(_("Category Description"), blank=True)
    site = models.ForeignKey(Site)

    @transaction.commit_on_success
    def save(self):
        old_tree_path = self.tree_path
        if self.tree_parent:
            if self.tree_parent.tree_path:
                self.tree_path = '%s/%s' % (self.tree_parent.tree_path, self.slug)
            else:
                self.tree_path = self.slug
        else:
            self.tree_path = ''
        super(Category, self).save()
        if old_tree_path != self.tree_path:
            children = Category.objects.filter(tree_path__startswith=old_tree_path+'/')
            for child in children:
                child.tree_path = child.tree_path.replace(old_tree_path, self.tree_path)
                child.save()

    def get_tree_parent(self):
        if self.tree_parent_id:
            return get_cached_object(Category, pk=self.tree_parent_id)
        return None

    @property
    def path(self):
        if self.tree_parent_id:
            return self.tree_path
        else:
            return self.slug

    def Box(self, box_type, nodelist):
        return CategoryBox(self, box_type, nodelist)

    def get_absolute_url(self):
        if not self.tree_parent_id:
            return reverse('root_homepage')
        else:
            return reverse(
                    'category_detail',
                    kwargs={
                        'category' : self.tree_path,
}
)


    def draw_title(self):
        return ('&nbsp;&nbsp;' * self.tree_path.count('/')) + self.title
    draw_title.allow_tags = True

    class Meta:
        ordering = ('title',)
        unique_together = (('site', 'tree_path'),)
        verbose_name = _('Category')
        verbose_name_plural = _('Categories')

    @cache_this(get_category_key)
    def __unicode__(self):
        return '%s/%s' % (self.site.name, self.tree_path)

class Listing(models.Model):
    """
    Listing of an object in a category. Each and every odject that have it's own detail page must have a Listing object
    that is valid (nod expired) and places him in the object's main category. Any object can be listed in any number of
    categories (but only once per category). Even if the object is listed in other categories besides its main category,
    its detail page's url still belongs to the main one.
    """
    target_ct = models.ForeignKey(ContentType)
    target_id = models.IntegerField()

    @property
    def target(self):
        return get_cached_object(self.target_ct, pk=self.target_id)

    category = models.ForeignKey(Category, db_index=True)

    publish_from = models.DateTimeField(_("Start of listing"), default=datetime.now)
    priority_from = models.DateTimeField(_("Start of prioritized listing"), default=datetime.now, null=True, blank=True)
    priority_to = models.DateTimeField(_("End of prioritized listing"), default=lambda: datetime.now() + timedelta(days=7), null=True, blank=True)
    priority_value = models.IntegerField(_("Priority"), blank=True, null=True)
    remove = models.BooleanField(_("Remove"), help_text=_("Remove object from listing after the priority wears off?"), default=False)

    commercial = models.BooleanField(_("Commercial"), default=False)

    hidden = models.BooleanField(_("Hidden"), default=False, help_text=_("Create the object's URL, but do not list it in listings?"))

    objects = ListingManager()

    def Box(self, box_type, nodelist):
        """
        Delegate the boxing
        """
        obj = self.target
        if hasattr(obj, 'Box'):
            return obj.Box(box_type, nodelist)
        return Box(obj, box_type, nodelist)

    def get_absolute_url(self):
        obj = self.target
        if obj.category_id != self.category_id:
            listing = obj.main_listing
        else:
            listing = self

        category = get_cached_object(Category, pk=obj.category_id)

        if category.tree_parent_id:
            url = reverse(
                    'object_detail',
                    kwargs={
                        'category' : category.tree_path,
                        'year' : listing.publish_from.year,
                        'month' : listing.publish_from.month,
                        'day' : listing.publish_from.day,
                        'content_type' : slugify(obj._meta.verbose_name_plural),
                        'slug' : getattr(obj, 'slug', str(obj._get_pk_val())),
}
)
        else:
            url = reverse(
                    'home_object_detail',
                    kwargs={
                        'year' : listing.publish_from.year,
                        'month' : listing.publish_from.month,
                        'day' : listing.publish_from.day,
                        'content_type' : slugify(obj._meta.verbose_name_plural),
                        'slug' : getattr(obj, 'slug', str(obj._get_pk_val())),
}
)
        if category.site_id != settings.SITE_ID:
            site = get_cached_object(Site, pk=category.site_id)
            return 'http://' + site.domain + url
        return url

    def __unicode__(self):
        try:
            return u'%s listed in %s' % (self.target, self.category)
        except models.ObjectDoesNotExist:
            return u'Broken listing in %s' % self.category

    def is_active(self):
        now = datetime.now()
        return not (self.priority_to and now > self.priority_to and self.remove)

    def is_published(self):
        now = datetime.now()
        return (now > self.publish_from)

    def full_url(self):
        from django.utils.safestring import mark_safe
        return mark_safe('<a href="%s">url</a>' % self.get_absolute_url())
    full_url.allow_tags = True


    class Meta:
        verbose_name = _('Listing')
        verbose_name_plural = _('Listings')
        ordering = ('-publish_from',)
        unique_together = (('category', 'target_id', 'target_ct'),)

class HitCount(models.Model):
    target_ct = models.ForeignKey(ContentType)
    target_id = models.IntegerField()
    last_seen = models.DateTimeField(editable=False)
    site = models.ForeignKey(Site)

    hits = models.PositiveIntegerField(_('Hits'), default=1)

    objects = HitCountManager()

    def save(self):
        self.last_seen = datetime.now()
        super(HitCount, self).save()

    @property
    def target(self):
        if not hasattr(self, '_target'):
            target_ct = get_cached_object(ContentType, pk=self.target_ct_id)
            self._target = get_cached_object(target_ct, pk=self.target_id)
        return self._target

    class Meta:
        ordering = ('-hits', '-last_seen',)
        verbose_name = 'Hit Count'
        verbose_name_plural = 'Hit Counts'

class Related(models.Model):
    """
    Related objects - model for recording related items. For example related articles.
    """
    target_ct = models.ForeignKey(ContentType, related_name='relation_for_set')
    target_id = models.IntegerField()

    source_ct = models.ForeignKey(ContentType, related_name='related_on_set')
    source_id = models.IntegerField()

    def __unicode__(self):
        return u'%s relates to %s' % (self.source, self.target)

    @property
    def source(self):
        if not hasattr(self, '_source'):
            self._source = get_cached_object(self.source_ct, pk=self.source_id)
        return self._source

    @property
    def target(self):
        if not hasattr(self, '_target'):
            self._target = get_cached_object(self.target_ct, pk=self.target_id)
        return self._target

    class Meta:
        verbose_name = _('Related')
        verbose_name_plural = _('Related')
        ordering = ('source_ct', 'source_id',)

class Dependency(models.Model):
    """
    Dependent objects - model for recording dependent items.
    For example a photo used in an article is the article's dependencies.
    """
    target_ct = models.ForeignKey(ContentType, related_name='dependency_for_set')
    target_id = models.IntegerField()
    target_key = models.CharField(max_length=100, blank=True)

    source_ct = models.ForeignKey(ContentType, related_name='dependent_on_set')
    source_id = models.IntegerField()
    source_key = models.CharField(max_length=100, blank=True)

    objects = DependencyManager()

    def __unicode__(self):
        return u'%s depends on %s' % (self.source, self.target)

    @property
    def source(self):
        return get_cached_object(self.source_ct, pk=self.source_id)

    @property
    def target(self):
        return get_cached_object(self.target_ct, pk=self.target_id)

    class Meta:
        verbose_name = _('Dependency')
        verbose_name_plural = _('Dependencies')
        ordering = ('source_ct', 'source_id',)
        unique_together = (('target_key', 'source_key',),)

admin.site.register(HitCount, HitCountOptions)
admin.site.register(Category, CategoryOptions)
admin.site.register(Source)
admin.site.register(Author, AuthorOptions)
admin.site.register(Listing, ListingOptions)
admin.site.register(Dependency , DependencyOptions)

