import time
from .base import BaseField, ObjectIdField
from .operations import String, Number, Common, List, Reference
from .exceptions import ValidationError
from .documents import Document
import re
import datetime
import dateutil.parser
import copy
import functools

__all__ = ['ObjectIdField', 'GenericField', 'StringField', 'EmailField', 'IntegerField', 'FloatField', 'BooleanField',
           'DateTimeField', 'DictField', 'ListField', 'MapField', 'EmbeddedDocumentField', 'ReferenceField']

ObjectIdField = ObjectIdField


class GenericField(BaseField):
    pass


class StringField(String, BaseField):
    def __init__(self, regex=None, min_length=None, max_length=None, escape=False, **kwargs):
        self.regex = re.compile(regex) if regex else None
        self.min_length = min_length
        self.max_length = max_length
        self.escape = escape
        BaseField.__init__(self, **kwargs)

    def to_python(self, value):
        if value is not None:
            return str(value)
        return ''

    def to_json(self, value, external=False):
        if value is not None:
            return self.to_python(value)
        return None

    def validate(self, value):
        assert isinstance(value, str)

        if self.max_length is not None and len(value) > self.max_length:
            raise ValidationError('String field "%s" value is too long (%s max, but %s)' % (self.name, self.max_length, len(value)))

        if self.min_length is not None and len(value) < self.min_length:
            raise ValidationError('String filed "%s" value is too short (%s min, but %s)' % (self.name, self.min_lenght, len(value)))

        if self.regex is not None and self.regex.match(value) is None:
            raise ValidationError('String filed "%s" value did not match validation regex' % self.name)


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
            raise ValidationError('field "%s" value %s could not be converted to int' % (self.name, value))

        if self.min_value is not None and value < self.min_value:
            raise ValidationError('Integer field "%s" value is too small (%s min)' % (self.name, self.min_value))

        if self.max_value is not None and value > self.max_value:
            raise ValidationError('Integer field "%s" value is too large (%s max)' % (self.name, self.max_value))

    @classmethod
    def from_val(cls, v):
        return int(v)

class FloatField(IntegerField):
    def to_python(self, value):
        if value is None:
            return self.get_default()
        return float(value)

    def validate(self, value):
        if value is None:
            return self.get_default()

        if isinstance(value, int):
            value = float(value)

        assert isinstance(value, float)

        if self.min_value is not None and value < self.min_value:
            raise ValidationError('Float field "%s" value is too small (%s min)' % (self.name, self.min_value))

        if self.max_value is not None and value > self.max_value:
            raise ValidationError('Float field "%s" value is too large (%s max)' % (self.name, self.max_value))

    @classmethod
    def from_val(cls, v):
        return float(v)

class BooleanField(BaseField):
    def to_python(self, value):
        if value is None:
            return None
        return bool(value)

    def validate(self, value):
        assert isinstance(value, bool)


class DateTimeField(BaseField):
    def validate(self, value):
        assert isinstance(value, datetime.datetime)

    def to_json(self, value, external=False):
        if isinstance(value, datetime.datetime):
            return int(time.mktime(value.timetuple()))

    def from_json(self, j, cur_val, update=False):
        deltas = {}

        dt = None if j is None else datetime.datetime.fromtimestamp(j)

        dt_compare = int(time.mktime(dt.timetuple())) if dt else None
        cur_val_compare = int(time.mktime(cur_val.timetuple())) if cur_val else None
        if dt_compare != cur_val_compare:
            deltas = {
                'old': cur_val_compare,
                'new': dt_compare
            }

        return dt, deltas

    def deltas(self, cur, base):
        delta = {}
        dt_compare = int(time.mktime(base.timetuple())) if base else None
        cur_val_compare = int(time.mktime(cur.timetuple())) if cur else None
        if dt_compare != cur_val_compare:
            delta = {
                'old': cur_val_compare,
                'new': dt_compare
            }
        return delta

    @classmethod
    def from_val(cls, v):
        if not v:
            return None
        elif v == 'now':
            return datetime.datetime.now()
        elif type(v) is str or type(v) is str:
            try:
                date = dateutil.parser.parse(v)
                return date
            except:
                return v
        elif type(v) is int:
            try:
                date = datetime.datetime.fromtimestamp(v)
                return date
            except:
                return v
        else:
            return v

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

            def to_mongo(self, value):
                return value

            def get_key(self, *args, **kwargs):
                return self.field.get_key(True) + '.' + self.key

        return Proxy(key, self)

    def to_json(self, value, external=False):
        if not value:
            return self.get_default()
        json_dict = {}
        for k,v in value.items():
            if isinstance(v, datetime.datetime):
                json_dict[k] = int(time.mktime(v.timetuple()))
            else:
                json_dict[k] = v
        return json_dict

    def new_instance(self):
        return {}


