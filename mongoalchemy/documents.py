from mongoalchemy import expressions, spec, fields
import copy

_cls_index = {}

class DocumentMetaclass(type):
    def __new__(cls, name, bases, attrs):
        metaclass = attrs.get('__metaclass__')
        super_new = super(DocumentMetaclass, cls).__new__
        
        if metaclass and issubclass(metaclass, DocumentMetaclass):
            return super_new(cls, name, bases, attrs)

        _fields = {}

        Meta = attrs.pop('Meta', None)

        if Meta and getattr(Meta, 'embedded', True):
            _meta = {
                'embedded': True
            }
        else:
            _meta = {
                'db': 'mongodb://localhost:27017/main',
                'collection': name.lower() + 's',
                'sorting': [],
                'get_latest_by': [],
                'indexes': [],
                'embedded': False
            }

        _meta.update({
            'verbose_name': name.lower(),
            'verbose_name_plural': name.lower() + 's',
         })

        for base in bases:
            if hasattr(base, '_fields'):
                _fields.update(copy.deepcopy(base._fields))
                
            if hasattr(base, '_meta'):
                _meta.update(copy.deepcopy(base._meta))

        Meta = attrs.pop('Meta', None)

        if Meta:
            for k in _meta:
                if hasattr(Meta, k):
                    _meta[k] = getattr(Meta, k)

        attrs['_meta'] = _meta

        for attr_name, attr_value in attrs.items():
            if hasattr(attr_value, '__class__') and issubclass(attr_value.__class__, fields.Field):
                attr_value.name = attr_name
                _fields[attr_name] = attr_value

        attrs['_fields'] = _fields

        new_cls = super_new(cls, name, bases, attrs)

        for field in new_cls._fields.values():
            field.parent = new_cls

        if not _meta['embedded']:
            new_cls.objects = spec.Manager()
            _meta['cls_key'] = '%s/%s:%s' % (_meta['db'], _meta['collection'], name)

            global _cls_index
            _cls_index[_meta['cls_key']] = new_cls

        return new_cls

class BaseDocument(object):
    def __init__(self, **data):
        self._data = {}

        for attr_name, attr_value in self._fields.iteritems():
            if attr_name in data:
                setattr(self, attr_name, data.pop(attr_name))
            else:
                value = getattr(self, attr_name, None)
                setattr(self, attr_name, value)

    def __iter__(self):
        return iter(self._fields)

    def __getitem__(self, name):
        try:
            if name in self._fields:
                return getattr(self, name)
        except AttributeError:
            pass

        raise KeyError(name)

    def __setitem__(self, name, value):
        if name not in self._fields:
            raise KeyError(name)
        
        return setattr(self, name, value)

    def __contains__(self, name):
        try:
            value = getattr(self, name)
            return value is not None
        except AttributeError:
            return False

    def __len__(self):
        return len(self._data)

    def __repr__(self):
        return u'<%s: %s>' % (self.__class__.__name__, unicode(self))

    def __str__(self):
        try:
            return unicode(self).encode('utf-8')
        except:
            _id = getattr(self, '_id', None)

            if _id:
                return unicode(_id)

            return '%s object' % self.__class__.__name__

    def to_mongo(self):
        pass

    @classmethod
    def from_mongo(cls, son):
        pass

    def __eq__(self, other):
        pass

class Document(BaseDocument):
    __metaclass__ = DocumentMetaclass

    def save(self, safe=True, force_insert=False):
        pass

    def delete(self, safe=False):
        pass

    def reload(self):
        pass