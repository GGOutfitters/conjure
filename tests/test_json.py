import unittest
import conjure
import json
import datetime

class JsonTest(unittest.TestCase):
    def test_json(self):
        class User(conjure.Document):
            name = conjure.StringField()
            age = conjure.IntegerField()

        class Comment(conjure.EmbeddedDocument):
            by = conjure.ReferenceField(User)
            message = conjure.StringField()

        class BlogPost(conjure.Document):
            content = conjure.StringField()
            author = conjure.ReferenceField(User)
            comments =  conjure.ListField( conjure.EmbeddedDocumentField(Comment))
            likes =  conjure.ListField(conjure.ReferenceField(User))

        User.drop_collection()
        BlogPost.drop_collection()

        author1 = User(name='Test User #1')
        author1.id = conjure.ObjectId('4ff8c1d20d196d04cc000028')
        author1.save()

        author2 = User(name='Test User #2')
        author2.id = conjure.ObjectId('4ff8c1d20d196d04cc000029')
        author2.save()

        post1 = BlogPost(content='Test Post #1')
        post1.id = conjure.ObjectId('4ff8c1d20d196d04cc000030')
        post1.author = author1
        post1.comments = [Comment(by=author1), Comment(by=author2)]
        post1.save()

        post2 = BlogPost(content='Test Post #2')
        post2.id = conjure.ObjectId('4ff8c1d20d196d04cc000031')
        post2.author = author2
        post2.comments = [Comment(by=author1), Comment(by=author2)]
        post2.likes = [author1]
        post2.save()

        post3 = BlogPost(content='Test Post #3')
        post3.id = conjure.ObjectId('4ff8c1d20d196d04cc000032')
        post3.author = author1
        post3.likes = [author2]
        post3.save()

        self.assertEqual(json.dumps(post2.to_json()), """{"content": "Test Post #2", "author": {"name": "Test User #2", "id": "4ff8c1d20d196d04cc000029"}, "id": "4ff8c1d20d196d04cc000031", "comments": [{"by": {"name": "Test User #1", "id": "4ff8c1d20d196d04cc000028"}}, {"by": {"name": "Test User #2", "id": "4ff8c1d20d196d04cc000029"}}], "likes": [{"name": "Test User #1", "id": "4ff8c1d20d196d04cc000028"}]}""")

        User.drop_collection()
        BlogPost.drop_collection()

    def test_internal_json(self):
        class UserContacts(conjure.EmbeddedDocument):
            emergency = conjure.StringField(internal=True)
            manager = conjure.StringField()

        class UserPreferences(conjure.EmbeddedDocument):
            email_enabled = conjure.BooleanField()

        class User(conjure.Document):
            name = conjure.StringField()
            age = conjure.IntegerField()
            salary = conjure.FloatField(internal=True)
            prefs = conjure.EmbeddedDocumentField(UserPreferences, internal=True)
            contacts = conjure.EmbeddedDocumentField(UserContacts)
            

        user = User(name='Andrew',
                    age=30,
                    salary=50000.25,
                    prefs = UserPreferences(email_enabled=True),
                    contacts = UserContacts(emergency='e_contact',
                                            manager='mgr_contact')
        )

        user_json_internal = user.to_json()
        user_json_external = user.to_json(external=True)
        
        self.assertEqual(user.name, user_json_internal['name'])
        self.assertEqual(user.name, user_json_external['name'])

        self.assertEqual(user.age, user_json_internal['age'])
        self.assertEqual(user.age, user_json_external['age'])

        self.assertEqual(user.salary, user_json_internal['salary'])
        self.assertFalse('salary' in user_json_external)

        self.assertEqual(user.prefs.email_enabled, user_json_internal['prefs']['email_enabled'])
        self.assertFalse('prefs' in user_json_external)

        self.assertEqual(user.contacts.emergency, user_json_internal['contacts']['emergency'])
        self.assertFalse('emergency' in user_json_external['contacts'])



    def test_unmarshal(self):

        class UserReferenceItem(conjure.Document):
            id = conjure.StringField()
            val = conjure.StringField()

        class UserHistoryItem(conjure.EmbeddedDocument):
            timestamp = conjure.DateTimeField()
            note = conjure.StringField()
            tags = conjure.ListField(conjure.StringField())

        class UserContacts(conjure.EmbeddedDocument):
            emergency = conjure.StringField()
            manager = conjure.StringField()

        class User(conjure.Document):
            name = conjure.StringField()
            age = conjure.IntegerField()
            salary = conjure.FloatField()
            email = conjure.EmailField()
            is_active = conjure.BooleanField()
            create_time = conjure.DateTimeField()
            prefs = conjure.DictField()

            contacts = conjure.EmbeddedDocumentField(UserContacts)

            favorite_foods = conjure.ListField(conjure.StringField())
            favorite_numbers = conjure.ListField(conjure.IntegerField())
            history = conjure.ListField(conjure.EmbeddedDocumentField(UserHistoryItem))

            ref_list1 = conjure.ListField(conjure.ReferenceField(UserReferenceItem), default=[])

            ref1 = conjure.ReferenceField(UserReferenceItem)
            

        user = User(name='Andrew',
                    age=30,
                    salary=50000.25,
                    email='atodd@ggoutfitters.com',
                    is_active=True,
                    create_time=datetime.datetime.now(),
                    prefs = {'key1':'val1', 'key2':'val2'},
                    contacts = UserContacts(emergency='e_contact',
                                            manager='mgr_contact'),
                    favorite_foods = ['chicken','veal','lamb'],
                    favorite_numbers = [1,1,2,3,5,8,13,21],
                    history = [UserHistoryItem(timestamp=datetime.datetime.now(),
                                               note='some note',
                                               tags=['a','b','c']
                                           )]
                    
        )

        ref = UserReferenceItem(id='1',val='asdf')
        ref.save()
        user.ref_list1.append(ref)
        ref = UserReferenceItem(id='2',val='ghjkl;')
        ref.save()
        user.ref_list1.append(ref)

        user.ref1 = ref

        #check that marshal/unmarshal returns the same json
        self.maxDiff = None
        old_json = user.to_json()
        user.from_json(user.to_json())

        new_json = user.to_json()
        self.assertEqual(old_json, new_json)


        #check that removing keys from json removes them
        #from the generated object
        mod_json = user.to_json()
        del mod_json['favorite_foods'][0]
        del mod_json['favorite_numbers'][2]
        del mod_json['contacts']['emergency']
        del mod_json['prefs']['key1']

        delta = user.from_json(mod_json)

        self.assertTrue('chicken' not in user.favorite_foods)
        self.assertTrue(2 not in user.favorite_numbers)
        self.assertTrue(user.contacts.emergency is None)
        self.assertTrue('key1' not in user.prefs)


        #test adding new fields
        mod_json['history'].append(mod_json['history'][0])
        mod_json['history'][1]['note']='new note'
        mod_json['favorite_foods'].append('tacos')
        mod_json['favorite_numbers'].append(42)
        
        delta = user.from_json(mod_json)

        self.assertTrue(user.history[1].note == 'new note')
        self.assertTrue(user.favorite_foods[-1] == 'tacos')
        self.assertTrue(user.favorite_numbers[-1] == 42)