class ListField(List, BaseField):
    def __init__(self, field, default=None, **kwargs):
        if not isinstance(field, BaseField):
            raise ValidationError('Argument to ListField constructor must be a valid field')

        field.owner = self
        self.field = field
        BaseField.__init__(self, default=default or list, **kwargs)

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

    def to_json(self, value, external=False):
        return [self.field.to_json(item, external=external) for item in value]

    def from_json(self, j, cur_val, update=False):
        deltas = {}

        #first trim cur_val to the length of input
        del cur_val[len(j):]

        #expand cur_val to the length of input
        while len(cur_val) < len(j):
            cur_val.append(None)

        #TODO: make deltas for anything deleted

        for i, val in enumerate(j):
            new_val, delta = self.field.from_json(val, cur_val[i] if i < len(cur_val) else None, update)
            cur_val[i] = new_val
            deltas[i]=delta

        return cur_val, deltas

    def deltas(self, cur, base):
        def _convert_json(_x):
            try:
                return _x.to_json()
            except:
                return _x

        if not cur:
            cur = []
        if not base:
            base = []

        cur_list = [_convert_json(x) for x in cur]
        base_list = [_convert_json(x) for x in base]

        deltas = {
            'added': [_convert_json(x) for x in cur if _convert_json(x) not in base_list],
            'removed': [_convert_json(x) for x in base if _convert_json(x) not in cur_list]
        }

        if not deltas['added'] and not deltas['removed']:
            deltas = {}

        for i in range(max(len(cur),len(base) if base else 0)):
            delta = self.field.deltas(cur[i] if i < len(cur) else None, base[i] if base and i < len(base) else None)
            if delta:
                deltas[str(i)]=delta
        return deltas


    def set_field(self, k, v, cur_val):
        if not cur_val:
            cur_val = self.document()
        k = k.split('.', 1)
        field = k[0]
        if type(getattr(cur_val, field)) is list:
            dot_string = k[1]
            spl = dot_string.split('.', 1)
            index = int(spl[0])
            if len(spl) == 2:
                cur_val._fields[field].set_field(spl[1], v, getattr(cur_val, field)[index])
            else:
                getattr(cur_val, field)[index] = v
                setattr(cur_val, field, getattr(cur_val, field))
        elif len(k) == 2:
            dot_string = k[1]
            if getattr(cur_val, field) is None:
                setattr(cur_val, field, cur_val._fields[field].document())
            cur_val._fields[field].set_field(dot_string, v, getattr(cur_val, k[0]))
        else:
            setattr(cur_val, field, cur_val._fields[field].from_val(v))

    def validate(self, value):
        if not isinstance(value, (list, tuple)):
            raise ValidationError('Only lists and tuples may be used in a list field')

        try:
            [self.field.validate(item) for item in value]
        except Exception as err:
            raise ValidationError('Invalid ListField item (%s)' % str(err))

    def add_to_document(self, cls):
        if not isinstance(self.field, ReferenceField):
            return

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
        return dict((k, self.field.to_python(item)) for k, item in value.items())

    def to_mongo(self, value):
        return dict((k, self.field.to_mongo(item)) for k, item in value.items())

    def to_json(self, value, external=False):
        value = value or {}
        return dict((k, self.field.to_json(item, external=external)) for k, item in value.items())

    def validate(self, value):
        if not isinstance(value, dict):
            raise ValidationError('Only dict may be used in a map field')

        try:
            [self.field.validate(item) for item in value.values()]
        except Exception as err:
            raise ValidationError('Invalid MapField item (%s)' % str(err))

    def __getitem__(self, key):
        if isinstance(self.field, EmbeddedDocumentField):
            class Proxy(Common):
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
                                return left + self.get_key(True) + right

                        e.expressions = dict((wrap(key), item) for key, item in e.expressions.items())

                    new_expression = expressions[0]

                    for expression in expressions[1:]:
                        new_expression &= expression

                    return new_expression

                def to_mongo(self, *args, **kwargs):
                    return self.field.field.to_mongo(*args, **kwargs)

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

    def new_instance(self):
        return self.document()

    def to_mongo(self, value):
        return self.document.to_mongo(value)

    def to_json(self, value, external=False):
        if isinstance(value, self.document):
            return value.__class__.to_json(value, external=external)

    def from_json(self, j, cur_val, update=False):
        deltas = {}

        if not cur_val:
            cur_val = self.document()

        for field_name in list(self.document._fields.keys()):
            field = self.document._fields[field_name]

            if field_name in j:

                new_val, field_deltas = field.from_json(j[field_name], getattr(cur_val, field_name), update)

                if field_name not in cur_val._data or new_val != cur_val._data[field_name]:
                    deltas.update({field_name: field_deltas})
                    cur_val._data[field_name] = new_val
            elif not update:
                if field_name in cur_val._data:
                    del cur_val._data[field_name]
                    deltas[field_name] = 'deleted'

        for field_name in list(j.keys()):
            if field_name not in list(self.document._fields.keys()):
                deltas[field_name] = 'unknown'

        return cur_val, deltas

    def deltas(self, cur, base):
        deltas = {}

        if not cur:
            cur = self.get_default()

        if not cur:
            return deltas

        for field_name in list(self.document._fields.keys()):
            field = self.document._fields[field_name]

            field_deltas = field.deltas(getattr(cur, field_name), getattr(base, field_name) if base else None)

            if field_deltas:
                deltas.update({field_name: field_deltas})

        return deltas

    def set_field(self, k, v, cur_val):
        if not cur_val:
            cur_val = self.document()
        k = k.split('.', 1)
        field = k[0]
        if len(k) == 2:
            dot_string = k[1]
            if getattr(cur_val, field) is None:
                setattr(cur_val, field, cur_val._fields[field].new_instance())
            if type(getattr(cur_val, field)) is dict:
                getattr(cur_val, field)[k[1]] = v
                setattr(cur_val, field, getattr(cur_val, field))
            else:
                cur_val._fields[field].set_field(dot_string, v, getattr(cur_val, k[0]))
        else:
            setattr(cur_val, field, cur_val._fields[field].from_val(v))

    def validate(self, value):
        if not isinstance(value, self.document):
            raise ValidationError('Invalid embedded document instance provided to an EmbeddedDocumentField')

        self.document.validate(value)

    def lookup_member(self, name):
        return self.document._fields.get(name)


