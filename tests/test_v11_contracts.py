import unittest
from uuid import uuid4
from app.v11_governance import action_key, decide_once

class FakeConn:
    def __init__(self, can_update=True): self.sql=[]; self.can_update=can_update
    def execute(self, sql, params):
        self.sql.append((sql,params))
        return self
    def fetchone(self): return ('APPROVED',) if self.can_update else None

class Contracts(unittest.TestCase):
    def setUp(self): self.run=str(uuid4())
    def test_key_stable(self):
        self.assertEqual(action_key(self.run,'servicenow.incident.create'),action_key(self.run,'servicenow.incident.create'))
    def test_tool_denied(self):
        with self.assertRaises(ValueError): action_key(self.run,'salesforce.account.delete')
    def test_approval_enqueues(self):
        c=FakeConn(); self.assertEqual(decide_once(c,'tenant-a',self.run,'approver',True,'servicenow.incident.create',{'account_id':'ACME'}),'APPROVED')
        self.assertEqual(len(c.sql),3)
        self.assertIn('INSERT INTO v11_outbox',c.sql[-1][0])
    def test_rejection_no_outbox(self):
        c=FakeConn(); self.assertEqual(decide_once(c,'tenant-a',self.run,'approver',False,'servicenow.incident.create',{}),'DENIED')
        self.assertEqual(len(c.sql),2)
    def test_replay_rejected(self):
        with self.assertRaisesRegex(ValueError,'already consumed'):
            decide_once(FakeConn(False),'tenant-a',self.run,'approver',True,'servicenow.incident.create',{})
if __name__=='__main__': unittest.main()
