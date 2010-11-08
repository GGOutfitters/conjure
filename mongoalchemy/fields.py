from .base import BaseField, ObjectIdField
from .operations import String, Number, Common, List, Reference
from .exceptions import ValidationError
from .documents import Document
import re
import datetime
import copy
import functools

ObjectIdField = ObjectIdField

class GenericField(BaseField):
    pass

class StringField(String, BaseField):
    def __init__(self, regex=None, min_length=None, max_length=None, **kwargs):
        self.regex = re.compile(regex) if regex else None
        self.min_length = min_length
        self.max_length = max_length
        BaseField.__init__(self, **kwargs)

    def to_python(self, value):
        return unicode(value)

    def validate(self, value):
        assert isinstance(value, (str, unicode))

        if self.max_length is not None and len(value) > self.max_length:
            raise ValidationError('String value is too long')

        if self.min_length is not None and len(value) < self.min_length:
            raise ValidationError('String value is too short')

        if self.regex is not None and self.regex.match(value) is None:
            raise ValidationError('String value did not match validation regex')

class EmailField(StringField):
    EMAIL_REGEX = re.compile(
        r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"
        r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'
        r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?$', re.IGNORECASE
    )

    def validate(self, value):
        if not EmailField.EMAIL_REGEX.match(value):
            raise ValidationError('Invalid Email: %s' % value)

class IntegerField(Number, BaseField):
    def __init__(self, min_value=None, max_value=None, **kwargs):
        self.min_value = min_value
        self.max_value = max_value
        BaseField.__init__(self, **kwargs)

    def to_python(self, value):
        if value is None:
            return self.get_default()
        return int(value)

    def validate(self, value):
        try:
            value = int(value)
        except:
            raise ValidationError('%s could not be converted to int' % value)

        if self.min_value is not None and value < self.min_value:
            raise ValidationError('Integer value is too small')

        if self.max_value is not None and value > self.max_value:
            raise ValidationError('Integer value is too large')

class FloatField(IntegerField):
    def to_python(self, value):
        return float(value)

    def validate(self, value):
        if value is None:
            return self.get_default()

        if isinstance(value, int):
            value = float(value)

        assert isinstance(value, float)

        if self.min_value is not None and value < self.min_value:
            raise ValidationError('Float value is too small')

        if self.max_value is not None and value > self.max_value:
            raise ValidationError('Float value is too large')

class BooleanField(BaseField):
    def to_python(self, value):
        return bool(value)

    def validate(self, value):
        assert isinstance(value, bool)

class DateTimeField(BaseField):
    def validate(self, value):
        assert isinstance(value, datetime.datetime)

class DictField(BaseField):
    def validate(self, value):
        if not isinstance(value, dict):
            raise ValidationError('Only dictionaries may be used in a DictField')

        if any(('.' in k or '$' in k) for k in value):
            raise ValidationError('Invalid dictionary key name - keys may not contain "." or "$" characters')

    def __getitem__(self, key):
        class Proxy(Common, String, Number):
            def __init__(self, key, field):
                self.key = key
                self.field = field

            def _validate(self, value):
                pass

            def get_key(self, *args, **kwargs):
                return self.field.get_key(False) + '.' + self.key

        return Proxy(key, self)