class ReferenceField(BaseField, Reference):
    def __init__(self, document_cls, lazyload_only=None, **kwargs):
        if not isinstance(document_cls, str) and \
                not (hasattr(document_cls, '_meta') and not document_cls._meta['embedded']):
            raise ValidationError('Argument to ReferenceField constructor must be a document class')

        self._document_cls = document_cls
        self._lazyload_only = lazyload_only

        BaseField.__init__(self, **kwargs)

    @property
    def document_cls(self):
        document_cls = self._document_cls

        if isinstance(document_cls, str):
            if document_cls == 'self':
                if isinstance(self.owner, ListField):
                    self._document_cls = self.owner.owner
                else:
                    self._document_cls = self.owner
            else:
                _module = document_cls.rpartition('.')
                _temp = __import__(_module[0], globals(), locals(), [_module[2]], -1)

                self._document_cls = _temp.__dict__[_module[2]]

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
        field = self.document_cls._fields['id']

        if isinstance(document, Document):
            doc_id = document.id

            if doc_id is None:
                raise ValidationError('You can only reference documents once they have been saved to the database')
        else:
            doc_id = document

        return field.to_mongo(doc_id)

    def to_json(self, value, external=False):
        if isinstance(value, Document):
            return self.document_cls.to_json(value, external=external)

    def deltas(self, cur, base):
        delta = {
            'old': base.to_json() if base else base,
            'new': cur.to_json() if cur else cur
        }
        if delta['old'] == delta['new']:
            return {}
        return delta

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

    def from_json(self, j, cur_val, update=False):
        new_doc = self.document_cls()

        id_val = j
        if isinstance(j, dict):
            id_val = j['id']

        q = self.document_cls.objects.filter_by(id=id_val).one()

        return q, {}
