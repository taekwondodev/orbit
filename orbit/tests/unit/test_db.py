import unittest

from alembic import autogenerate
from alembic import migration as alembic_migration

from orbit.db import api as db_api
from orbit.db import migration
from orbit import orb as orb_model
from orbit.tests.unit import fakes

Status = orb_model.Status


class TestMigration(unittest.TestCase):

    def test_upgrade_is_repeatable_and_matches_the_code_schema(self):
        engine = fakes.database()

        migration.upgrade(engine)

        with engine.connect() as conn:
            context = alembic_migration.MigrationContext.configure(conn)
            diff = autogenerate.compare_metadata(context, db_api.metadata)
        self.assertEqual([], diff)


class TestOrbRepository(unittest.TestCase):

    def setUp(self):
        self.repo = fakes.repository()

    def test_added_orb_reads_back_unchanged(self):
        orb = fakes.orb()

        self.repo.add(orb)

        self.assertEqual(orb, self.repo.get('project-a', orb.id))

    def test_orb_of_another_project_is_invisible(self):
        orb = fakes.orb()
        self.repo.add(orb)

        self.assertIsNone(self.repo.get('project-b', orb.id))
        self.assertEqual([], self.repo.list('project-b'))

    def test_list_returns_only_the_project_orbs_filtered_by_status(self):
        mine = fakes.orb(id='a')
        active = fakes.orb(id='b', status=Status.ACTIVE)
        other = fakes.orb(id='c', project_id='project-b')
        for orb in (mine, active, other):
            self.repo.add(orb)

        self.assertEqual(['a', 'b'],
                         [o.id for o in self.repo.list('project-a')])
        self.assertEqual(['b'], [o.id for o in self.repo.list(
            'project-a', status=Status.ACTIVE)])

    def test_update_applies_when_status_is_the_expected_one(self):
        orb = fakes.orb()
        self.repo.add(orb)

        updated = self.repo.update(orb.id, Status.RESERVING,
                                   status=Status.BUILDING, stack_id='stack-1')

        self.assertTrue(updated)
        stored = self.repo.get('project-a', orb.id)
        self.assertEqual(Status.BUILDING, stored.status)
        self.assertEqual('stack-1', stored.stack_id)
        self.assertIsNotNone(stored.updated_at)

    def test_update_from_a_superseded_status_changes_nothing(self):
        orb = fakes.orb(status=Status.DELETING)
        self.repo.add(orb)

        updated = self.repo.update(orb.id, Status.RESERVING,
                                   status=Status.BUILDING, stack_id='stack-1')

        self.assertFalse(updated)
        self.assertEqual(orb, self.repo.get('project-a', orb.id))

    def test_stored_host_keys_are_not_replaced(self):
        orb = fakes.orb(status=Status.ACTIVE)
        self.repo.add(orb)
        self.repo.update(orb.id, Status.ACTIVE,
                         ssh_host_keys=(fakes.HOST_KEY_ED25519,))

        updated = self.repo.update(orb.id, Status.ACTIVE,
                                   ssh_host_keys=(fakes.HOST_KEY_ECDSA,))

        self.assertFalse(updated)
        self.assertEqual((fakes.HOST_KEY_ED25519,),
                         self.repo.get('project-a', orb.id).ssh_host_keys)

    def test_reaching_deleted_records_the_deletion_time(self):
        orb = fakes.orb(status=Status.DELETING)
        self.repo.add(orb)

        self.repo.update(orb.id, Status.DELETING, status=Status.DELETED)

        self.assertIsNotNone(self.repo.get('project-a', orb.id).deleted_at)