class ListField(List, BaseField):
    def __init__(self, field, default=None, **kwargs):
        if not isinstance(field, BaseField):
            raise ValidationError('Argument to ListField constructor must be a valid field')

        field.owner = self
        self.field = field
        BaseField.__init__(self, default=default or [], **kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        if isinstance(self.field, ReferenceField):
            referenced_cls = self.field.document_cls
            lazyload_only = self.field._lazyload_only

            value_list = instance._data.get(self.name)

            if value_list:
                deref_list = []

                for value in value_list:
                    if not isinstance(value, Document):
                        if value is not None:
                            q = referenced_cls.objects.filter_by(id=value)

                            if lazyload_only:
                                q = q.only(*lazyload_only)

                            deref_list.append(q.one())
                    else:
                        deref_list.append(value)

                instance._data[self.name] = deref_list

        return BaseField.__get__(self, instance, owner)

    def to_python(self, value):
        return [self.field.to_python(item) for item in value]

    def to_mongo(self, value):
        return [self.field.to_mongo(item) for item in value]

    def validate(self, value):
        if not isinstance(value, (list, tuple)):
            raise ValidationError('Only lists and tuples may be used in a list field')

        try:
            [self.field.validate(item) for item in value]
        except Exception, err:
            raise ValidationError('Invalid ListField item (%s)' % str(err))

    def add_to_document(self, cls):
        if not isinstance(self.field, ReferenceField): return

        name = self.name

        def proxy(self):
            value_list = self._data.get(name) or []

            if value_list:
                for i, value in enumerate(value_list):
                    if isinstance(value, Document):
                        value = value.id

                    value_list[i] = value

            return value_list

        setattr(cls, name + '_', property(proxy))

    def lookup_member(self, name):
        return self.field.lookup_member(name)

class MapField(BaseField):
    def __init__(self, field, **kwargs):
        if not isinstance(field, BaseField):
            raise ValidationError('Argument to MapField constructor must be a valid field')

        field.owner = self
        self.field = field
        BaseField.__init__(self, **kwargs)

    def to_python(self, value):
        return dict((k, self.field.to_python(item)) for k, item in value.iteritems())

    def to_mongo(self, value):
        return dict((k, self.field.to_mongo(item)) for k, item in value.iteritems())

    def validate(self, value):
        if not isinstance(value, dict):
            raise ValidationError('Only dict may be used in a map field')

        try:
            [self.field.validate(item) for item in value.itervalues()]
        except Exception, err:
            raise ValidationError('Invalid MapField item (%s)' % str(err))

    def __getitem__(self, key):
        if isinstance(self.field, EmbeddedDocumentField):
            class Proxy(object):
                def __init__(self, key, field):
                    self.key = key
                    self.field = field

                def __lshift__(self, expressions):
                    if not isinstance(expressions, tuple):
                        expressions = expressions,

                    for e in expressions:
                        def wrap(name):
                            if e.is_query():
                                left, _, right = name.partition(self.field.name)
                                return left + self.get_key(False) + right
                            elif e.is_update():
                                left, _, right = name.rpartition(self.field.name)
                                return left + self.get_key(True)  + right

                        e.expressions = dict((wrap(key), item) for key, item in e.expressions.iteritems())

                    new_expression = expressions[0]

                    for expression in expressions[1:]:
                        new_expression &= expression

                    return new_expression

                def _validate(self, value):
                    pass

                def get_key(self, *args, **kwargs):
                    return self.field.get_key(*args, **kwargs) + '.' + self.key
            return Proxy(key, self)
        else:
            field = copy.deepcopy(self.field)

            def get_key(field, key, *args, **kwargs):
                return field.get_key(*args, **kwargs) + '.' + key

            field.get_key = functools.partial(get_key, self.field, key)

            return field

class EmbeddedDocumentField(BaseField):
    def __init__(self, document, **kwargs):
        if not (hasattr(document, '_meta') and document._meta['embedded']):
            raise ValidationError('Invalid embedded document class provided to an EmbeddedDocumentField')

        if 'parent_field' in document._meta:
            raise ValidationError('This document is already embedded')

        document._meta['parent_field'] = self
        self.document = document

        BaseField.__init__(self, **kwargs)

    def to_python(self, value):
        if not isinstance(value, self.document):
            return self.document.to_python(value)

        return value

    def to_mongo(self, value):
        return self.document.to_mongo(value)

    def validate(self, value):
        if not isinstance(value, self.document):
            raise ValidationError('Invalid embedded document instance provided to an EmbeddedDocumentField')

        self.document.validate(value)

    def lookup_member(self, name):
        return self.document._fields.get(name)

class ReferenceField(BaseField, Reference):
    def __init__(self, document_cls, lazyload_only=None, **kwargs):
        if document_cls != 'self' and not (hasattr(document_cls, '_meta') and not document_cls._meta['embedded']):
            raise ValidationError('Argument to ReferenceField constructor must be a document class')

        self._document_cls = document_cls
        self._lazyload_only = lazyload_only

        BaseField.__init__(self, **kwargs)

    @property
    def document_cls(self):
        if self._document_cls == 'self':
            self._document_cls = self.owner

        return self._document_cls

    def __get__(self, instance, owner):
        if instance is None:
            return self

        value = instance._data.get(self.name)

        if not isinstance(value, Document):
            if value is not None:
                q = self.document_cls.objects.filter_by(id=value)

                if self._lazyload_only:
                    q = q.only(*self._lazyload_only)

                instance._data[self.name] = q.one()

        return BaseField.__get__(self, instance, owner)

    def to_mongo(self, document):
        field = self._document_cls._fields['id']

        if isinstance(document, Document):
            doc_id = document.id

            if doc_id is None:
                raise ValidationError('You can only reference documents once they have been saved to the database')
        else:
            doc_id = document

        return field.to_mongo(doc_id)

    def validate(self, value):
        if isinstance(value, Document):
            assert isinstance(value, self.document_cls)

    def add_to_document(self, cls):
        name = self.name

        def proxy(self):
            value = self._data.get(name)

            if isinstance(value, Document):
                value = value.id

            return value

        setattr(cls, name + '_id', property(proxy))

    def lookup_member(self, name):
        return self.document_cls._fields.get(name)

