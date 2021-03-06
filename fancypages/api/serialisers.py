import re
import shortuuid
import logging

from django.http import Http404
from django.db.models import get_model
from django.utils.translation import ugettext as _
from django.contrib.contenttypes.models import ContentType

from rest_framework import serializers

from .. import library
from ..utils import get_page_model, get_node_model


logger = logging.getLogger('fancypages.api')

# FancyPage = get_page_model()
# PageNode = get_node_model()
# Container = get_model('fancypages', 'Container')
# ContentBlock = get_model('fancypages', 'ContentBlock')
# OrderedContainer = get_model('fancypages', 'OrderedContainer')

SHORTUUID_REGEX = re.compile(r'[{0}]+'.format(shortuuid.get_alphabet()))


class BlockSerializer(serializers.ModelSerializer):
    container = serializers.SlugRelatedField(slug_field='uuid')
    display_order = serializers.IntegerField(required=False, default=-1)
    code = serializers.CharField(required=True)

    def __init__(self, instance=None, data=None, files=None, context=None,
                 partial=False, many=None, allow_add_remove=False, **kwargs):
        if instance:
            self.Meta.model = instance.__class__
        elif data is not None:
            code = data.get('code')
            block_class = library.get_content_block(code)
            if block_class:
                self.Meta.model = block_class

        super(BlockSerializer, self).__init__(
            instance, data, files, context, partial, many, allow_add_remove,
            **kwargs)

    def restore_object(self, attrs, instance=None):
        # we need to remove the 'code' attribute as it is not a valid keyword
        # for content block subclasses. It's only used in the serialiser
        if 'code' in attrs:
            del attrs['code']
        return super(BlockSerializer, self).restore_object(attrs, instance)

    class Meta:
        pass

    def __new__(cls, *args, **kwargs):
        cls.Meta.model = get_model('fancypages', 'ContentBlock')


class BlockCodeSerializer(serializers.Serializer):
    container = serializers.CharField()
    code = serializers.CharField(required=True)

    def validate_container(self, attrs, source):
        Container = get_model('fancypages', 'Container')
        container_uuid = attrs.get('container')
        try:
            container = Container.objects.get(uuid=container_uuid)
        except Container.DoesNotExist:
            raise serializers.ValidationError(
                "no container could be found with ID {}".format(
                    container_uuid))
        attrs['container'] = container
        return attrs

    def restore_object(self, attrs, instance=None):
        block_class = library.get_content_block(attrs.get('code'))
        return block_class(container=attrs.get('container'))


class BlockMoveSerializer(serializers.ModelSerializer):
    container = serializers.SlugRelatedField(slug_field='uuid')
    index = serializers.IntegerField(source='display_order')

    class Meta:
        read_only_fields = ['display_order']

    def __new__(cls, *args, **kwargs):
        cls.Meta.model = get_model('fancypages', 'ContentBlock')


class OrderedContainerSerializer(serializers.ModelSerializer):
    block = serializers.RegexField(regex=SHORTUUID_REGEX, source='block_uuid')
    title = serializers.CharField(required=False, default=_("New Tab"))

    def restore_object(self, attrs, instance=None):
        block_uuid = attrs.pop('block_uuid')
        try:
            block = ContentBlock.objects.get_subclass(uuid=block_uuid)
        except ContentBlock.DoesNotExist:
            logger.info(
                "invalid block UUID passed to serializer",
                extra={'block_uuid': block_uuid, 'attrs': attrs})
            raise Http404("block ID is invalid")

        try:
            content_type = ContentType.objects.get_for_model(block.__class__)
        except ContentType.DoesNotExist:
            logger.info(
                "could not find content type for block",
                extra={'block_uuid': block_uuid, 'attrs': attrs,
                       'model': block.__class__})
            raise Http404("block ID is invalid")

        attrs.update({'object_id': block.id, 'content_type': content_type})
        instance = super(OrderedContainerSerializer, self).restore_object(
            attrs, instance)
        if instance is not None:
            instance.display_order = instance.page_object.tabs.count()
        return instance

    class Meta:
        exclude = ['display_order', 'object_id', 'content_type']

    def __new__(cls, *args, **kwargs):
        cls.Meta.model = get_model('fancypages', 'OrderedContainer')


class PageMoveSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField('get_page_title')
    is_visible = serializers.SerializerMethodField('get_visibility')

    parent = serializers.CharField(required=False, default='0')
    new_index = serializers.IntegerField()
    old_index = serializers.IntegerField(required=True)

    def get_page_title(self):
        return self.object.name

    def get_visibility(self):
        return self.object.is_visible

    def save(self, *args, **kwargs):
        obj = super(PageMoveSerializer, self).save(*args, **kwargs)
        if obj.new_index <= obj.old_index:
            position = 'left'
        else:
            position = 'right'

        # if the parent UUID is '' the page will be moved to the
        # root level. That means we have to lookup the root node
        # that we use to relate the move to. This is the root node
        # at the position of the new_index. If it is the last node
        # the index will cause a IndexError so we insert the page
        # after the last node.
        PageNode = get_node_model()
        if obj.parent == '0':
            try:
                node = PageNode.get_root_nodes()[obj.new_index]
            except IndexError:
                node = PageNode().get_last_root_node()
                position = 'right'
        # in this case the page is moved relative to a parent node.
        # we have to handle the same special case for the last node
        # as above and also have to insert as 'first-child' if no
        # other children are present due to different relative node
        else:
            node = PageNode.objects.get(page__uuid=obj.parent)
            if not node.numchild:
                position = 'first-child'
            else:
                try:
                    node = node.get_children()[obj.new_index]
                except IndexError:
                    position = 'last-child'
        obj.move(node, position)
        return obj.page

    class Meta:
        # model = get_page_model()
        fields = ['parent', 'new_index', 'old_index']
        read_only_fields = ['status']

    def __new__(cls, *args, **kwargs):
        cls.Meta.model = get_page_model()
