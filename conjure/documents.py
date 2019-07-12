from .base import BaseDocument, DocumentMeta, ObjectIdField
from .exceptions import OperationError
from .query import Query
import pymongo.errors
import copy

__all__ = ['Document', 'EmbeddedDocument']


class Document(BaseDocument, metaclass=DocumentMeta):
    id = ObjectIdField(db_field='_id')
    objects = Query(None, None)

    _base = {}

    def __init__(self, **data):
        super(Document, self).__init__(**data)
        if self._meta['track_changes']:
            self._base = copy.deepcopy(self)
            

    def save(self, insert=False):
        self.validate()

        doc = self.to_mongo()

        try:
            collection = self.__class__.objects._collection

            if insert:
                object_id = collection.insert(doc)
            else:
                object_id = collection.save(doc)
        except pymongo.errors.OperationFailure as err:
            raise OperationError(str(err))

        self['id'] = object_id

    def delete(self):
        #noinspection PyUnresolvedReferences
        object_id = self._fields['id'].to_mongo(self.id)

        try:
            self.__class__.objects.filter_by(id=object_id).delete()
        except pymongo.errors.OperationFailure as err:
            raise OperationError(str(err))

    def reload(self):
        data = self.__class__.objects.filter_by(id=self.id)._one()

        #noinspection PyUnresolvedReferences
        for field in list(self.__class__._fields.values()):
            if field.db_field in data:
                self._data[field.name] = field.to_python(data[field.db_field])

    @classmethod
    def drop_collection(cls):
        cls.objects._collection.drop()


class EmbeddedDocument(BaseDocument, metaclass=DocumentMeta):
    _meta = {'embedded': True}
