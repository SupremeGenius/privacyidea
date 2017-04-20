"""
This test file tests the lib.usercache

The lib.usercache.py only depends on the database model
"""
from contextlib import contextmanager

from mock import patch

from privacyidea.lib.error import UserError
from .base import MyTestCase
from privacyidea.lib.resolver import (save_resolver, delete_resolver)
from privacyidea.lib.realm import (set_realm, delete_realm)
from privacyidea.lib.user import (User, get_username, create_user)
from privacyidea.lib.usercache import (get_cache_time,
                                       cache_username, delete_user_cache,
                                       EXPIRATION_SECONDS, retrieve_latest_entry)
from privacyidea.lib.config import set_privacyidea_config, get_from_config
from datetime import timedelta
from datetime import datetime
from privacyidea.models import UserCache


class UserCacheTestCase(MyTestCase):
    """
    Test the user on the database level
    """
    PWFILE = "tests/testdata/passwd"
    resolvername1 = "resolver1"
    realm1 = "realm1"
    username = "root"
    uid = "0"

    sql_realm = "sqlrealm"
    sql_resolver = "SQL1"
    sql_parameters = {'Driver': 'sqlite',
                  'Server': '/tests/testdata/',
                  'Database': "testuser.sqlite",
                  'Table': 'users',
                  'Encoding': 'utf8',
                  'Map': '{ "username": "username", \
                    "userid" : "id", \
                    "email" : "email", \
                    "surname" : "name", \
                    "givenname" : "givenname", \
                    "password" : "password", \
                    "phone": "phone", \
                    "mobile": "mobile"}',
                  'resolver': sql_resolver,
                  'type': 'sqlresolver',
    }

    def _create_realm(self):

        rid = save_resolver({"resolver": self.resolvername1,
                               "type": "passwdresolver",
                               "fileName": self.PWFILE,
                               "type.fileName": "string",
                               "desc.fileName": "The name of the file"})
        self.assertTrue(rid > 0, rid)
        rid = set_realm(realm=self.realm1, resolvers=[self.resolvername1])
        self.assertTrue(rid > 0, rid)

    def _delete_realm(self):
        delete_realm(self.realm1)
        delete_resolver(self.resolvername1)

    def test_00_set_config(self):
        set_privacyidea_config(EXPIRATION_SECONDS, 600)

        exp_delta = get_cache_time()
        self.assertEqual(exp_delta, timedelta(seconds=600))

    def test_01_get_username_from_cache(self):
        # If a username is already contained in the cache, the function
        # lib.user.get_username will return the cache value
        username = "cached_user"
        resolver = "resolver1"
        uid = "1"

        expiration_delta = get_cache_time()
        r = UserCache(username, resolver, uid, datetime.now()).save()
        u_name = get_username(uid, resolver)
        self.assertEqual(u_name, username)

        # A non-existing user is not in the cache and returns and empty username
        u_name = get_username(uid, "resolver_does_not_exist")
        self.assertEqual(u_name, "")

    def test_02_get_resolvers(self):
        # create realm
        self._create_realm()
        # delete user_cache
        r = delete_user_cache()
        self.assertTrue(r >= 0)

        # The username is not in the cache. It is fetched from the resolver
        # At the same time the cache is filled.
        user = User(self.username, self.realm1)
        self.assertEqual(user.login, self.username)
        # The user ID is fetched from the resolver
        self.assertEqual(user.uid, self.uid)

        # Now, the cache should have exactly one entry
        entry = UserCache.query.one()
        self.assertEqual(entry.user_id, self.uid)
        self.assertEqual(entry.username, self.username)
        self.assertEqual(entry.resolver, self.resolvername1)

        # delete the resolver, which also purges the cache
        self._delete_realm()

        # manually re-add the entry from above
        UserCache(entry.username, entry.resolver, entry.user_id, entry.timestamp).save()

        # the username is fetched from the cache
        u_name = get_username(self.uid, self.resolvername1)
        self.assertEqual(u_name, self.username)

        # delete the cache
        r = delete_user_cache()

        # try to fetch the username. It is not in the cache and the
        # resolver does not exist anymore.
        u_name = get_username(self.uid, self.resolvername1)
        self.assertEqual(u_name, "")

    def test_03_get_identifiers(self):
        # create realm
        self._create_realm()
        # delete user_cache
        r = delete_user_cache()
        self.assertTrue(r >= 0)

        # The username is not in the cache. It is fetched from the resolver
        # At the same time the cache is filled. Implicitly we test the
        # _get_resolvers!
        user = User(self.username, self.realm1, self.resolvername1)
        uids = user.get_user_identifiers()
        self.assertEqual(user.login, self.username)
        self.assertEqual(user.uid, self.uid)

        # Now, the cache should have exactly one entry
        entry = UserCache.query.one()
        self.assertEqual(entry.user_id, self.uid)
        self.assertEqual(entry.username, self.username)
        self.assertEqual(entry.resolver, self.resolvername1)

        # delete the resolver, which also purges the cache
        self._delete_realm()

        # manually re-add the entry from above
        UserCache(entry.username, entry.resolver, entry.user_id, entry.timestamp).save()

        # the username is fetched from the cache
        u_name = get_username(self.uid, self.resolvername1)
        self.assertEqual(u_name, self.username)

        # The `User` class also fetches the UID from the cache
        user2 = User(self.username, self.realm1, self.resolvername1)
        self.assertEqual(user2.uid, self.uid)

        # delete the cache
        r = delete_user_cache()

        # try to fetch the username. It is not in the cache and the
        # resolver does not exist anymore.
        u_name = get_username(self.uid, self.resolvername1)
        self.assertEqual(u_name, "")

        # similar case for the `User` class
        # The `User` class also tries to fetch the UID from the cache
        with self.assertRaises(UserError):
            user3 = User(self.username, self.realm1, self.resolvername1)


    def test_04_delete_cache(self):
        now = datetime.now()
        UserCache("hans1", "resolver1", "uid1", now).save()
        UserCache("hans2", "resolver2", "uid2", now).save()

        r = UserCache.query.filter(UserCache.username == "hans1").first()
        self.assertTrue(r)
        r = UserCache.query.filter(UserCache.username == "hans2").first()
        self.assertTrue(r)

        # delete hans1
        delete_user_cache(username="hans1")
        r = UserCache.query.filter(UserCache.username == "hans1").first()
        self.assertFalse(r)
        r = UserCache.query.filter(UserCache.username == "hans2").first()
        self.assertTrue(r)

        # delete resolver2
        delete_user_cache(resolver="resolver2")
        r = UserCache.query.filter(UserCache.username == "hans1").first()
        self.assertFalse(r)
        r = UserCache.query.filter(UserCache.username == "hans2").first()
        self.assertFalse(r)

    def test_05_multiple_entries(self):
        # two consistent entries
        now = datetime.now()
        UserCache("hans1", "resolver1", "uid1", now - timedelta(seconds=60)).save()
        UserCache("hans1", "resolver1", "uid1", now).save()

        r = UserCache.query.filter(UserCache.username == "hans1", UserCache.resolver == "resolver1")
        self.assertEquals(r.count(), 2)

        u_name = get_username("uid1", "resolver1")
        self.assertEqual(u_name, "hans1")

        r = delete_user_cache()

        # two inconsistent entries: most recent entry (ordered by datetime) wins
        UserCache("hans2", "resolver1", "uid1", now).save()
        UserCache("hans1", "resolver1", "uid1", now - timedelta(seconds=60)).save()

        r = UserCache.query.filter(UserCache.user_id == "uid1", UserCache.resolver == "resolver1")
        self.assertEquals(r.count(), 2)

        u_name = get_username("uid1", "resolver1")
        self.assertEqual(u_name, "hans2")

        # Clean up the cache
        r = delete_user_cache()

    def test_06_implicit_cache_population(self):
        self._create_realm()
        # testing `get_username`
        self.assertEquals(UserCache.query.count(), 0)
        # the cache is empty, so the username is read from the resolver
        u_name = get_username(self.uid, self.resolvername1)
        self.assertEqual(self.username, u_name)
        # it should be part of the cache now
        r = UserCache.query.filter(UserCache.user_id == self.uid, UserCache.resolver == self.resolvername1).one()
        self.assertEqual(self.username, r.username)
        # Apart from that, the cache should be empty.
        self.assertEqual(UserCache.query.count(), 1)
        r = delete_user_cache()

        # testing `User()`, but this time we add an already-expired entry to the cache
        self.assertEquals(UserCache.query.count(), 0)
        UserCache(self.username, self.resolvername1, 'fake_uid', datetime.now() - timedelta(weeks=50)).save()
        # cache contains an expired entry, uid is read from the resolver (we can verify
        # that the cache entry is indeed not queried as it contains 'fake_uid' instead of the correct uid)
        user = User(self.username, self.realm1, self.resolvername1)
        self.assertEqual(user.uid, self.uid)
        # a new entry should have been added to the cache now
        r = retrieve_latest_entry((UserCache.username == self.username) & (UserCache.resolver == self.resolvername1))
        self.assertEqual(self.uid, r.user_id)
        # But the expired entry is also still in the cache
        self.assertEqual(UserCache.query.count(), 2)
        r = delete_user_cache()

        self._delete_realm()

    def _populate_cache(self):
        self.assertEquals(UserCache.query.count(), 0)
        # initially populate the cache with three entries
        timestamp = datetime.now()
        UserCache("hans1", self.resolvername1, "uid1", timestamp).save()
        UserCache("hans2", self.resolvername1, "uid2", timestamp - timedelta(weeks=50)).save()
        UserCache("hans3", "resolver2", "uid2", timestamp).save()
        self.assertEquals(UserCache.query.count(), 3)

    def test_07_invalidate_save_resolver(self):
        self._create_realm()
        self._populate_cache()
        # call save_resolver on resolver1, which should invalidate all entries of "resolver1"
        # (even the expired 'hans2' one)
        save_resolver({"resolver": self.resolvername1,
             "type": "passwdresolver",
             "fileName": self.PWFILE,
             "type.fileName": "string",
             "desc.fileName": "Some change"
        })
        self.assertEquals(UserCache.query.count(), 1)
        # Only hans3 in resolver2 should still be in the cache
        # We can use get_username to ensure it is fetched from the cache
        # because resolver2 does not actually exist
        u_name = get_username("uid2", "resolver2")
        self.assertEquals("hans3", u_name)
        delete_user_cache()
        self._delete_realm()

    def test_08_invalidate_delete_resolver(self):
        self._create_realm()
        self._populate_cache()
        # call delete_resolver on resolver1, which should invalidate all of its entries
        self._delete_realm()
        self.assertEquals(UserCache.query.count(), 1)
        # Only hans3 in resolver2 should still be in the cache
        u_name = get_username("uid2", "resolver2")
        self.assertEquals("hans3", u_name)
        delete_user_cache()

    def _create_sql_realm(self):
        rid = save_resolver(self.sql_parameters)
        self.assertTrue(rid > 0, rid)

        (added, failed) = set_realm(self.sql_realm, [self.sql_resolver])
        self.assertEqual(len(failed), 0)
        self.assertEqual(len(added), 1)

    def _delete_sql_realm(self):
        delete_realm(self.sql_realm)
        delete_resolver(self.sql_resolver)

    def test_09_invalidate_edit_user(self):
        # Validate that editing users actually invalidates the cache. For that, we first need an editable resolver
        self._create_sql_realm()
        # The cache is initially empty
        self.assertEquals(UserCache.query.count(), 0)
        # The following adds an entry to the cache
        user = User(login="wordpressuser", realm=self.sql_realm)
        self.assertEquals(UserCache.query.count(), 1)
        uinfo = user.info
        self.assertEqual(uinfo.get("givenname", ""), "")

        user.update_user_info({"givenname": "wordy"})
        uinfo = user.info
        self.assertEqual(uinfo.get("givenname"), "wordy")
        # This should have removed the entry from the cache
        self.assertEqual(UserCache.query.count(), 0)
        # But now it gets added again
        user2 = User(login="wordpressuser", realm=self.sql_realm)
        self.assertEqual(UserCache.query.count(), 1)
        # Change it back for the other tests
        user.update_user_info({"givenname": ""})
        uinfo = user.info
        self.assertEqual(uinfo.get("givenname", ""), "")
        self.assertEqual(UserCache.query.count(), 0)
        self._delete_sql_realm()

    def test_10_invalidate_delete_user(self):
        # Validate that deleting users actually invalidates the cache. For that, we first need an editable resolver
        self._create_sql_realm()
        # The cache is initially empty
        self.assertEquals(UserCache.query.count(), 0)
        # The following adds an entry to the cache
        user = User(login="wordpressuser", realm=self.sql_realm)
        self.assertEquals(UserCache.query.count(), 1)
        uinfo = user.info
        user.delete()
        # This should have removed the entry from the cache
        self.assertEqual(UserCache.query.count(), 0)
        # We add the user again for the other tests
        create_user(self.sql_resolver, uinfo)
        self.assertEqual(UserCache.query.count(), 0)
        self._delete_sql_realm()

    @contextmanager
    def _patch_datetime_now(self, target, delta=timedelta(days=1)):
        with patch(target) as mock_datetime:
            mock_datetime.now.side_effect = lambda: datetime.now() + delta
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            yield mock_datetime

    def test_11_cache_expiration(self):
        # delete user_cache
        r = delete_user_cache()
        self.assertTrue(r >= 0)
        # populate the cache with artificial data
        now = datetime.now()
        UserCache("hans1", "resolver1", "uid1", now).save()
        UserCache("hans2", "resolver1", "uid2", now).save()
        # check that the cache is indeed queried
        self.assertEqual(get_username("uid1", "resolver1"), "hans1")
        self.assertEqual(User("hans2", "realm1", "resolver1").uid, "uid2")
        # check that the (non-existent) resolver is queried
        # for entries not contained in the cache
        self.assertEqual(get_username("uid3", "resolver1"), "")

        # Now, let one day pass, which makes the entries above expire
        with self._patch_datetime_now('privacyidea.lib.usercache.datetime.datetime') as mock_datetime:
            # check that the cache is not queried anymore
            self.assertEqual(UserCache.query.count(), 2)
            self.assertEqual(get_username("uid1", "resolver1"), "")
            with self.assertRaises(UserError):
                User("hans2", "realm1", "resolver1")
            self.assertEqual(get_username("uid3", "resolver1"), "")
            # if we now extend the expiration delta to two days, it is again queried!
            # we do not use `set_privacyidea_config` for that, as it proved to be very hard
            # to get privacyIDEA to reload the configuration properly while still using
            # the mocked datetime.
            with patch('privacyidea.lib.usercache.get_cache_time') as mock_get_cache_time:
                mock_get_cache_time.return_value = timedelta(days=2)
                self.assertEqual(UserCache.query.count(), 2)
                # the entries are now relevant again
                self.assertEqual(get_username("uid1", "resolver1"), "hans1")
                self.assertEqual(User("hans2", "realm1", "resolver1").uid, "uid2")
                self.assertEqual(get_username("uid3", "resolver1"), "")
            # back to using normal expiration delta of 600 seconds, we add another entry in the future
            UserCache("hans4", "resolver1", "uid4", mock_datetime.now()).save()
            self.assertEqual(UserCache.query.count(), 3)
            # we now remove old entries, only the newest remains
            delete_user_cache(expired=True)
            self.assertEqual(UserCache.query.count(), 1)
            self.assertEqual(UserCache.query.one().user_id, "uid4")