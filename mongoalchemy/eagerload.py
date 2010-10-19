class Eagerload(object):
    def __init__(self, field, fields=None):
        self.fields = fields

        from mongoalchemy.fields import ListField
        if isinstance(field, ListField):
            self.field = field.field
            self.name = field.name + '_'
            self.multi = True
        else:
            self.field = field
            self.name = field.name + '_id'
            self.multi = False

        self.documents = []

    def add_documents(self, documents):
        if isinstance(documents, list):
            self.documents.extend(documents)
        else:
            self.documents.append(documents)

    def flush(self):
        if len(self.documents) == 0:
            return

        ids = set()
        
        for document in self.documents:
            _id = getattr(document, self.name)

            if _id:
                if isinstance(_id, list):
                    ids |= set(_id)
                else:
                    ids.add(_id)

        if ids:
            cls = self.field.document_cls

            if len(ids) == 1:
                values = cls.objects.filter(cls._id == ids.pop())
            else:
                values = cls.objects.filter(cls._id.in_(list(ids)))

            if self.fields is not None:
                values = values.only(*self.fields)

            for value in values:
                for document in self.documents:
                    if self.multi:
                        try:
                            data = document._data[self.field.name]

                            while True:
                                data[data.index(value._id)] = value
                        except ValueError:
                            pass
                        except IndexError:
                            pass
                        except KeyError:
                            pass
                    else:
                        document._data[self.field.name] = value